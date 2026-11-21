package com.projectseele.client.render;

import java.io.Reader;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;

import com.google.gson.Gson;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.EvaScale;
import com.projectseele.entity.EvaUnit01Entity;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.packs.resources.ResourceManager;
import net.minecraft.util.Mth;
import net.minecraft.world.level.ClipContext;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraft.world.phys.HitResult;
import net.minecraft.world.phys.Vec3;
import org.joml.Quaternionf;
import org.joml.Vector3f;
import software.bernie.geckolib.cache.object.BakedGeoModel;
import software.bernie.geckolib.cache.object.GeoBone;

/**
 * Render-rate EVA pose synthesis independent from the 20 Hz entity clock.
 *
 * <p>The simulation still owns collision, damage and network authority. This
 * engine owns only the visual skeleton: it samples licensed motion capture,
 * synchronizes gait by travelled distance, blends adjacent gaits in quaternion
 * space and inertializes pose changes every rendered frame. During the first
 * rollout it is deliberately enabled only on entities tagged by the isolated
 * motion lab; the authority save cannot receive an unreviewed retarget.</p>
 */
public final class EvaMotionEngineV2
{
    private static final ResourceLocation DATABASE = new ResourceLocation(
            ProjectSeele.MODID, "motion/eva_humanoid_v2.json");
    private static final ResourceLocation PHYSICS_DATABASE = new ResourceLocation(
            ProjectSeele.MODID, "motion/eva_physics_preview_v1.json");
    private static final ResourceLocation GROUNDED_DATABASE = new ResourceLocation(
            ProjectSeele.MODID, "motion/eva_grounded_preview_v1.json");
    private static final ResourceLocation ORDINARY_ATTACK_REVIEW_DATABASE =
            new ResourceLocation(ProjectSeele.MODID,
                    "motion/eva_ordinary_attack_review_v1.json");
    private static final double WALK_STRIDE_BLOCKS = 25.8334D;
    private static final double RUN_STRIDE_BLOCKS = 31.3944D;
    private static final double CROUCH_STRIDE_BLOCKS = 9.2990D;
    private static final float MODEL_UNITS_PER_SOURCE_METRE = 112.0F;
    // The first live pass proved that Gecko's reflected render matrix cannot
    // share the same world conversion as the offline Bedrock skeleton. Keep
    // the bad layer fail-closed until it is rebuilt from tracked model-space
    // matrices; the reviewed offline limb retarget remains active.
    private static final boolean MODEL_SPACE_FOOT_LOCK_READY = false;
    private static final Set<String> LOWER_BODY = Set.of(
            "torso_lower", "leg_l", "shin_l", "foot_l",
            "leg_r", "shin_r", "foot_r");
    private static final Map<Integer, RuntimeState> STATES = new HashMap<>();
    private static volatile MotionDatabase database = MotionDatabase.empty();
    private static volatile MotionDatabase physicsDatabase =
            MotionDatabase.empty();
    private static volatile MotionDatabase groundedDatabase =
            MotionDatabase.empty();
    private static volatile MotionDatabase ordinaryAttackReviewDatabase =
            MotionDatabase.empty();

    private EvaMotionEngineV2() {}

    public static void reload(ResourceManager resourceManager)
    {
        STATES.clear();
        database = load(resourceManager, DATABASE, "EVA Motion Engine V2");
        physicsDatabase = load(resourceManager, PHYSICS_DATABASE,
                "EVA physics preview");
        groundedDatabase = load(resourceManager, GROUNDED_DATABASE,
                "EVA grounded mocap preview");
        ordinaryAttackReviewDatabase = load(resourceManager,
                ORDINARY_ATTACK_REVIEW_DATABASE,
                "EVA ordinary attack review");
    }

    private static MotionDatabase load(ResourceManager resourceManager,
                                       ResourceLocation location,
                                       String label)
    {
        try (Reader reader = resourceManager.getResource(location)
                .orElseThrow(() -> new IllegalStateException(
                        "missing EVA motion database " + location))
                .openAsReader())
        {
            MotionDatabase loaded = MotionDatabase.parse(new Gson().fromJson(
                    reader, JsonObject.class));
            ProjectSeele.LOGGER.info(
                    "{} loaded: clips={} bones={} frames={}", label,
                    loaded.clips.size(), loaded.bones.length,
                    loaded.totalFrames);
            return loaded;
        }
        catch (Exception exception)
        {
            ProjectSeele.LOGGER.error(
                    label + " database rejected", exception);
            return MotionDatabase.empty();
        }
    }

