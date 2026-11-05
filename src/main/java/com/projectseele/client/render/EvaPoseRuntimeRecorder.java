package com.projectseele.client.render;

import java.io.BufferedWriter;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.EvaUnit01Entity;
import net.minecraft.client.Camera;
import net.minecraft.client.Minecraft;
import net.minecraft.network.chat.Component;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import org.joml.Matrix4f;
import software.bernie.geckolib.cache.object.GeoBone;

/** Records the final matrices emitted by the real Gecko render path. */
public final class EvaPoseRuntimeRecorder
{
    private static final boolean SMOKE_R58=Boolean.getBoolean("projectseele.poseCaptureSmoke");

    private static final int MAX_FRAMES = 900;
    private static final int SMOKE_FRAMES = 1;
    private static final DateTimeFormatter FILE_TIME =
            DateTimeFormatter.ofPattern("yyyyMMdd_HHmmss");
    private static Session session;
    private static FrameCapture currentFrame;
    private static boolean smokeStarted;

    private EvaPoseRuntimeRecorder() {}

    public static boolean wants(EvaUnit01Entity entity)
    {
        return session != null && session.entityId == entity.getId();
    }

    /** Makes the one-frame userdev smoke deterministic across camera angles. */
    public static boolean requestsSmokeRender()
    {
        return SMOKE_R58
                && !smokeStarted && session == null;
    }

    /** Development-only smoke hook; it never changes entity or animation state. */
    public static void maybeStartSmoke(EvaUnit01Entity entity)
    {
        if (!SMOKE_R58
                || smokeStarted || session != null || !EvaPoseGraph.ready()
                || entity.getMotionLabPhysicsPreview() != 0
                || entity.getVisualPose() != EvaUnit01Entity.VISUAL_NORMAL)
        {
            return;
        }
        smokeStarted = true;
        String label = EvaManifoldInnerBody.previewEnabled()
                ? "phase_e_smoke"
                : EvaWeightedInnerProxy.previewEnabled()
                        ? "phase_d_smoke" : "phase_c_smoke";
        start(entity.getId(), label);
    }

    public static void start(int entityId, String rawLabel)
    {
        stop(false, "replaced");
        if (!EvaPoseGraph.ready())
        {
            notifyPlayer("EVA PoseGraph contracts are not loaded.");
            return;
        }
        String label = sanitize(rawLabel);
        Path directory = Minecraft.getInstance().gameDirectory.toPath()
                .resolve("pose-captures");
        try
        {
            Files.createDirectories(directory);
            String stem = "eva_pose_" + LocalDateTime.now().format(FILE_TIME)
                    + "_" + label;
            Path frames = directory.resolve(stem + ".jsonl");
            Path owners = directory.resolve(stem + ".owners.json");
            BufferedWriter writer = Files.newBufferedWriter(frames,
                    StandardCharsets.UTF_8, StandardOpenOption.CREATE_NEW,
                    StandardOpenOption.WRITE);
            int frameLimit = Boolean.getBoolean(
                    "projectseele.poseCaptureSmoke")
                    ? SMOKE_FRAMES : MAX_FRAMES;
            session = new Session(entityId, label, frames, owners, writer,
                    frameLimit);
            writeHeader(session);
            notifyPlayer("EVA final-pose recording started: "
                    + frames.toAbsolutePath());
            ProjectSeele.LOGGER.info(
                    "EVA final-pose recording started: entity={} label={} path={}",
                    entityId, label, frames.toAbsolutePath());
        }
        catch (Exception exception)
        {
            session = null;
            ProjectSeele.LOGGER.error(
                    "Unable to start EVA final-pose recording", exception);
            notifyPlayer("EVA final-pose recording failed to start: "
                    + exception.getMessage());
        }
    }

    public static void stopByCommand()
    {
        if (session == null)
        {
            notifyPlayer("No EVA final-pose recording is active.");
            return;
        }
        stop(true, "operator_stop");
    }

