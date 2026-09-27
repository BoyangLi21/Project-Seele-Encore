package com.projectseele.client.render;

import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.EvaUnit01Entity;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.packs.resources.ResourceManager;
import software.bernie.geckolib.cache.object.BakedGeoModel;

/**
 * Phase-B single commit point for every post-Gecko EVA bone write.
 *
 * <p>Gecko's base/arms/strike controller stack remains one explicitly named
 * upstream composite. MotionEngine preview/live owners and the two
 * renderer-era aim adapters are applied only here, in contract order.</p>
 */
public final class EvaPoseGraph
{
    private static final ResourceLocation RIG = new ResourceLocation(
            ProjectSeele.MODID, "eva/eva_rig_schema.json");
    private static final ResourceLocation AUTHORITY = new ResourceLocation(
            ProjectSeele.MODID, "eva/eva_pose_authority_contract.json");
    private static final ResourceLocation ACTIONS = new ResourceLocation(
            ProjectSeele.MODID, "eva/eva_approved_actions.json");
    private static volatile Contract contract = Contract.empty();
    private static final Map<Integer, Snapshot> LAST_COMMITS = new HashMap<>();
    private static long commitSerial;
    private static boolean firstCommitLogged;

    private EvaPoseGraph() {}

    public static void reload(ResourceManager resources)
    {
        EvaPoseTransition.clear();
        LAST_COMMITS.clear();
        commitSerial = 0L;
        firstCommitLogged = false;
        try
        {
            String rigText = read(resources, RIG);
            String authorityText = read(resources, AUTHORITY);
            String actionsText = read(resources, ACTIONS);
            JsonObject rig = JsonParser.parseString(rigText).getAsJsonObject();
            JsonObject authority = JsonParser.parseString(
                    authorityText).getAsJsonObject();
            JsonObject actions = JsonParser.parseString(
                    actionsText).getAsJsonObject();
            if (rig.get("schema").getAsInt() != 1
                    || authority.get("schema").getAsInt() != 1
                    || actions.get("schema").getAsInt() != 1)
            {
                throw new IllegalArgumentException(
                        "unsupported EVA pose-authority contract schema");
            }
            String rigVersion = rig.get("rigVersion").getAsString();
            String poseGraphVersion = authority.get(
                    "poseGraphVersion").getAsString();
            if (!rigVersion.equals(authority.get("rigVersion").getAsString())
                    || !rigVersion.equals(actions.get(
                    "rigVersion").getAsString())
                    || !poseGraphVersion.equals(actions.get(
                    "poseGraphVersion").getAsString())
                    || !"ENFORCE_POST_GECKO_SINGLE_COMMIT".equals(
                    authority.get("mode").getAsString()))
            {
                throw new IllegalArgumentException(
                        "EVA Phase-B contract versions disagree");
            }

            List<String> boneOrder = new ArrayList<>();
            Map<String, String> defaultOwners = new LinkedHashMap<>();
            for (JsonElement element : rig.getAsJsonArray("bones"))
            {
                JsonObject bone = element.getAsJsonObject();
                String name = bone.get("name").getAsString();
                if (defaultOwners.put(name,
                        bone.get("defaultOwner").getAsString()) != null)
                {
                    throw new IllegalArgumentException(
                            "duplicate canonical EVA bone " + name);
                }
                boneOrder.add(name);
            }
            if (boneOrder.size() != rig.get("boneCount").getAsInt())
            {
                throw new IllegalArgumentException(
                        "canonical EVA bone count mismatch");
            }

            Map<String, Set<String>> masks = new LinkedHashMap<>();
            for (Map.Entry<String, JsonElement> entry : authority
                    .getAsJsonObject("boneMasks").entrySet())
            {
                masks.put(entry.getKey(), stringSet(
                        entry.getValue().getAsJsonArray()));
            }
            List<String> priority = stringList(authority.getAsJsonArray(
                    "ownerPriority"));
            Map<String, String> actionStatuses = new LinkedHashMap<>();
            for (Map.Entry<String, JsonElement> entry : actions
                    .getAsJsonObject("actions").entrySet())
            {
                actionStatuses.put(entry.getKey(), entry.getValue()
                        .getAsJsonObject().get("status").getAsString());
            }
            String mode = authority.get("mode").getAsString();
            contract = new Contract(true, rigVersion, poseGraphVersion, mode,
                    sha256(rigText), sha256(authorityText),
                    sha256(actionsText), List.copyOf(boneOrder),
                    Map.copyOf(defaultOwners), immutableMasks(masks),
                    List.copyOf(priority), Map.copyOf(actionStatuses));
            ProjectSeele.LOGGER.info(
                    "EVA PoseGraph authority loaded: rig={} graph={} mode={} bones={} actionLocks={}",
                    rigVersion, poseGraphVersion, mode, boneOrder.size(),
                    actionStatuses.size());
        }
        catch (Exception exception)
        {
            contract = Contract.empty();
            ProjectSeele.LOGGER.error(
                    "EVA PoseGraph authority contracts rejected", exception);
        }
    }

