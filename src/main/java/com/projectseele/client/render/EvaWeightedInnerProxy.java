package com.projectseele.client.render;

import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HashMap;
import java.util.HexFormat;
import java.util.Map;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.VertexConsumer;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.EvaUnit01Entity;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.packs.resources.ResourceManager;
import org.joml.Matrix3f;
import org.joml.Matrix4f;
import org.joml.Vector3f;
import software.bernie.geckolib.cache.object.BakedGeoModel;
import software.bernie.geckolib.cache.object.GeoBone;

/** Isolated after-recursion renderer for the Phase-D weighted inner proxy. */
public final class EvaWeightedInnerProxy
{
    private static final boolean PROXY_PREVIEW_R58=Boolean.getBoolean("projectseele.skinnedProxyPreview");

    private static final ResourceLocation CONTRACT = new ResourceLocation(
            ProjectSeele.MODID, "eva/eva_weighted_proxy_contract.json");
    private static final ResourceLocation PROXY = new ResourceLocation(
            ProjectSeele.MODID,
            "eva/eva_unit01_inner_proxy.skinned.json");
    private static volatile EvaSkinnedMeshRuntime.MeshData mesh;
    private static volatile Status status = Status.missing();
    private static boolean firstRenderLogged;

    private EvaWeightedInnerProxy() {}

    public static void reload(ResourceManager resources)
    {
        mesh = null;
        firstRenderLogged = false;
        try
        {
            String contractText = read(resources, CONTRACT);
            String proxyText = read(resources, PROXY);
            JsonObject contract = JsonParser.parseString(
                    contractText).getAsJsonObject();
            JsonObject proxyJson = JsonParser.parseString(
                    proxyText).getAsJsonObject();
            validateContract(contract, proxyJson);
            EvaSkinnedMeshRuntime.MeshData loaded =
                    EvaSkinnedMeshRuntime.load(resources, PROXY);
            JsonObject expected = contract.getAsJsonObject("expected");
            int segmentCount = proxyJson.getAsJsonArray("segments").size();
            require(loaded.palette().size() ==
                    expected.get("paletteBones").getAsInt(),
                    "weighted proxy palette count differs");
            require(segmentCount == expected.get("segments").getAsInt(),
                    "weighted proxy segment count differs");
            require(loaded.vertices().size() ==
                    expected.get("vertices").getAsInt(),
                    "weighted proxy vertex count differs");
            require(loaded.indices().length / 3 ==
                    expected.get("triangles").getAsInt(),
                    "weighted proxy triangle count differs");
            require(loaded.blendedVertices() ==
                    expected.get("blendedVertices").getAsInt(),
                    "weighted proxy blended count differs");
            mesh = loaded;
            status = new Status(true, previewEnabled(),
                    loaded.palette().size(), segmentCount,
                    loaded.vertices().size(), loaded.indices().length / 3,
                    loaded.blendedVertices(), sha256(contractText),
                    sha256(proxyText), 0L, -1, -1.0F, "none");
            ProjectSeele.LOGGER.info(
                    "EVA weighted inner proxy loaded: palette={} segments={} "
                            + "vertices={} triangles={} blended={} "
                            + "previewEnabled={} replacesTiger=false",
                    status.paletteBones(), status.segments(),
                    status.vertices(), status.triangles(),
                    status.blendedVertices(), status.previewEnabled());
        }
        catch (Exception exception)
        {
            status = Status.failed(exception.getMessage());
            ProjectSeele.LOGGER.error(
                    "EVA weighted inner proxy rejected", exception);
        }
    }

    public static void prepare(BakedGeoModel model)
    {
        EvaSkinnedMeshRuntime.MeshData current = mesh;
        if (!previewEnabled() || current == null)
        {
            return;
        }
        for (String name : current.palette())
        {
            model.getBone(name).ifPresent(bone ->
                    bone.setTrackingMatrices(true));
        }
    }