    public static void showStatus()
    {
        Session active = session;
        notifyPlayer(active == null
                ? "No EVA final-pose recording is active."
                : "EVA final-pose recording: frames=" + active.frameIndex
                        + "/" + active.frameLimit + " path="
                        + active.frames.toAbsolutePath());
    }

    public static void beginFrame(EvaUnit01Entity entity, float partialTick)
    {
        Session active = session;
        if (active == null || active.entityId != entity.getId())
        {
            return;
        }
        EvaPoseGraph.Snapshot pose = EvaPoseGraph.observe(entity, partialTick);
        if (!pose.eligibleForHumanReview())
        {
            stop(true, "ineligible_pose_authority:" + pose.actionToken());
            return;
        }
        currentFrame = new FrameCapture(active.frameIndex, partialTick, pose,
                new LinkedHashMap<>());
    }

    public static void trackMatrices(GeoBone bone)
    {
        if (session != null)
        {
            bone.setTrackingMatrices(true);
        }
    }

    public static void captureBone(EvaUnit01Entity entity, GeoBone bone,
                                   boolean isReRender)
    {
        FrameCapture frame = currentFrame;
        if (frame == null || isReRender || !wants(entity))
        {
            return;
        }
        String rotationOwner = frame.pose.owners().getOrDefault(
                bone.getName(), "UNDECLARED_VARIANT_BONE");
        String positionOwner = frame.pose.positionOwners().getOrDefault(
                bone.getName(), "UNDECLARED_VARIANT_BONE");
        String scaleOwner = frame.pose.scaleOwners().getOrDefault(
                bone.getName(), "UNDECLARED_VARIANT_BONE");
        frame.bones.put(bone.getName(), new BoneCapture(rotationOwner,
                positionOwner, scaleOwner,
                bone.isHidden(), matrix(bone.getLocalSpaceMatrix()),
                matrix(bone.getModelSpaceMatrix()),
                matrix(bone.getWorldSpaceMatrix()),
                new float[] {bone.getPosX(), bone.getPosY(), bone.getPosZ()},
                new float[] {bone.getRotX(), bone.getRotY(), bone.getRotZ()},
                new float[] {bone.getScaleX(), bone.getScaleY(),
                        bone.getScaleZ()}));
    }

    public static void endFrame(EvaUnit01Entity entity)
    {
        Session active = session;
        FrameCapture frame = currentFrame;
        currentFrame = null;
        if (active == null || frame == null || active.entityId != entity.getId())
        {
            return;
        }
        try
        {
            frame = new FrameCapture(frame.index, frame.partialTick,
                    EvaPoseGraph.committedSnapshot(entity, frame.pose),
                    frame.bones);
            JsonObject json = frameJson(entity, frame);
            active.writer.write(json.toString());
            active.writer.newLine();
            active.recordOwners(frame.pose);
            active.recordAction(frame.pose.actionToken());
            active.frameIndex++;
            if (active.frameIndex % 30 == 0)
            {
                active.writer.flush();
            }
            if (active.frameIndex >= active.frameLimit)
            {
                stop(true, "frame_limit");
            }
        }
        catch (Exception exception)
        {
            ProjectSeele.LOGGER.error(
                    "EVA final-pose frame recording failed", exception);
            stop(true, "write_failure");
        }
    }

