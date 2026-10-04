package com.projectseele.client.render;

import com.google.gson.JsonArray;
import com.google.gson.JsonParser;
import com.mojang.blaze3d.vertex.PoseStack;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.EvaDorsalMechanism;
import net.minecraft.client.Minecraft;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.phys.Vec3;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/** Review-only TV cage shell; moving bodies share the measured pad's release clock. */
final class TvCageEnclosureR44
{
    private record Component(String part, int variant, String motion, Vec3 normal,
                             double outboard, Vec3 translation, float from, float to) {}
    private static final Map<String, RigidMachineryPartR44> PARTS = new HashMap<>();
    private static final List<Component> COMPONENTS = new ArrayList<>();
    private static boolean attempted;

    static void clearCache()
    {
        attempted = false;
        PARTS.clear();
        COMPONENTS.clear();
    }

    private static Vec3 point(JsonArray values)
    {
        if (values.size() != 3) throw new IllegalArgumentException("Three-dimensional translation required");
        Vec3 result = new Vec3(values.get(0).getAsDouble(), values.get(1).getAsDouble(), values.get(2).getAsDouble());
        if (!Double.isFinite(result.x) || !Double.isFinite(result.y) || !Double.isFinite(result.z))
            throw new IllegalArgumentException("Invalid cage position");
        return result;
    }

    private static void load()
    {
        if (attempted) return;
        attempted = true;
        var path = new ResourceLocation(ProjectSeele.MODID, "mesh/tv_shoulder_shells_r44.json");
        var resource = Minecraft.getInstance().getResourceManager().getResource(path);
        try (var stream = resource.orElseThrow().open())
        {
            byte[] encoded = stream.readAllBytes();
            var root = JsonParser.parseString(new String(encoded, StandardCharsets.UTF_8)).getAsJsonObject();
            if (root.get("stride").getAsInt() != 6
                    || !root.get("frame").getAsString().equals("fixed_gantry_local_metres_world_axes"))
                throw new IllegalArgumentException("Unexpected cage coordinate convention");
            for (var item : root.getAsJsonObject("parts").entrySet())
                PARTS.put(item.getKey(), RigidMachineryPartR44.triangles(item.getValue().getAsJsonArray()));
            int[] shoulders = new int[3];
            for (var item : root.getAsJsonArray("components"))
            {
                var row = item.getAsJsonObject();
                String part = row.get("part").getAsString(), motion = row.get("motion").getAsString();
                int variant = row.has("variant") ? row.get("variant").getAsInt() : -1;
                if (!PARTS.containsKey(part) || variant < -1 || variant > 2)
                    throw new IllegalArgumentException("Unresolved cage component");
                Vec3 normal = Vec3.ZERO, translation = Vec3.ZERO;
                double outboard = 0;
                float from = 0, to = 1;
                switch (motion)
                {
                    case "fixed" -> { }
                    case "translation_only_with_exact_facet_pad" ->
                    {
                        if (variant < 0) throw new IllegalArgumentException("A shoulder must belong to one body");
                        normal = point(row.getAsJsonArray("normal"));
                        if (Math.abs(normal.length() - 1) > .0001)
                            throw new IllegalArgumentException("Unit shoulder normal required");
                        outboard = row.get("outboard_m").getAsDouble();
                        if (Math.abs(Math.abs(outboard) - 5.35) > .0001
                                || Math.abs(row.get("normal_lift_m").getAsDouble() - 2.1) > .0001)
                            throw new IllegalArgumentException("Cage and contact-pad release must agree");
                        shoulders[variant]++;
                    }
                    case "telescoping_translation" ->
                    {
                        translation = point(row.getAsJsonArray("translation_open_local"));
                        var interval = row.getAsJsonArray("opening_interval");
                        from = interval.get(0).getAsFloat();
                        to = interval.get(1).getAsFloat();
                        if (from < 0 || to > 1 || from >= to)
                            throw new IllegalArgumentException("Invalid beam release interval");
                    }
                    default -> throw new IllegalArgumentException("Unknown cage motion " + motion);
                }
                COMPONENTS.add(new Component(part, variant, motion, normal, outboard, translation, from, to));
            }
            for (int count : shoulders)
                if (count != 2) throw new IllegalArgumentException("All six shoulder housings are required");
            if (!PARTS.containsKey("cage_frame_lower_r44"))
                throw new IllegalArgumentException("A complete replacement fixed support frame is required");
            ProjectSeele.LOGGER.info("R44 TV cage visual resource source={} sha256={} parts={} components={}",
                    resource.orElseThrow().sourcePackId(), java.util.HexFormat.of().formatHex(
                            java.security.MessageDigest.getInstance("SHA-256").digest(encoded)), PARTS.size(), COMPONENTS.size());
        }
        catch (Exception error)
        {
            PARTS.clear();
            COMPONENTS.clear();
            ProjectSeele.LOGGER.error("R44 TV cage candidate rejected; retaining complete previous machinery", error);
        }
    }

    private static float ramp(float value, float from, float to)
    {
        return EvaDorsalMechanism.smooth((value - from) / (to - from));
    }

    static boolean render(int variant, float opening, PoseStack poses, int light)
    {
        if (!com.projectseele.world.TvCageCollisionR44.enabled() || variant < 0 || variant > 2) return false;
        load();
        if (COMPONENTS.isEmpty()) return false;
        // Fixed supports are generated as complete members, never triangle-clipped by height.
        PARTS.get("cage_frame_lower_r44").draw(poses, TvFacilityMeshes.currentBuffers(), light);
        for (var component : COMPONENTS)
        {
            if (component.variant >= 0 && component.variant != variant) continue;
            if (component.part.equals("cage_frame_lower_r44")) continue;
            // These replace real walkway guards only after their complete world component is migrated.
            if (component.part.startsWith("thin_side_rails")) continue;
            Vec3 move = switch (component.motion)
            {
                case "translation_only_with_exact_facet_pad" -> component.normal.scale(2.1 * ramp(opening, 0, .25F))
                        .add(component.outboard * ramp(opening, .23F, .88F), 0, 0);
                case "telescoping_translation" -> component.translation.scale(ramp(opening, component.from, component.to));
                default -> Vec3.ZERO;
            };
            poses.pushPose();
            poses.translate(move.x, move.y, move.z);
            PARTS.get(component.part).draw(poses, TvFacilityMeshes.currentBuffers(), light);
            poses.popPose();
        }
        return true;
    }

    private TvCageEnclosureR44() { }
}