    public static boolean ready()
    {
        return contract.ready();
    }

    public static Contract contract()
    {
        return contract;
    }

    public static Snapshot observe(EvaUnit01Entity entity, float partialTick)
    {
        return snapshot(entity, partialTick,
                EvaMotionEngineV2.BoneWrites.empty(),
                EvaMotionEngineV2.BoneWrites.empty(), EvaMotionEngineV2.BoneWrites.empty(), false);
    }

    /** Applies every post-Gecko writer once and records the exact final owner. */
    public static Snapshot commit(EvaUnit01Entity entity,
                                  BakedGeoModel model, float partialTick)
    {
        return commit(entity,model,partialTick,null);
    }
    public static Snapshot commit(EvaUnit01Entity entity,BakedGeoModel model,float partialTick,org.joml.Matrix4f modelToWorld)
    {
        EvaMechanicalResetR30.apply(entity);
        if (!contract.ready())
        {
            return Snapshot.empty();
        }
        EvaCervicalPivotR25.apply(entity,model,partialTick);
        EvaPoseTransition.rememberGecko(model);
        if(entity.isFirstBattleActive())
        {
            // The paired performance owns the complete skeleton. In the old
            // path, the late gameplay hand writer replaced its finger bases.
            var scene=FirstBattlePoseRenderer.apply(entity,model,partialTick);
            return finish(entity,model,partialTick,modelToWorld,scene,EvaMotionEngineV2.BoneWrites.empty(),EvaMotionEngineV2.BoneWrites.empty());
        }
        if(com.projectseele.physics.CombatBodyDynamics.active(entity))
        {
            var physical=PhysicalBodyRenderer.apply(entity,model,partialTick);
            return finish(entity,model,partialTick,modelToWorld,physical,EvaMotionEngineV2.BoneWrites.empty(),EvaMotionEngineV2.BoneWrites.empty());
        }
        if(com.projectseele.entity.EvaCombatSupportR33.ready(entity)
                &&com.projectseele.entity.EvaGameplayMotionR32.sharedBody(entity,partialTick)
                &&entity.getWeapon()==EvaUnit01Entity.WEAPON_FISTS)
        {
            // This owner produces the complete body. Do not evaluate the old
            // locomotion/impact/transition/foot-placement stack and overwrite it
            // afterwards: that also leaves those controllers' histories stale.
            com.projectseele.client.visual.CombatR31Client.normalWitness(entity,model,"before");
            com.projectseele.visual.BodyPoseLayersR40.begin(entity,partialTick);
            var body=EvaCombatPoseR31.apply(entity,model,partialTick,modelToWorld);
            var hands=EvaHandPoseR28.apply(entity,model,partialTick);
            if(com.projectseele.visual.BodyPoseLayersR40.ENABLED)
                for(String name:com.projectseele.visual.BodyPoseLayersR40.BONES)
                    model.getBone(name).ifPresent(b->com.projectseele.visual.BodyPoseLayersR40.rendered(name,EvaRigTransforms.model(b)));
            com.projectseele.visual.BodyPoseLayersR40.end();
            com.projectseele.client.visual.CombatR31Client.normalWitness(entity,model,"after");
            return finish(entity,model,partialTick,modelToWorld,body,EvaMotionEngineV2.BoneWrites.empty(),hands);
        }
        if(entity.isNervLogisticsLocked())
        {
            // The dormant clip only keys the upper body. Explicitly release
            // residual lower-body animation when the airframe enters its rack.
            for(String name:new String[]{"root","torso_lower","leg_l","leg_r","shin_l","shin_r","foot_l","foot_r","toe_l","toe_r","aim_pitch"})
                model.getBone(name).ifPresent(b->{b.setRotX(0);b.setRotY(0);b.setRotZ(0);b.setPosX(0);b.setPosY(0);b.setPosZ(0);});
        }
        EvaMotionEngineV2.BoneWrites motionWrites = EvaMotionEngineV2.apply(
                entity, model, partialTick);
        var locomotion=EvaLocomotionRig.apply(entity,model,partialTick);
        if(!locomotion.rotationBones().isEmpty())motionWrites=locomotion;

        if (!motionWrites.rotationBones().contains("aim_pitch"))
        {
            model.getBone("aim_pitch").ifPresent(aimPitch ->
            {
                float pitch = entity.getWeapon()
                        == EvaUnit01Entity.WEAPON_CANNON
                        || entity.getWeapon() == EvaUnit01Entity.WEAPON_RIFLE
                        ? (float)Math.toRadians(entity.getCannonAimPitch())
                        : 0.0F;
                // Minecraft positive X looks down; the Bedrock parent uses
                // the opposite sign.
                aimPitch.setRotX(-pitch);
                aimPitch.setRotY(aimPitch.getRotY());
                aimPitch.setRotZ(aimPitch.getRotZ());
            });
        }
        if (entity.getPilotEntity() != null && !entity.isNervLogisticsLocked()
                && !motionWrites.rotationBones().contains("head"))
        {
            model.getBone("head").ifPresent(head ->
            {
                head.setRotY((float)Math.toRadians(
                        -entity.pilotHeadYawForRender(partialTick)));
                head.setRotX((float)Math.toRadians(
                        -entity.pilotHeadPitchForRender(partialTick)));
                head.setRotZ(head.getRotZ());
            });
        }
        var impact=EvaImpactPose.apply(entity,model,partialTick);
        if(!impact.rotationBones().isEmpty())
        {Set<String> r=new LinkedHashSet<>(motionWrites.rotationBones());r.addAll(impact.rotationBones());motionWrites=new EvaMotionEngineV2.BoneWrites(Set.copyOf(r),motionWrites.positionBones(),"MOTION_ENGINE_LIVE_ACTION");}
        EvaMotionEngineV2.BoneWrites transitions = EvaPoseTransition.apply(
                entity, model, partialTick);
        var jointWrites=entity.getMotionLabPhysicsPreview()==0&&!entity.isFirstBattleActive()?EvaArmArticulation.apply(model):EvaMotionEngineV2.BoneWrites.empty();
        var flight=UNFlightPoseR29.apply(entity,model,partialTick,modelToWorld);
        var firearm=EvaRifleContactRig.apply(entity,model,partialTick,modelToWorld);
        var terrain=EvaFootPlacement.apply(entity,model,partialTick,modelToWorld);
        var optics=EvaUNLaserPose.apply(entity,model,modelToWorld);
        var dorsal=EvaDorsalPose.apply(entity,model);
        var shoulders=EvaShoulderClearanceR25.apply(entity,model,modelToWorld,partialTick);
        var fingers=EvaHandPoseR28.apply(entity,model,partialTick);
        Set<String> jointR=new LinkedHashSet<>(jointWrites.rotationBones());jointR.addAll(firearm.rotationBones());
        jointR.addAll(flight.rotationBones());
        Set<String> jointP=new LinkedHashSet<>(jointWrites.positionBones());jointP.addAll(firearm.positionBones());
        jointP.addAll(flight.positionBones());
        jointR.addAll(terrain.rotationBones());jointP.addAll(terrain.positionBones());
        jointR.addAll(optics.rotationBones());jointR.addAll(dorsal.rotationBones());
        jointR.addAll(shoulders.rotationBones());
        jointR.addAll(fingers.rotationBones());jointP.addAll(fingers.positionBones());
        firearm=new EvaMotionEngineV2.BoneWrites(Set.copyOf(jointR),Set.copyOf(jointP),"MOTION_ENGINE_LIVE_ACTION");
        if(!firearm.rotationBones().isEmpty())
        {
            Set<String> r=new LinkedHashSet<>(motionWrites.rotationBones());r.addAll(firearm.rotationBones());
            Set<String> p=new LinkedHashSet<>(motionWrites.positionBones());p.addAll(firearm.positionBones());
            motionWrites=new EvaMotionEngineV2.BoneWrites(Set.copyOf(r),Set.copyOf(p),"MOTION_ENGINE_LIVE_ACTION");
        }
        com.projectseele.client.visual.CombatR31Client.normalWitness(entity,model,"before");
        var combat=EvaCombatPoseR31.apply(entity,model,partialTick,modelToWorld);
        com.projectseele.client.visual.CombatR31Client.normalWitness(entity,model,"after");
        if(!combat.rotationBones().isEmpty())motionWrites=combat;
        var shutdown=EvaShutdownPoseR30.apply(entity,model,partialTick);
        if(!shutdown.rotationBones().isEmpty())motionWrites=shutdown;
        var airTransport=EvaAirTransportPoseR31.apply(entity,model,partialTick);
        if(!airTransport.rotationBones().isEmpty())motionWrites=airTransport;
        if(com.projectseele.entity.EvaBayRepairR33.active(entity)
                &&com.projectseele.entity.EvaDorsalMechanism.bow(entity)<=.001F
                &&com.projectseele.entity.EvaDorsalMechanism.open(entity)<=.001F)
        {
            float phase=com.projectseele.entity.EvaBayRepairR33.progress(entity,partialTick);
            float held=com.projectseele.entity.EvaDorsalMechanism.smooth(Math.min(phase/.05F,(1-phase)/.05F));
            model.getBone("head").ifPresent(b->{b.setRotX(b.getRotX()*(1-held));b.setRotY(b.getRotY()*(1-held));b.setRotZ(b.getRotZ()*(1-held));});
            Set<String> heldBones=new LinkedHashSet<>(motionWrites.rotationBones());heldBones.add("head");
            motionWrites=new EvaMotionEngineV2.BoneWrites(Set.copyOf(heldBones),motionWrites.positionBones(),"MOTION_ENGINE_LIVE_ACTION");
        }
        return finish(entity,model,partialTick,modelToWorld,motionWrites,transitions,firearm);
    }

