package com.projectseele.client.render;

import java.io.Reader;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashSet;
import java.util.Map;
import java.util.Set;
import java.util.WeakHashMap;

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
 * space and inertializes pose changes every rendered frame. Ordinary fist
 * attacks use the promoted visual database in normal play; damage, cooldown,
 * hit zones and input validation remain server-authoritative.</p>
 */
public final class EvaMotionEngineV2
{
    public static final String OWNER_PREVIEW = "MOTION_ENGINE_PREVIEW";
    public static final String OWNER_LIVE_ACTION =
            "MOTION_ENGINE_LIVE_ACTION";
    private static final ResourceLocation DATABASE = new ResourceLocation(
            ProjectSeele.MODID, "motion/eva_humanoid_v2.json");
    private static final ResourceLocation PHYSICS_DATABASE = new ResourceLocation(
            ProjectSeele.MODID, "motion/eva_physics_preview_v1.json");
    private static final ResourceLocation GROUNDED_DATABASE = new ResourceLocation(
            ProjectSeele.MODID, "motion/eva_grounded_preview_v1.json");
    private static final ResourceLocation ORDINARY_ATTACK_DATABASE =
            new ResourceLocation(ProjectSeele.MODID,
                    "motion/eva_ordinary_attack_v1.json");
    private static final ResourceLocation LIVE_ORDINARY_ATTACK_DATABASE =
            new ResourceLocation(ProjectSeele.MODID,
                    "motion/eva_ordinary_attack_group_c_v1.json");
    private static final ResourceLocation LIVE_KICK_DATABASE =
            new ResourceLocation(ProjectSeele.MODID,
                    "motion/eva_kick_side_left_v1.json");
    private static final ResourceLocation LIVE_KNIFE_DATABASE =
            new ResourceLocation(ProjectSeele.MODID,
                    "motion/eva_knife_attacks_phase_m_v1.json");
    private static final ResourceLocation CONNECTED_LOCOMOTION_DATABASE =
            new ResourceLocation(ProjectSeele.MODID,
                    "motion/eva_connected_locomotion_v1.json");
    private static final Map<EvaUnit01Entity, GameplayState> GAMEPLAY = new WeakHashMap<>();
    private static volatile MotionDatabase connectedLocomotion = MotionDatabase.empty();
    private static final double WALK_STRIDE_BLOCKS = 25.8334D;
    private static final double RUN_STRIDE_BLOCKS = 31.3944D;
    private static final double CROUCH_STRIDE_BLOCKS = 9.2990D;
    private static final float MODEL_UNITS_PER_SOURCE_METRE = 112.0F;
    private static final double LIVE_ATTACK_RECOVERY_SECONDS = 0.16D;
    private static final float MAX_LIVE_ROOT_STEP_METRES = 0.0055F;
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
    private static volatile MotionDatabase ordinaryAttackDatabase =
            MotionDatabase.empty();
    private static volatile MotionDatabase liveOrdinaryAttackDatabase =
            MotionDatabase.empty();
    private static volatile MotionDatabase liveKickDatabase =
            MotionDatabase.empty();
    private static volatile MotionDatabase liveKnifeDatabase =
            MotionDatabase.empty();
    private static volatile MotionDatabase liveHeavyDatabase=MotionDatabase.empty();

    private EvaMotionEngineV2() {}
    public static void resetEntityR30(EvaUnit01Entity entity){STATES.remove(entity.getId());GAMEPLAY.remove(entity);}

