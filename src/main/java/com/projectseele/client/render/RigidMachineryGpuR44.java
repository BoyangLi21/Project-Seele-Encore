package com.projectseele.client.render;

import com.google.gson.JsonObject;
import com.mojang.blaze3d.systems.RenderSystem;
import com.mojang.blaze3d.vertex.*;
import com.projectseele.ProjectSeele;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.OutlineBufferSource;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.client.renderer.ShaderInstance;
import net.minecraft.client.renderer.texture.OverlayTexture;
import net.minecraft.resources.ResourceLocation;
import org.joml.Matrix3f;
import org.joml.Matrix4f;
import java.lang.reflect.Method;
import java.util.IdentityHashMap;
import java.util.LinkedHashMap;
import java.util.Map;

/** Reuses exact rigid vertices in the selected entity/shadow shader, without a lower-detail substitute. */
public final class RigidMachineryGpuR44
{
    private record Key(ShaderInstance pipeline, boolean external, boolean mirror,
                       int light, int entity, int blockEntity, int item) { }
    private record Mesh(VertexBuffer buffer, int bytes) { }
    private static final Map<Object, LinkedHashMap<Key, Mesh>> PARTS = new IdentityHashMap<>();
    private static Object irisState;
    private static Method entityId, blockEntityId, itemId;
    private static boolean resolved, logged;
    private static long draws, uploads, uploadedVertices, clears, releasedBytes;

    public static boolean enabled()
    {
        String configured = System.getProperty("projectseele.rigidMachineryGpu");
        if (configured != null) return Boolean.parseBoolean(configured);
        // Retain the old explicit review override for controlled CPU baselines.
        return Boolean.parseBoolean(System.getProperty("projectseele.r44RigidMachineryGpu", "true"));
    }

    private static boolean resolveIrisState()
    {
        if (!resolved)
        {
            resolved = true;
            try
            {
                var type = Class.forName("net.irisshaders.iris.uniforms.CapturedRenderingState");
                irisState = type.getField("INSTANCE").get(null);
                entityId = type.getMethod("getCurrentRenderedEntity");
                blockEntityId = type.getMethod("getCurrentRenderedBlockEntity");
                itemId = type.getMethod("getCurrentRenderedItem");
            }
            catch (ReflectiveOperationException unavailable)
            {
                ProjectSeele.LOGGER.warn("R44 cached machinery cannot preserve Iris material IDs; using ordinary vertices", unavailable);
            }
        }
        return irisState != null && entityId != null && blockEntityId != null && itemId != null;
    }

