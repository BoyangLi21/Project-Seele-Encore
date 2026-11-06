package com.projectseele.client.render;

import com.google.gson.JsonParser;
import com.mojang.blaze3d.vertex.PoseStack;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import net.minecraft.client.renderer.LightTexture;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.client.renderer.texture.OverlayTexture;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.util.Mth;

/** Optional private source geometry, shared by near and distant encounter draws. */
final class RamielSourceModelR53
{
    private static final String ROOT = "/assets/projectseele/";
    private static final String SELECTION = "eva/ramiel_source_r53_sources.json";
    private static boolean checked;
    private static List<Part> parts;
    private static String sourceHash = "";
    private record Material(ResourceLocation texture, boolean emissive) { }
    /** axis: the arm direction (0 x, 1 y, 2 z) of an open-form spike group, -1 otherwise. */
    private record Part(String name, boolean open, int shift, boolean core,
                        Material material, float[] vertices, int axis) { }

    private static synchronized boolean selected()
    {
        if (checked) return parts != null;
        try (var selection = RamielSourceModelR53.class.getResourceAsStream(ROOT + SELECTION))
        {
            if (selection == null) { checked = true; return false; }
            var manifest = JsonParser.parseString(new String(selection.readAllBytes(), StandardCharsets.UTF_8)).getAsJsonObject();
            require(manifest.get("schema").getAsString().equals("projectseele.r53.ramiel-selection.v1"), "Ramiel selection schema");
            byte[] mesh = null;
            for (var resource : manifest.getAsJsonObject("resources").entrySet())
            {
                require(!resource.getKey().contains("..") && !resource.getKey().startsWith("/"), "Relative Ramiel resource required");
                try (var stream = RamielSourceModelR53.class.getResourceAsStream(ROOT + resource.getKey()))
                {
                    require(stream != null, "Selected Ramiel resource missing");
                    byte[] bytes = stream.readAllBytes();
                    if (resource.getKey().equals("mesh/ramiel_source_r53.json")) mesh = bytes;
                }
            }
            require(mesh != null, "Selected Ramiel mesh missing");
            var data = JsonParser.parseString(new String(mesh, StandardCharsets.UTF_8)).getAsJsonObject();
            require(data.get("schema").getAsString().equals("projectseele.r53.ramiel-source.v1")
                    && data.get("stride").getAsInt() == 8, "Supplied Ramiel source schema required");
            sourceHash = data.has("source_sha256") ? data.get("source_sha256").getAsString() : "";
            var materials = new ArrayList<Material>();
            for (var value : data.getAsJsonArray("materials"))
            {
                var material = value.getAsJsonObject();
                materials.add(new Material(new ResourceLocation(material.get("texture").getAsString()), material.get("emissive").getAsBoolean()));
            }
            var loaded = new ArrayList<Part>();
            int faces = 0;
            for (var value : data.getAsJsonArray("parts"))
            {
                var part = value.getAsJsonObject();
                var encoded = part.getAsJsonArray("vertices");
                require(!encoded.isEmpty() && encoded.size() % 24 == 0, "Complete Ramiel triangles required");
                float[] vertices = new float[encoded.size()];
                for (int i = 0; i < vertices.length; i++)
                {
                    vertices[i] = encoded.get(i).getAsFloat();
                    require(Float.isFinite(vertices[i]), "Finite Ramiel source vertices required");
                }
                faces += vertices.length / 24;
                boolean open = part.get("phase").getAsString().equals("open"), core = part.get("core").getAsBoolean();
                float[] extent = new float[3];
                for (int i = 0; i < vertices.length; i += 8)
                    for (int k = 0; k < 3; k++) extent[k] = Math.max(extent[k], Math.abs(vertices[i + k]));
                int axis = extent[0] >= extent[1] && extent[0] >= extent[2] ? 0 : extent[1] >= extent[2] ? 1 : 2;
                float second = Math.max(Math.min(extent[0], extent[1]), Math.min(Math.max(extent[0], extent[1]), extent[2]));
                if (!open || core || extent[axis] < 1.6F * second) axis = -1;
                loaded.add(new Part(part.get("name").getAsString(), open,
                        part.get("shell_shift").getAsInt(), core,
                        materials.get(part.get("material").getAsInt()), vertices, axis));
            }
            require(faces == 8816 && loaded.size() == 9, "All Ramiel source primitives required");
            parts = List.copyOf(loaded);
            checked = true;
            return true;
        }
        catch (IOException failure)
        {
            throw new IllegalStateException("Selected Ramiel source unavailable", failure);
        }
    }

