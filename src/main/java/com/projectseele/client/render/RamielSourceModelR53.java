package com.projectseele.client.render;

import com.google.gson.JsonParser;
import com.mojang.blaze3d.vertex.PoseStack;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.HexFormat;
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
    private record Part(String name, boolean open, int shift, boolean core,
                        Material material, float[] vertices) { }

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
                    require(HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes)).equals(resource.getValue().getAsString()), "Selected Ramiel source changed");
                    if (resource.getKey().equals("mesh/ramiel_source_r53.json")) mesh = bytes;
                }
            }
            require(mesh != null, "Selected Ramiel mesh missing");
            var data = JsonParser.parseString(new String(mesh, StandardCharsets.UTF_8)).getAsJsonObject();
            require(data.get("schema").getAsString().equals("projectseele.r53.ramiel-source.v1")
                    && data.get("stride").getAsInt() == 8 && data.get("source_faces").getAsInt() == 8816
                    && data.get("removed_faces").getAsInt() == 0, "Complete supplied Ramiel source required");
            sourceHash = data.get("source_sha256").getAsString();
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
                loaded.add(new Part(part.get("name").getAsString(), part.get("phase").getAsString().equals("open"),
                        part.get("shell_shift").getAsInt(), part.get("core").getAsBoolean(),
                        materials.get(part.get("material").getAsInt()), vertices));
            }
            require(faces == 8816 && loaded.size() == 9, "All Ramiel source primitives required");
            parts = List.copyOf(loaded);
            checked = true;
            return true;
        }
        catch (IOException | java.security.NoSuchAlgorithmException failure)
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
            float alpha = part.open() ? blend : 1 - blend;
            if (alpha <= .001F) continue;
            poses.pushPose();
            poses.translate(0, part.shift() * 3.75F * expose, 0);
            if (part.core())
            {
                float pulse = charging ? 1.1F + .3F * Mth.sin(time * .5F) : .95F;
                poses.scale(pulse, pulse, pulse);
            }
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

    private static void require(boolean accepted, String reason)
    {
        if (!accepted) throw new IllegalArgumentException(reason);
    }
    private RamielSourceModelR53() { }
}