    private static Snapshot finish(EvaUnit01Entity entity,BakedGeoModel model,float partialTick,org.joml.Matrix4f modelToWorld,
                                   EvaMotionEngineV2.BoneWrites motionWrites,EvaMotionEngineV2.BoneWrites transitions,EvaMotionEngineV2.BoneWrites firearm)
    {
        var mouth=EvaMouthR37.apply(entity,model,partialTick);
        if(!mouth.rotationBones().isEmpty())
        {var names=new java.util.HashSet<>(motionWrites.rotationBones());names.addAll(mouth.rotationBones());var positions=new java.util.HashSet<>(motionWrites.positionBones());positions.addAll(mouth.positionBones());motionWrites=new EvaMotionEngineV2.BoneWrites(Set.copyOf(names),Set.copyOf(positions),"MOTION_ENGINE_LIVE_ACTION");}
        com.projectseele.client.visual.MechanicsR31Client.captureBones(entity,model,partialTick,modelToWorld);
        EvaPowerAttachmentR25.capture(entity,model,modelToWorld);
        JointAuditR38.capture(entity,model,partialTick);
        EvaPoseTransition.recordFinal(entity,model);
        Snapshot committed = snapshot(
                entity, partialTick, motionWrites, transitions, firearm, true);
        if (LAST_COMMITS.size() > 48)
        {
            LAST_COMMITS.clear();
        }
        LAST_COMMITS.put(entity.getId(), committed);
        if (!firstCommitLogged)
        {
            firstCommitLogged = true;
            ProjectSeele.LOGGER.info(
                    "EVA PoseGraph first enforced commit: entity={} serial={} "
                            + "motionRotationBones={} motionPositionBones={} pilotAim={}",
                    entity.getId(), committed.commitSerial(),
                    motionWrites.rotationBones().size(),
                    motionWrites.positionBones().size(),
                    entity.getPilotEntity() != null);
        }
        return committed;
    }