    static Map<String, Object> diagnostic()
    {
        if (!selected()) return Map.of("selected", false);
        return Map.of("selected", true, "source_sha256", sourceHash, "parts", parts.size(),
                "source_faces", parts.stream().mapToInt(p -> p.vertices().length / 24).sum(),
                "closed_faces", parts.stream().filter(p -> !p.open()).mapToInt(p -> p.vertices().length / 24).sum(),
                "open_faces", parts.stream().filter(Part::open).mapToInt(p -> p.vertices().length / 24).sum());
    }

    static boolean draw(PoseStack poses, MultiBufferSource buffers, float expose, float time, boolean charging, int packedLight)
    {
        if (!selected()) return false;
        float blend = Mth.clamp(expose, 0, 1);
        blend = blend * blend * (3 - 2 * blend);
        for (var part : parts)
        {
            // The octahedron opens: its halves part and shrink back while the
            // spike arms are driven out of the core one axis after another,
            // overshooting a little and settling; they do not fade in.
            float alpha;
            poses.pushPose();
            poses.translate(0, part.shift() * 3.75F * expose, 0);
            if (part.core())
            {
                alpha = part.open() ? blend : 1 - blend;
                float pulse = charging ? 1.1F + .3F * Mth.sin(time * .5F) : .95F;
                poses.scale(pulse, pulse, pulse);
            }
            else if (!part.open())
            {
                float shrink = 1 - .22F * blend;
                poses.scale(shrink, shrink, shrink);
                alpha = 1 - smooth((blend - .3F) / .55F);
            }
            else if (part.axis() >= 0)
            {
                float delay = part.name().startsWith("Ramiel2.2") ? 0 : part.name().startsWith("Ramiel2.3") ? .12F : .24F;
                float u = Mth.clamp((blend - delay) / .76F, 0, 1);
                float along = Math.max(.02F, overshoot(u));
                if (charging && u >= 1) along *= 1 + .035F * Mth.sin(time * .9F + part.axis() * 2.1F);
                float across = .35F + .65F * smooth(u * 1.6F);
                var turn = part.axis() == 0 ? com.mojang.math.Axis.XP : part.axis() == 1 ? com.mojang.math.Axis.YP : com.mojang.math.Axis.ZP;
                poses.mulPose(turn.rotationDegrees((1 - u) * 90F));
                poses.scale(part.axis() == 0 ? along : across, part.axis() == 1 ? along : across, part.axis() == 2 ? along : across);
                alpha = Math.min(1, u * 5);
            }
            else alpha = blend;
            if (alpha <= .001F) { poses.popPose(); continue; }
            var consumer = buffers.getBuffer(RenderType.entityTranslucent(part.material().texture()));
            var pose = poses.last();
            var v = part.vertices();
            for (int triangle = 0; triangle < v.length; triangle += 24)
                for (int corner = 0; corner < 4; corner++)
                {
                    int i = triangle + Math.min(corner, 2) * 8;
                    consumer.vertex(pose.pose(), v[i], v[i+1], v[i+2]).color(1F, 1F, 1F, alpha)
                            .uv(v[i+3], v[i+4]).overlayCoords(OverlayTexture.NO_OVERLAY)
                            .uv2(part.material().emissive() ? LightTexture.FULL_BRIGHT : packedLight)
                            .normal(pose.normal(), v[i+5], v[i+6], v[i+7]).endVertex();
                }
            poses.popPose();
        }
        return true;
    }

    private static float smooth(float t)
    {
        t = Mth.clamp(t, 0, 1);
        return t * t * (3 - 2 * t);
    }

    /** Ease out with a small overshoot (about 6%) before settling at 1. */
    private static float overshoot(float t)
    {
        float c = 1.1F, x = t - 1;
        return 1 + (c + 1) * x * x * x + c * x * x;
    }

    private static void require(boolean accepted, String reason)
    {
        if (!accepted) throw new IllegalArgumentException(reason);
    }
    private RamielSourceModelR53() { }
}
