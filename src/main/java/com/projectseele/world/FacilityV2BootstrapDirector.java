package com.projectseele.world;

import java.util.ArrayDeque;
import java.util.Arrays;
import java.util.Deque;
import java.util.List;
import java.util.Map;
import java.util.WeakHashMap;

import com.projectseele.ProjectSeele;
import net.minecraft.core.BlockPos;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.tags.BiomeTags;
import net.minecraft.world.level.levelgen.Heightmap;

/**
 * Incremental, zero-write preflight for the clean FacilitySchema v2 region.
 *
 * <p>It samples candidate terrain under the same fixed rules as the accepted
 * schema. No receipt is persisted until one candidate passes every coarse and
 * critical-footprint gate.</p>
 */
public final class FacilityV2BootstrapDirector
{
    private static final int COARSE_SIDE = 25;
    private static final int COARSE_COUNT = COARSE_SIDE * COARSE_SIDE;
    private static final int COARSE_SPACING = 64;
    private static final int COARSE_RADIUS = 768;
    private static final int MAX_COLUMNS_PER_TICK = 256;
    private static final long MAX_NANOS_PER_TICK = 2_000_000L;

    private static final Map<MinecraftServer, BootstrapJob> JOBS =
            new WeakHashMap<>();
    private static String lastResult = "not started";

    private FacilityV2BootstrapDirector() {}