    public static void renderAfterRoot(PoseStack poseStack,
                                       EvaUnit01Entity entity,
                                       GeoBone root,
                                       MultiBufferSource bufferSource,
                                       int packedLight, int packedOverlay)
    {
        EvaSkinnedMeshRuntime.MeshData current = mesh;
        if (!previewEnabled() || current == null
                || entity.getUnitVariant() != EvaUnit01Entity.UNIT_01)
        {
            return;
        }
        Map<String, GeoBone> bones = new HashMap<>();
        collect(root, bones);
        Matrix4f[] palette = new Matrix4f[current.palette().size()];
        for (int index = 0; index < palette.length; index++)
        {
            String name = current.palette().get(index);
            GeoBone bone = bones.get(name);
            if (bone == null || !bone.isTrackingMatrices())
            {
                status = status.withFailure(
                        "missing tracked palette bone " + name);
                return;
            }
            palette[index] = new Matrix4f(bone.getModelSpaceMatrix());
        }
        try
        {
            float[] positions = EvaSkinnedMeshRuntime.skinPositions(
                    current, palette);
            Vector3f[] normals = EvaSkinnedMeshRuntime.skinNormals(
                    current, palette);
            VertexConsumer target = bufferSource.getBuffer(
                    RenderType.entityTranslucent(
                            EvaUnit01Renderer.textureResourceForVariant(
                                    entity.getUnitVariant())));
            Matrix4f pose = poseStack.last().pose();
            Matrix3f normal = poseStack.last().normal();
            int[] indices = current.indices();
            for (int index = 0; index < indices.length; index += 3)
            {
                emit(target, pose, normal, current, positions, normals,
                        indices[index], packedLight, packedOverlay);
                emit(target, pose, normal, current, positions, normals,
                        indices[index + 1], packedLight, packedOverlay);
                emit(target, pose, normal, current, positions, normals,
                        indices[index + 2], packedLight, packedOverlay);
                emit(target, pose, normal, current, positions, normals,
                        indices[index + 2], packedLight, packedOverlay);
            }
            float bindDelta = maximumBindDelta(current, positions);
            status = status.withRender(entity.getId(), bindDelta);
            if (!firstRenderLogged)
            {
                firstRenderLogged = true;
                ProjectSeele.LOGGER.info(
                        "EVA weighted inner proxy rendered after recursion: "
                                + "entity={} palette={} vertices={} "
                                + "triangles={} bindDelta={} "
                                + "replacesTiger=false",
                        entity.getId(), current.palette().size(),
                        current.vertices().size(), indices.length / 3,
                        bindDelta);
            }
        }
        catch (Exception exception)
        {
            status = status.withFailure(exception.getMessage());
            ProjectSeele.LOGGER.error(
                    "EVA weighted inner proxy render failed", exception);
        }
    }

    public static boolean previewEnabled()
    {
        return PROXY_PREVIEW_R58;
    }

    public static Status status()
    {
        return status;
    }

    private static void emit(VertexConsumer target, Matrix4f pose,
                             Matrix3f normalMatrix,
                             EvaSkinnedMeshRuntime.MeshData meshData,
                             float[] positions, Vector3f[] normals,
                             int vertexIndex, int packedLight,
                             int packedOverlay)
    {
        int offset = vertexIndex * 3;
        EvaSkinnedMeshRuntime.VertexData source =
                meshData.vertices().get(vertexIndex);
        Vector3f normal = normals[vertexIndex];
        target.vertex(pose, positions[offset], positions[offset + 1],
                        positions[offset + 2])
                .color(96, 220, 255, 118)
                .uv(source.u(), source.v())
                .overlayCoords(packedOverlay)
                .uv2(packedLight)
                .normal(normalMatrix, normal.x, normal.y, normal.z)
                .endVertex();
    }

    private static void collect(GeoBone bone, Map<String, GeoBone> target)
    {
        target.put(bone.getName(), bone);
        for (GeoBone child : bone.getChildBones())
        {
            collect(child, target);
        }
    }

