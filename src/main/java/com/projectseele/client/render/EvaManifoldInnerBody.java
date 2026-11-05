package com.projectseele.client.render;

import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

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

/** Phase-E single-component inner body, isolated from the live Tiger body. */
public final class EvaManifoldInnerBody
{
    private static final boolean MANIFOLD_PREVIEW_R58=Boolean.getBoolean("projectseele.manifoldInnerPreview");
    private static final boolean MANIFOLD_AUDIT_R58=Boolean.getBoolean("projectseele.manifoldInnerAuditOnly");

    private static final int ORIENTATION_CORRECTION_SWEEPS = 48;
    private static final float ORIENTATION_TARGET_DOT = 1.0E-5F;
    private static final float ORIENTATION_MAX_VERTEX_DELTA = 0.10F;
    private static final ResourceLocation CONTRACT = new ResourceLocation(
            ProjectSeele.MODID, "eva/eva_manifold_inner_contract.json");
    private static final ResourceLocation BODY = new ResourceLocation(
            ProjectSeele.MODID,
            "eva/eva_unit01_manifold_inner.skinned.json");
    private static final ResourceLocation MASKS = new ResourceLocation(
            ProjectSeele.MODID, "eva/eva_unit01_rigid_shell_masks.json");
    private static volatile EvaSkinnedMeshRuntime.MeshData mesh;
    private static volatile Status status = Status.missing();
    private static final Map<Integer, FrameSnapshot> FRAME_SNAPSHOTS =
            new ConcurrentHashMap<>();
    private static boolean firstRenderLogged;

    private EvaManifoldInnerBody() {}

