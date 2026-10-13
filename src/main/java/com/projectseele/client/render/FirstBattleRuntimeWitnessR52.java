package com.projectseele.client.render;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.EvaDorsalMechanism;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.FirstBattleClip;
import com.projectseele.entity.FirstBattleSignals;
import net.minecraft.client.Minecraft;
import net.minecraft.world.entity.Entity;
import org.joml.Matrix4f;
import org.joml.Vector3f;
import software.bernie.geckolib.cache.object.BakedGeoModel;
import software.bernie.geckolib.cache.object.GeoBone;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.HashMap;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/** Small opt-in receipt of one native paired performance, never a mesh dump. */
public final class FirstBattleRuntimeWitnessR52
{
    public static final boolean ENABLED = Boolean.getBoolean("projectseele.firstBattleRuntimeWitnessR52");
    private static final Set<String> BONES = Set.of("root", "torso_lower", "torso_upper", "head",
            "arm_l", "arm_r", "forearm_l", "forearm_r", "leg_l", "leg_r", "shin_l", "shin_r", "r37_jaw",
            "hand_l", "hand_r", "foot_l", "foot_r", "r45_hand_l_index_1", "r45_hand_r_index_1", "r45_hand_l_thumb_1", "r45_hand_r_thumb_1");
    private static final Map<UUID, State> ACTORS = new HashMap<>();
    private static UUID sceneEva;
    private static long firstFrame;
    private static int rows;
    private static boolean failed, started;
    private static final class State
    {
        int lastBucket = -1;
        long frame;
        JsonObject row;
    }
    private FirstBattleRuntimeWitnessR52() {}

    public static void writer(Entity entity, BakedGeoModel model, float partial,
                              FirstBattleClip.BonePose desired)
    {
        if (!ENABLED || failed || rows >= 96
                || !(entity instanceof FirstBattleSignals.Actor actor)
                || !actor.firstBattleSignals().active(entity)) return;
        Entity hero = actor.isFirstBattleEva() ? entity
                : entity.level().getEntity(actor.firstBattleSignals().partner(entity));
        if (hero == null) return;
        if (sceneEva == null) sceneEva = hero.getUUID();
        if (!sceneEva.equals(hero.getUUID())) return;
        int age = actor.firstBattleSignals().age(entity);
        if (age < 0 || age > FirstBattleClip.DURATION_TICKS) return;
        int bucket = age / 10;
        if (!ACTORS.containsKey(entity.getUUID()) && ACTORS.size() >= 2) return;
        State state = ACTORS.computeIfAbsent(entity.getUUID(), ignored -> new State());
        if (state.lastBucket >= bucket) return;
        if (state.row != null && state.frame == FirstBattleSignals.clientFrameTime()) return;
        state.frame = FirstBattleSignals.clientFrameTime();
        if (firstFrame == 0) firstFrame = state.frame;
        float seconds = actor.firstBattleSignals().time(entity, partial);
        JsonObject row = new JsonObject();
        row.addProperty("actor", actor.isFirstBattleEva() ? "eva" : "sachiel");
        row.addProperty("entity_id", entity.getId());
        row.addProperty("uuid", entity.getUUID().toString());
        row.addProperty("scene_eva_uuid", sceneEva.toString());
        row.addProperty("age_bucket_half_second", bucket);
        row.addProperty("synced_age_ticks", age);
        row.addProperty("scene_seconds", seconds);
        row.addProperty("reference_seconds", FirstBattleClip.referenceSeconds(seconds));
        row.addProperty("wall_seconds", (state.frame - firstFrame) / 1.0e9);
        row.addProperty("world_tick", entity.level().getGameTime());
        row.addProperty("frame_nanos", state.frame);
        row.addProperty("partial", partial);
        row.addProperty("writer_shadow_pass", ShaderShadowPassR44.active());
        row.addProperty("fps", Minecraft.getInstance().getFps());
        row.addProperty("clip_sha256", FirstBattleClip.fingerprint());
        row.add("entity_position", vector((float)entity.getX(), (float)entity.getY(), (float)entity.getZ()));
        if (entity instanceof EvaUnit01Entity eva)
        {
            row.addProperty("powered", eva.isPoweredOn());
            row.addProperty("berserk", eva.isBerserk());
            row.addProperty("eyes_enabled", EvaDorsalMechanism.eyesEnabled(eva));
            row.addProperty("eye_surface", EvaDorsalMechanism.eyeSurface(eva));
            row.addProperty("anatomical_hand_authority",FirstBattleClip.ownsAnatomicalHandsR52(eva.getUnitVariant()));
            row.addProperty("pilot_control_locked",eva.pilotControlLockedForReviewR52());
            row.addProperty("jaw_owner","EvaMouthR37; first-battle hand authority does not own jaw");
        }
        JsonObject authored = new JsonObject();
        for (int i = 0; i < desired.names().length; i++)
        {
            String name = desired.names()[i];
            if (!BONES.contains(name)) continue;
            Vector3f euler = EvaMotionEngineV2.motionQuaternionToAuthoredEuler(desired.rotations()[i]);
            JsonObject channel = new JsonObject();
            channel.add("expected_rot_xyz_radians", vector(-euler.x, -euler.y, euler.z));
            Vector3f p = desired.positions()[i];
            channel.add("clip_pos_xyz", vector(p.x, p.y, p.z));
            authored.add(name, channel);
        }
        row.add("clip_desired", authored);
        row.add("writer_bones", bones(model));
        row.add("submitted_parts", new JsonObject());
        state.row = row;
    }

