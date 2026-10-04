package com.projectseele.client.render;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.projectseele.ProjectSeele;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.entity.Entity;
import org.joml.Matrix4f;
import org.joml.Quaternionf;
import org.joml.Vector3f;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.HashSet;
import java.util.Set;
import java.util.Map;
import java.util.HashMap;
import java.util.UUID;

/** Opt-in copies of parsed weights and vertices actually passed to emit. */
final class RiggedAngelSkinWitnessR44
{
    static final String OUTPUT = System.getProperty("projectseele.r44RiggedSkinWitnessPath", "");
    static final boolean ENABLED = !OUTPUT.isEmpty();
    private static final Set<String> IDENTITIES = new HashSet<>();
    private static final Map<UUID, Long> LAST_SAMPLE_TICK = new HashMap<>();
    private static int samples;
    private static boolean failed;
    private final JsonObject row = new JsonObject();
    private final JsonArray vertices = new JsonArray();
    private final JsonArray localVertices = new JsonArray();
    private final Matrix4f world;

    private RiggedAngelSkinWitnessR44(Entity entity, ResourceLocation resource,
                                    float partial, Matrix4f world)
    {
        this.world = new Matrix4f(world);
        row.addProperty("kind", "actual-weighted-emit-vertices");
        row.addProperty("entity_uuid", entity.getUUID().toString());
        row.addProperty("game_time", entity.level().getGameTime());
        row.addProperty("frame", com.projectseele.entity.FirstBattleSignals.clientFrameTime());
        row.addProperty("partial_tick", partial);
        row.addProperty("actor_tick", entity.tickCount);
        if (entity instanceof com.projectseele.entity.SachielEntity sachiel)
        {
            var state = new JsonObject();
            state.addProperty("no_ai", sachiel.isNoAi());
            state.addProperty("on_ground", sachiel.onGround());
            state.addProperty("origin_y", sachiel.getY());
            state.addProperty("strike_active", sachiel.isStrikeActive());
            state.addProperty("strike_mode", sachiel.strikeMode());
            state.addProperty("strike_age", sachiel.strikeAge(partial));
            state.addProperty("first_battle", sachiel.isFirstBattleActive());
            state.addProperty("body_dynamics_active", com.projectseele.physics.CombatBodyDynamics.active(sachiel));
            state.addProperty("reaction_active", com.projectseele.entity.CombatReactionsR36.active(sachiel));
            state.addProperty("held", com.projectseele.entity.EvaCombatR31.holds(sachiel));
            row.add("actual_sachiel_state", state);
        }
        row.addProperty("resource", resource.toString());
        row.addProperty("gpu_pixels_sampled", false);
        row.addProperty("dominant_review", DqSkinReferenceR44.REVIEW);
        row.addProperty("running_sum_review", DqSkinReferenceR44.RUNNING);
        JsonArray transform = new JsonArray();
        for (float value : this.world.get(new float[16])) transform.add(value);
        row.add("actual_emit_to_world_matrix_column_major", transform);
        row.add("vertices_world_xyz", vertices);
        row.add("vertices_emit_xyz", localVertices);
    }

    static RiggedAngelSkinWitnessR44 begin(Object actor, ResourceLocation resource,
                                          float partial, Matrix4f world)
    {
        if (!ENABLED || failed || world == null || !(actor instanceof Entity entity)
                || samples >= Integer.getInteger("projectseele.r44RiggedSkinWitnessFrames", 360)) return null;
        long tick = entity.level().getGameTime();
        long previous = LAST_SAMPLE_TICK.getOrDefault(entity.getUUID(), Long.MIN_VALUE);
        int gap = Math.max(1, Integer.getInteger("projectseele.r44RiggedSkinWitnessTickGap", 1));
        if (previous != Long.MIN_VALUE && tick >= previous && tick - previous < gap) return null;
        LAST_SAMPLE_TICK.put(entity.getUUID(), tick);
        samples++;
        return new RiggedAngelSkinWitnessR44(entity, resource, partial, world);
    }

    void vertex(Vector3f point)
    {
        localVertices.add(point.x); localVertices.add(point.y); localVertices.add(point.z);
        Vector3f actual = world.transformPosition(new Vector3f(point));
        vertices.add(actual.x); vertices.add(actual.y); vertices.add(actual.z);
    }