    public static Snapshot committedSnapshot(EvaUnit01Entity entity,
                                             Snapshot fallback)
    {
        return LAST_COMMITS.getOrDefault(entity.getId(), fallback);
    }

    private static Snapshot snapshot(EvaUnit01Entity entity,
                                     float partialTick,
                                     EvaMotionEngineV2.BoneWrites motionWrites,
                                     EvaMotionEngineV2.BoneWrites transitions,
                                     EvaMotionEngineV2.BoneWrites firearm,
                                     boolean committed)
    {
        Contract current = contract;
        if (!current.ready())
        {
            return Snapshot.empty();
        }
        String actionToken = actionToken(entity, partialTick);
        float phase = phase(entity, partialTick);
        String motionOwner = motionWrites.owner();
        boolean weaponAimActive = !motionWrites.rotationBones()
                .contains("aim_pitch");
        boolean pilotAimActive = entity.getPilotEntity() != null
                && !motionWrites.rotationBones().contains("head");
        LinkedHashSet<String> activeLayers = new LinkedHashSet<>();
        activeLayers.add("GECKO_COMPOSITE");
        if (!motionWrites.isEmpty())
        {
            activeLayers.add(motionOwner);
        }
        if (weaponAimActive)
        {
            activeLayers.add("POSE_GRAPH_WEAPON_AIM");
        }
        if (pilotAimActive)
        {
            activeLayers.add("POSE_GRAPH_PILOT_AIM");
        }

        Map<String, String> rotationOwners = new LinkedHashMap<>();
        Map<String, String> positionOwners = new LinkedHashMap<>();
        Map<String, String> scaleOwners = new LinkedHashMap<>();
        for (String bone : current.boneOrder())
        {
            rotationOwners.put(bone, "GECKO_COMPOSITE");
            positionOwners.put(bone, "GECKO_COMPOSITE");
            scaleOwners.put(bone, "GECKO_COMPOSITE");
        }
        for (String bone : motionWrites.rotationBones())
        {
            if (rotationOwners.containsKey(bone))
            {
                rotationOwners.put(bone, motionOwner);
            }
        }
        for (String bone : motionWrites.positionBones())
        {
            if (positionOwners.containsKey(bone))
            {
                positionOwners.put(bone, motionOwner);
            }
        }
        if (weaponAimActive && rotationOwners.containsKey("aim_pitch"))
        {
            rotationOwners.put("aim_pitch", "POSE_GRAPH_WEAPON_AIM");
        }
        if (pilotAimActive
                && rotationOwners.containsKey("head"))
        {
            rotationOwners.put("head", "POSE_GRAPH_PILOT_AIM");
        }
        if (!transitions.isEmpty())
        {
            activeLayers.add(EvaPoseTransition.OWNER);
            transitions.rotationBones().forEach(bone ->
                    rotationOwners.put(bone, EvaPoseTransition.OWNER));
            transitions.positionBones().forEach(bone ->
                    positionOwners.put(bone, EvaPoseTransition.OWNER));
            transitions.rotationBones().forEach(bone ->
                    scaleOwners.put(bone, EvaPoseTransition.OWNER));
        }

        // Firearm contact is solved after transition blending, including weapon scale.
        if (!firearm.isEmpty())
        {
            for (String bone : firearm.rotationBones())
                rotationOwners.put(bone, motionOwner);
            for (String bone : firearm.positionBones())
            {
                positionOwners.put(bone, motionOwner);
                scaleOwners.put(bone, motionOwner);
            }
        }

        List<String> upstreamSources = upstreamSources(entity, partialTick);
        Map<String, List<String>> upstreamOverlaps = upstreamOverlaps(
                entity, partialTick, current);
        int preview = entity.getMotionLabPhysicsPreview();
        boolean eligible = preview == 0
                && entity.getVisualPose() == EvaUnit01Entity.VISUAL_NORMAL;
        long serial = committed ? ++commitSerial : 0L;
        return new Snapshot(actionToken, phase,
                List.copyOf(activeLayers), List.copyOf(upstreamSources),
                Map.copyOf(rotationOwners), Map.copyOf(positionOwners),
                Map.copyOf(scaleOwners), Map.of(),
                Map.copyOf(upstreamOverlaps),
                eligible, actionStatus(actionToken,
                current.actionStatuses()), committed, serial);
    }