    private static float maximumBindDelta(
            EvaSkinnedMeshRuntime.MeshData meshData, float[] positions)
    {
        float maximum = 0.0F;
        for (int index = 0; index < meshData.vertices().size(); index++)
        {
            Vector3f bind = meshData.vertices().get(index).position();
            int offset = index * 3;
            maximum = Math.max(maximum, Math.abs(
                    bind.x - positions[offset]));
            maximum = Math.max(maximum, Math.abs(
                    bind.y - positions[offset + 1]));
            maximum = Math.max(maximum, Math.abs(
                    bind.z - positions[offset + 2]));
        }
        return maximum;
    }

    private static void validateContract(JsonObject contract,
                                         JsonObject proxy)
    {
        require(contract.get("schema").getAsInt() == 1
                && "D".equals(contract.get("phase").getAsString()),
                "weighted proxy contract schema or phase differs");
        require("AFTER_RECURSION_RESEARCH_PROXY".equals(
                contract.get("status").getAsString()),
                "weighted proxy is not research-only");
        require((ProjectSeele.MODID
                + ":eva/eva_unit01_inner_proxy.skinned.json").equals(
                contract.get("proxyResource").getAsString()),
                "weighted proxy resource differs");
        JsonObject activation = contract.getAsJsonObject(
                "runtimeActivation");
        require(!activation.get("defaultEnabled").getAsBoolean()
                && !activation.get("replacesTigerBody").getAsBoolean()
                && !activation.get("writesPoseBones").getAsBoolean()
                && !activation.get("productionReady").getAsBoolean()
                && activation.get(
                "humanReviewRequiredBeforePromotion").getAsBoolean(),
                "weighted proxy escaped isolation");
        require("RESEARCH_PROXY_NOT_LIVE_BODY".equals(
                proxy.get("status").getAsString()),
                "weighted mesh resource claims live status");
        Map<String, Boolean> interfaces = new HashMap<>();
        for (JsonElement element : proxy.getAsJsonArray("segments"))
        {
            JsonObject segment = element.getAsJsonObject();
            interfaces.put(segment.get("parent").getAsString() + "->"
                    + segment.get("child").getAsString(), true);
        }
        for (JsonElement element : contract.getAsJsonArray(
                "requiredInterfaces"))
        {
            JsonArray pair = element.getAsJsonArray();
            require(interfaces.containsKey(pair.get(0).getAsString()
                    + "->" + pair.get(1).getAsString()),
                    "weighted proxy misses required interface");
        }
    }

    private static String read(ResourceManager resources,
                               ResourceLocation location) throws Exception
    {
        try (InputStream stream = resources.getResource(location)
                .orElseThrow(() -> new IllegalStateException(
                        "missing weighted proxy resource " + location)).open())
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

    private static void require(boolean condition, String message)
    {
        if (!condition) throw new IllegalArgumentException(message);
    }

    public record Status(boolean ready, boolean previewEnabled,
                         int paletteBones, int segments, int vertices,
                         int triangles, int blendedVertices,
                         String contractSha256, String proxySha256,
                         long renderedFrames, int lastEntityId,
                         float lastBindDelta, String failure)
    {
        private static Status missing()
        {
            return failed("not_loaded");
        }

        private static Status failed(String reason)
        {
            return new Status(false, EvaWeightedInnerProxy.previewEnabled(),
                    0, 0, 0, 0, 0,
                    "missing", "missing", 0L, -1, -1.0F,
                    reason == null ? "failed" : reason);
        }

        private Status withRender(int entityId, float bindDelta)
        {
            return new Status(this.ready,
                    EvaWeightedInnerProxy.previewEnabled(),
                    this.paletteBones, this.segments, this.vertices,
                    this.triangles, this.blendedVertices,
                    this.contractSha256, this.proxySha256,
                    this.renderedFrames + 1L, entityId, bindDelta, "none");
        }

        private Status withFailure(String reason)
        {
            return new Status(false,
                    EvaWeightedInnerProxy.previewEnabled(),
                    this.paletteBones, this.segments, this.vertices,
                    this.triangles, this.blendedVertices,
                    this.contractSha256, this.proxySha256,
                    this.renderedFrames, this.lastEntityId,
                    this.lastBindDelta,
                    reason == null ? "failed" : reason);
        }
    }
}