    private static JsonObject frameJson(EvaUnit01Entity entity,
                                        FrameCapture frame)
    {
        JsonObject root = new JsonObject();
        root.addProperty("type", "frame");
        root.addProperty("frame", frame.index);
        root.addProperty("clientTick", entity.tickCount);
        root.addProperty("partialTick", frame.partialTick);
        root.addProperty("renderNanos", System.nanoTime());
        root.add("entity", entityJson(entity));
        root.add("camera", cameraJson());
        root.add("poseGraph", poseJson(frame.pose));
        root.add("contacts", contactsJson(entity));
        root.add("weightedProxy", weightedProxyJson());
        root.add("manifoldInner", manifoldInnerJson());

        LocalVisualAssetFingerprint.Fingerprint fingerprint =
                EvaUnit01Renderer.visualFingerprintForVariant(
                        entity.getUnitVariant());
        JsonObject resources = new JsonObject();
        resources.addProperty("compactTag", fingerprint.compactTag());
        resources.addProperty("sourcePack", fingerprint.sourcePack());
        resources.addProperty("valid", fingerprint.valid());
        for (Map.Entry<String, LocalVisualAssetFingerprint.ResourceDigest> entry
                : fingerprint.resources().entrySet())
        {
            resources.addProperty(entry.getKey() + "Sha256",
                    entry.getValue().sha256());
        }
        root.add("resources", resources);

        JsonObject bones = new JsonObject();
        for (Map.Entry<String, BoneCapture> entry : frame.bones.entrySet())
        {
            BoneCapture capture = entry.getValue();
            JsonObject bone = new JsonObject();
            bone.addProperty("owner", capture.rotationOwner);
            bone.addProperty("rotationOwner", capture.rotationOwner);
            bone.addProperty("positionOwner", capture.positionOwner);
            bone.addProperty("scaleOwner", capture.scaleOwner);
            bone.addProperty("hidden", capture.hidden);
            bone.add("localMatrix", floats(capture.localMatrix));
            bone.add("modelMatrix", floats(capture.modelMatrix));
            bone.add("worldMatrix", floats(capture.worldMatrix));
            bone.add("finalPosition", floats(capture.position));
            bone.add("finalRotationRadians", floats(capture.rotation));
            bone.add("finalScale", floats(capture.scale));
            bones.add(entry.getKey(), bone);
        }
        root.add("bones", bones);

        JsonArray missing = new JsonArray();
        for (String canonical : EvaPoseGraph.contract().boneOrder())
        {
            if (!frame.bones.containsKey(canonical))
            {
                missing.add(canonical);
            }
        }
        root.add("missingCanonicalBones", missing);
        root.add("sockets", socketJson(entity, frame));
        return root;
    }

    private static JsonObject entityJson(EvaUnit01Entity entity)
    {
        JsonObject json = new JsonObject();
        json.addProperty("id", entity.getId());
        json.addProperty("uuid", entity.getStringUUID());
        json.addProperty("variant", entity.getUnitVariant());
        json.add("position", vector(entity.position()));
        json.add("velocity", vector(entity.getDeltaMovement()));
        json.addProperty("yaw", entity.getYRot());
        json.addProperty("bodyYaw", entity.yBodyRot);
        json.addProperty("weapon", entity.getWeapon());
        json.addProperty("crouching", entity.isPilotCrouching());
        json.addProperty("prone", entity.isPilotProne());
        json.addProperty("sprinting", entity.isPilotSprinting());
        json.addProperty("visualPose", entity.getVisualPose());
        json.addProperty("motionPreview", entity.getMotionLabPhysicsPreview());
        AABB box = entity.getBoundingBox();
        json.add("aabb", floats(new float[] {(float)box.minX,
                (float)box.minY, (float)box.minZ, (float)box.maxX,
                (float)box.maxY, (float)box.maxZ}));
        return json;
    }

    private static JsonObject cameraJson()
    {
        Minecraft minecraft = Minecraft.getInstance();
        Camera camera = minecraft.gameRenderer.getMainCamera();
        JsonObject json = new JsonObject();
        json.add("position", vector(camera.getPosition()));
        json.addProperty("yaw", camera.getYRot());
        json.addProperty("pitch", camera.getXRot());
        json.addProperty("fovOption", minecraft.options.fov().get());
        json.addProperty("cameraType",
                minecraft.options.getCameraType().name());
        return json;
    }