    /** Returns true when V2 replaced the authored base skeleton this frame. */
    public static boolean apply(EvaUnit01Entity entity, BakedGeoModel model,
                                float partialTick)
    {
        int previewMode = entity.getMotionLabPhysicsPreview();
        if (previewMode == 3)
        {
            return applyLivePhysics(model);
        }
        boolean replayPreview = previewMode == 1 || previewMode == 2;
        boolean groundedPreview = previewMode == 4 || previewMode == 5;
        boolean ordinaryAttackReview = previewMode >= 6 && previewMode <= 9;
        boolean labPreview = replayPreview || groundedPreview
                || ordinaryAttackReview;
        MotionDatabase db = ordinaryAttackReview
                ? ordinaryAttackReviewDatabase
                : groundedPreview ? groundedDatabase
                : replayPreview ? physicsDatabase : database;
        if (!labPreview || db.bones.length == 0
                || entity.isNervLogisticsLocked() || entity.isCrucified()
                || (!labPreview && !entity.isPoweredOn())
                || entity.isPilotProne()
                || entity.isPilotCrouching()
                || entity.getVisualPose() == EvaUnit01Entity.VISUAL_CROUCH
                || entity.getVisualPose() == EvaUnit01Entity.VISUAL_CROUCH_WALK
                || entity.getVisualPose() == EvaUnit01Entity.VISUAL_CRAWL)
        {
            STATES.remove(entity.getId());
            return false;
        }
        if (STATES.size() > 48)
        {
            STATES.clear();
        }

        RuntimeState runtime = STATES.get(entity.getId());
        if (runtime == null || runtime.rotations.length != db.bones.length)
        {
            runtime = new RuntimeState(db.bones.length);
            STATES.put(entity.getId(), runtime);
        }
        if (runtime.previewMode != previewMode)
        {
            runtime.previewMode = previewMode;
            runtime.comboTime = 0.0D;
            runtime.actionTime = 0.0D;
            runtime.selectionKey = "";
        }
        long now = System.nanoTime();
        double dt;
        if (runtime.lastNanos == 0L)
        {
            dt = 1.0D / 60.0D;
        }
        else
        {
            dt = Mth.clamp((now - runtime.lastNanos) / 1_000_000_000.0D,
                    1.0D / 360.0D, 0.05D);
        }
        runtime.lastNanos = now;

        boolean airborneNow = entity.isVisuallyAirborneForRender()
                || entity.getVisualPose() == EvaUnit01Entity.VISUAL_JUMP
                || entity.getVisualPose() == EvaUnit01Entity.VISUAL_FALL
                || entity.getVisualPose() == EvaUnit01Entity.VISUAL_LIVE_JUMP;
        if (!runtime.airStateInitialized)
        {
            runtime.airStateInitialized = true;
            runtime.wasAirborne = airborneNow;
            if (airborneNow)
            {
                runtime.airborneAge = 0.0D;
                runtime.fallAge = 0.0D;
                runtime.apexReached = false;
            }
        }
        else
        {
            if (!runtime.wasAirborne && airborneNow)
            {
                runtime.airborneAge = 0.0D;
                runtime.fallAge = 0.0D;
                runtime.apexReached = false;
                runtime.landingActive = false;
                runtime.selectionKey = "";
            }
            if (runtime.wasAirborne && !airborneNow)
            {
                runtime.landingActive = true;
                runtime.selectionKey = "";
                runtime.actionTime = 0.0D;
            }
            runtime.wasAirborne = airborneNow;
        }
        if (airborneNow)
        {
            runtime.airborneAge += dt;
            if (entity.visualVerticalSpeedForRender() <= 0.0D)
            {
                runtime.apexReached = true;
            }
            if (runtime.apexReached)
            {
                runtime.fallAge += dt;
            }
        }

        MotionClip takeoffClip = labPreview
                ? null : db.clip("jump_takeoff_v2");
        Selection selection;
        if (ordinaryAttackReview)
        {
            String clipName;
            if (previewMode == 9)
            {
                MotionClip jab = db.clip("ordinary_attack_jab_left");
                MotionClip cross = db.clip("ordinary_attack_cross_right");
                MotionClip hook = db.clip("ordinary_attack_hook_right");
                double total = jab.durationSeconds + cross.durationSeconds
                        + hook.durationSeconds;
                runtime.comboTime = total <= 0.0D
                        ? 0.0D : (runtime.comboTime + dt) % total;
                clipName = runtime.comboTime < jab.durationSeconds
                        ? "ordinary_attack_jab_left"
                        : runtime.comboTime < jab.durationSeconds
                                + cross.durationSeconds
                        ? "ordinary_attack_cross_right"
                        : "ordinary_attack_hook_right";
            }
            else
            {
                runtime.comboTime = 0.0D;
                clipName = previewMode == 7
                        ? "ordinary_attack_jab_left"
                        : previewMode == 8
                                ? "ordinary_attack_hook_right"
                                : "ordinary_attack_cross_right";
            }
            selection = Selection.single(db.clip(clipName), clipName);
            runtime.landingActive = false;
        }
        else if (groundedPreview)
        {
            String clipName = previewMode == 5
                    ? "grounded_run" : "grounded_walk";
            MotionClip clip = db.clip(clipName);
            double speed = Math.max(0.01D,
                    entity.visualHorizontalSpeedForRender());
            selection = Selection.locomotion(clip, null, 0.0F, speed,
                    clip.strideBlocks(1.0D), clipName);
            runtime.landingActive = false;
        }
        else if (replayPreview)
        {
            String clip = previewMode == 2
                    ? "physics_recovery" : "physics_walk";
            selection = Selection.single(db.clip(clip), clip);
            runtime.landingActive = false;
        }
        else if (runtime.landingActive)
        {
            selection = Selection.single(db.clip("jump_landing_v2"),
                    "landing_v2");
        }
        else if (airborneNow)
        {
            selection = runtime.airborneAge < takeoffClip.durationSeconds
                    ? Selection.single(takeoffClip, "takeoff_v2")
                    : Selection.single(db.clip("jump_airborne_v2"),
                            "airborne_v2");
        }
        else
        {
            selection = select(entity, db);
        }
        if (!selection.key().equals(runtime.selectionKey))
        {
            boolean enteringLocomotion = selection.locomotion()
                    && !runtime.lastLocomotion;
            runtime.selectionKey = selection.key();
            runtime.actionTime = 0.0D;
            if (enteringLocomotion || !selection.locomotion())
            {
                runtime.phase = 0.0D;
            }
            runtime.distanceInitialized = false;
        }
        runtime.lastLocomotion = selection.locomotion();

        if (replayPreview || ordinaryAttackReview)
        {
            runtime.actionTime += dt;
            runtime.phase = wrap01(runtime.actionTime
                    / selection.primary().durationSeconds);
        }
        else if (groundedPreview)
        {
            double renderX = Mth.lerp((double)partialTick,
                    entity.xOld, entity.getX());
            double renderZ = Mth.lerp((double)partialTick,
                    entity.zOld, entity.getZ());
            if (runtime.distanceInitialized)
            {
                double step = Math.hypot(renderX - runtime.lastRenderX,
                        renderZ - runtime.lastRenderZ);
                if (Double.isFinite(step) && step < 12.0D)
                {
                    runtime.phase = wrap01(runtime.phase + step
                            / Math.max(1.0D, selection.strideBlocks()));
                }
            }
            runtime.lastRenderX = renderX;
            runtime.lastRenderZ = renderZ;
            runtime.distanceInitialized = true;
        }
        else if ("airborne_v2".equals(selection.key()))
        {
            if (runtime.apexReached)
            {
                runtime.phase = 0.5D + 0.5D * Mth.clamp(
                        runtime.fallAge / 0.30D, 0.0D, 1.0D);
            }
            else
            {
                runtime.phase = 0.5D * Mth.clamp(
                        (runtime.airborneAge - takeoffClip.durationSeconds)
                                / 0.30D, 0.0D, 1.0D);
            }
        }
        else if (selection.locomotion())
        {
            double cyclesPerSecond = selection.speedBlocksPerSecond()
                    / Math.max(1.0D, selection.strideBlocks());
            runtime.phase = wrap01(runtime.phase + cyclesPerSecond * dt);
        }
        else if (selection.primary().loop)
        {
            runtime.phase = wrap01(runtime.phase
                    + dt / selection.primary().durationSeconds);
        }
        else
        {
            runtime.actionTime = Math.min(selection.primary().durationSeconds,
                    runtime.actionTime + dt);
            runtime.phase = Mth.clamp(runtime.actionTime
                    / selection.primary().durationSeconds, 0.0D, 1.0D);
        }
        if (runtime.landingActive
                && runtime.actionTime >= selection.primary().durationSeconds)
        {
            runtime.landingActive = false;
        }

        selection.primary().sample(runtime.phase, runtime.poseA);
        runtime.target.copyFrom(runtime.poseA);
        if (selection.secondary() != null && selection.blend() > 0.0001F)
        {
            selection.secondary().sample(runtime.phase, runtime.poseB);
            PoseBuffer.blend(runtime.poseA, runtime.poseB,
                    selection.blend(), runtime.target);
        }
        PoseBuffer target = runtime.target;

        if (selection.locomotion())
        {
            applyDirectionalWarp(entity, target, db);
        }

        if (MODEL_SPACE_FOOT_LOCK_READY
                && !selection.key().startsWith("jump")
                && !selection.key().startsWith("takeoff")
                && !selection.key().startsWith("airborne")
                && !selection.key().startsWith("landing"))
        {
            applyFootLocks(entity, model, partialTick, runtime, target, db);
        }
        else
        {
            runtime.leftFoot.release();
            runtime.rightFoot.release();
        }

        Vector3f rootOffset = new Vector3f(target.rootMeters)
                .mul(MODEL_UNITS_PER_SOURCE_METRE);
        model.getBone("root").ifPresent(root ->
        {
            if (groundedPreview || ordinaryAttackReview)
            {
                root.setPosX(root.getInitialSnapshot().getOffsetX()
                        - rootOffset.x);
                root.setPosZ(root.getInitialSnapshot().getOffsetZ()
                        + rootOffset.z);
            }
            root.setPosY(root.getInitialSnapshot().getOffsetY()
                    + rootOffset.y);
        });

        boolean meleeActive = entity.getCockpitAttackAnim(partialTick) > 0.0F
                || entity.getCockpitSmashAnim(partialTick) > 0.0F;
        boolean fullBody = entity.getWeapon() == EvaUnit01Entity.WEAPON_FISTS
                && !meleeActive;
        float inertialAlpha;
        if (replayPreview || ordinaryAttackReview)
        {
            inertialAlpha = 1.0F;
        }
        else
        {
            double halfLife = groundedPreview ? 0.035D
                    : selection.locomotion() ? 0.050D : 0.075D;
            inertialAlpha = (float)(1.0D - Math.exp(
                    -Math.log(2.0D) * dt / halfLife));
        }

        for (int index = 0; index < db.bones.length; index++)
        {
            String name = db.bones[index];
            // Normal gameplay keeps Gecko's weapon-specific finger layer.
            // The isolated ordinary-attack review owns its audited static
            // fist explicitly so the body clip cannot silently show an open
            // hand. The long digits use mirrored axis adapters; the retained
            // native thumb is already given its per-side hinge in the review
            // database.
            if (name.startsWith("finger_") && !ordinaryAttackReview)
            {
                continue;
            }
            if (!fullBody && !LOWER_BODY.contains(name))
            {
                continue;
            }
            Quaternionf wanted = target.rotations[index];
            Quaternionf current = runtime.rotations[index];
            if (!runtime.initialized[index])
            {
                current.set(wanted);
                runtime.initialized[index] = true;
            }
            else
            {
                current.slerp(wanted, inertialAlpha).normalize();
            }
            model.getBone(name).ifPresent(bone ->
            {
                Vector3f euler = current.getEulerAnglesXYZ(new Vector3f());
                // Gecko's Builtin BakedModelFactory converts authored
                // Bedrock rotations as (-X, -Y, +Z). This runtime path must
                // perform the same basis change or an offline-correct pose is
                // mirrored into a folded limb configuration in game.
                bone.setRotX(-euler.x);
                bone.setRotY(-euler.y);
                bone.setRotZ(euler.z);
            });
        }
        return true;
    }

