package com.projectseele.world;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;
import java.util.WeakHashMap;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;

/** Root's explicit translation of the inherited headquarters devices only.
 * Terminal and EVA plant coordinates never pass through this frame. */
public final class NervHeadquartersFrameR52
{
    public static final String FILE = "r52/headquarters.json";
    public record Frame(long epoch, String directoryFingerprint, BlockPos translation,
                        String commandDoorManifest, String commandDoorSha256)
    {
        public BlockPos apply(BlockPos original) { return original.offset(translation); }
        public BlockPos inverse(BlockPos actual) { return actual.subtract(translation); }
        public Vec3 apply(Vec3 original) { return original.add(translation.getX(), translation.getY(), translation.getZ()); }
        public AABB apply(AABB original) { return original.move(translation.getX(), translation.getY(), translation.getZ()); }
        String identity() { return epoch + "/" + directoryFingerprint + "/" + translation + "/" + commandDoorManifest + "/" + commandDoorSha256; }
    }
    private static final class State
    {
        final NervManifestPollR52 poll = new NervManifestPollR52();
        int observed = Integer.MIN_VALUE;
        long epoch, modified = -1, size = -1;
        String fingerprint = "", fault = "";
        Frame frame;
    }
    private static final Map<ServerLevel, State> STATES = new WeakHashMap<>();

    public static Frame frame(ServerLevel level)
    {
        if (level == null || !level.dimension().equals(FacilitySchemaV2.DIMENSION)
                || !NervRouteRuntimeR52.claimed(level)) return null;
        State state = STATES.computeIfAbsent(level, ignored -> new State());
        int tick = level.getServer().getTickCount();
        long epoch = NervRouteRuntimeR52.commissioningEpoch(level);
        String fingerprint = NervRouteRuntimeR52.directoryFingerprint(level);
        if (state.epoch != epoch || !state.fingerprint.equals(fingerprint))
        {
            state.epoch = epoch; state.fingerprint = fingerprint;
            state.frame = null; state.modified = -1; state.poll.invalidate();
            state.observed = Integer.MIN_VALUE;
        }
        if (state.observed == tick) return state.frame;
        state.observed = tick;
        try
        {
            Path path = level.getServer().getWorldPath(LevelResource.ROOT).resolve(FILE);
            var probe = state.poll.probe(path, tick);
            if (!probe.available()) { state.frame = null; return null; }
            if (probe.changed() && (state.frame == null || state.modified != probe.modified() || state.size != probe.size()))
            {
                if (probe.size() > 65536) throw new IllegalArgumentException("Bounded headquarters declaration required");
                state.frame = parse(JsonParser.parseString(Files.readString(path)).getAsJsonObject(), epoch, fingerprint);
                state.modified = probe.modified(); state.size = probe.size(); state.fault = "";
            }
            return state.frame;
        }
        catch (Exception failure)
        {
            state.frame = null;
            if (state.poll.warningDue(failure.toString(), tick))
                ProjectSeele.LOGGER.warn("R52 headquarters devices held; old coordinates remain retired: {}", failure.toString());
            state.fault = failure.toString();
            return null;
        }
    }
    public static boolean bound(ServerLevel level) { return frame(level) != null; }
    public static void invalidate(ServerLevel level)
    {
        var state = STATES.get(level);
        if (state != null) { state.observed = Integer.MIN_VALUE; state.modified = -1; state.poll.invalidate(); }
    }
    public static Frame parse(JsonObject root, long epoch, String fingerprint)
    {
        if (!"projectseele.r52.headquarters-frame.v1".equals(root.get("schema").getAsString())
                || !"projectseele:geofront".equals(root.get("dimension").getAsString())
                || !"headquarters".equals(root.get("component").getAsString())
                || !root.get("installed").getAsBoolean()
                || root.get("epoch").getAsLong() != epoch || epoch <= 0
                || !fingerprint.matches("[0-9a-f]{64}")
                || !fingerprint.equals(root.get("directory_fingerprint").getAsString()))
            throw new IllegalArgumentException("Root headquarters declaration does not match the current claim");
        var row = root.getAsJsonArray("translation");
        if (row == null || row.size() != 3) throw new IllegalArgumentException("Three-axis headquarters translation required");
        int[] delta = new int[3];
        for (int i = 0; i < 3; i++)
        {
            double value = row.get(i).getAsDouble();
            if (!Double.isFinite(value) || value != Math.rint(value) || Math.abs(value) > 4096)
                throw new IllegalArgumentException("Integral bounded headquarters translation required");
            delta[i] = (int)value;
        }
        BlockPos translation = new BlockPos(delta[0], delta[1], delta[2]);
        // Root's R52 scope approves this complete headquarters translation.
        // A Terminal or hangar declaration cannot be relabelled as this frame.
        if (!translation.equals(new BlockPos(0, -93, 0)))
            throw new IllegalArgumentException("Headquarters frame differs from Root's approved component translation");
        String manifest = root.get("command_door_manifest").getAsString();
        Path relative = Path.of(manifest);
        if (relative.isAbsolute() || manifest.contains(":") || manifest.contains("\\")
                || !manifest.startsWith("r52/") || manifest.contains("..") || !manifest.endsWith(".json"))
            throw new IllegalArgumentException("Root world-relative headquarters door declaration required");
        String sha = root.get("command_door_sha256").getAsString();
        if (!sha.matches("[0-9a-f]{64}")) throw new IllegalArgumentException("Actual headquarters door artifact hash required");
        return new Frame(epoch, fingerprint, translation, manifest, sha);
    }
    private NervHeadquartersFrameR52() {}
}