    private static JsonObject poseJson(EvaPoseGraph.Snapshot pose)
    {
        JsonObject json = new JsonObject();
        json.addProperty("actionToken", pose.actionToken());
        json.addProperty("phaseProgress", pose.phaseProgress());
        json.addProperty("actionLockStatus", pose.actionLockStatus());
        json.addProperty("committed", pose.committed());
        json.addProperty("commitSerial", pose.commitSerial());
        json.addProperty("eligibleForHumanReview",
                pose.eligibleForHumanReview());
        json.add("activeLayers", strings(pose.activeLayers()));
        json.add("upstreamSources", strings(pose.upstreamSources()));
        JsonObject owners = new JsonObject();
        pose.owners().forEach(owners::addProperty);
        json.add("owners", owners);
        JsonObject positionOwners = new JsonObject();
        pose.positionOwners().forEach(positionOwners::addProperty);
        json.add("positionOwners", positionOwners);
        JsonObject scaleOwners = new JsonObject();
        pose.scaleOwners().forEach(scaleOwners::addProperty);
        json.add("scaleOwners", scaleOwners);
        JsonObject conflicts = new JsonObject();
        pose.conflicts().forEach((bone, values) ->
                conflicts.add(bone, strings(values)));
        json.add("ownerConflicts", conflicts);
        JsonObject upstreamOverlaps = new JsonObject();
        pose.upstreamOverlaps().forEach((bone, values) ->
                upstreamOverlaps.add(bone, strings(values)));
        json.add("upstreamOverlapCandidates", upstreamOverlaps);
        return json;
    }

    private static JsonObject contactsJson(EvaUnit01Entity entity)
    {
        JsonObject json = new JsonObject();
        json.addProperty("entityOnGround", entity.onGround());
        json.addProperty("leftFoot", "UNOBSERVED_PHASE_A");
        json.addProperty("rightFoot", "UNOBSERVED_PHASE_A");
        json.addProperty("leftHand", "UNOBSERVED_PHASE_A");
        json.addProperty("rightHand", "UNOBSERVED_PHASE_A");
        json.addProperty("weapon", "UNOBSERVED_PHASE_A");
        return json;
    }

    private static JsonObject weightedProxyJson()
    {
        EvaWeightedInnerProxy.Status proxy = EvaWeightedInnerProxy.status();
        JsonObject json = new JsonObject();
        json.addProperty("ready", proxy.ready());
        json.addProperty("previewEnabled", proxy.previewEnabled());
        json.addProperty("renderedFrames", proxy.renderedFrames());
        json.addProperty("lastEntityId", proxy.lastEntityId());
        json.addProperty("lastBindDelta", proxy.lastBindDelta());
        json.addProperty("failure", proxy.failure());
        return json;
    }

    private static JsonObject manifoldInnerJson()
    {
        EvaManifoldInnerBody.Status body = EvaManifoldInnerBody.status();
        JsonObject json = new JsonObject();
        json.addProperty("ready", body.ready());
        json.addProperty("previewEnabled", body.previewEnabled());
        json.addProperty("renderedFrames", body.renderedFrames());
        json.addProperty("lastEntityId", body.lastEntityId());
        json.addProperty("lastBindDelta", body.lastBindDelta());
        json.addProperty("failure", body.failure());
        return json;
    }

    private static JsonObject socketJson(EvaUnit01Entity entity,
                                         FrameCapture frame)
    {
        JsonObject json = new JsonObject();
        for (String name : new String[] {"hand_l", "hand_r", "knife",
                "cannon", "lance", "n2"})
        {
            BoneCapture bone = frame.bones.get(name);
            if (bone != null)
            {
                json.add(name, floats(bone.worldMatrix));
            }
        }
        Vec3 aim = entity.getAimDirectionForPoseCapture();
        json.add("aimDirection", vector(aim));
        Vec3 muzzle = entity.getMuzzlePositionForPoseCapture(aim);
        if (muzzle != null)
        {
            json.add("muzzleWorld", vector(muzzle));
        }
        return json;
    }