    private static boolean applyLivePhysics(BakedGeoModel model)
    {
        EvaLivePhysicsBridge.Snapshot snapshot =
                EvaLivePhysicsBridge.sample();
        if (snapshot == null)
        {
            return false;
        }
        Vector3f rootMeters = snapshot.rootMeters();
        model.getBone("root").ifPresent(root ->
        {
            root.setPosX(root.getInitialSnapshot().getOffsetX()
                    + rootMeters.x * MODEL_UNITS_PER_SOURCE_METRE);
            root.setPosY(root.getInitialSnapshot().getOffsetY()
                    + rootMeters.y * MODEL_UNITS_PER_SOURCE_METRE);
            root.setPosZ(root.getInitialSnapshot().getOffsetZ()
                    + rootMeters.z * MODEL_UNITS_PER_SOURCE_METRE);
        });
        Quaternionf[] rotations = snapshot.rotations();
        for (int index = 0; index < EvaLivePhysicsBridge.BONES.length;
                index++)
        {
            String name = EvaLivePhysicsBridge.BONES[index];
            Quaternionf rotation = rotations[index];
            model.getBone(name).ifPresent(bone ->
            {
                Vector3f euler = rotation.getEulerAnglesXYZ(new Vector3f());
                bone.setRotX(-euler.x);
                bone.setRotY(-euler.y);
                bone.setRotZ(euler.z);
            });
        }
        return true;
    }