    void palette(String[] bones, Matrix4f[] matrices, boolean[] scaled,
                 Quaternionf[] real, Quaternionf[] dual)
    {
        JsonArray rows = new JsonArray();
        for (int bone = 0; bone < bones.length; bone++)
        {
            JsonObject sample = new JsonObject(); sample.addProperty("bone", bones[bone]);
            sample.addProperty("scaled_lbs_branch", scaled[bone]);
            JsonArray matrix = new JsonArray(); float[] values = matrices[bone].get(new float[16]);
            for (float value : values) matrix.add(value);
            sample.add("actual_root_relative_matrix_column_major", matrix);
            sample.add("actual_real_quaternion_xyzw", quaternion(real[bone]));
            sample.add("actual_dual_quaternion_xyzw", quaternion(dual[bone]));
            rows.add(sample);
        }
        row.add("actual_palette", rows);
    }

    void supportTranslation(Vector3f translation)
    {
        JsonArray values = new JsonArray();
        values.add(translation.x); values.add(translation.y); values.add(translation.z);
        row.add("actual_ground_support_translation_emit_xyz", values);
    }

    private static JsonArray quaternion(Quaternionf quaternion)
    {
        JsonArray values = new JsonArray();
        values.add(quaternion.x); values.add(quaternion.y);
        values.add(quaternion.z); values.add(quaternion.w);
        return values;
    }

    void finish(String branch)
    {
        row.addProperty("branch", branch);
        row.addProperty("vertices", vertices.size() / 3);
        write(row);
    }

    static void parsed(ResourceLocation resource, String pack, String sha,
                       String[] bones, float[] decodedVertices, int[] indices, float[] weights)
    {
        if (!ENABLED || !IDENTITIES.add(resource + ":" + sha)) return;
        JsonObject row = new JsonObject(); row.addProperty("kind", "actual-parsed-weighted-resource");
        row.addProperty("resource", resource.toString()); row.addProperty("source_pack_id", pack);
        row.addProperty("source_bytes_sha256", sha); row.addProperty("weighted_load_succeeded", true);
        row.addProperty("mesh_url_exposed_by_resource_api", false);
        row.addProperty("resource_identity_scope", "ResourceLocation + actual sourcePackId + bytes opened by load; no guessed physical URL");
        try
        {
            var code = RiggedAngelLayer.class.getResource("RiggedAngelLayer.class");
            row.addProperty("loaded_renderer_class_url", String.valueOf(code));
            if (code != null) try (var stream = code.openStream())
            {
                row.addProperty("loaded_renderer_class_sha256", java.util.HexFormat.of().formatHex(
                        java.security.MessageDigest.getInstance("SHA-256").digest(stream.readAllBytes())));
            }
        }
        catch (Exception error) { row.addProperty("loaded_code_identity_error", error.toString()); }
        row.addProperty("decode_order", "Exact source indices/weights retained; no filtering, reordering or normalization in load");
        row.addProperty("running_sum_contract", "Decoded four-slot order; skip zero weights; align positive slot quaternion+dual to weighted running real sum; no global or per-frame palette sign rewrite");
        JsonArray names = new JsonArray(), ids = new JsonArray(), values = new JsonArray();
        JsonArray geometry = new JsonArray();
        for (String bone : bones) names.add(bone);
        for (int index : indices) ids.add(index);
        for (float weight : weights) values.add(weight);
        for (float vertex : decodedVertices) geometry.add(vertex);
        row.addProperty("decoded_vertex_stride", 8);
        row.addProperty("decoded_position_to_emit", "(-x/16, y/16, z/16)");
        row.add("decoded_vertices", geometry);
        row.add("bones", names); row.add("parsed_indices", ids); row.add("parsed_weights", values); write(row);
    }

    static void fallback(Object actor, ResourceLocation resource, String bone)
    {
        if (!ENABLED || !(actor instanceof Entity entity) || !bone.equals("root")) return;
        JsonObject row = new JsonObject(); row.addProperty("kind", "actual-weighted-fallback-dispatch");
        row.addProperty("entity_uuid", entity.getUUID().toString()); row.addProperty("resource", resource.toString());
        row.addProperty("weighted_load_succeeded", false); row.addProperty("renderer", "LocalTriangleMeshLayer"); write(row);
    }

    private static void write(JsonObject row)
    {
        if (failed) return;
        try
        {
            Path path = Path.of(OUTPUT).toAbsolutePath();
            Files.createDirectories(path.getParent());
            Files.writeString(path, row + "\n", StandardOpenOption.CREATE, StandardOpenOption.APPEND);
        }
        catch (Exception error)
        {
            failed = true;
            ProjectSeele.LOGGER.error("R44 actual skin witness could not save", error);
        }
    }

    private RiggedAngelSkinWitnessR44() { world = null; }
}