    private static void writeHeader(Session active) throws IOException
    {
        EvaPoseGraph.Contract contract = EvaPoseGraph.contract();
        JsonObject header = new JsonObject();
        header.addProperty("type", "header");
        header.addProperty("schema", 1);
        header.addProperty("captureContract",
                "FINAL_POST_CONTROLLER_GECKO_MATRICES");
        header.addProperty("label", active.label);
        header.addProperty("entityId", active.entityId);
        header.addProperty("maxFrames", active.frameLimit);
        header.addProperty("rigVersion", contract.rigVersion());
        header.addProperty("poseGraphVersion", contract.poseGraphVersion());
        header.addProperty("rigContractSha256", contract.rigSha256());
        header.addProperty("authorityContractSha256",
                contract.authoritySha256());
        header.addProperty("approvedActionsSha256",
                contract.actionsSha256());
        header.addProperty("poseGraphMode", contract.mode());
        EvaSkinnedMeshRuntime.Status skinning =
                EvaSkinnedMeshRuntime.status();
        header.addProperty("skinnedMeshRuntimeReady", skinning.ready());
        header.addProperty("skinnedMeshFormat", skinning.format());
        header.addProperty("skinnedMeshContractSha256",
                skinning.contractSha256());
        header.addProperty("skinnedMeshProbeSha256",
                skinning.probeSha256());
        header.addProperty("skinnedMeshPaletteBones",
                skinning.paletteBones());
        header.addProperty("skinnedMeshProbeVertices",
                skinning.vertices());
        header.addProperty("skinnedMeshProbeTriangles",
                skinning.triangles());
        header.addProperty("skinnedMeshBlendedVertices",
                skinning.blendedVertices());
        header.addProperty("skinnedMeshBindDelta", skinning.bindError());
        header.addProperty("skinnedMeshPoseDelta", skinning.probeError());
        header.addProperty("skinnedMeshNormalDelta", skinning.normalError());
        header.addProperty("skinnedLiveBodyEnabled",
                skinning.liveBodyEnabled());
        EvaWeightedInnerProxy.Status proxy =
                EvaWeightedInnerProxy.status();
        header.addProperty("weightedProxyReady", proxy.ready());
        header.addProperty("weightedProxyPreviewEnabled",
                proxy.previewEnabled());
        header.addProperty("weightedProxyPaletteBones",
                proxy.paletteBones());
        header.addProperty("weightedProxySegments", proxy.segments());
        header.addProperty("weightedProxyVertices", proxy.vertices());
        header.addProperty("weightedProxyTriangles", proxy.triangles());
        header.addProperty("weightedProxyBlendedVertices",
                proxy.blendedVertices());
        header.addProperty("weightedProxyContractSha256",
                proxy.contractSha256());
        header.addProperty("weightedProxyResourceSha256",
                proxy.proxySha256());
        header.addProperty("weightedProxyReplacesTiger", false);
        EvaManifoldInnerBody.Status manifold =
                EvaManifoldInnerBody.status();
        header.addProperty("manifoldInnerReady", manifold.ready());
        header.addProperty("manifoldInnerPreviewEnabled",
                manifold.previewEnabled());
        header.addProperty("manifoldInnerPaletteBones",
                manifold.paletteBones());
        header.addProperty("manifoldInnerPrimitives",
                manifold.primitives());
        header.addProperty("manifoldInnerVertices", manifold.vertices());
        header.addProperty("manifoldInnerTriangles",
                manifold.triangles());
        header.addProperty("manifoldInnerComponents",
                manifold.components());
        header.addProperty("manifoldInnerNonManifoldEdges",
                manifold.nonManifoldEdges());
        header.addProperty("manifoldInnerEuler",
                manifold.eulerCharacteristic());
        header.addProperty("manifoldRigidParts", manifold.rigidParts());
        header.addProperty("manifoldRigidTriangles",
                manifold.rigidTriangles());
        header.addProperty("manifoldContractSha256",
                manifold.contractSha256());
        header.addProperty("manifoldBodySha256", manifold.bodySha256());
        header.addProperty("manifoldMaskSha256", manifold.maskSha256());
        header.addProperty("manifoldReplacesTiger", false);
        header.addProperty("automaticVisualApproval", false);
        header.add("resultVocabulary", strings(List.of(
                "FAIL", "ELIGIBLE_FOR_HUMAN_REVIEW")));
        active.writer.write(header.toString());
        active.writer.newLine();
        active.writer.flush();
    }