    private static List<String> upstreamSources(EvaUnit01Entity entity,
                                                float partialTick)
    {
        List<String> result = new ArrayList<>();
        result.add("GECKO_CONTROLLER_BASE");
        if (armsControllerActive(entity))
        {
            result.add("GECKO_CONTROLLER_ARMS");
        }
        if (strikeActive(entity, partialTick))
        {
            result.add("GECKO_CONTROLLER_STRIKE");
        }
        return result;
    }

    private static Map<String, List<String>> upstreamOverlaps(
            EvaUnit01Entity entity, float partialTick, Contract current)
    {
        Map<String, LinkedHashSet<String>> candidates = new LinkedHashMap<>();
        for (String bone : current.boneOrder())
        {
            candidates.put(bone, new LinkedHashSet<>(Set.of(
                    "GECKO_CONTROLLER_BASE")));
        }
        if (armsControllerActive(entity))
        {
            addCandidate(candidates, current.masks(), "UPPER_BODY",
                    "GECKO_CONTROLLER_ARMS");
            addCandidate(candidates, current.masks(), "GRIP",
                    "GECKO_CONTROLLER_ARMS");
            addCandidate(candidates, current.masks(), "WEAPON_SOCKET",
                    "GECKO_CONTROLLER_ARMS");
        }
        if (strikeActive(entity, partialTick))
        {
            addCandidate(candidates, current.masks(), "LOWER_BODY",
                    "GECKO_CONTROLLER_STRIKE");
            addCandidate(candidates, current.masks(), "UPPER_BODY",
                    "GECKO_CONTROLLER_STRIKE");
            addCandidate(candidates, current.masks(), "GRIP",
                    "GECKO_CONTROLLER_STRIKE");
            addCandidate(candidates, current.masks(), "WEAPON_SOCKET",
                    "GECKO_CONTROLLER_STRIKE");
        }
        Map<String, List<String>> overlaps = new LinkedHashMap<>();
        candidates.forEach((bone, values) ->
        {
            if (values.size() > 1)
            {
                overlaps.put(bone, List.copyOf(values));
            }
        });
        return overlaps;
    }