    private static Selection select(EvaUnit01Entity entity,
                                    MotionDatabase db)
    {
        int visual = entity.getVisualPose();
        double speed = Math.max(0.0D,
                entity.visualHorizontalSpeedForRender());
        if (visual == EvaUnit01Entity.VISUAL_IDLE)
        {
            return Selection.single(db.clip("idle"), "idle");
        }
        if (visual == EvaUnit01Entity.VISUAL_JUMP
                || visual == EvaUnit01Entity.VISUAL_LIVE_JUMP)
        {
            return Selection.single(db.clip("jump_start"), "jump_start");
        }
        if (visual == EvaUnit01Entity.VISUAL_FALL)
        {
            return Selection.single(db.clip("jump_loop"), "jump_loop");
        }
        if (visual == EvaUnit01Entity.VISUAL_CROUCH)
        {
            return Selection.single(db.clip("crouch_idle"), "crouch_idle");
        }
        if (visual == EvaUnit01Entity.VISUAL_CROUCH_WALK
                || entity.isPilotCrouching())
        {
            if (speed < 0.28D)
            {
                return Selection.single(db.clip("crouch_idle"),
                        "crouch_idle");
            }
            return Selection.locomotion(db.clip("crouch_walk"), null,
                    0.0F, speed, CROUCH_STRIDE_BLOCKS, "crouch_walk");
        }
        if (visual == EvaUnit01Entity.VISUAL_RUN_CONTACT
                || entity.isPilotSprinting())
        {
            float blend = (float)Mth.clamp((speed - 8.0D) / 8.0D,
                    0.0D, 1.0D);
            MotionClip jog = db.clip("jog");
            MotionClip sprint = db.clip("sprint");
            double stride = Mth.lerp(blend,
                    jog.strideBlocks(RUN_STRIDE_BLOCKS),
                    sprint.strideBlocks(RUN_STRIDE_BLOCKS));
            return Selection.locomotion(jog, sprint,
                    blend, speed, stride, "run");
        }
        if (visual == EvaUnit01Entity.VISUAL_WALK_CONTACT
                || visual == EvaUnit01Entity.VISUAL_RIFLE_WALK_CONTACT
                || entity.isVisuallyMovingForRender())
        {
            float blend = (float)Mth.clamp((speed - 6.0D) / 5.0D,
                    0.0D, 1.0D);
            MotionClip walk = db.clip("walk");
            MotionClip jog = db.clip("jog");
            double stride = Mth.lerp(blend,
                    walk.strideBlocks(WALK_STRIDE_BLOCKS),
                    jog.strideBlocks(RUN_STRIDE_BLOCKS));
            return Selection.locomotion(walk, jog,
                    blend, speed, stride, "walk");
        }
        if (entity.isVisuallyAirborneForRender())
        {
            return Selection.single(db.clip(
                    entity.visualVerticalSpeedForRender() > 0.15D
                            ? "jump_start" : "jump_loop"), "airborne");
        }
        return Selection.single(db.clip("idle"), "idle");
    }