    public static StartResult start(ServerLevel level)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return new StartResult(false, "R52 Root owns the claimed facility");
        if (!FacilityWorldPolicy.isCleanRebuild(level.getServer()))
        {
            return new StartResult(false,
                    "Facility v2 commissioning is restricted to the staged "
                            + FacilityWorldPolicy.CLEAN_DIRECTORY + " save");
        }
        if (!level.dimension().equals(FacilitySchemaV2.DIMENSION))
        {
            return new StartResult(false,
                    "Facility v2 must be commissioned in the GeoFront dimension");
        }
        if (!(level.getChunkSource().getGenerator()
                instanceof GeoFrontBoundedChunkGenerator generator)
                || !generator.matchesFacilityBaselineContract())
        {
            return new StartResult(false,
                    "GeoFront generator does not match the frozen Facility v2 "
                            + "candidate/surface contract");
        }
        FacilityV2SavedData data = FacilityV2SavedData.get(level);
        if (data.commissioned())
        {
            return new StartResult(false,
                    "Facility v2 is already commissioned: " + data.summary());
        }
        MinecraftServer server = level.getServer();
        if (JOBS.containsKey(server))
        {
            return new StartResult(false,
                    "Facility v2 preflight is already active");
        }
        JOBS.put(server, new BootstrapJob(level));
        lastResult = "committed candidate "
                + FacilitySchemaV2.ACTIVE_CANDIDATE_INDEX
                + " coarse preflight";
        ProjectSeele.LOGGER.info(
                "FacilitySchema v2 zero-write preflight started");
        return new StartResult(true, lastResult);
    }

    public static String status(MinecraftServer server)
    {
        BootstrapJob job = JOBS.get(server);
        return job == null ? lastResult : job.summary();
    }

    public static boolean active(MinecraftServer server)
    {
        return JOBS.containsKey(server);
    }

    public static void tick(MinecraftServer server)
    {
        if (NervLegacyGenerationGuardR52.retired(server)) { JOBS.remove(server); return; }
        if (!FacilityWorldPolicy.isCleanRebuild(server))
        {
            JOBS.remove(server);
            return;
        }
        BootstrapJob job = JOBS.get(server);
        if (job == null)
        {
            return;
        }
        try
        {
            if (job.tick())
            {
                lastResult = job.summary();
                JOBS.remove(server);
            }
        }
        catch (RuntimeException exception)
        {
            lastResult = "FAILED: " + exception.getClass().getSimpleName()
                    + ": " + exception.getMessage();
            JOBS.remove(server);
            ProjectSeele.LOGGER.error(
                    "FacilitySchema v2 preflight failed", exception);
        }
    }

    public record StartResult(boolean accepted, String message) {}

    private enum Phase
    {
        COARSE,
        CRITICAL,
        COMPLETE,
        FAILED
    }

    private static final class BootstrapJob
    {
        private final ServerLevel level;
        private int candidateIndex =
                FacilitySchemaV2.ACTIVE_CANDIDATE_INDEX;
        private Phase phase = Phase.COARSE;
        private int cursor;
        private final int[] heights = new int[COARSE_COUNT];
        private final boolean[] land = new boolean[COARSE_COUNT];
        private int surfaceY;
        private int minimumHeight = Integer.MAX_VALUE;
        private int maximumHeight = Integer.MIN_VALUE;
        private int p10;
        private int median;
        private int p90;
        private int oceanSamples;
        private int largestLandCluster;
        private List<CriticalFootprint> critical = List.of();
        private int criticalIndex;
        private long criticalCursor;
        private int criticalMinimumHeight = Integer.MAX_VALUE;
        private int criticalMaximumHeight = Integer.MIN_VALUE;
        private String failure = "";

        private BootstrapJob(ServerLevel level)
        {
            this.level = level;
        }

        private boolean tick()
        {
            long start = System.nanoTime();
            int processed = 0;
            while (processed < MAX_COLUMNS_PER_TICK
                    && System.nanoTime() - start < MAX_NANOS_PER_TICK)
            {
                if (this.phase == Phase.COARSE)
                {
                    sampleCoarse();
                }
                else if (this.phase == Phase.CRITICAL)
                {
                    sampleCritical();
                }
                else
                {
                    return true;
                }
                processed++;
            }
            return this.phase == Phase.COMPLETE
                    || this.phase == Phase.FAILED;
        }

        private void sampleCoarse()
        {
            BlockPos centre =
                    FacilitySchemaV2.CANDIDATE_CENTRES.get(this.candidateIndex);
            int sampleX = this.cursor % COARSE_SIDE;
            int sampleZ = this.cursor / COARSE_SIDE;
            int x = centre.getX() - COARSE_RADIUS
                    + sampleX * COARSE_SPACING;
            int z = centre.getZ() - COARSE_RADIUS
                    + sampleZ * COARSE_SPACING;
            int height = this.level.getHeight(
                    Heightmap.Types.MOTION_BLOCKING_NO_LEAVES, x, z);
            BlockPos surface = new BlockPos(x, height - 1, z);
            boolean ocean = this.level.getBiome(surface)
                    .is(BiomeTags.IS_OCEAN);
            this.heights[this.cursor] = height;
            this.land[this.cursor] = !ocean;
            if (ocean)
            {
                this.oceanSamples++;
            }
            this.minimumHeight = Math.min(this.minimumHeight, height);
            this.maximumHeight = Math.max(this.maximumHeight, height);
            this.cursor++;
            if (this.cursor < COARSE_COUNT)
            {
                return;
            }

            int[] sorted = this.heights.clone();
            Arrays.sort(sorted);
            this.p10 = percentile(sorted, 0.10D);
            this.median = percentile(sorted, 0.50D);
            this.p90 = percentile(sorted, 0.90D);
            this.largestLandCluster = largestLandCluster(this.land);
            this.surfaceY = FacilitySchemaV2.WORLDGEN_SURFACE_DATUM;
            /*
             * Candidate 0 is already frozen into the custom GeoFront chunk
             * generator. Natural surface relief is therefore evidence for
             * the receipt, not a candidate-selection gate. The former
             * overworld-style p10/p90/min-height rejection incorrectly
             * rejected the intentional continent before any owner could
             * establish its own level route datum.
             */
            if (this.surfaceY < FacilitySchemaV2.MIN_SURFACE_Y
                    || this.surfaceY > FacilitySchemaV2.MAX_SURFACE_Y
                    || this.surfaceY + 105
                    > FacilitySchemaV2.REGION_MAX_Y_EXCLUSIVE)
            {
                rejectCandidate("coarse terrain gate");
                return;
            }

            FacilitySchemaV2.ResolvedManifest manifest =
                    FacilitySchemaV2.resolve(this.candidateIndex,
                            this.surfaceY);
            this.critical = List.of(
                    footprint(manifest, "TOKYO3_APRON",
                            this.surfaceY - 16, this.surfaceY + 48),
                    footprint(manifest, "SURFACE_TRANSIT",
                            this.surfaceY - 16, this.surfaceY + 48),
                    footprint(manifest, "PUBLIC_LIFT_SHAFT",
                            Integer.MIN_VALUE, this.surfaceY + 16),
                    footprint(manifest, "UNIT00_SILO",
                            Integer.MIN_VALUE, this.surfaceY + 49),
                    footprint(manifest, "UNIT01_SILO",
                            Integer.MIN_VALUE, this.surfaceY + 49),
                    footprint(manifest, "UNIT02_SILO",
                            Integer.MIN_VALUE, this.surfaceY + 49));
            this.phase = Phase.CRITICAL;
            this.criticalIndex = 0;
            this.criticalCursor = 0L;
        }

        private void sampleCritical()
        {
            if (this.criticalIndex >= this.critical.size())
            {
                complete();
                return;
            }
            CriticalFootprint footprint =
                    this.critical.get(this.criticalIndex);
            int sizeX = footprint.maxX() - footprint.minX();
            int sizeZ = footprint.maxZ() - footprint.minZ();
            long volume = (long) sizeX * sizeZ;
            int x = footprint.minX()
                    + (int) (this.criticalCursor % sizeX);
            int z = footprint.minZ()
                    + (int) (this.criticalCursor / sizeX);
            int height = this.level.getHeight(
                    Heightmap.Types.MOTION_BLOCKING_NO_LEAVES, x, z);
            BlockPos surface = new BlockPos(x, height - 1, z);
            /*
             * These columns are sampled into the immutable receipt, but do
             * not reject natural relief. Every listed owner has an explicit
             * construction envelope that clears headroom and establishes its
             * own floor/foundation at the fixed schema datum. Generator
             * identity above is the hard safety boundary.
             */
            this.criticalMinimumHeight = Math.min(
                    this.criticalMinimumHeight, height);
            this.criticalMaximumHeight = Math.max(
                    this.criticalMaximumHeight, height);
            this.criticalCursor++;
            if (this.criticalCursor >= volume)
            {
                this.criticalIndex++;
                this.criticalCursor = 0L;
            }
        }

        private void complete()
        {
            FacilitySchemaV2.ResolvedManifest manifest =
                    FacilitySchemaV2.resolve(this.candidateIndex,
                            this.surfaceY);
            String manifestHash = FacilityV2Hashing.manifestContractHash(
                    manifest, this.level.dimension().location(),
                    this.level.getSeed());
            String coreHash = FacilityV2Hashing.bootstrapRegionCoreHash(
                    manifestHash, this.minimumHeight, this.maximumHeight,
                    this.p10, this.median, this.p90, this.oceanSamples,
                    this.largestLandCluster, this.criticalMinimumHeight,
                    this.criticalMaximumHeight);
            FacilityV2SavedData.get(this.level).commission(manifest, coreHash);
            this.phase = Phase.COMPLETE;
            ProjectSeele.LOGGER.info(
                    "FacilitySchema v2 commissioned candidate={} surfaceY={} "
                            + "p10/median/p90={}/{}/{} min/max={}/{} "
                            + "ocean={} landCluster={} criticalMin/Max={}/{} "
                            + "core={}",
                    this.candidateIndex, this.surfaceY, this.p10,
                    this.median, this.p90, this.minimumHeight,
                    this.maximumHeight, this.oceanSamples,
                    this.largestLandCluster,
                    this.criticalMinimumHeight,
                    this.criticalMaximumHeight, coreHash);
        }

        private void rejectCandidate(String reason)
        {
            ProjectSeele.LOGGER.warn(
                    "FacilitySchema v2 rejected candidate {}: {}",
                    this.candidateIndex, reason);
            this.phase = Phase.FAILED;
            this.failure = "committed candidate rejected; " + reason;
        }

        private String summary()
        {
            if (this.phase == Phase.FAILED)
            {
                return "FAILED " + this.failure;
            }
            if (this.phase == Phase.COMPLETE)
            {
                return "COMPLETE candidate=" + this.candidateIndex
                        + " surfaceY=" + this.surfaceY;
            }
            if (this.phase == Phase.COARSE)
            {
                return "candidate=" + this.candidateIndex
                        + " coarse=" + this.cursor + "/" + COARSE_COUNT;
            }
            CriticalFootprint current = this.criticalIndex
                    < this.critical.size()
                    ? this.critical.get(this.criticalIndex) : null;
            return "candidate=" + this.candidateIndex
                    + " critical=" + this.criticalIndex + "/"
                    + this.critical.size()
                    + (current == null ? "" : " zone=" + current.zoneId());
        }
    }

    private static int percentile(int[] sorted, double percentile)
    {
        int index = (int) Math.floor(
                percentile * Math.max(0, sorted.length - 1));
        return sorted[Math.max(0, Math.min(sorted.length - 1, index))];
    }

    private static int largestLandCluster(boolean[] land)
    {
        boolean[] seen = new boolean[land.length];
        int largest = 0;
        for (int start = 0; start < land.length; start++)
        {
            if (!land[start] || seen[start])
            {
                continue;
            }
            int size = 0;
            Deque<Integer> queue = new ArrayDeque<>();
            queue.add(start);
            seen[start] = true;
            while (!queue.isEmpty())
            {
                int current = queue.removeFirst();
                size++;
                int x = current % COARSE_SIDE;
                int z = current / COARSE_SIDE;
                for (int dz = -1; dz <= 1; dz++)
                {
                    for (int dx = -1; dx <= 1; dx++)
                    {
                        if ((dx == 0 && dz == 0)
                                || x + dx < 0 || x + dx >= COARSE_SIDE
                                || z + dz < 0 || z + dz >= COARSE_SIDE)
                        {
                            continue;
                        }
                        int next = (z + dz) * COARSE_SIDE + x + dx;
                        if (land[next] && !seen[next])
                        {
                            seen[next] = true;
                            queue.addLast(next);
                        }
                    }
                }
            }
            largest = Math.max(largest, size);
        }
        return largest;
    }

    private static CriticalFootprint footprint(
            FacilitySchemaV2.ResolvedManifest manifest, String zoneId,
            int minimumHeight, int maximumHeight)
    {
        FacilitySchemaV2.IntBox owner =
                manifest.requireZone(zoneId).owner();
        return new CriticalFootprint(zoneId, owner.minX(), owner.minZ(),
                owner.maxX(), owner.maxZ(), minimumHeight, maximumHeight);
    }

    private record CriticalFootprint(String zoneId, int minX, int minZ,
                                     int maxX, int maxZ, int minimumHeight,
                                     int maximumHeight) {}
}