    public static void reload(ResourceManager resourceManager)
    {
        com.projectseele.entity.EvaBodyPose.reload();
        liveHeavyDatabase=load(resourceManager,new ResourceLocation(ProjectSeele.MODID,"motion/eva_heavy_right_cross_r05.json"),"EVA R05 right cross");
        STATES.clear();
        GAMEPLAY.clear();
        ResourceLocation revisedLocomotion=new ResourceLocation(ProjectSeele.MODID,"motion/eva_connected_locomotion_r10.json");
        if(resourceManager.getResource(revisedLocomotion).isEmpty())revisedLocomotion=new ResourceLocation(ProjectSeele.MODID,"motion/eva_connected_locomotion_r05.json");
        connectedLocomotion = load(resourceManager, resourceManager.getResource(revisedLocomotion).isPresent()?revisedLocomotion:CONNECTED_LOCOMOTION_DATABASE,
                "EVA connected locomotion");
        database = load(resourceManager, DATABASE, "EVA Motion Engine V2");
        physicsDatabase = load(resourceManager, PHYSICS_DATABASE,
                "EVA physics preview");
        groundedDatabase = load(resourceManager, GROUNDED_DATABASE,
                "EVA grounded mocap preview");
        ordinaryAttackDatabase = load(resourceManager,
                ORDINARY_ATTACK_DATABASE,
                "EVA ordinary attack runtime");
        liveOrdinaryAttackDatabase = load(resourceManager,
                LIVE_ORDINARY_ATTACK_DATABASE,
                "EVA group-C ordinary attack runtime");
        liveKickDatabase = load(resourceManager, LIVE_KICK_DATABASE,
                "EVA K1 side-kick runtime");
        liveKnifeDatabase = load(resourceManager, LIVE_KNIFE_DATABASE,
                "EVA approved Phase-M knife runtime");
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

    /** Returns the exact transform channels replaced after Gecko this frame. */
    public static BoneWrites apply(EvaUnit01Entity entity,
                                   BakedGeoModel model, float partialTick)
    {
        if(entity.isFirstBattleActive())return FirstBattlePoseRenderer.apply(entity,model,partialTick);
        int previewMode = entity.getMotionLabPhysicsPreview();
        if (previewMode == 0)
        {
            return applyGameplay(entity, model, partialTick);
        }
        if (previewMode == 3)
        {
            return applyLivePhysics(model);
        }
        boolean replayPreview = previewMode == 1 || previewMode == 2;
        boolean groundedPreview = previewMode == 4 || previewMode == 5;
        boolean ordinaryAttackReview = previewMode >= 6 && previewMode <= 9;
        boolean labPreview = replayPreview || groundedPreview
                || ordinaryAttackReview;
        boolean gameplayOrdinaryAttack = entity.getWeapon()
                == EvaUnit01Entity.WEAPON_FISTS
                && entity.getOrdinaryAttackStage() >= 0
                && !entity.isPilotProne() && !entity.isPilotCrouching();
        boolean gameplayKick = !gameplayOrdinaryAttack
                && entity.isKickMotionActive(partialTick);
        int gameplayKnifeType = entity.getKnifeMotionType(partialTick);
        boolean gameplayKnife = !gameplayOrdinaryAttack && !gameplayKick
                && gameplayKnifeType >= 0;
        boolean gameplayLiveAction = gameplayOrdinaryAttack || gameplayKick
                || gameplayKnife;
        RuntimeState existingRuntime = STATES.get(entity.getId());
        boolean gameplayRecovery = !gameplayLiveAction
                && previewMode == 0
                && entity.getWeapon() == EvaUnit01Entity.WEAPON_FISTS
                && !entity.isPilotProne() && !entity.isPilotCrouching()
                && existingRuntime != null
                && existingRuntime.liveAttackActive
                && existingRuntime.liveAttackRecoveryAge
                        < LIVE_ATTACK_RECOVERY_SECONDS;
        boolean motionDriven = labPreview || gameplayOrdinaryAttack
                || gameplayKick || gameplayKnife || gameplayRecovery;
        MotionDatabase db = gameplayOrdinaryAttack
                ? liveOrdinaryAttackDatabase
                : gameplayKick ? liveKickDatabase
                : gameplayKnife ? liveKnifeDatabase
                : gameplayRecovery && existingRuntime != null
                        && "kick".equals(existingRuntime.liveActionFamily)
                ? liveKickDatabase
                : gameplayRecovery ? liveOrdinaryAttackDatabase
                : ordinaryAttackReview ? ordinaryAttackDatabase
                : groundedPreview ? groundedDatabase
                : replayPreview ? physicsDatabase : database;
        if (!motionDriven || db.bones.length == 0
                || entity.isNervLogisticsLocked() || entity.isCrucified()
                || (!labPreview && !entity.isPoweredOn())
                || entity.isPilotProne()
                || entity.isPilotCrouching()
                || entity.getVisualPose() == EvaUnit01Entity.VISUAL_CROUCH
                || entity.getVisualPose() == EvaUnit01Entity.VISUAL_CROUCH_WALK
                || entity.getVisualPose() == EvaUnit01Entity.VISUAL_CRAWL)
        {
            STATES.remove(entity.getId());
            return BoneWrites.empty();
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
        if (gameplayLiveAction)
        {
            runtime.liveAttackActive = true;
            runtime.liveAttackRecoveryAge = 0.0D;
            String family = gameplayKick ? "kick"
                    : gameplayKnife ? gameplayKnifeType == 1
                            ? "knife_reverse" : "knife_forward"
                    : "ordinary";
            if (!family.equals(runtime.liveActionFamily))
            {
                runtime.liveActionFamily = family;
                runtime.liveTransitionAge = 0.0D;
            }
            else
            {
                runtime.liveTransitionAge += dt;
            }
            if (gameplayOrdinaryAttack)
            {
                runtime.lastLiveAttackStage = Mth.clamp(
                        entity.getOrdinaryAttackStage(), 0, 3);
            }
        }
        else if (gameplayRecovery)
        {
            runtime.liveAttackRecoveryAge += dt;
        }

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
                runtime.carryLandingGait = false;
                runtime.selectionKey = "";
            }
            if (runtime.wasAirborne && !airborneNow)
            {
                runtime.landingActive = true;
                runtime.landingGaitPhase = 0.0D;
                runtime.carryLandingGait = false;
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

        MotionClip takeoffClip = motionDriven
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
        else if (gameplayOrdinaryAttack)
        {
            String clipName = switch (entity.getOrdinaryAttackStage())
            {
                case 0 -> "ordinary_attack_group_c_stage_1";
                case 1 -> "ordinary_attack_group_c_stage_2";
                case 2 -> "ordinary_attack_group_c_stage_3";
                default -> "ordinary_attack_group_c_stage_1_loop";
            };
            selection = Selection.single(db.clip(clipName), clipName);
            runtime.landingActive = false;
        }
        else if (gameplayKick)
        {
            selection = Selection.single(db.clip("kick_side_left"),
                    "kick_side_left");
            runtime.landingActive = false;
        }
        else if (gameplayKnife)
        {
            String clipName = gameplayKnifeType == 1
                    ? "eva_short_knife_stab_twist_reverse"
                    : "eva_locked_knife_stab_twist_forward";
            selection = Selection.single(db.clip(clipName), clipName);
            runtime.landingActive = false;
        }
        else if (gameplayRecovery)
        {
            String clipName;
            if ("kick".equals(runtime.liveActionFamily))
            {
                clipName = "kick_side_left";
            }
            else
            {
                clipName = switch (runtime.lastLiveAttackStage)
                {
                    case 0 -> "ordinary_attack_group_c_stage_1";
                    case 1 -> "ordinary_attack_group_c_stage_2";
                    case 2 -> "ordinary_attack_group_c_stage_3";
                    default -> "ordinary_attack_group_c_stage_1_loop";
                };
            }
            selection = Selection.single(db.clip(clipName),
                    clipName + "_recovery");
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
            selection = runtime.airborneAge < takeoffClip.durationSeconds / 1.55D
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
            if (gameplayLiveAction)
            {
                ProjectSeele.LOGGER.info(
                        "EVA post-Gecko live pose selected: entity={} family={} "
                                + "clip={} stage={} bones={}",
                        entity.getId(), gameplayKick ? "kick"
                                : gameplayKnife ? gameplayKnifeType == 1
                                        ? "knife_reverse" : "knife_forward"
                                : "ordinary",
                        selection.key(), entity.getOrdinaryAttackStage(),
                        db.bones.length);
            }
            runtime.selectionKey = selection.key();
            runtime.actionTime = 0.0D;
            if (enteringLocomotion && runtime.carryLandingGait)
            {
                runtime.phase = runtime.landingGaitPhase;
                runtime.carryLandingGait = false;
            }
            else if (enteringLocomotion || !selection.locomotion())
            {
                runtime.phase = 0.0D;
            }
            runtime.distanceInitialized = false;
        }
        runtime.lastLocomotion = selection.locomotion();

        if (gameplayOrdinaryAttack)
        {
            runtime.phase = entity.getOrdinaryAttackProgress(partialTick);
        }
        else if (gameplayKick)
        {
            runtime.phase = entity.getKickAttackProgress(partialTick);
        }
        else if (gameplayKnife)
        {
            runtime.phase = entity.getKnifeMotionProgress(
                    gameplayKnifeType, partialTick);
        }
        else if (gameplayRecovery)
        {
            runtime.phase = 1.0D;
        }
        else if (replayPreview || ordinaryAttackReview)
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
                        (runtime.airborneAge - takeoffClip.durationSeconds / 1.55D)
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
            double playbackRate="takeoff_v2".equals(selection.key())?1.55D:
                    "landing_v2".equals(selection.key())?1.7D:1.0D;
            runtime.actionTime = Math.min(selection.primary().durationSeconds,
                    runtime.actionTime + dt * playbackRate);
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
        if(runtime.landingActive&&(entity.getDeltaMovement().horizontalDistanceSqr()>.01D||entity.isPilotSprinting()))
        {
            Selection locomotion=select(entity,db);
            if(locomotion.locomotion())
            {
                runtime.landingGaitPhase=wrap01(runtime.landingGaitPhase+dt*locomotion.speedBlocksPerSecond()/Math.max(1,locomotion.strideBlocks()));
                runtime.carryLandingGait=true;
                locomotion.primary().sample(runtime.landingGaitPhase,runtime.poseB);
                float landingBlend=(float)Mth.clamp((runtime.phase-.12D)/.70D,0D,1D);
                PoseBuffer.blend(runtime.poseA,runtime.poseB,landingBlend,runtime.target);
            }
        }
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

        Set<String> positionBones = new LinkedHashSet<>();
        Set<String> rotationBones = new LinkedHashSet<>();
        Vector3f rootOffset = new Vector3f(target.rootMeters)
                .mul(MODEL_UNITS_PER_SOURCE_METRE);
        if (gameplayLiveAction)
        {
            float rootAlpha = (float)(1.0D - Math.exp(
                    -Math.log(2.0D) * dt
                            / liveActionHalfLife(gameplayKick, runtime)));
            if (!runtime.liveRootInitialized)
            {
                runtime.currentLiveRootYOffset = 0.0F;
                runtime.liveRootInitialized = true;
            }
            float rootStep = (rootOffset.y
                    - runtime.currentLiveRootYOffset) * rootAlpha;
            float maximumRootStep = MAX_LIVE_ROOT_STEP_METRES
                    * MODEL_UNITS_PER_SOURCE_METRE;
            runtime.currentLiveRootYOffset += Mth.clamp(
                    rootStep, -maximumRootStep, maximumRootStep);
            runtime.liveAttackRootYOffset =
                    runtime.currentLiveRootYOffset;
            rootOffset.y = runtime.currentLiveRootYOffset;
        }
        else if (gameplayRecovery)
        {
            float rootAlpha = (float)(1.0D - Math.exp(
                    -Math.log(2.0D) * dt / 0.035D));
            float maximumRootStep = MAX_LIVE_ROOT_STEP_METRES
                    * MODEL_UNITS_PER_SOURCE_METRE;
            float rootStep = -runtime.currentLiveRootYOffset * rootAlpha;
            runtime.currentLiveRootYOffset += Mth.clamp(
                    rootStep, -maximumRootStep, maximumRootStep);
            runtime.liveAttackRootYOffset =
                    runtime.currentLiveRootYOffset;
            rootOffset.set(0.0F, runtime.currentLiveRootYOffset, 0.0F);
        }
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
            positionBones.add("root");
        });

        boolean meleeActive = entity.getCockpitAttackAnim(partialTick) > 0.0F
                || entity.getCockpitSmashAnim(partialTick) > 0.0F;
        boolean fullBody = ordinaryAttackReview || gameplayOrdinaryAttack
                || gameplayKick || gameplayKnife || gameplayRecovery
                || entity.getWeapon() == EvaUnit01Entity.WEAPON_FISTS
                && !meleeActive;
        float inertialAlpha;
        if (replayPreview || ordinaryAttackReview)
        {
            inertialAlpha = 1.0F;
        }
        else
        {
            double halfLife = gameplayLiveAction
                    ? liveActionHalfLife(gameplayKick, runtime)
                    : gameplayRecovery ? 0.035D
                    : groundedPreview ? 0.035D
                    : selection.locomotion() ? 0.050D : 0.075D;
            inertialAlpha = (float)(1.0D - Math.exp(
                    -Math.log(2.0D) * dt / halfLife));
            if (gameplayRecovery
                    && runtime.liveAttackRecoveryAge
                            >= LIVE_ATTACK_RECOVERY_SECONDS)
            {
                inertialAlpha = 1.0F;
            }
        }

        for (int index = 0; index < db.bones.length; index++)
        {
            String name = db.bones[index];
            // Weapon gameplay keeps Gecko's weapon-specific finger layer.
            // Ordinary fist mocap owns its audited static fist explicitly so
            // the promoted body clip cannot silently show an open hand. The
            // retained native thumb already carries its per-side opposition.
            if (name.startsWith("finger_")
                    && !ordinaryAttackReview && !gameplayOrdinaryAttack
                    && !gameplayKick && !gameplayKnife && !gameplayRecovery)
            {
                continue;
            }
            if (!fullBody && !LOWER_BODY.contains(name))
            {
                continue;
            }
            Quaternionf wanted = target.rotations[index];
            GeoBone geckoBone = model.getBone(name).orElse(null);
            if (gameplayRecovery)
            {
                if (geckoBone == null)
                {
                    continue;
                }
                wanted = geckoRotationAsMotionQuaternion(geckoBone);
            }
            Quaternionf current = runtime.rotations[index];
            if (!runtime.initialized[index])
            {
                if (gameplayLiveAction && geckoBone != null)
                {
                    current.set(geckoRotationAsMotionQuaternion(geckoBone))
                            .slerp(wanted, inertialAlpha).normalize();
                }
                else
                {
                    current.set(wanted);
                }
                runtime.initialized[index] = true;
            }
            else
            {
                current.slerp(wanted, inertialAlpha).normalize();
            }
            model.getBone(name).ifPresent(bone ->
            {
                Vector3f euler = motionQuaternionToAuthoredEuler(current);
                // Gecko's Builtin BakedModelFactory converts authored
                // Bedrock rotations as (-X, -Y, +Z). This runtime path must
                // perform the same basis change or an offline-correct pose is
                // mirrored into a folded limb configuration in game.
                bone.setRotX(-euler.x);
                bone.setRotY(-euler.y);
                bone.setRotZ(euler.z);
                rotationBones.add(name);
            });
            if (target.positionAuthored[index])
            {
                Vector3f position = target.positions[index];
                model.getBone(name).ifPresent(bone ->
                {
                    // GeoBone/RenderUtils applies the Bedrock X reflection;
                    // these are the exact authored offsets used by Blender.
                    bone.setPosX(position.x);
                    bone.setPosY(position.y);
                    bone.setPosZ(position.z);
                    positionBones.add(name);
                });
            }
        }
        if (gameplayRecovery
                && runtime.liveAttackRecoveryAge
                        >= LIVE_ATTACK_RECOVERY_SECONDS)
        {
            runtime.liveAttackActive = false;
            runtime.liveAttackRootYOffset = 0.0F;
            runtime.currentLiveRootYOffset = 0.0F;
            runtime.liveRootInitialized = false;
        }
        return new BoneWrites(Set.copyOf(rotationBones),
                Set.copyOf(positionBones),
                gameplayLiveAction || gameplayRecovery
                        ? OWNER_LIVE_ACTION : OWNER_PREVIEW);
    }