    private static void stop(boolean notify, String reason)
    {
        Session active = session;
        session = null;
        currentFrame = null;
        if (active == null)
        {
            return;
        }
        try
        {
            JsonObject footer = new JsonObject();
            footer.addProperty("type", "footer");
            footer.addProperty("frames", active.frameIndex);
            footer.addProperty("stopReason", reason);
            active.writer.write(footer.toString());
            active.writer.newLine();
            active.writer.flush();
            active.writer.close();
            writeOwnerTimeline(active, reason);
        }
        catch (Exception exception)
        {
            ProjectSeele.LOGGER.error(
                    "Unable to finish EVA final-pose recording", exception);
        }
        ProjectSeele.LOGGER.info(
                "EVA final-pose recording stopped: frames={} reason={} path={}",
                active.frameIndex, reason, active.frames.toAbsolutePath());
        if (notify)
        {
            notifyPlayer("EVA final-pose recording stopped: frames="
                    + active.frameIndex + " reason=" + reason + " path="
                    + active.frames.toAbsolutePath());
        }
    }

    private static void writeOwnerTimeline(Session active, String reason)
            throws IOException
    {
        active.closeRanges();
        JsonObject root = new JsonObject();
        root.addProperty("schema", 1);
        root.addProperty("frames", active.frameIndex);
        root.addProperty("stopReason", reason);
        JsonObject bones = new JsonObject();
        active.ownerRanges.forEach((bone, ranges) ->
        {
            JsonArray values = new JsonArray();
            ranges.forEach(range -> values.add(range.toJson()));
            bones.add(bone, values);
        });
        root.add("boneOwnerTimeline", bones);
        root.add("boneRotationOwnerTimeline", bones.deepCopy());
        JsonObject positions = new JsonObject();
        active.positionOwnerRanges.forEach((bone, ranges) ->
        {
            JsonArray values = new JsonArray();
            ranges.forEach(range -> values.add(range.toJson()));
            positions.add(bone, values);
        });
        root.add("bonePositionOwnerTimeline", positions);
        JsonObject scales = new JsonObject();
        active.scaleOwnerRanges.forEach((bone, ranges) ->
        {
            JsonArray values = new JsonArray();
            ranges.forEach(range -> values.add(range.toJson()));
            scales.add(bone, values);
        });
        root.add("boneScaleOwnerTimeline", scales);
        JsonArray actions = new JsonArray();
        active.actionRanges.forEach(range -> actions.add(range.toJson()));
        root.add("actionTimeline", actions);
        Files.writeString(active.owners, root.toString() + "\n",
                StandardCharsets.UTF_8, StandardOpenOption.CREATE_NEW,
                StandardOpenOption.WRITE);
    }

    private static String sanitize(String raw)
    {
        String result = raw == null ? "capture" : raw.trim()
                .replaceAll("[^A-Za-z0-9._-]+", "_");
        if (result.isBlank()) result = "capture";
        return result.length() > 48 ? result.substring(0, 48) : result;
    }

    private static void notifyPlayer(String text)
    {
        Minecraft minecraft = Minecraft.getInstance();
        if (minecraft.player != null)
        {
            minecraft.player.displayClientMessage(
                    Component.literal(text), false);
        }
    }

    private static float[] matrix(Matrix4f matrix)
    {
        float[] values = new float[16];
        matrix.get(values);
        return values;
    }

    private static JsonArray floats(float[] values)
    {
        JsonArray array = new JsonArray();
        for (float value : values)
        {
            array.add(value);
        }
        return array;
    }