    private static double wrap01(double value)
    {
        value %= 1.0D;
        return value < 0.0D ? value + 1.0D : value;
    }

    private static void applyDirectionalWarp(EvaUnit01Entity entity,
                                             PoseBuffer pose,
                                             MotionDatabase db)
    {
        Vec3 velocity = entity.getDeltaMovement()
                .multiply(1.0D, 0.0D, 1.0D);
        if (velocity.lengthSqr() < 1.0E-5D)
        {
            return;
        }
        double yaw = Math.toRadians(entity.getYRot());
        Vec3 forward = new Vec3(-Math.sin(yaw), 0.0D, Math.cos(yaw));
        Vec3 right = new Vec3(Math.cos(yaw), 0.0D, Math.sin(yaw));
        double relative = Math.atan2(velocity.dot(right),
                velocity.dot(forward));
        float lowerYaw = (float)Mth.clamp(relative,
                -Math.toRadians(72.0D), Math.toRadians(72.0D));
        int lower = db.index("torso_lower");
        int upper = db.index("torso_upper");
        int head = db.index("head");
        if (lower >= 0)
        {
            pose.rotations[lower] = new Quaternionf().rotationY(lowerYaw)
                    .mul(pose.rotations[lower]).normalize();
        }
        if (upper >= 0)
        {
            pose.rotations[upper] = new Quaternionf()
                    .rotationY(-lowerYaw * 0.88F)
                    .mul(pose.rotations[upper]).normalize();
        }
        if (head >= 0)
        {
            pose.rotations[head] = new Quaternionf()
                    .rotationY(-lowerYaw * 0.12F)
                    .mul(pose.rotations[head]).normalize();
        }
    }

    private static void applyFootLocks(EvaUnit01Entity entity,
                                       BakedGeoModel model,
                                       float partialTick,
                                       RuntimeState runtime,
                                       PoseBuffer target,
                                       MotionDatabase db)
    {
        Vec3 entityPosition = new Vec3(
                Mth.lerp((double)partialTick, entity.xOld, entity.getX()),
                Mth.lerp((double)partialTick, entity.yOld, entity.getY()),
                Mth.lerp((double)partialTick, entity.zOld, entity.getZ()));
        float yaw = Mth.rotLerp(partialTick, entity.yRotO, entity.getYRot());
        Vector3f rootModelOffset = new Vector3f(0.0F,
                target.rootMeters.y * MODEL_UNITS_PER_SOURCE_METRE, 0.0F);
        solveFoot(entity, "l", target.leftContact, runtime.leftFoot,
                entityPosition, yaw, model, target, db, rootModelOffset);
        solveFoot(entity, "r", target.rightContact, runtime.rightFoot,
                entityPosition, yaw, model, target, db, rootModelOffset);
    }