    private static BoneWrites applyGameplay(EvaUnit01Entity entity,
                                           BakedGeoModel model, float partialTick)
    {
        if (!entity.isPoweredOn() || entity.isNervLogisticsLocked()
                || entity.isCrucified() || entity.isBerserk()
                || entity.getActivationTicks() > 0 || entity.isPilotProne()
                || entity.isShieldBraced())
        {
            GAMEPLAY.remove(entity);
            return BoneWrites.empty();
        }
        int ordinary = entity.getOrdinaryAttackStage();
        boolean heavy = entity.isHeavyMotionActive();
        boolean kick = entity.isKickMotionActive(partialTick);
        int knife = entity.getKnifeMotionType(partialTick);
        boolean action = heavy || ordinary >= 0 || kick || knife >= 0;
        boolean base = !action && !entity.hasLegacyStrikeForRender() && entity.getVisualPose() == 0
                && !entity.isVisuallyAirborneForRender()
                && (entity.getWeapon() == EvaUnit01Entity.WEAPON_FISTS
                    || entity.getWeapon() == EvaUnit01Entity.WEAPON_KNIFE
                    || entity.getWeapon() == EvaUnit01Entity.WEAPON_RIFLE)
                && !(entity.getWeapon() == EvaUnit01Entity.WEAPON_FISTS
                    && entity.getCockpitSmashAnim(partialTick) > 0.0F)
                && !(entity.isPilotCrouching()
                    && (entity.getCockpitAttackAnim(partialTick) > 0.0F
                        || entity.getCockpitSmashAnim(partialTick) > 0.0F));
        if (!action && !base) return BoneWrites.empty();
        MotionDatabase db = heavy ? liveHeavyDatabase : ordinary >= 0 ? liveOrdinaryAttackDatabase
                : kick ? liveKickDatabase : knife >= 0 ? liveKnifeDatabase : connectedLocomotion;
        if (db.bones.length == 0) return BoneWrites.empty();
        GameplayState state = GAMEPLAY.computeIfAbsent(entity, ignored -> new GameplayState());
        double time = (entity.tickCount + (double)partialTick) / 20.0D;
        double dt = Math.max(0.0D, Math.min(0.1D, time - state.time));
        double x = Mth.lerp((double)partialTick, entity.xOld, entity.getX());
        double z = Mth.lerp((double)partialTick, entity.zOld, entity.getZ());
        state.time = time;
        state.x = x;
        state.z = z;
        state.initialized = true;
        PoseBuffer target = state.buffers.computeIfAbsent(db, ignored -> new PoseBuffer(db.bones.length));
        String clip;
        double phase;
        if (heavy)
        {
            clip = "heavy_right_cross";
            phase = entity.heavyMotionProgress(partialTick);
        }
        else if (ordinary >= 0)
        {
            clip = ordinary == 3 ? "ordinary_attack_group_c_stage_1_loop"
                    : "ordinary_attack_group_c_stage_" + (ordinary + 1);
            phase = entity.getOrdinaryAttackProgress(partialTick);
        }
        else if (kick)
        {
            clip = "kick_side_left";
            phase = entity.getKickAttackProgress(partialTick);
        }
        else if (knife >= 0)
        {
            clip = knife == 1 ? "eva_short_knife_stab_twist_reverse"
                    : "eva_locked_knife_stab_twist_forward";
            phase = entity.getKnifeMotionProgress(knife, partialTick);
        }
        else
        {
            boolean moving = entity.isVisuallyMovingForRender();
            boolean crouch = entity.isPilotCrouching();
            if (!state.stanceInitialized)
            {
                state.stanceInitialized = true;
                state.crouched = crouch;
                state.stanceStart = Double.NEGATIVE_INFINITY;
            }
            else if (state.crouched != crouch)
            {
                state.crouched = crouch;
                state.stanceStart = time;
            }
            state.run = entity.rifleRunBlend(partialTick);
            clip = crouch ? moving ? "crouch_walk" : "crouch_idle" : moving ? "walk" : "idle";
            // One phase drives the feet, rifle carrier motion and contact audio.
            // Weapon changes therefore cannot restart the gait on a different foot.
            state.gaitPhase = wrap01(entity.rifleGaitPhase(partialTick));
            phase = moving ? state.gaitPhase : wrap01(time / db.clip(clip).durationSeconds);
            String stanceClip = crouch ? "stand_to_crouch" : "crouch_to_stand";
            if (moving) state.stanceStart = Double.NEGATIVE_INFINITY;
            double stanceAge = time - state.stanceStart;
            if (!moving && stanceAge < db.clip(stanceClip).durationSeconds)
            {
                clip = stanceClip;
                phase = Math.max(0.0D, stanceAge / db.clip(clip).durationSeconds);
            }
        }
        db.clip(clip).sample(phase, target);
        if (base && clip.equals("walk") && state.run > 0.0001F)
        {
            if (state.runPose == null) state.runPose = new PoseBuffer(db.bones.length);
            db.clip("run").sample(phase, state.runPose);
            PoseBuffer.blend(target, state.runPose, state.run, target);
        }
        if (base && entity.isVisuallyMovingForRender())
        {
            applyDirectionalWarp(entity, target, db);
        }
        Set<String> rotations = new LinkedHashSet<>();
        Set<String> positions = new LinkedHashSet<>();
        model.getBone("root").ifPresent(root ->
        {
            root.setPosY(root.getInitialSnapshot().getOffsetY() + target.rootMeters.y * MODEL_UNITS_PER_SOURCE_METRE);
            if (base)
            {
                root.setPosX(root.getInitialSnapshot().getOffsetX() + target.rootMeters.x * MODEL_UNITS_PER_SOURCE_METRE);
                root.setPosZ(root.getInitialSnapshot().getOffsetZ() + target.rootMeters.z * MODEL_UNITS_PER_SOURCE_METRE);
            }
            else if(heavy){root.setPosX(root.getInitialSnapshot().getOffsetX());root.setPosZ(root.getInitialSnapshot().getOffsetZ());}
            positions.add("root");
        });
        for (int i = 0; i < db.bones.length; i++)
        {
            String name = db.bones[i];
            if(base&&entity.getWeapon()==EvaUnit01Entity.WEAPON_RIFLE&&(name.startsWith("finger_")||name.startsWith("arm_")||name.startsWith("forearm_")||name.startsWith("wrist_")||name.startsWith("hand_")||name.equals("cannon")||name.equals("aim_pitch")))continue;
            if (base && (name.equals("head") || entity.getWeapon() == EvaUnit01Entity.WEAPON_KNIFE
                    && (name.startsWith("finger_") || name.equals("arm_r")
                        || name.equals("forearm_r") || name.equals("hand_r")))) continue;
            GeoBone bone = model.getBone(name).orElse(null);
            if (bone == null) continue;
            Vector3f euler = motionQuaternionToAuthoredEuler(target.rotations[i]);
            bone.setRotX(-euler.x);
            bone.setRotY(-euler.y);
            bone.setRotZ(euler.z);
            rotations.add(name);
            if (target.positionAuthored[i])
            {
                Vector3f p = target.positions[i];
                bone.setPosX(p.x);
                bone.setPosY(p.y);
                bone.setPosZ(p.z);
                positions.add(name);
            }
        }
        return new BoneWrites(Set.copyOf(rotations), Set.copyOf(positions), OWNER_LIVE_ACTION);
    }