    private static boolean strikeActive(EvaUnit01Entity entity,
                                        float partialTick)
    {
        return !entity.isHeavyMotionActive() && (entity.getCockpitAttackAnim(partialTick) > 0.0F
                || entity.getCockpitSmashAnim(partialTick) > 0.0F);
    }

    private static boolean armsControllerActive(EvaUnit01Entity entity)
    {
        if (entity.isCrucified() || entity.isBerserk()
                || entity.isNervLogisticsLocked() || !entity.isPoweredOn())
        {
            return false;
        }
        int weapon = entity.getWeapon();
        int visual = entity.getVisualPose();
        if (entity.isShieldBraced()) return true;
        if (weapon == EvaUnit01Entity.WEAPON_N2)
            return !entity.isPilotProne()
                    && visual == EvaUnit01Entity.VISUAL_NORMAL;
        if (weapon == EvaUnit01Entity.WEAPON_KNIFE
                || weapon == EvaUnit01Entity.WEAPON_LANCE)
            return visual == EvaUnit01Entity.VISUAL_NORMAL;
        if (weapon == EvaUnit01Entity.WEAPON_CANNON
                || weapon == EvaUnit01Entity.WEAPON_RIFLE)
            return entity.isPilotProne()
                    || visual == EvaUnit01Entity.VISUAL_PRONE_CANNON
                    || visual == EvaUnit01Entity.VISUAL_NORMAL;
        return false;
    }

    private static String actionToken(EvaUnit01Entity entity,
                                      float partialTick)
    {
        if (entity.getMotionLabPhysicsPreview() > 0)
        {
            return "motion_engine_preview_"
                    + entity.getMotionLabPhysicsPreview();
        }
        if (entity.isCrucified()) return "crucified";
        if (entity.isBerserk()) return "berserk";
        if (entity.getActivationTicks() > 0) return "activation";
        if (entity.getOrdinaryAttackStage() >= 0)
            return "unarmed_attack";
        if (entity.isKickMotionActive(partialTick))
            return "kick_attack";
        int knife = entity.getKnifeMotionType(partialTick);
        if (knife >= 0)
            return knife == 1 ? "knife_attack_reverse"
                    : "knife_attack_forward";
        if (entity.getCockpitSmashAnim(partialTick) > 0.0F)
            return entity.getWeapon() == EvaUnit01Entity.WEAPON_KNIFE
                    ? "progressive_knife" : "unarmed_smash";
        if (entity.getCockpitAttackAnim(partialTick) > 0.0F)
            return entity.getWeapon() == EvaUnit01Entity.WEAPON_KNIFE
                    ? "progressive_knife" : "unarmed_attack";
        if (entity.isPilotProne()) return "prone_crawl";
        if (entity.isPilotCrouching()) return "crouch";
        if (entity.isVisuallyAirborneForRender()) return "jump_landing";
        if (entity.isVisuallyMovingForRender())
            return entity.isPilotSprinting() ? "run" : "walk";
        return "idle";
    }