    static boolean draw(Object identity, float[] vertices, ResourceLocation texture,
                        PoseStack poses, MultiBufferSource buffers, int light)
    {
        if (!enabled() || buffers instanceof OutlineBufferSource)
            return false;
        boolean external = ShaderShadowPassR44.enabled();
        ShaderInstance custom = RigidCapsuleGpu.machineryShader();
        if (!external && custom == null || external && !resolveIrisState()) return false;
        BufferUploader.reset();
        var type = RenderType.entitySolid(texture);
        type.setupRenderState();
        try
        {
            ShaderInstance active = external ? RenderSystem.getShader() : custom;
            if (active == null || external && !active.getClass().getName().contains("ExtendedShader")) return false;
            boolean mirror = poses.last().pose().determinant() < 0;
            int entity = 0, blockEntity = 0, item = 0;
            if (external)
            {
                try
                {
                    entity = (Integer) entityId.invoke(irisState);
                    blockEntity = (Integer) blockEntityId.invoke(irisState);
                    item = (Integer) itemId.invoke(irisState);
                }
                catch (ReflectiveOperationException failure) { return false; }
            }
            var key = new Key(active, external, mirror, external ? light : 0, entity, blockEntity, item);
            var variants = PARTS.computeIfAbsent(identity, ignored -> new LinkedHashMap<>(16, .75F, true));
            Mesh mesh = variants.get(key);
            if (mesh == null)
            {
                int count = vertices.length / 11;
                var builder = new BufferBuilder(Math.max(1024, count * 96 + 64));
                builder.begin(VertexFormat.Mode.QUADS, DefaultVertexFormat.NEW_ENTITY);
                for (int quad = 0; quad < vertices.length; quad += 44)
                {
                    for (int corner = 0; corner < 4; corner++)
                    {
                        int offset = quad + (mirror ? 3 - corner : corner) * 11;
                        float sign = mirror ? -1 : 1;
                        // Bake the reflection as well as reversing winding. The remaining
                        // matrix is proper, so Iris's generated face normal transforms correctly.
                        builder.vertex(sign * vertices[offset], vertices[offset + 1], vertices[offset + 2],
                                vertices[offset + 3], vertices[offset + 4], vertices[offset + 5], 1,
                                vertices[offset + 9], vertices[offset + 10], OverlayTexture.NO_OVERLAY,
                                external ? light : 0, sign * vertices[offset + 6], vertices[offset + 7], vertices[offset + 8]);
                    }
                }
                var uploaded = new VertexBuffer(VertexBuffer.Usage.STATIC);
                uploaded.bind();
                uploaded.upload(builder.end());
                VertexBuffer.unbind();
                mesh = new Mesh(uploaded, count * uploaded.getFormat().getVertexSize());
                variants.put(key, mesh);
                uploads++;
                uploadedVertices += count;
                // Moving machinery may cross several light levels. Bound its GPU cache.
                if (variants.size() > 16)
                {
                    var iterator = variants.entrySet().iterator();
                    var oldest = iterator.next();
                    oldest.getValue().buffer.close();
                    iterator.remove();
                }
            }
            Matrix4f local = new Matrix4f(poses.last().pose());
            Matrix3f normal = new Matrix3f(poses.last().normal());
            if (mirror) { local.scale(-1, 1, 1); normal.scale(-1, 1, 1); }
            if (!external)
            {
                RenderSystem.setShader(() -> active);
                active.safeGetUniform("BoneMat").set(local);
                active.safeGetUniform("BoneNormal").set(normal);
                active.safeGetUniform("FrameLight").set((float) (light & 65535), (float) (light >>> 16 & 65535));
                active.safeGetUniform("FrameOverlay").set(0F, 10F);
            }
            Matrix4f modelView = new Matrix4f(RenderSystem.getModelViewMatrix());
            if (external) modelView.mul(local);
            mesh.buffer.bind();
            mesh.buffer.drawWithShader(modelView, RenderSystem.getProjectionMatrix(), active);
            draws++;
            if (!logged)
            {
                logged = true;
                ProjectSeele.LOGGER.info("R44 rigid machinery GPU candidate active: exact vertices, entity shader {}, stride {}",
                        active.getClass().getName(), mesh.buffer.getFormat().getVertexSize());
            }
            return true;
        }
        finally
        {
            VertexBuffer.unbind();
            BufferUploader.reset();
            type.clearRenderState();
        }
    }

    public static JsonObject snapshot()
    {
        var result = new JsonObject();
        result.addProperty("enabled", enabled());
        result.addProperty("draw_calls", draws);
        result.addProperty("uploads", uploads);
        result.addProperty("uploaded_vertices", uploadedVertices);
        result.addProperty("cached_batches", PARTS.values().stream().mapToInt(Map::size).sum());
        result.addProperty("cached_vertex_bytes", PARTS.values().stream().flatMap(m -> m.values().stream()).mapToLong(Mesh::bytes).sum());
        result.addProperty("clear_calls", clears);
        result.addProperty("released_vertex_bytes", releasedBytes);
        result.addProperty("outline_uses_original_consumer", true);
        return result;
    }

    static void clear()
    {
        releasedBytes += PARTS.values().stream().flatMap(m -> m.values().stream()).mapToLong(Mesh::bytes).sum();
        PARTS.values().forEach(m -> m.values().forEach(p -> p.buffer.close()));
        PARTS.clear();
        clears++;
    }

    private RigidMachineryGpuR44() { }
}