    private static final class GameplayState
    {
        private final Map<MotionDatabase, PoseBuffer> buffers = new HashMap<>();
        private PoseBuffer runPose;
        private double time;
        private double x;
        private double z;
        private double gaitPhase;
        private float run;
        private boolean initialized;
        private boolean stanceInitialized;
        private boolean crouched;
        private double stanceStart;
    }

    private static Quaternionf geckoRotationAsMotionQuaternion(GeoBone bone)
    {
        double x = -bone.getRotX();
        double y = -bone.getRotY();
        double z = bone.getRotZ();
        double cx = Math.cos(x * 0.5D);
        double sx = Math.sin(x * 0.5D);
        double cy = Math.cos(y * 0.5D);
        double sy = Math.sin(y * 0.5D);
        double cz = Math.cos(z * 0.5D);
        double sz = Math.sin(z * 0.5D);
        return new Quaternionf(
                (float)(sx * cy * cz - cx * sy * sz),
                (float)(cx * sy * cz + sx * cy * sz),
                (float)(cx * cy * sz - sx * sy * cz),
                (float)(cx * cy * cz + sx * sy * sz)).normalize();
    }

    /** Matches Blender mathutils Quaternion.to_euler("XYZ") exactly. */
    static double rifleGaitPhase(EvaUnit01Entity entity)
    {
        GameplayState state = GAMEPLAY.get(entity);
        return state == null ? 0 : state.gaitPhase;
    }