    public static void finalWriter(Entity entity, BakedGeoModel model, String owner)
    {
        State state = current(entity);
        if (state == null) return;
        state.row.addProperty("final_writer", owner);
        state.row.add("final_bones", bones(model));
    }

    static boolean wants(Entity entity, String bone)
    { return BONES.contains(bone) && current(entity) != null; }

    static void localSubmission(Entity entity, GeoBone bone, Matrix4f submitted, Matrix4f world,
                                long requestedRevision, boolean skinReused, boolean gpu,
                                float[] values, int stride, float px, float py, float pz)
    {
        State state = current(entity);
        if (state == null || !BONES.contains(bone.getName())) return;
        JsonObject part = new JsonObject();
        part.addProperty("path", gpu ? "local-mesh-gpu" : "local-mesh-vertex-consumer");
        part.addProperty("pose_revision", requestedRevision);
        part.addProperty("skin_cache_reused", skinReused);
        part.add("submitted_bone_matrix", matrix(submitted));
        part.add("submitted_world_matrix", matrix(world));
        if (gpu && RigidCapsuleGpu.lastWitnessSubmission != null)
        {
            var receipt = RigidCapsuleGpu.lastWitnessSubmission;
            part.addProperty("gpu_buffer_revision", receipt.revision());
            part.addProperty("gpu_uploaded", receipt.uploaded());
            part.addProperty("gpu_shader", receipt.shader());
            part.add("gpu_model_view_matrix", matrix(receipt.modelView()));
        }
        // Three fixed submitted points expose stale scratch buffers without exporting geometry.
        JsonArray points = new JsonArray();
        int count = values.length / stride;
        for (int vertex : new int[]{0, count / 2, Math.max(0, count - 1)})
        {
            int at = vertex * stride;
            if (at + 2 >= values.length) continue;
            Vector3f point = new Vector3f(-(values[at] + px) / 16, (values[at+1] + py) / 16, (values[at+2] + pz) / 16);
            world.transformPosition(point);
            points.add(vector(point.x, point.y, point.z));
        }
        part.add("three_submitted_world_points", points);
        if(bone.getName().startsWith("foot_")||bone.getName().startsWith("shin_"))
        {
            float min=Float.POSITIVE_INFINITY,max=Float.NEGATIVE_INFINITY;Vector3f lowest=new Vector3f();
            for(int at=0;at+2<values.length;at+=stride)
            {
                Vector3f point=new Vector3f(-(values[at]+px)/16,(values[at+1]+py)/16,(values[at+2]+pz)/16);world.transformPosition(point);
                if(point.y<min){min=point.y;lowest.set(point);}max=Math.max(max,point.y);
            }
            part.addProperty("actual_submitted_min_world_y",min);part.addProperty("actual_submitted_max_world_y",max);part.add("actual_lowest_world_point",vector(lowest.x,lowest.y,lowest.z));
            var near=new net.minecraft.world.phys.Vec3(lowest.x,lowest.y,lowest.z);
            var hit=entity.level().clip(new net.minecraft.world.level.ClipContext(near.add(0,.35,0),near.add(0,-2,0),net.minecraft.world.level.ClipContext.Block.COLLIDER,net.minecraft.world.level.ClipContext.Fluid.NONE,entity));
            part.addProperty("ground_probe_block_hit",hit.getType()==net.minecraft.world.phys.HitResult.Type.BLOCK);
            if(hit.getType()==net.minecraft.world.phys.HitResult.Type.BLOCK){part.addProperty("actual_ground_y",hit.getLocation().y);part.addProperty("actual_sole_gap",min-hit.getLocation().y);}
        }
        state.row.getAsJsonObject("submitted_parts").add(bone.getName(), part);
    }

