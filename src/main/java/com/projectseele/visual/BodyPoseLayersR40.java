package com.projectseele.visual;

import com.google.gson.*;
import com.projectseele.entity.*;
import java.nio.file.*;
import org.joml.Matrix4f;

/** Opt-in, render-scoped evidence; never changes a pose or enables a gameplay path. */
public final class BodyPoseLayersR40
{
    public static final boolean ENABLED = Boolean.getBoolean("projectseele.r40PoseLayers");
    public static final String[] BONES = {"root", "torso_lower", "torso_upper", "head",
            "leg_l", "leg_r", "shin_l", "shin_r", "ankle_l", "ankle_r", "foot_l", "foot_r",
            "arm_l", "arm_r", "forearm_l", "forearm_r", "hand_l", "hand_r",
            "finger_index_l", "finger_index_r", "finger_middle_l", "finger_middle_r", "finger_thumb_l", "finger_thumb_r"};
    private static final JsonArray ROWS = new JsonArray();
    private static final ThreadLocal<JsonObject> CURRENT = new ThreadLocal<>();
    private static long lastTick = -1;
    private static final com.projectseele.util.WeakIdentityMap<EvaUnit01Entity,Long> NETWORK_TICKS=new com.projectseele.util.WeakIdentityMap<>();

    public static void begin(EvaUnit01Entity actor, float partial)
    {
        CURRENT.remove();
        boolean network=com.projectseele.client.visual.RuntimeR44ClientProbe.poseLayerActor(actor);
        if (!ENABLED || !(network||CombatR31Review.ENABLED&&actor.getId()==CombatR31Review.evaId)
                || !actor.level().isClientSide || ROWS.size() >= 1200) return;
        long tick = actor.level().getGameTime();
        if(network)
        {
            Long previous=NETWORK_TICKS.get(actor);if(previous!=null&&tick-previous<Math.max(1,Integer.getInteger("projectseele.r44PoseLayerTickGap",20)))return;
            NETWORK_TICKS.put(actor,tick);
        }
        if (lastTick == tick) return;
        lastTick = tick;
        JsonObject current = new JsonObject();
        CURRENT.set(current);
        current.addProperty("tick", tick);
        current.addProperty("entity_uuid",actor.getUUID().toString());current.addProperty("variant",EvaGameplayMotionR32.variant(actor));
        current.addProperty("stance",actor.rifleStanceLevel(partial));current.addProperty("gait",actor.rifleGaitPhase(partial));
        current.addProperty("world_y",actor.getPosition(partial).y);
        current.addProperty("entity_on_ground",actor.onGround());
        current.addProperty("entity_live_action",actor.hasLiveActionForRender(partial));
        current.addProperty("entity_visually_airborne",actor.isVisuallyAirborneForRender());
        current.addProperty("review_tick", CombatR31Review.stageTicks);
        current.addProperty("stage", CombatR31Review.stageName);
        current.addProperty("partial", partial);
        current.addProperty("ordinary", actor.getOrdinaryAttackStage());
        current.addProperty("ordinary_phase", actor.getOrdinaryAttackProgress(partial));
        current.addProperty("heavy_phase", actor.heavyMotionProgress(partial));
        current.add("layers", new JsonObject());
        ROWS.add(current);
    }

    public static void capture(String stage, EvaBodyPose.Sample pose)
    {
        if (!ENABLED) return;
        JsonObject current = CURRENT.get();
        if (current == null) return;
        JsonObject bones = new JsonObject();
        for (String name : BONES)
        {
            if (!pose.rig.containsKey(name)) continue;
            JsonObject bone = new JsonObject();
            bone.add("matrix", matrix(pose.matrix(name)));
            var q = pose.rotations.get(name);
            bone.add("quaternion_xyzw", floats(q.x, q.y, q.z, q.w));
            var p = pose.positions.get(name);
            bone.add("position_blocks", floats(p.x, p.y, p.z));
            bones.add(name, bone);
        }
        current.getAsJsonObject("layers").add(stage, bones);
    }

    public static void metadata(String key, JsonElement value)
    {
        JsonObject current=CURRENT.get();
        if(current!=null)current.add(key,value.deepCopy());
    }
    public static void appendMetadata(String key, JsonElement value)
    {
        JsonObject current=CURRENT.get();if(current==null)return;
        if(!current.has(key))current.add(key,new JsonArray());
        current.getAsJsonArray(key).add(value.deepCopy());
    }

    public static void rendered(String name, Matrix4f transform)
    {
        JsonObject current = CURRENT.get();
        if (current == null) return;
        if (!current.has("rendered")) current.add("rendered", new JsonObject());
        current.getAsJsonObject("rendered").add(name, matrix(transform));
    }

    private static JsonArray floats(float... values)
    {
        var out = new JsonArray();
        for (float value : values) out.add(value);
        return out;
    }

    private static JsonArray matrix(Matrix4f value) { return floats(value.get(new float[16])); }
    public static void end() { CURRENT.remove(); }
    public static void write(Path folder) throws java.io.IOException
    {
        if (!ENABLED) return;
        var result = new JsonObject();
        result.addProperty("units", "model blocks before RENDER_SCALE=5; matrices column-major");
        result.addProperty("kind", "same-render source/terrain/reaction/ground/foot-constraint/final-Gecko matrices");
        result.add("samples", ROWS);
        Files.writeString(folder.resolve("body_layers_r40.json"), new Gson().toJson(result));
    }
    private BodyPoseLayersR40() {}
}