    static Vector3f motionQuaternionToAuthoredEuler(
            Quaternionf rotation)
    {
        return QuaternionChannels.euler(rotation);
    }

    private static double liveActionHalfLife(boolean kick,
                                             RuntimeState runtime)
    {
        if (runtime.liveTransitionAge < 0.14D)
        {
            return 0.060D;
        }
        return kick ? 0.030D : 0.025D;
    }

    private static BoneWrites applyLivePhysics(BakedGeoModel model)
    {
        EvaLivePhysicsBridge.Snapshot snapshot =
                EvaLivePhysicsBridge.sample();
        if (snapshot == null)
        {
            return BoneWrites.empty();
        }
        Set<String> positionBones = new LinkedHashSet<>();
        Set<String> rotationBones = new LinkedHashSet<>();
        Vector3f rootMeters = snapshot.rootMeters();
        model.getBone("root").ifPresent(root ->
        {
            root.setPosX(root.getInitialSnapshot().getOffsetX()
                    + rootMeters.x * MODEL_UNITS_PER_SOURCE_METRE);
            root.setPosY(root.getInitialSnapshot().getOffsetY()
                    + rootMeters.y * MODEL_UNITS_PER_SOURCE_METRE);
            root.setPosZ(root.getInitialSnapshot().getOffsetZ()
                    + rootMeters.z * MODEL_UNITS_PER_SOURCE_METRE);
            positionBones.add("root");
        });
        Quaternionf[] rotations = snapshot.rotations();
        for (int index = 0; index < EvaLivePhysicsBridge.BONES.length;
                index++)
        {
            String name = EvaLivePhysicsBridge.BONES[index];
            Quaternionf rotation = rotations[index];
            model.getBone(name).ifPresent(bone ->
            {
            Vector3f euler = motionQuaternionToAuthoredEuler(rotation);
                bone.setRotX(-euler.x);
                bone.setRotY(-euler.y);
                bone.setRotZ(euler.z);
                rotationBones.add(name);
            });
        }
        return new BoneWrites(Set.copyOf(rotationBones),
                Set.copyOf(positionBones), OWNER_PREVIEW);
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
        // Backward travel reverses the gait phase; do not twist the pelvis
        // towards 180 degrees while the chest still faces the pilot's aim.
        if (relative > Math.PI * 0.5D) relative -= Math.PI;
        if (relative < -Math.PI * 0.5D) relative += Math.PI;
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
        for(int retry=0;retry<4&&hit.getType()==HitResult.Type.BLOCK;retry++)
        {
            var pos=hit.getBlockPos();var state=entity.level().getBlockState(pos);
            var shape=state.getCollisionShape(entity.level(),pos,net.minecraft.world.phys.shapes.CollisionContext.of(entity));
            if(!com.projectseele.entity.EvaObstacleCollision.ignores(entity,state,pos,shape))break;
            start=new Vec3(predicted.x,pos.getY()-.001D,predicted.z);
            hit=entity.level().clip(new ClipContext(start,end,ClipContext.Block.COLLIDER,ClipContext.Fluid.NONE,entity));
        }
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

    public record BoneWrites(Set<String> rotationBones,
                             Set<String> positionBones,
                             String owner)
    {
        public static BoneWrites empty()
        {
            return new BoneWrites(Set.of(), Set.of(), "NONE");
        }

        public boolean isEmpty()
        {
            return this.rotationBones.isEmpty()
                    && this.positionBones.isEmpty();
        }
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
        private boolean carryLandingGait;
        private double landingGaitPhase;
        private boolean apexReached;
        private double airborneAge;
        private double fallAge;
        private boolean distanceInitialized;
        private double lastRenderX;
        private double lastRenderZ;
        private boolean liveAttackActive;
        private double liveAttackRecoveryAge;
        private String liveActionFamily = "";
        private double liveTransitionAge;
        private int lastLiveAttackStage;
        private float liveAttackRootYOffset;
        private boolean liveRootInitialized;
        private float currentLiveRootYOffset;
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
        private final Vector3f[] positions;
        private final boolean[] positionAuthored;
        private final Vector3f rootMeters = new Vector3f();
        private boolean leftContact;
        private boolean rightContact;

        private PoseBuffer(int bones)
        {
            this.rotations = new Quaternionf[bones];
            this.positions = new Vector3f[bones];
            this.positionAuthored = new boolean[bones];
            for (int index = 0; index < bones; index++)
            {
                this.rotations[index] = new Quaternionf();
                this.positions[index] = new Vector3f();
            }
        }

        private void copyFrom(PoseBuffer source)
        {
            for (int index = 0; index < this.rotations.length; index++)
            {
                this.rotations[index].set(source.rotations[index]);
                this.positions[index].set(source.positions[index]);
                this.positionAuthored[index] =
                        source.positionAuthored[index];
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
                output.positions[index].set(first.positions[index])
                        .lerp(second.positions[index], amount);
                output.positionAuthored[index] =
                        first.positionAuthored[index]
                                || second.positionAuthored[index];
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
                output.positions[index].set(first.positions[index])
                        .lerp(second.positions[index], alpha);
                output.positionAuthored[index] =
                        first.positionAuthored[index]
                                || second.positionAuthored[index];
            }
            output.rootMeters.set(first.rootMeters)
                    .lerp(second.rootMeters, alpha);
            output.leftContact = alpha < 0.5F
                    ? first.leftContact : second.leftContact;
            output.rightContact = alpha < 0.5F
                    ? first.rightContact : second.rightContact;
        }
    }

    private record Frame(Quaternionf[] rotations, Vector3f[] positions,
                         boolean[] positionAuthored, Vector3f rootMeters,
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
                    Vector3f[] positions = new Vector3f[bones.length];
                    boolean[] positionAuthored = new boolean[bones.length];
                    JsonObject positionsJson = frameJson.has(
                            "bone_position_xyz")
                            ? frameJson.getAsJsonObject("bone_position_xyz")
                            : null;
                    for (int boneIndex = 0; boneIndex < bones.length;
                            boneIndex++)
                    {
                        JsonArray q = rotationsJson.get(boneIndex)
                                .getAsJsonArray();
                        rotations[boneIndex] = new Quaternionf(
                                q.get(1).getAsFloat(), q.get(2).getAsFloat(),
                                q.get(3).getAsFloat(), q.get(0).getAsFloat())
                                .normalize();
                        positions[boneIndex] = new Vector3f();
                        if (positionsJson != null
                                && positionsJson.has(bones[boneIndex]))
                        {
                            JsonArray value = positionsJson.getAsJsonArray(
                                    bones[boneIndex]);
                            if (value.size() != 3)
                            {
                                throw new IllegalArgumentException(
                                        "bone_position_xyz must have three "
                                                + "components");
                            }
                            positions[boneIndex].set(
                                    value.get(0).getAsFloat(),
                                    value.get(1).getAsFloat(),
                                    value.get(2).getAsFloat());
                            positionAuthored[boneIndex] = true;
                        }
                    }
                    JsonArray contact = frameJson
                            .getAsJsonArray("foot_contact");
                    JsonArray rootPosition = frameJson
                            .getAsJsonArray("root_m");
                    frames[frameIndex] = new Frame(rotations, positions,
                            positionAuthored,
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