    private static void solveFoot(EvaUnit01Entity entity, String side,
                                  boolean contact,
                                  FootLock lock, Vec3 entityPosition,
                                  float yaw, BakedGeoModel model,
                                  PoseBuffer pose, MotionDatabase db,
                                  Vector3f rootModelOffset)
    {
        if (!contact)
        {
            lock.release();
            return;
        }
        int torsoIndex = db.index("torso_lower");
        int legIndex = db.index("leg_" + side);
        int shinIndex = db.index("shin_" + side);
        int footIndex = db.index("foot_" + side);
        GeoBone torsoBone = model.getBone("torso_lower").orElse(null);
        GeoBone legBone = model.getBone("leg_" + side).orElse(null);
        GeoBone shinBone = model.getBone("shin_" + side).orElse(null);
        GeoBone footBone = model.getBone("foot_" + side).orElse(null);
        if (torsoIndex < 0 || legIndex < 0 || shinIndex < 0
                || footIndex < 0 || torsoBone == null || legBone == null
                || shinBone == null || footBone == null)
        {
            lock.release();
            return;
        }

        Vector3f torsoPivot = pivot(torsoBone);
        Vector3f hip = pivot(legBone);
        Vector3f kneeRest = pivot(shinBone);
        Vector3f ankleRest = pivot(footBone);
        Quaternionf torso = new Quaternionf(pose.rotations[torsoIndex]);
        Quaternionf hipRotation = new Quaternionf(pose.rotations[legIndex]);
        Quaternionf kneeRotation = new Quaternionf(pose.rotations[shinIndex]);
        Quaternionf footRotation = new Quaternionf(pose.rotations[footIndex]);

        Vector3f currentAnkle = anklePosition(torsoPivot, torso, hip,
                kneeRest, ankleRest, hipRotation, kneeRotation);
        currentAnkle.add(rootModelOffset);
        if (!lock.locked)
        {
            Vec3 predicted = modelToWorld(currentAnkle, entityPosition, yaw);
            double ankleClearance = ankleRest.y
                    * EvaScale.RENDER_SCALE / 16.0D;
            lock.world = groundedAnkle(entity, predicted, ankleClearance);
            lock.locked = true;
            return;
        }
        Vector3f wantedModel = worldToModel(lock.world, entityPosition, yaw);
        wantedModel.sub(rootModelOffset);
        Quaternionf inverseTorso = new Quaternionf(torso).conjugate();
        Vector3f wanted = new Vector3f(wantedModel).sub(torsoPivot);
        inverseTorso.transform(wanted).add(torsoPivot);

        Vector3f upperRest = new Vector3f(kneeRest).sub(hip);
        Vector3f lowerRest = new Vector3f(ankleRest).sub(kneeRest);
        float upperLength = upperRest.length();
        float lowerLength = lowerRest.length();
        Vector3f toTarget = new Vector3f(wanted).sub(hip);
        float distance = Mth.clamp(toTarget.length(),
                Math.abs(upperLength - lowerLength) + 0.01F,
                upperLength + lowerLength - 0.01F);
        if (distance < 1.0E-4F)
        {
            return;
        }
        Vector3f direction = toTarget.normalize(new Vector3f());
        float along = (upperLength * upperLength
                - lowerLength * lowerLength + distance * distance)
                / (2.0F * distance);
        float bend = Mth.sqrt(Math.max(0.0F,
                upperLength * upperLength - along * along));
        Vector3f bendNormal = new Vector3f(1.0F, 0.0F, 0.0F);
        Vector3f perpendicular = bendNormal.cross(direction,
                new Vector3f());
        if (perpendicular.lengthSquared() < 1.0E-6F)
        {
            perpendicular.set(0.0F, 0.0F, -1.0F);
        }
        else
        {
            perpendicular.normalize();
        }
        Vector3f wantedKnee = new Vector3f(hip)
                .fma(along, direction).fma(bend, perpendicular);

        Vector3f currentUpper = new Vector3f(upperRest);
        hipRotation.transform(currentUpper);
        Vector3f wantedUpper = new Vector3f(wantedKnee).sub(hip);
        Quaternionf hipDelta = new Quaternionf().rotationTo(
                currentUpper.normalize(), wantedUpper.normalize());
        Quaternionf solvedHip = hipDelta.mul(hipRotation,
                new Quaternionf()).normalize();

        Vector3f currentLowerLocal = new Vector3f(lowerRest);
        kneeRotation.transform(currentLowerLocal);
        Vector3f wantedLowerLocal = new Vector3f(wanted).sub(wantedKnee);
        new Quaternionf(solvedHip).conjugate().transform(wantedLowerLocal);
        Quaternionf kneeDelta = new Quaternionf().rotationTo(
                currentLowerLocal.normalize(), wantedLowerLocal.normalize());
        Quaternionf solvedKnee = kneeDelta.mul(kneeRotation,
                new Quaternionf()).normalize();

        Quaternionf originalFootWorld = new Quaternionf(hipRotation)
                .mul(kneeRotation).mul(footRotation).normalize();
        Quaternionf solvedLegWorldInverse = new Quaternionf(solvedHip)
                .mul(solvedKnee).conjugate();
        Quaternionf solvedFoot = solvedLegWorldInverse
                .mul(originalFootWorld).normalize();

        pose.rotations[legIndex] = solvedHip;
        pose.rotations[shinIndex] = solvedKnee;
        pose.rotations[footIndex] = solvedFoot;
    }

    private static Vec3 groundedAnkle(EvaUnit01Entity entity,
                                      Vec3 predicted,
                                      double ankleClearance)
    {
        Vec3 start = predicted.add(0.0D, 12.0D, 0.0D);
        Vec3 end = predicted.add(0.0D, -24.0D, 0.0D);
        BlockHitResult hit = entity.level().clip(new ClipContext(
                start, end, ClipContext.Block.COLLIDER,
                ClipContext.Fluid.NONE, entity));
        if (hit.getType() != HitResult.Type.BLOCK)
        {
            return predicted;
        }
        return new Vec3(predicted.x, hit.getLocation().y + ankleClearance,
                predicted.z);
    }

    private static Vector3f anklePosition(Vector3f torsoPivot,
                                          Quaternionf torso,
                                          Vector3f hip,
                                          Vector3f kneeRest,
                                          Vector3f ankleRest,
                                          Quaternionf hipRotation,
                                          Quaternionf kneeRotation)
    {
        Vector3f upper = new Vector3f(kneeRest).sub(hip);
        hipRotation.transform(upper);
        Vector3f knee = new Vector3f(hip).add(upper);
        Vector3f lower = new Vector3f(ankleRest).sub(kneeRest);
        new Quaternionf(hipRotation).mul(kneeRotation).transform(lower);
        Vector3f ankle = knee.add(lower);
        ankle.sub(torsoPivot);
        torso.transform(ankle);
        return ankle.add(torsoPivot);
    }

    private static Vector3f pivot(GeoBone bone)
    {
        // GeoBone already stores Bedrock pivot X with Gecko's reflection.
        // Convert back to the motion database's Bedrock coordinate system.
        return new Vector3f(-bone.getPivotX(), bone.getPivotY(),
                bone.getPivotZ());
    }

    private static Vec3 modelToWorld(Vector3f model, Vec3 origin, float yaw)
    {
        double scale = EvaScale.RENDER_SCALE / 16.0D;
        double radians = Math.toRadians(yaw);
        Vec3 forward = new Vec3(-Math.sin(radians), 0.0D,
                Math.cos(radians));
        Vec3 left = new Vec3(-Math.cos(radians), 0.0D,
                -Math.sin(radians));
        return origin.add(left.scale(model.x * scale))
                .add(0.0D, model.y * scale, 0.0D)
                .add(forward.scale(-model.z * scale));
    }