    private static float phase(EvaUnit01Entity entity, float partialTick)
    {
        if (entity.getOrdinaryAttackStage() >= 0)
        {
            return entity.getOrdinaryAttackProgress(partialTick);
        }
        if (entity.isKickMotionActive(partialTick))
        {
            return entity.getKickAttackProgress(partialTick);
        }
        int knife = entity.getKnifeMotionType(partialTick);
        if (knife >= 0)
        {
            return entity.getKnifeMotionProgress(knife, partialTick);
        }
        return Math.max(entity.getCockpitAttackAnim(partialTick),
                entity.getCockpitSmashAnim(partialTick));
    }

    private static String actionStatus(String action,
                                       Map<String, String> statuses)
    {
        return statuses.getOrDefault(action, "UNLOCKED_RUNTIME_STATE");
    }

    private static void addCandidate(
            Map<String, LinkedHashSet<String>> candidates,
            Map<String, Set<String>> masks, String mask, String owner)
    {
        for (String bone : masks.getOrDefault(mask, Set.of()))
        {
            addOwnerCandidate(candidates, bone, owner);
        }
    }

    private static void addOwnerCandidate(
            Map<String, LinkedHashSet<String>> candidates,
            String bone, String owner)
    {
        LinkedHashSet<String> boneCandidates = candidates.get(bone);
        if (boneCandidates != null)
        {
            boneCandidates.add(owner);
        }
    }

    private static String read(ResourceManager resources,
                               ResourceLocation location) throws Exception
    {
        try (InputStream stream = resources.getResource(location)
                .orElseThrow(() -> new IllegalStateException(
                        "missing EVA pose-authority contract " + location)).open())
        {
            return new String(stream.readAllBytes(), StandardCharsets.UTF_8);
        }
    }

    private static String sha256(String text) throws Exception
    {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        return HexFormat.of().formatHex(digest.digest(
                text.getBytes(StandardCharsets.UTF_8)));
    }

    private static List<String> stringList(JsonArray array)
    {
        List<String> result = new ArrayList<>();
        array.forEach(value -> result.add(value.getAsString()));
        return result;
    }

    private static Set<String> stringSet(JsonArray array)
    {
        return Set.copyOf(stringList(array));
    }

    private static Map<String, Set<String>> immutableMasks(
            Map<String, Set<String>> source)
    {
        Map<String, Set<String>> result = new HashMap<>();
        source.forEach((name, mask) -> result.put(name, Set.copyOf(mask)));
        return Collections.unmodifiableMap(result);
    }

    public record Contract(boolean ready, String rigVersion,
                           String poseGraphVersion, String mode,
                           String rigSha256,
                           String authoritySha256, String actionsSha256,
                           List<String> boneOrder,
                           Map<String, String> defaultOwners,
                           Map<String, Set<String>> masks,
                           List<String> priority,
                           Map<String, String> actionStatuses)
    {
        private static Contract empty()
        {
            return new Contract(false, "missing", "missing", "missing",
                    "missing", "missing", "missing", List.of(), Map.of(),
                    Map.of(), List.of(), Map.of());
        }
    }

    public record Snapshot(String actionToken, float phaseProgress,
                           List<String> activeLayers,
                           List<String> upstreamSources,
                           Map<String, String> owners,
                           Map<String, String> positionOwners,
                           Map<String, String> scaleOwners,
                           Map<String, List<String>> conflicts,
                           Map<String, List<String>> upstreamOverlaps,
                           boolean eligibleForHumanReview,
                           String actionLockStatus,
                           boolean committed, long commitSerial)
    {
        private static Snapshot empty()
        {
            return new Snapshot("pose_graph_unavailable", 0.0F, List.of(),
                    List.of(), Map.of(), Map.of(), Map.of(), Map.of(),
                    Map.of(), false, "CONTRACT_REJECTED", false, 0L);
        }
    }
}