    private static JsonArray strings(List<String> values)
    {
        JsonArray array = new JsonArray();
        values.forEach(array::add);
        return array;
    }

    private static JsonArray vector(Vec3 vector)
    {
        JsonArray array = new JsonArray();
        array.add(vector.x);
        array.add(vector.y);
        array.add(vector.z);
        return array;
    }

    private record BoneCapture(String rotationOwner, String positionOwner,
                               String scaleOwner, boolean hidden,
                               float[] localMatrix, float[] modelMatrix,
                               float[] worldMatrix, float[] position,
                               float[] rotation, float[] scale) {}

    private record FrameCapture(int index, float partialTick,
                                EvaPoseGraph.Snapshot pose,
                                Map<String, BoneCapture> bones) {}

    private static final class TimelineRange
    {
        private int start;
        private int end;
        private final String value;

        private TimelineRange(int frame, String value)
        {
            this.start = frame;
            this.end = frame;
            this.value = value;
        }

        private JsonObject toJson()
        {
            JsonObject json = new JsonObject();
            json.addProperty("startFrame", this.start);
            json.addProperty("endFrame", this.end);
            json.addProperty("value", this.value);
            return json;
        }
    }

    private static final class Session
    {
        private final int entityId;
        private final String label;
        private final Path frames;
        private final Path owners;
        private final BufferedWriter writer;
        private final int frameLimit;
        private int frameIndex;
        private final Map<String, List<TimelineRange>> ownerRanges =
                new LinkedHashMap<>();
        private final Map<String, List<TimelineRange>> positionOwnerRanges =
                new LinkedHashMap<>();
        private final Map<String, List<TimelineRange>> scaleOwnerRanges =
                new LinkedHashMap<>();
        private final List<TimelineRange> actionRanges = new ArrayList<>();

        private Session(int entityId, String label, Path frames, Path owners,
                        BufferedWriter writer, int frameLimit)
        {
            this.entityId = entityId;
            this.label = label;
            this.frames = frames;
            this.owners = owners;
            this.writer = writer;
            this.frameLimit = frameLimit;
        }

        private void recordOwners(EvaPoseGraph.Snapshot pose)
        {
            pose.owners().forEach((bone, owner) -> append(
                    this.ownerRanges.computeIfAbsent(
                            bone, ignored -> new ArrayList<>()), owner));
            pose.positionOwners().forEach((bone, owner) -> append(
                    this.positionOwnerRanges.computeIfAbsent(
                            bone, ignored -> new ArrayList<>()), owner));
            pose.scaleOwners().forEach((bone, owner) -> append(
                    this.scaleOwnerRanges.computeIfAbsent(
                            bone, ignored -> new ArrayList<>()), owner));
        }

        private void recordAction(String action)
        {
            append(this.actionRanges, action);
        }

        private void append(List<TimelineRange> ranges, String value)
        {
            if (!ranges.isEmpty())
            {
                TimelineRange last = ranges.get(ranges.size() - 1);
                if (last.value.equals(value))
                {
                    last.end = this.frameIndex;
                    return;
                }
            }
            ranges.add(new TimelineRange(this.frameIndex, value));
        }

        private void closeRanges()
        {
            int last = Math.max(0, this.frameIndex - 1);
            this.ownerRanges.values().forEach(ranges ->
            {
                if (!ranges.isEmpty()) ranges.get(ranges.size() - 1).end = last;
            });
            this.positionOwnerRanges.values().forEach(ranges ->
            {
                if (!ranges.isEmpty()) ranges.get(ranges.size() - 1).end = last;
            });
            this.scaleOwnerRanges.values().forEach(ranges ->
            {
                if (!ranges.isEmpty()) ranges.get(ranges.size() - 1).end = last;
            });
            if (!this.actionRanges.isEmpty())
                this.actionRanges.get(this.actionRanges.size() - 1).end = last;
        }
    }
}