    static void angelSubmission(Entity entity, String path, Matrix4f submitted, Matrix4f world,
                                String[] names, Matrix4f[] palette, int cacheA, int cacheB, float blend)
    {
        State state = current(entity);
        if (state == null) return;
        JsonObject part = new JsonObject();
        part.addProperty("path", path);
        part.add("submitted_root_matrix", matrix(submitted));
        part.add("submitted_world_matrix", matrix(world));
        part.addProperty("surface_cache_frame_a", cacheA);
        part.addProperty("surface_cache_frame_b", cacheB);
        part.addProperty("surface_cache_blend", blend);
        JsonObject selected = new JsonObject();
        if (palette != null) for (int i = 0; i < names.length; i++)
            if (BONES.contains(names[i])) selected.add(names[i], matrix(palette[i]));
        part.add("actual_skin_palette", selected);
        state.row.getAsJsonObject("submitted_parts").add("weighted_body", part);
    }

    public static void finish(Entity entity, GeoBone root)
    {
        State state = current(entity);
        if (state == null) return;
        JsonObject finalBones = new JsonObject();
        collect(root, finalBones);
        state.row.add("final_at_root_return", finalBones);
        try
        {
            Path path = outputPath();
            Files.createDirectories(path.toAbsolutePath().getParent());
            if (!started)
            {
                Files.writeString(path, "", StandardCharsets.UTF_8, StandardOpenOption.CREATE, StandardOpenOption.TRUNCATE_EXISTING);
                started = true;
                ProjectSeele.LOGGER.info("R52 first-battle runtime witness: {} (one scene, <=96 rows, no mesh dump)", path.toAbsolutePath());
            }
            Files.writeString(path, state.row + System.lineSeparator(), StandardCharsets.UTF_8, StandardOpenOption.APPEND);
            state.lastBucket = state.row.get("age_bucket_half_second").getAsInt();
            rows++;
        }
        catch (Exception error)
        {
            failed = true;
            ProjectSeele.LOGGER.error("R52 first-battle runtime witness failed", error);
        }
        state.row = null;
    }

    private static Path outputPath()
    {
        String selected = System.getProperty("projectseele.firstBattleRuntimeWitnessR52Output", "");
        return selected.isBlank() ? Minecraft.getInstance().gameDirectory.toPath().resolve("logs/first_battle_runtime_r52.jsonl") : Path.of(selected);
    }
    private static State current(Entity entity)
    {
        if (!ENABLED || failed || rows >= 96) return null;
        State state = ACTORS.get(entity.getUUID());
        if (state == null || state.row == null || state.frame != FirstBattleSignals.clientFrameTime()) return null;
        return ShaderShadowPassR44.active() ? null : state;
    }
    private static JsonObject bones(BakedGeoModel model)
    {
        JsonObject values = new JsonObject();
        for (String name : BONES) model.getBone(name).ifPresent(bone -> values.add(name, channel(bone)));
        return values;
    }
    private static void collect(GeoBone bone, JsonObject values)
    {
        if (BONES.contains(bone.getName())) values.add(bone.getName(), channel(bone));
        for (GeoBone child : bone.getChildBones()) collect(child, values);
    }
    private static JsonObject channel(GeoBone bone)
    {
        JsonObject value = new JsonObject();
        value.add("rot_xyz_radians", vector(bone.getRotX(), bone.getRotY(), bone.getRotZ()));
        value.add("pos_xyz", vector(bone.getPosX(), bone.getPosY(), bone.getPosZ()));
        return value;
    }
    private static JsonArray vector(float x, float y, float z)
    { JsonArray array = new JsonArray(); array.add(x); array.add(y); array.add(z); return array; }
    private static JsonArray matrix(Matrix4f value)
    { JsonArray array = new JsonArray(); if (value != null) for (float v : value.get(new float[16])) array.add(v); return array; }
}