    private static Vector3f worldToModel(Vec3 world, Vec3 origin, float yaw)
    {
        double scale = EvaScale.RENDER_SCALE / 16.0D;
        double radians = Math.toRadians(yaw);
        Vec3 forward = new Vec3(-Math.sin(radians), 0.0D,
                Math.cos(radians));
        Vec3 left = new Vec3(-Math.cos(radians), 0.0D,
                -Math.sin(radians));
        Vec3 offset = world.subtract(origin);
        return new Vector3f((float)(offset.dot(left) / scale),
                (float)(offset.y / scale),
                (float)(-offset.dot(forward) / scale));
    }

    private record Selection(MotionClip primary, MotionClip secondary,
                             float blend, double speedBlocksPerSecond,
                             double strideBlocks, boolean locomotion,
                             String key)
    {
        private static Selection single(MotionClip clip, String key)
        {
            return new Selection(clip, null, 0.0F, 0.0D, 1.0D,
                    false, key);
        }

        private static Selection locomotion(MotionClip primary,
                                            MotionClip secondary,
                                            float blend, double speed,
                                            double stride, String key)
        {
            return new Selection(primary, secondary, blend, speed, stride,
                    true, key);
        }
    }

    private static final class RuntimeState
    {
        private final Quaternionf[] rotations;
        private final boolean[] initialized;
        private final PoseBuffer poseA;
        private final PoseBuffer poseB;
        private final PoseBuffer target;
        private long lastNanos;
        private double phase;
        private double actionTime;
        private double comboTime;
        private int previewMode = Integer.MIN_VALUE;
        private String selectionKey = "";
        private boolean lastLocomotion;
        private boolean airStateInitialized;
        private boolean wasAirborne;
        private boolean landingActive;
        private boolean apexReached;
        private double airborneAge;
        private double fallAge;
        private boolean distanceInitialized;
        private double lastRenderX;
        private double lastRenderZ;
        private final FootLock leftFoot = new FootLock();
        private final FootLock rightFoot = new FootLock();

        private RuntimeState(int bones)
        {
            this.rotations = new Quaternionf[bones];
            this.initialized = new boolean[bones];
            for (int index = 0; index < bones; index++)
            {
                this.rotations[index] = new Quaternionf();
            }
            this.poseA = new PoseBuffer(bones);
            this.poseB = new PoseBuffer(bones);
            this.target = new PoseBuffer(bones);
        }
    }

    private static final class FootLock
    {
        private boolean locked;
        private Vec3 world = Vec3.ZERO;

        private void release()
        {
            this.locked = false;
            this.world = Vec3.ZERO;
        }
    }

    private static final class PoseBuffer
    {
        private final Quaternionf[] rotations;
        private final Vector3f rootMeters = new Vector3f();
        private boolean leftContact;
        private boolean rightContact;

        private PoseBuffer(int bones)
        {
            this.rotations = new Quaternionf[bones];
            for (int index = 0; index < bones; index++)
            {
                this.rotations[index] = new Quaternionf();
            }
        }

        private void copyFrom(PoseBuffer source)
        {
            for (int index = 0; index < this.rotations.length; index++)
            {
                this.rotations[index].set(source.rotations[index]);
            }
            this.rootMeters.set(source.rootMeters);
            this.leftContact = source.leftContact;
            this.rightContact = source.rightContact;
        }

        private static void blend(PoseBuffer first, PoseBuffer second,
                                  float amount, PoseBuffer output)
        {
            for (int index = 0; index < output.rotations.length; index++)
            {
                output.rotations[index].set(first.rotations[index])
                        .slerp(second.rotations[index], amount).normalize();
            }
            output.rootMeters.set(first.rootMeters)
                    .lerp(second.rootMeters, amount);
            output.leftContact = amount < 0.5F
                    ? first.leftContact : second.leftContact;
            output.rightContact = amount < 0.5F
                    ? first.rightContact : second.rightContact;
        }
    }

    private static final class MotionClip
    {
        private final double durationSeconds;
        private final boolean loop;
        private final boolean closedEndpoint;
        private final double strideBlocks;
        private final Frame[] frames;

        private MotionClip(double durationSeconds, boolean loop,
                           boolean closedEndpoint, double strideBlocks,
                           Frame[] frames)
        {
            this.durationSeconds = durationSeconds;
            this.loop = loop;
            this.closedEndpoint = closedEndpoint;
            this.strideBlocks = strideBlocks;
            this.frames = frames;
        }

        private double strideBlocks(double fallback)
        {
            return this.strideBlocks > 0.01D ? this.strideBlocks : fallback;
        }

        private void sample(double normalizedTime, PoseBuffer output)
        {
            double scaled = this.loop
                    ? wrap01(normalizedTime) * (this.closedEndpoint
                            ? this.frames.length - 1 : this.frames.length)
                    : Mth.clamp(normalizedTime, 0.0D, 1.0D)
                            * (this.frames.length - 1);
            int firstIndex = Math.min(this.frames.length - 1,
                    (int)Math.floor(scaled));
            int secondIndex = this.loop
                    ? (this.closedEndpoint
                            ? Math.min(this.frames.length - 1, firstIndex + 1)
                            : (firstIndex + 1) % this.frames.length)
                    : Math.min(this.frames.length - 1, firstIndex + 1);
            float alpha = (float)(scaled - Math.floor(scaled));
            Frame first = this.frames[firstIndex];
            Frame second = this.frames[secondIndex];
            for (int index = 0; index < output.rotations.length; index++)
            {
                output.rotations[index].set(first.rotations[index])
                        .slerp(second.rotations[index], alpha).normalize();
            }
            output.rootMeters.set(first.rootMeters)
                    .lerp(second.rootMeters, alpha);
            output.leftContact = alpha < 0.5F
                    ? first.leftContact : second.leftContact;
            output.rightContact = alpha < 0.5F
                    ? first.rightContact : second.rightContact;
        }
    }

