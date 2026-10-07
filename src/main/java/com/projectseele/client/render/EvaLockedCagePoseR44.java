package com.projectseele.client.render;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.projectseele.entity.EvaUnit01Entity;
import net.minecraft.client.Minecraft;
import net.minecraft.world.level.storage.LevelResource;
import software.bernie.geckolib.cache.object.BakedGeoModel;
import software.bernie.geckolib.cache.object.GeoBone;
import java.nio.file.Files;
import java.nio.file.StandardOpenOption;
import java.util.HashMap;
import java.util.LinkedHashSet;
import java.util.Map;
import java.util.Set;

/** A restrained airframe has one structural bind pose; the dorsal hinge remains mechanical. */
final class EvaLockedCagePoseR44
{
    private static final Map<Integer, Integer> LAST_TICK = new HashMap<>();
    private static final Map<Integer, Integer> SAMPLES = new HashMap<>();

    static boolean applies(EvaUnit01Entity entity)
    {
        return !entity.isExperimentalUnit() && entity.isNervLogisticsLocked() && !entity.isFirstBattleActive()
                && !entity.isCrucified() && !com.projectseele.physics.CombatBodyDynamics.active(entity)
                && !com.projectseele.entity.EvaShutdownR30.displayed(entity)
                && !com.projectseele.entity.EvaAirTransportR31.active(entity);
    }

    static EvaMotionEngineV2.BoneWrites apply(EvaUnit01Entity entity, BakedGeoModel model)
    {
        Set<String> bones = new LinkedHashSet<>();
        for (GeoBone root : model.topLevelBones()) restore(root, bones);
        // Socket opening/head bow is an actual equipment state, not an idle
        // body overlay. Its torso release starts from this fixed bind pose.
        EvaDorsalPose.apply(entity, model);
        return new EvaMotionEngineV2.BoneWrites(Set.copyOf(bones), Set.copyOf(bones), "MOTION_ENGINE_LIVE_ACTION");
    }

    private static void restore(GeoBone bone, Set<String> bones)
    {
        var bind = bone.getInitialSnapshot();
        bone.setRotX(bind.getRotX()); bone.setRotY(bind.getRotY()); bone.setRotZ(bind.getRotZ());
        bone.setPosX(bind.getOffsetX()); bone.setPosY(bind.getOffsetY()); bone.setPosZ(bind.getOffsetZ());
        bone.setScaleX(bind.getScaleX()); bone.setScaleY(bind.getScaleY()); bone.setScaleZ(bind.getScaleZ());
        bones.add(bone.getName());
        for (GeoBone child : bone.getChildBones()) restore(child, bones);
    }

    static void witness(EvaUnit01Entity entity, BakedGeoModel model, String stage)
    {
        if (!Boolean.getBoolean("projectseele.r44HangarMeshWitness") || entity.isExperimentalUnit()) return;
        var mc = Minecraft.getInstance();
        if (mc.getSingleplayerServer() == null || ShaderShadowPassR44.active()) return;
        var world = mc.getSingleplayerServer().getWorldPath(LevelResource.ROOT).normalize();
        if (!world.getFileName().toString().equals(com.projectseele.visual.NativeReviewWorldsR45.expectedName())) return;
        int id = entity.getId();
        if (stage.equals("after_gecko"))
        {
            int previous = LAST_TICK.getOrDefault(id, Integer.MIN_VALUE);
            if (previous != Integer.MIN_VALUE && entity.tickCount - previous < 20 || SAMPLES.getOrDefault(id, 0) >= 12) return;
            LAST_TICK.put(id, entity.tickCount); SAMPLES.merge(id, 1, Integer::sum);
        }
        else if (LAST_TICK.getOrDefault(id, Integer.MIN_VALUE) != entity.tickCount) return;
        JsonObject row = new JsonObject();
        row.addProperty("entity_uuid", entity.getUUID().toString()); row.addProperty("variant", entity.getUnitVariant());
        row.addProperty("tick", entity.tickCount); row.addProperty("stage", stage); row.addProperty("locked", entity.isNervLogisticsLocked());
        row.addProperty("scope", "Actual bone model matrices at the post-Gecko/final cage boundary; submitted mesh is recorded separately by HangarMeshWitnessR44");
        JsonArray values = new JsonArray();
        for (String name : new String[]{"root","torso_lower","torso_upper","aim_pitch","clavicle_l","clavicle_r","arm_l","arm_r","forearm_l","forearm_r"})
        {
            var bone = model.getBone(name).orElse(null); if (bone == null) continue;
            JsonObject value = new JsonObject(); value.addProperty("bone", name);
            JsonArray rotation = new JsonArray(); rotation.add(bone.getRotX()); rotation.add(bone.getRotY()); rotation.add(bone.getRotZ()); value.add("actual_local_rotation_radians_xyz", rotation);
            JsonArray matrix = new JsonArray(); for (float number : EvaRigTransforms.model(bone).get(new float[16])) matrix.add(number);
            value.add("actual_model_matrix_column_major", matrix); values.add(value);
        }
        row.add("bones", values);
        try { Files.writeString(world.resolve("r44_locked_cage_pose.jsonl"), row + "\n", StandardOpenOption.CREATE, StandardOpenOption.APPEND); }
        catch (Exception error) { throw new IllegalStateException("Could not save the actual locked cage pose", error); }
    }

    private EvaLockedCagePoseR44() {}
}