    public static void reload(ResourceManager resources)
    {
        mesh = null;
        FRAME_SNAPSHOTS.clear();
        firstRenderLogged = false;
        try
        {
            String contractText = read(resources, CONTRACT);
            String bodyText = read(resources, BODY);
            String maskText = read(resources, MASKS);
            JsonObject contract = JsonParser.parseString(
                    contractText).getAsJsonObject();
            JsonObject body = JsonParser.parseString(
                    bodyText).getAsJsonObject();
            JsonObject masks = JsonParser.parseString(
                    maskText).getAsJsonObject();
            validateContract(contract, body, masks);
            EvaSkinnedMeshRuntime.MeshData loaded =
                    EvaSkinnedMeshRuntime.load(resources, BODY);
            JsonObject expected = contract.getAsJsonObject("expected");
            JsonObject manifold = body.getAsJsonObject("manifold");
            require(loaded.palette().size() ==
                    expected.get("paletteBones").getAsInt(),
                    "manifold palette count differs");
            require(loaded.vertices().size() ==
                    expected.get("vertices").getAsInt(),
                    "manifold vertex count differs");
            require(loaded.indices().length / 3 ==
                    expected.get("triangles").getAsInt(),
                    "manifold triangle count differs");
            mesh = loaded;
            status = new Status(true, previewEnabled(),
                    loaded.palette().size(),
                    manifold.get("primitiveCount").getAsInt(),
                    loaded.vertices().size(), loaded.indices().length / 3,
                    manifold.get("components").getAsInt(),
                    manifold.get("nonManifoldEdges").getAsInt(),
                    manifold.get("eulerCharacteristic").getAsInt(),
                    masks.get("sourcePartCount").getAsInt(),
                    masks.get("sourceTriangleCount").getAsInt(),
                    sha256(contractText), sha256(bodyText),
                    sha256(maskText), 0L, -1, -1.0F, "none");
            ProjectSeele.LOGGER.info(
                    "EVA manifold inner body loaded: palette={} primitives={} "
                            + "vertices={} triangles={} components={} "
                            + "nonManifoldEdges={} euler={} rigidParts={} "
                            + "rigidTriangles={} previewEnabled={} "
                            + "replacesTiger=false",
                    status.paletteBones(), status.primitives(),
                    status.vertices(), status.triangles(),
                    status.components(), status.nonManifoldEdges(),
                    status.eulerCharacteristic(), status.rigidParts(),
                    status.rigidTriangles(), status.previewEnabled());
        }
        catch (Exception exception)
        {
            status = Status.failed(exception.getMessage());
            ProjectSeele.LOGGER.error(
                    "EVA manifold inner body rejected", exception);
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
        Map<String, GeoBone> bones = new LinkedHashMap<>();
        collect(root, bones);
        Matrix4f[] palette = new Matrix4f[current.palette().size()];
        for (int index = 0; index < palette.length; index++)
        {
            String name = current.palette().get(index);
            GeoBone bone = bones.get(name);
            if (bone == null || !bone.isTrackingMatrices())
            {
                status = status.withFailure(
                        "missing tracked manifold bone " + name);
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
            CorrectionMetrics correction = correctOrientations(
                    current, positions, normals);
            int[] indices = current.indices();
            if (!auditOnly())
            {
                VertexConsumer target = bufferSource.getBuffer(
                        RenderType.entityTranslucent(
                                EvaUnit01Renderer.textureResourceForVariant(
                                        entity.getUnitVariant())));
                Matrix4f pose = poseStack.last().pose();
                Matrix3f normal = poseStack.last().normal();
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
            }
            float bindDelta = maximumBindDelta(current, positions);
            status = status.withRender(entity.getId(), bindDelta);
            FrameMetrics metrics = auditFrame(current, positions, normals);
            List<float[]> paletteMatrices = new ArrayList<>();
            for (Matrix4f matrix : palette)
            {
                float[] values = new float[16];
                matrix.get(values);
                paletteMatrices.add(values);
            }
            List<String> boneNames = new ArrayList<>();
            List<float[]> boneMatrices = new ArrayList<>();
            for (Map.Entry<String, GeoBone> entry : bones.entrySet())
            {
                boneNames.add(entry.getKey());
                float[] values = new float[16];
                entry.getValue().getModelSpaceMatrix().get(values);
                boneMatrices.add(values);
            }
            FRAME_SNAPSHOTS.put(entity.getId(), new FrameSnapshot(
                    true, entity.getId(),
                    status.renderedFrames(), List.copyOf(current.palette()),
                    List.copyOf(paletteMatrices), List.copyOf(boneNames),
                    List.copyOf(boneMatrices), metrics.triangles,
                    metrics.invertedTriangles,
                    metrics.collapsedTriangles, metrics.minimumDoubleArea,
                    metrics.bounds, correction.sweeps,
                    correction.maximumVertexDelta));
            if (!firstRenderLogged)
            {
                firstRenderLogged = true;
                ProjectSeele.LOGGER.info(
                        "EVA manifold inner body rendered after recursion: "
                                + "entity={} palette={} vertices={} "
                                + "triangles={} bindDelta={} inverted={} "
                                + "collapsed={} minDoubleArea={} "
                                + "correctionSweeps={} correctionMax={} "
                                + "auditOnly={} replacesTiger=false",
                        entity.getId(), current.palette().size(),
                        current.vertices().size(), indices.length / 3,
                        bindDelta, metrics.invertedTriangles,
                        metrics.collapsedTriangles,
                        metrics.minimumDoubleArea, correction.sweeps,
                        correction.maximumVertexDelta, auditOnly());
            }
        }
        catch (Exception exception)
        {
            status = status.withFailure(exception.getMessage());
            ProjectSeele.LOGGER.error(
                    "EVA manifold inner body render failed", exception);
        }
    }

    public static boolean previewEnabled()
    {
        return MANIFOLD_PREVIEW_R58;
    }

    public static boolean auditOnly()
    {
        return MANIFOLD_AUDIT_R58;
    }

    public static Status status()
    {
        return status;
    }

    public static FrameSnapshot frameSnapshot(int entityId)
    {
        return FRAME_SNAPSHOTS.getOrDefault(
                entityId, FrameSnapshot.missing());
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
                .color(128, 255, 128, 106)
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

    private static FrameMetrics auditFrame(
            EvaSkinnedMeshRuntime.MeshData meshData, float[] positions,
            Vector3f[] normals)
    {
        int inverted = 0;
        int collapsed = 0;
        float minimumArea = Float.POSITIVE_INFINITY;
        float[] bounds = new float[] {Float.POSITIVE_INFINITY,
                Float.POSITIVE_INFINITY, Float.POSITIVE_INFINITY,
                Float.NEGATIVE_INFINITY, Float.NEGATIVE_INFINITY,
                Float.NEGATIVE_INFINITY};
        for (int index = 0; index < meshData.vertices().size(); index++)
        {
            int offset = index * 3;
            bounds[0] = Math.min(bounds[0], positions[offset]);
            bounds[1] = Math.min(bounds[1], positions[offset + 1]);
            bounds[2] = Math.min(bounds[2], positions[offset + 2]);
            bounds[3] = Math.max(bounds[3], positions[offset]);
            bounds[4] = Math.max(bounds[4], positions[offset + 1]);
            bounds[5] = Math.max(bounds[5], positions[offset + 2]);
        }
        int[] indices = meshData.indices();
        for (int index = 0; index < indices.length; index += 3)
        {
            int a = indices[index];
            int b = indices[index + 1];
            int c = indices[index + 2];
            Vector3f pa = position(positions, a);
            Vector3f edgeA = position(positions, b).sub(pa);
            Vector3f edgeB = position(positions, c).sub(pa);
            Vector3f face = edgeA.cross(edgeB);
            float area = face.length();
            minimumArea = Math.min(minimumArea, area);
            if (!Float.isFinite(area) || area <= 1.0E-7F)
            {
                collapsed++;
                continue;
            }
            Vector3f average = new Vector3f(normals[a])
                    .add(normals[b]).add(normals[c]);
            if (average.lengthSquared() <= 1.0E-10F
                    || face.dot(average) <= 0.0F)
            {
                inverted++;
            }
        }
        return new FrameMetrics(indices.length / 3, inverted, collapsed,
                minimumArea, bounds);
    }

    private static CorrectionMetrics correctOrientations(
            EvaSkinnedMeshRuntime.MeshData meshData, float[] positions,
            Vector3f[] normals)
    {
        float[] original = positions.clone();
        int[] indices = meshData.indices();
        int completedSweeps = 0;
        for (int sweep = 0; sweep < ORIENTATION_CORRECTION_SWEEPS; sweep++)
        {
            int changed = 0;
            for (int triangle = 0; triangle < indices.length;
                    triangle += 3)
            {
                int a = indices[triangle];
                int b = indices[triangle + 1];
                int c = indices[triangle + 2];
                int ao = a * 3;
                int bo = b * 3;
                int co = c * 3;
                float nx = normals[a].x + normals[b].x + normals[c].x;
                float ny = normals[a].y + normals[b].y + normals[c].y;
                float nz = normals[a].z + normals[b].z + normals[c].z;
                float normalLength = (float) Math.sqrt(
                        nx * nx + ny * ny + nz * nz);
                if (normalLength <= 1.0E-10F) continue;
                nx /= normalLength;
                ny /= normalLength;
                nz /= normalLength;
                float ux = positions[bo] - positions[ao];
                float uy = positions[bo + 1] - positions[ao + 1];
                float uz = positions[bo + 2] - positions[ao + 2];
                float vx = positions[co] - positions[ao];
                float vy = positions[co + 1] - positions[ao + 1];
                float vz = positions[co + 2] - positions[ao + 2];
                float fx = uy * vz - uz * vy;
                float fy = uz * vx - ux * vz;
                float fz = ux * vy - uy * vx;
                float signed = fx * nx + fy * ny + fz * nz;
                if (signed >= ORIENTATION_TARGET_DOT) continue;

                float gbx = vy * nz - vz * ny;
                float gby = vz * nx - vx * nz;
                float gbz = vx * ny - vy * nx;
                float gcx = ny * uz - nz * uy;
                float gcy = nz * ux - nx * uz;
                float gcz = nx * uy - ny * ux;
                float gax = -(gbx + gcx);
                float gay = -(gby + gcy);
                float gaz = -(gbz + gcz);
                float denominator = gax * gax + gay * gay + gaz * gaz
                        + gbx * gbx + gby * gby + gbz * gbz
                        + gcx * gcx + gcy * gcy + gcz * gcz;
                if (denominator <= 1.0E-12F) continue;
                float lambda = (ORIENTATION_TARGET_DOT - signed)
                        / denominator;
                positions[ao] += lambda * gax;
                positions[ao + 1] += lambda * gay;
                positions[ao + 2] += lambda * gaz;
                positions[bo] += lambda * gbx;
                positions[bo + 1] += lambda * gby;
                positions[bo + 2] += lambda * gbz;
                positions[co] += lambda * gcx;
                positions[co + 1] += lambda * gcy;
                positions[co + 2] += lambda * gcz;
                changed++;
            }
            completedSweeps = sweep + 1;
            if (changed == 0) break;
        }
        float maximum = 0.0F;
        for (int index = 0; index < positions.length; index += 3)
        {
            float dx = positions[index] - original[index];
            float dy = positions[index + 1] - original[index + 1];
            float dz = positions[index + 2] - original[index + 2];
            maximum = Math.max(maximum, (float) Math.sqrt(
                    dx * dx + dy * dy + dz * dz));
        }
        if (maximum > ORIENTATION_MAX_VERTEX_DELTA)
        {
            throw new IllegalStateException(
                    "manifold orientation correction exceeded " + maximum);
        }
        return new CorrectionMetrics(completedSweeps, maximum);
    }

    private static Vector3f position(float[] positions, int index)
    {
        int offset = index * 3;
        return new Vector3f(positions[offset], positions[offset + 1],
                positions[offset + 2]);
    }

    private static void validateContract(JsonObject contract,
                                         JsonObject body,
                                         JsonObject masks)
    {
        require(contract.get("schema").getAsInt() == 1
                && "E".equals(contract.get("phase").getAsString()),
                "manifold contract schema or phase differs");
        require("MANIFOLD_INNER_AND_RIGID_MASK_RESEARCH".equals(
                contract.get("status").getAsString()),
                "manifold contract is not research-only");
        JsonObject activation = contract.getAsJsonObject(
                "runtimeActivation");
        require(!activation.get("defaultEnabled").getAsBoolean()
                && !activation.get("replacesTigerBody").getAsBoolean()
                && !activation.get("productionReady").getAsBoolean()
                && activation.get(
                "humanReviewRequiredBeforePromotion").getAsBoolean(),
                "manifold body escaped isolation");
        require("RESEARCH_MANIFOLD_NOT_LIVE_BODY".equals(
                body.get("status").getAsString()),
                "manifold resource claims live status");
        JsonObject manifold = body.getAsJsonObject("manifold");
        require(manifold.get("components").getAsInt() == 1
                && manifold.get("nonManifoldEdges").getAsInt() == 0
                && manifold.get("eulerCharacteristic").getAsInt() == 2,
                "manifold topology metadata is invalid");
        require(manifold.get("orientationCorrectionSweeps").getAsInt()
                == ORIENTATION_CORRECTION_SWEEPS
                && Math.abs(manifold.get("orientationTargetDot").getAsFloat()
                - ORIENTATION_TARGET_DOT) <= 1.0E-9F
                && Math.abs(manifold.get(
                "orientationMaximumVertexDelta").getAsFloat()
                - ORIENTATION_MAX_VERTEX_DELTA) <= 1.0E-7F,
                "manifold correction contract differs");
        require("TIGER_SINGLE_OWNER_SHELL_MASK".equals(
                masks.get("status").getAsString()),
                "Tiger rigid mask status differs");
        JsonObject expected = contract.getAsJsonObject("expected");
        require(masks.get("sourcePartCount").getAsInt() ==
                expected.get("rigidParts").getAsInt()
                && masks.get("sourceTriangleCount").getAsInt() ==
                expected.get("rigidTriangles").getAsInt(),
                "Tiger rigid mask counts differ");
    }

    private static String read(ResourceManager resources,
                               ResourceLocation location) throws Exception
    {
        try (InputStream stream = resources.getResource(location)
                .orElseThrow(() -> new IllegalStateException(
                        "missing manifold inner resource " + location)).open())
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
                         int paletteBones, int primitives, int vertices,
                         int triangles, int components,
                         int nonManifoldEdges, int eulerCharacteristic,
                         int rigidParts, int rigidTriangles,
                         String contractSha256, String bodySha256,
                         String maskSha256, long renderedFrames,
                         int lastEntityId, float lastBindDelta,
                         String failure)
    {
        private static Status missing()
        {
            return failed("not_loaded");
        }

        private static Status failed(String reason)
        {
            return new Status(false,
                    EvaManifoldInnerBody.previewEnabled(),
                    0, 0, 0, 0, 0, 0, 0, 0, 0,
                    "missing", "missing", "missing", 0L, -1, -1.0F,
                    reason == null ? "failed" : reason);
        }

        private Status withRender(int entityId, float bindDelta)
        {
            return new Status(this.ready,
                    EvaManifoldInnerBody.previewEnabled(),
                    this.paletteBones, this.primitives, this.vertices,
                    this.triangles, this.components,
                    this.nonManifoldEdges, this.eulerCharacteristic,
                    this.rigidParts, this.rigidTriangles,
                    this.contractSha256, this.bodySha256, this.maskSha256,
                    this.renderedFrames + 1L, entityId, bindDelta, "none");
        }

        private Status withFailure(String reason)
        {
            return new Status(false,
                    EvaManifoldInnerBody.previewEnabled(),
                    this.paletteBones, this.primitives, this.vertices,
                    this.triangles, this.components,
                    this.nonManifoldEdges, this.eulerCharacteristic,
                    this.rigidParts, this.rigidTriangles,
                    this.contractSha256, this.bodySha256, this.maskSha256,
                    this.renderedFrames, this.lastEntityId,
                    this.lastBindDelta,
                    reason == null ? "failed" : reason);
        }
    }

    private record FrameMetrics(int triangles, int invertedTriangles,
                                int collapsedTriangles,
                                float minimumDoubleArea, float[] bounds) {}

    private record CorrectionMetrics(int sweeps,
                                     float maximumVertexDelta) {}

    public record FrameSnapshot(boolean ready, int entityId, long serial,
                                List<String> palette,
                                List<float[]> paletteMatrices,
                                List<String> boneNames,
                                List<float[]> boneMatrices, int triangles,
                                int invertedTriangles,
                                int collapsedTriangles,
                                float minimumDoubleArea, float[] bounds,
                                int correctionSweeps,
                                float maximumCorrection)
    {
        private static FrameSnapshot missing()
        {
            return new FrameSnapshot(false, -1, 0L, List.of(), List.of(),
                    List.of(), List.of(), 0, 0, 0, Float.NaN,
                    new float[0], 0, Float.NaN);
        }
    }
}