    private record Frame(Quaternionf[] rotations, Vector3f rootMeters,
                         boolean leftContact, boolean rightContact) {}

    private static final class MotionDatabase
    {
        private final String[] bones;
        private final Map<String, Integer> indices;
        private final Map<String, MotionClip> clips;
        private final int totalFrames;

        private MotionDatabase(String[] bones,
                               Map<String, Integer> indices,
                               Map<String, MotionClip> clips,
                               int totalFrames)
        {
            this.bones = bones;
            this.indices = indices;
            this.clips = clips;
            this.totalFrames = totalFrames;
        }

        private static MotionDatabase empty()
        {
            return new MotionDatabase(new String[0], Map.of(), Map.of(), 0);
        }

        private int index(String bone)
        {
            return this.indices.getOrDefault(bone, -1);
        }

        private MotionClip clip(String name)
        {
            MotionClip clip = this.clips.get(name);
            if (clip == null)
            {
                throw new IllegalStateException("missing EVA motion clip " + name);
            }
            return clip;
        }

        private static MotionDatabase parse(JsonObject root)
        {
            if (root == null || root.get("schema").getAsInt() != 2)
            {
                throw new IllegalArgumentException("unsupported motion schema");
            }
            JsonArray boneArray = root.getAsJsonArray("bones");
            String[] bones = new String[boneArray.size()];
            Set<String> unique = new HashSet<>();
            Map<String, Integer> indices = new HashMap<>();
            for (int index = 0; index < bones.length; index++)
            {
                bones[index] = boneArray.get(index).getAsString();
                if (!unique.add(bones[index]))
                {
                    throw new IllegalArgumentException(
                            "duplicate motion bone " + bones[index]);
                }
                indices.put(bones[index], index);
            }
            Map<String, MotionClip> clips = new HashMap<>();
            int totalFrames = 0;
            for (Map.Entry<String, JsonElement> entry
                    : root.getAsJsonObject("clips").entrySet())
            {
                JsonObject json = entry.getValue().getAsJsonObject();
                JsonArray frameArray = json.getAsJsonArray("frames");
                if (frameArray.size() < 2)
                {
                    throw new IllegalArgumentException(
                            "motion clip has fewer than two frames: "
                                    + entry.getKey());
                }
                Frame[] frames = new Frame[frameArray.size()];
                for (int frameIndex = 0; frameIndex < frames.length;
                        frameIndex++)
                {
                    JsonObject frameJson = frameArray.get(frameIndex)
                            .getAsJsonObject();
                    JsonArray rotationsJson = frameJson
                            .getAsJsonArray("rotation_wxyz");
                    if (rotationsJson.size() != bones.length)
                    {
                        throw new IllegalArgumentException(
                                "bone/frame mismatch in " + entry.getKey());
                    }
                    Quaternionf[] rotations = new Quaternionf[bones.length];
                    for (int boneIndex = 0; boneIndex < bones.length;
                            boneIndex++)
                    {
                        JsonArray q = rotationsJson.get(boneIndex)
                                .getAsJsonArray();
                        rotations[boneIndex] = new Quaternionf(
                                q.get(1).getAsFloat(), q.get(2).getAsFloat(),
                                q.get(3).getAsFloat(), q.get(0).getAsFloat())
                                .normalize();
                    }
                    JsonArray contact = frameJson
                            .getAsJsonArray("foot_contact");
                    JsonArray rootPosition = frameJson
                            .getAsJsonArray("root_m");
                    frames[frameIndex] = new Frame(rotations,
                            new Vector3f(rootPosition.get(0).getAsFloat(),
                                    rootPosition.get(1).getAsFloat(),
                                    rootPosition.get(2).getAsFloat()),
                            contact.get(0).getAsBoolean(),
                            contact.get(1).getAsBoolean());
                }
                MotionClip clip = new MotionClip(
                        json.get("duration_seconds").getAsDouble(),
                        json.get("loop").getAsBoolean(),
                        json.has("closed_endpoint")
                                && json.get("closed_endpoint").getAsBoolean(),
                        parseStrideBlocks(json),
                        frames);
                clips.put(entry.getKey(), clip);
                totalFrames += frames.length;
            }
            return new MotionDatabase(bones, Map.copyOf(indices),
                    Map.copyOf(clips), totalFrames);
        }

        private static double parseStrideBlocks(JsonObject clip)
        {
            if (!clip.has("root_travel_m"))
            {
                return 0.0D;
            }
            JsonArray travel = clip.getAsJsonArray("root_travel_m");
            if (travel.size() != 3)
            {
                throw new IllegalArgumentException(
                        "root_travel_m must have three components");
            }
            double x = travel.get(0).getAsDouble();
            double z = travel.get(2).getAsDouble();
            return Math.hypot(x, z) * MODEL_UNITS_PER_SOURCE_METRE
                    * EvaScale.RENDER_SCALE / 16.0D;
        }
    }
}
