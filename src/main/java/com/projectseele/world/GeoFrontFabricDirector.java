package com.projectseele.world;

import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.Map;

import com.projectseele.ProjectSeele;
import net.minecraft.core.BlockPos;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.TicketType;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.chunk.LevelChunk;

/**
 * Budgeted executor for the persistent GeoFront exterior fabric.
 *
 * <p>Only an explicit administrator command can commit or start the fabric.
 * Once authorized, the cursor resumes across saves. Missing chunks receive a
 * preparation ticket and the writer yields without advancing. The dedicated
 * S19 construction save may synchronously acquire only the current authored
 * chunk after ticketing it; this prevents an expired prefetch ticket from
 * leaving a persistent build cursor parked forever.</p>
 */
public final class GeoFrontFabricDirector
{
    public static final int MAX_CHANGED_BLOCKS_PER_TICK = 8192;
    public static final int MAX_VISITED_PER_TICK = 65536;
    public static final long MAX_NANOS_PER_TICK = 12_000_000L;
    private static final int MAX_PREPARED_CHUNKS = 32;
    private static final int PREFETCH_SCAN_LIMIT = 65536;
    private static final long PREFETCH_NANOS = 2_000_000L;
    private static final int MAX_LIGHT_CHANGES_PER_TICK = 512;
    private static final int MAX_LIGHT_VISITS_PER_TICK = 8192;
    private static final long MAX_LIGHT_NANOS_PER_TICK = 6_000_000L;
    /*
     * The dedicated rescue save is constructed unattended before human
     * review.  It may spend most of a server tick on authored world writes;
     * normal saves retain the conservative live-play budget above.
     */
    private static final int RESCUE_CHANGED_BLOCKS_PER_TICK = 32768;
    private static final int RESCUE_VISITED_PER_TICK = 262144;
    private static final long RESCUE_NANOS_PER_TICK = 30_000_000L;
    /*
     * Lighting propagation retains substantially more section state than an
     * ordinary block pass. Keep its write budget conservative even in the
     * unattended rescue build, and cap the one global preparation window at
     * sixteen chunks so the 1,280-block cavern cannot exhaust the light
     * engine while scenery construction is running.
     */
    private static final int RESCUE_LIGHT_CHANGES_PER_TICK = 512;
    private static final int RESCUE_LIGHT_VISITS_PER_TICK = 8192;
    private static final long RESCUE_LIGHT_NANOS_PER_TICK = 6_000_000L;
    /*
     * The GeoFront dimension already supplies permanent ambient light.
     * Four authored light decks cover the inhabited terrain, command volume,
     * gardens and public circulation.  Continuing the decorative grid through
     * all twelve sky levels loads and serialises thousands of otherwise unused
     * chunks without making the player route materially brighter.
     */
    private static final long RESCUE_LIGHT_WORK_LIMIT =
            53L * 53L * 4L;
    private static final int RESCUE_PREPARED_CHUNKS = 16;
    private static final int RESCUE_CAVERN_CHUNKS_PER_TICK = 4;
    private static final TicketType<ChunkPos> FABRIC_PREPARATION =
            TicketType.create("projectseele_fabric_preparation",
                    Comparator.comparingLong(ChunkPos::toLong), 200);
    /*
     * Access-ordered on purpose.  Releasing a ticket as soon as its first
     * authored block was reached let the chunk unload while later blocks in
     * the same row were still pending.  The server then spent nearly all its
     * time serialising and reloading the same chunks.  A bounded sliding
     * window keeps the active construction band resident without pinning the
     * complete 1,280-block cavern.
     */
    private static final LinkedHashMap<Long, ChunkPos>
            PREPARATION_TICKETS = new LinkedHashMap<>(64, 0.75F, true);

    private GeoFrontFabricDirector() {}

    /** Drops static ticket bookkeeping between integrated-server sessions. */
    public static void resetRuntime()
    {
        PREPARATION_TICKETS.clear();
    }

    public static void commit(ServerLevel level)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return;
        FacilityWorldPolicy.requireCleanRebuild(
                level.getServer(), "GeoFrontFabricDirector.commit");
        FacilityV2SavedData facility = FacilityV2SavedData.get(level);
        requireCleanFabricDomain(level, facility.manifest());
        GeoFrontFabricSavedData.get(level).commit(facility);
        ProjectSeele.LOGGER.info(
                "GeoFrontFabric committed region={} revision={} plan={}",
                FacilitySchemaV2.REGION_ID,
                GeoFrontFabricPlan.FABRIC_REVISION,
                FacilityV2Hashing.fabricPlanHash(
                        facility.regionCoreHash(),
                        java.util.List.of(
                                GeoFrontFabricPlan.Feature.values())));
    }

    public static void startAll(ServerLevel level)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return;
        FacilityWorldPolicy.requireCleanRebuild(
                level.getServer(), "GeoFrontFabricDirector.startAll");
        FacilityV2SavedData facility = FacilityV2SavedData.get(level);
        GeoFrontFabricSavedData data =
                GeoFrontFabricSavedData.get(level);
        if (!data.validFor(facility))
        {
            throw new IllegalStateException(
                    "GeoFrontFabric receipt does not match FacilitySchema");
        }
        data.startProgramme();
        if (!data.reconciliationActive())
        {
            startNextIfReady(level, data);
        }
    }

    public static void start(ServerLevel level,
                             GeoFrontFabricPlan.Feature feature)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return;
        FacilityWorldPolicy.requireCleanRebuild(
                level.getServer(), "GeoFrontFabricDirector.start");
        FacilityV2SavedData facility = FacilityV2SavedData.get(level);
        GeoFrontFabricSavedData data =
                GeoFrontFabricSavedData.get(level);
        if (!data.validFor(facility))
        {
            throw new IllegalStateException(
                    "GeoFrontFabric receipt does not match FacilitySchema");
        }
        data.begin(feature);
        ProjectSeele.LOGGER.info(
                "GeoFrontFabric queued {} work={} contract={}",
                feature.id(), feature.authoredWork(),
                feature.contractHash());
    }

    public static void tick(MinecraftServer server)
    {
        if (NervLegacyGenerationGuardR52.retired(server)) return;
        if (!FacilityWorldPolicy.isCleanRebuild(server))
        {
            return;
        }
        ServerLevel level = server.getLevel(FacilitySchemaV2.DIMENSION);
        if (level == null)
        {
            return;
        }
        FacilityV2SavedData facility = FacilityV2SavedData.get(level);
        if (!facility.commissioned())
        {
            return;
        }
        GeoFrontFabricSavedData data =
                GeoFrontFabricSavedData.get(level);
        if (data.lifecycle() == GeoFrontFabricSavedData.Lifecycle.DRAFT
                || data.lifecycle()
                == GeoFrontFabricSavedData.Lifecycle.FAILED)
        {
            return;
        }
        if (!data.validFor(facility))
        {
            ProjectSeele.LOGGER.error(
                    "GeoFrontFabric receipt no longer matches FacilitySchema "
                            + "v2; no exterior writes will be attempted");
            return;
        }
        FacilityV2RouteGateDirector.openWestExteriorSeamIfReady(
                level, facility, data);
        if (data.reconciliationActive())
        {
            advanceReconciliation(level, facility, data);
            return;
        }
        if (data.activeFeature().isEmpty())
        {
            if (data.programmeActive())
            {
                startNextIfReady(level, data);
            }
            return;
        }
        advance(level, facility, data,
                data.activeFeature().orElseThrow());
    }

    private static void startNextIfReady(
            ServerLevel level, GeoFrontFabricSavedData data)
    {
        data.nextPending().ifPresent(feature ->
        {
            data.begin(feature);
            ProjectSeele.LOGGER.info(
                    "GeoFrontFabric programme started {}",
                    feature.id());
        });
    }

    private static void advance(ServerLevel level,
                                FacilityV2SavedData facility,
                                GeoFrontFabricSavedData data,
                                GeoFrontFabricPlan.Feature feature)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return;
        GeoFrontFabricSavedData.FeatureRecord record =
                data.requireFeature(feature);
        long cursor = record.cursor();
        long cursorAtTickStart = cursor;
        long visited = record.visited();
        long changed = record.changed();
        long total = feature.authoredWork();
        int changedThisTick = 0;
        int visitedThisTick = 0;
        long start = System.nanoTime();
        boolean rescue = FacilityWorldPolicy.isCleanRebuild(
                level.getServer());
        int changedBudget = feature == GeoFrontFabricPlan.Feature.LIGHTING
                ? (rescue ? RESCUE_LIGHT_CHANGES_PER_TICK
                : MAX_LIGHT_CHANGES_PER_TICK)
                : (rescue ? RESCUE_CHANGED_BLOCKS_PER_TICK
                : MAX_CHANGED_BLOCKS_PER_TICK);
        int visitedBudget = feature == GeoFrontFabricPlan.Feature.LIGHTING
                ? (rescue ? RESCUE_LIGHT_VISITS_PER_TICK
                : MAX_LIGHT_VISITS_PER_TICK)
                : (rescue ? RESCUE_VISITED_PER_TICK
                : MAX_VISITED_PER_TICK);
        long timeBudget = feature == GeoFrontFabricPlan.Feature.LIGHTING
                ? (rescue ? RESCUE_LIGHT_NANOS_PER_TICK
                : MAX_LIGHT_NANOS_PER_TICK)
                : (rescue ? RESCUE_NANOS_PER_TICK
                : MAX_NANOS_PER_TICK);
        long workLimit = rescue
                && feature == GeoFrontFabricPlan.Feature.LIGHTING
                ? Math.min(total, RESCUE_LIGHT_WORK_LIMIT) : total;
        FacilitySchemaV2.ResolvedManifest manifest = facility.manifest();
        if (rescue && feature == GeoFrontFabricPlan.Feature
                .CAVERN_SURFACE_FINISH)
        {
            advanceRescueCavern(level, data, record, manifest);
            return;
        }
        try
        {
            prepareAhead(level, manifest, feature, cursor, workLimit);
            while (cursor < workLimit
                    && changedThisTick < changedBudget
                    && visitedThisTick < visitedBudget
                    && System.nanoTime() - start < timeBudget)
            {
                GeoFrontFabricPlan.FabricBlock authored =
                        GeoFrontFabricPlan.blockAt(
                                manifest, feature, cursor);
                if (authored == null)
                {
                    cursor++;
                    visited++;
                    visitedThisTick++;
                    continue;
                }
                BlockPos position = authored.position();
                boolean protectedByFacility =
                        feature == GeoFrontFabricPlan.Feature.WEST_SEAM
                                ? GeoFrontFabricPlan.ownerContains(
                                manifest, position)
                                : GeoFrontFabricPlan.ownerGuarded(
                                manifest, position);
                if (protectedByFacility
                        || !manifest.region().contains(
                        pointBox(position))
                        || !GeoFrontFabricPlan.insideCavern(
                        manifest.centre(), position))
                {
                    cursor++;
                    visited++;
                    visitedThisTick++;
                    continue;
                }

                if (!ensureChunkReady(level, position))
                {
                    break;
                }

                BlockState target = authored.state();
                BlockState current = level.getBlockState(position);
                if (feature == GeoFrontFabricPlan.Feature.LIGHTING
                        && !current.isAir()
                        && !current.is(Blocks.LIGHT))
                {
                    cursor++;
                    visited++;
                    visitedThisTick++;
                    continue;
                }
                if (!current.equals(target))
                {
                    if (rescue && feature == GeoFrontFabricPlan.Feature
                            .CAVERN_SURFACE_FINISH)
                    {
                        /*
                         * This pass writes millions of plain shell/terrain
                         * blocks while no human is reviewing the world. Direct
                         * chunk writes avoid one client packet and one light
                         * propagation task per block; the completed save is
                         * reopened before review, so normal chunk sync sends
                         * the final state once.
                         */
                        level.getChunkAt(position).setBlockState(
                                position, target, false);
                    }
                    else
                    {
                        level.setBlock(position, target,
                                Block.UPDATE_CLIENTS);
                    }
                    changed++;
                    changedThisTick++;
                }
                cursor++;
                visited++;
                visitedThisTick++;
            }

            if (cursor >= workLimit && workLimit < total)
            {
                cursor = total;
            }
            data.update(feature, cursor, visited, changed);
            if (cursor < total
                    && cursor / 500_000L
                    > cursorAtTickStart / 500_000L)
            {
                ProjectSeele.LOGGER.info(
                        "GeoFrontFabric progress {} {}/{} ({}%) changed={}",
                        feature.id(), cursor, total,
                        Math.min(99L, cursor * 100L
                                / Math.max(1L, total)),
                        changed);
            }
            if (cursor >= total)
            {
                data.complete(feature);
                releasePreparationTickets(level);
                ProjectSeele.LOGGER.info(
                        "GeoFrontFabric completed {} visited={} changed={}",
                        feature.id(), visited, changed);
            }
        }
        catch (RuntimeException exception)
        {
            releasePreparationTickets(level);
            data.fail(feature, exception.getClass().getSimpleName()
                    + ": " + exception.getMessage());
            ProjectSeele.LOGGER.error(
                    "GeoFrontFabric failed " + feature.id(), exception);
        }
    }

    /**
     * Builds the rescue cavern a chunk at a time. The ordinary authored order
     * sweeps 1,280 blocks across each row and repeatedly reloads the same chunk
     * columns hundreds of times. Chunk-major construction loads each column
     * once, seals the stepped ellipsoid skin, lays its terrain, and then moves
     * on. LevelChunk keeps section counts and heightmaps coherent while the
     * deliberate no-notify path avoids millions of client/light updates.
     */
    private static void advanceRescueCavern(
            ServerLevel level,
            GeoFrontFabricSavedData data,
            GeoFrontFabricSavedData.FeatureRecord record,
            FacilitySchemaV2.ResolvedManifest manifest)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return;
        int radius = GeoFrontFabricPlan.CAVERN_RADIUS_XZ;
        int minChunkX = Math.floorDiv(
                manifest.centre().getX() - radius, 16);
        int maxChunkX = Math.floorDiv(
                manifest.centre().getX() + radius, 16);
        int minChunkZ = Math.floorDiv(
                manifest.centre().getZ() - radius, 16);
        int maxChunkZ = Math.floorDiv(
                manifest.centre().getZ() + radius, 16);
        int spanX = maxChunkX - minChunkX + 1;
        int spanZ = maxChunkZ - minChunkZ + 1;
        long totalChunks = (long) spanX * spanZ;
        long chunkCursor = Math.min(totalChunks,
                data.rescueCavernChunkCursor());
        long visited = record.visited();
        long changed = record.changed();
        long startedAt = System.nanoTime();
        int processed = 0;

        try
        {
            prepareRescueCavernAhead(level, manifest, chunkCursor,
                    totalChunks, minChunkX, minChunkZ, spanX);
            while (chunkCursor < totalChunks
                    && processed < RESCUE_CAVERN_CHUNKS_PER_TICK
                    && System.nanoTime() - startedAt
                    < RESCUE_NANOS_PER_TICK)
            {
                int chunkX = minChunkX
                        + (int) (chunkCursor % spanX);
                int chunkZ = minChunkZ
                        + (int) (chunkCursor / spanX);
                if (!chunkIntersectsCavern(manifest, chunkX, chunkZ,
                        radius))
                {
                    chunkCursor++;
                    continue;
                }

                BlockPos probe = new BlockPos(chunkX << 4,
                        GeoFrontFabricPlan.CAVERN_CENTRE_Y, chunkZ << 4);
                if (!ensureChunkReady(level, probe))
                {
                    break;
                }

                LevelChunk chunk = level.getChunk(chunkX, chunkZ);
                CavernWriteStats stats = writeRescueCavernChunk(
                        chunk, manifest);
                if (stats.changed() > 0L)
                {
                    chunk.setUnsaved(true);
                }
                visited += stats.visited();
                changed += stats.changed();
                chunkCursor++;
                processed++;
            }

            data.updateRescueCavernChunkCursor(chunkCursor);
            if (chunkCursor >= totalChunks)
            {
                long total = GeoFrontFabricPlan.Feature
                        .CAVERN_SURFACE_FINISH.authoredWork();
                data.update(GeoFrontFabricPlan.Feature
                                .CAVERN_SURFACE_FINISH,
                        total, Math.max(visited, total), changed);
                data.complete(GeoFrontFabricPlan.Feature
                        .CAVERN_SURFACE_FINISH);
                data.clearRescueCavernChunkCursor();
                releasePreparationTickets(level);
                ProjectSeele.LOGGER.info(
                        "GeoFrontFabric completed cavern_surface_finish "
                                + "chunkMajor={}/{} visited={} changed={}",
                        totalChunks, totalChunks, visited, changed);
            }
            else
            {
                data.update(GeoFrontFabricPlan.Feature
                                .CAVERN_SURFACE_FINISH,
                        record.cursor(), visited, changed);
                if (chunkCursor > 0L && chunkCursor % 256L == 0L)
                {
                    ProjectSeele.LOGGER.info(
                            "GeoFrontFabric cavern chunk-major progress "
                                    + "{}/{} changed={}",
                            chunkCursor, totalChunks, changed);
                }
            }
        }
        catch (RuntimeException exception)
        {
            releasePreparationTickets(level);
            data.fail(GeoFrontFabricPlan.Feature
                            .CAVERN_SURFACE_FINISH,
                    exception.getClass().getSimpleName()
                            + ": " + exception.getMessage());
            ProjectSeele.LOGGER.error(
                    "GeoFrontFabric failed cavern_surface_finish "
                            + "chunk-major pass", exception);
        }
    }

    private static void prepareRescueCavernAhead(
            ServerLevel level,
            FacilitySchemaV2.ResolvedManifest manifest,
            long cursor, long totalChunks,
            int minChunkX, int minChunkZ, int spanX)
    {
        Long protectedKey = null;
        if (cursor < totalChunks)
        {
            int currentX = minChunkX + (int) (cursor % spanX);
            int currentZ = minChunkZ + (int) (cursor / spanX);
            protectedKey = ChunkPos.asLong(currentX, currentZ);
        }
        long scan = cursor;
        int requested = 0;
        while (scan < totalChunks
                && requested < RESCUE_PREPARED_CHUNKS)
        {
            int chunkX = minChunkX + (int) (scan % spanX);
            int chunkZ = minChunkZ + (int) (scan / spanX);
            scan++;
            if (!chunkIntersectsCavern(manifest, chunkX, chunkZ,
                    GeoFrontFabricPlan.CAVERN_RADIUS_XZ))
            {
                continue;
            }
            BlockPos probe = new BlockPos(chunkX << 4,
                    GeoFrontFabricPlan.CAVERN_CENTRE_Y, chunkZ << 4);
            if (level.hasChunkAt(probe))
            {
                continue;
            }
            ChunkPos chunk = new ChunkPos(chunkX, chunkZ);
            ensurePreparationTicket(level, chunk, chunk.toLong(),
                    protectedKey);
            requested++;
        }
    }

    private static boolean chunkIntersectsCavern(
            FacilitySchemaV2.ResolvedManifest manifest,
            int chunkX, int chunkZ, int radius)
    {
        int minRelativeX = (chunkX << 4)
                - manifest.centre().getX();
        int maxRelativeX = minRelativeX + 15;
        int minRelativeZ = (chunkZ << 4)
                - manifest.centre().getZ();
        int maxRelativeZ = minRelativeZ + 15;
        int closestX = Math.max(minRelativeX,
                Math.min(0, maxRelativeX));
        int closestZ = Math.max(minRelativeZ,
                Math.min(0, maxRelativeZ));
        return (long) closestX * closestX
                + (long) closestZ * closestZ
                <= (long) radius * radius;
    }

    private static CavernWriteStats writeRescueCavernChunk(
            LevelChunk chunk,
            FacilitySchemaV2.ResolvedManifest manifest)
    {
        long visited = 0L;
        long changed = 0L;
        int startX = chunk.getPos().getMinBlockX();
        int startZ = chunk.getPos().getMinBlockZ();
        BlockState shell = GeoFrontFabricPlan.cavernShellState();
        BlockPos.MutableBlockPos mutable = new BlockPos.MutableBlockPos();

        for (int worldX = startX; worldX < startX + 16; worldX++)
        {
            int relativeX = worldX - manifest.centre().getX();
            for (int worldZ = startZ; worldZ < startZ + 16; worldZ++)
            {
                int relativeZ = worldZ - manifest.centre().getZ();
                int verticalRadius = cavernVerticalRadius(
                        relativeX, relativeZ);
                if (verticalRadius < 0)
                {
                    continue;
                }

                int neighbourRadius = verticalRadius;
                neighbourRadius = Math.max(neighbourRadius,
                        cavernVerticalRadius(relativeX - 1, relativeZ));
                neighbourRadius = Math.max(neighbourRadius,
                        cavernVerticalRadius(relativeX + 1, relativeZ));
                neighbourRadius = Math.max(neighbourRadius,
                        cavernVerticalRadius(relativeX, relativeZ - 1));
                neighbourRadius = Math.max(neighbourRadius,
                        cavernVerticalRadius(relativeX, relativeZ + 1));
                int top = GeoFrontFabricPlan.CAVERN_CENTRE_Y
                        + verticalRadius;
                int bottom = GeoFrontFabricPlan.CAVERN_CENTRE_Y
                        - verticalRadius;
                int neighbourTop = GeoFrontFabricPlan.CAVERN_CENTRE_Y
                        + neighbourRadius;
                int neighbourBottom = GeoFrontFabricPlan.CAVERN_CENTRE_Y
                        - neighbourRadius;

                for (int y = top - 1; y <= neighbourTop; y++)
                {
                    mutable.set(worldX, y, worldZ);
                    visited++;
                    if (writeRescueCavernBlock(chunk, manifest,
                            mutable, shell))
                    {
                        changed++;
                    }
                }
                for (int y = neighbourBottom; y <= bottom + 1; y++)
                {
                    mutable.set(worldX, y, worldZ);
                    visited++;
                    if (writeRescueCavernBlock(chunk, manifest,
                            mutable, shell))
                    {
                        changed++;
                    }
                }

                if ((long) relativeX * relativeX
                        + (long) relativeZ * relativeZ
                        <= 632L * 632L)
                {
                    int surface = GeoFrontFabricPlan.terrainHeight(
                            relativeX, relativeZ);
                    for (int layer = 0; layer < 4; layer++)
                    {
                        BlockState terrain = layer == 0
                                ? Blocks.GRASS_BLOCK.defaultBlockState()
                                : layer <= 2
                                ? Blocks.DIRT.defaultBlockState()
                                : Blocks.STONE.defaultBlockState();
                        mutable.set(worldX, surface - layer, worldZ);
                        visited++;
                        if (writeRescueCavernBlock(chunk, manifest,
                                mutable, terrain))
                        {
                            changed++;
                        }
                    }
                }
            }
        }
        return new CavernWriteStats(visited, changed);
    }

    private static int cavernVerticalRadius(int relativeX, int relativeZ)
    {
        double nx = relativeX
                / (double) GeoFrontFabricPlan.CAVERN_RADIUS_XZ;
        double nz = relativeZ
                / (double) GeoFrontFabricPlan.CAVERN_RADIUS_XZ;
        double remaining = 1.0D - nx * nx - nz * nz;
        if (remaining < 0.0D)
        {
            return -1;
        }
        return (int) Math.floor(GeoFrontFabricPlan.CAVERN_RADIUS_Y
                * Math.sqrt(remaining));
    }

    private static boolean writeRescueCavernBlock(
            LevelChunk chunk,
            FacilitySchemaV2.ResolvedManifest manifest,
            BlockPos position, BlockState target)
    {
        if (!manifest.region().contains(pointBox(position))
                || GeoFrontFabricPlan.ownerGuarded(manifest, position)
                || GeoFrontFabricPlan.cavernFoundationExcluded(
                manifest, position))
        {
            return false;
        }
        BlockState current = chunk.getBlockState(position);
        if (current.equals(target))
        {
            return false;
        }
        chunk.setBlockState(position, target, false);
        return true;
    }

    /**
     * Keep a small asynchronous window in front of the persistent cursor.
     * The old single-ticket path waited for one new chunk before it could
     * even request the next and turned first construction into a multi-hour
     * serial world-generation job.
     */
    private static void prepareAhead(
            ServerLevel level,
            FacilitySchemaV2.ResolvedManifest manifest,
            GeoFrontFabricPlan.Feature feature,
            long cursor,
            long workLimit)
    {
        long scan = cursor;
        int scanned = 0;
        long startedAt = System.nanoTime();
        Long protectedKey = chunkKeyAt(manifest, feature, cursor);
        while (scan < workLimit
                && scanned < PREFETCH_SCAN_LIMIT
                && System.nanoTime() - startedAt < PREFETCH_NANOS)
        {
            GeoFrontFabricPlan.FabricBlock authored =
                    GeoFrontFabricPlan.blockAt(manifest, feature, scan);
            scan++;
            scanned++;
            if (authored == null)
            {
                continue;
            }
            BlockPos position = authored.position();
            if (!manifest.region().contains(pointBox(position))
                    || !GeoFrontFabricPlan.insideCavern(
                    manifest.centre(), position)
                    || level.hasChunkAt(position))
            {
                continue;
            }
            ChunkPos chunk = new ChunkPos(position);
            long key = chunk.toLong();
            ensurePreparationTicket(level, chunk, key, protectedKey);
        }
    }

    private static Long chunkKeyAt(
            FacilitySchemaV2.ResolvedManifest manifest,
            GeoFrontFabricPlan.Feature feature,
            long cursor)
    {
        if (cursor < 0L || cursor >= feature.authoredWork())
        {
            return null;
        }
        GeoFrontFabricPlan.FabricBlock authored =
                GeoFrontFabricPlan.blockAt(manifest, feature, cursor);
        return authored == null
                ? null : new ChunkPos(authored.position()).toLong();
    }

    private static void advanceReconciliation(
            ServerLevel level, FacilityV2SavedData facility,
            GeoFrontFabricSavedData data)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return;
        GeoFrontFabricSavedData.ReconciliationProgress progress =
                data.reconciliationProgress();
        int pass = progress.pass();
        int featureIndex = progress.featureIndex();
        long cursor = progress.cursor();
        long visited = progress.visited();
        long changed = progress.changed();
        int changedThisTick = 0;
        int visitedThisTick = 0;
        long start = System.nanoTime();
        FacilitySchemaV2.ResolvedManifest manifest = facility.manifest();
        java.util.List<GeoFrontFabricPlan.FeatureContract> contracts =
                data.reconciliationContracts(pass);
        try
        {
            while (changedThisTick < MAX_CHANGED_BLOCKS_PER_TICK
                    && visitedThisTick < MAX_VISITED_PER_TICK
                    && System.nanoTime() - start < MAX_NANOS_PER_TICK)
            {
                if (featureIndex >= contracts.size())
                {
                    if (pass == 0)
                    {
                        pass = 1;
                        featureIndex = 0;
                        cursor = 0L;
                        contracts = data.reconciliationContracts(pass);
                        continue;
                    }
                    data.updateReconciliation(pass, featureIndex,
                            cursor, visited, changed);
                    data.completeReconciliation();
                    releasePreparationTickets(level);
                    ProjectSeele.LOGGER.info(
                            "GeoFrontFabric reconciliation complete "
                                    + "visited={} changed={}",
                            visited, changed);
                    return;
                }

                GeoFrontFabricPlan.FeatureContract contract =
                        contracts.get(featureIndex);
                if (cursor >= contract.authoredWork())
                {
                    featureIndex++;
                    cursor = 0L;
                    continue;
                }
                GeoFrontFabricPlan.FabricBlock dirty =
                        GeoFrontFabricPlan.blockAt(
                                manifest, contract, cursor);
                if (dirty == null)
                {
                    cursor++;
                    visited++;
                    visitedThisTick++;
                    continue;
                }
                BlockPos position = dirty.position();
                if (!manifest.region().contains(pointBox(position))
                        || !GeoFrontFabricPlan.insideCavern(
                        manifest.centre(), position))
                {
                    cursor++;
                    visited++;
                    visitedThisTick++;
                    continue;
                }
                GeoFrontFabricPlan.ResolvedFabricBlock resolved =
                        GeoFrontFabricPlan.desiredBlock(
                                manifest, position);
                if (!resolved.writable())
                {
                    cursor++;
                    visited++;
                    visitedThisTick++;
                    continue;
                }
                if (!ensureChunkReady(level, position))
                {
                    break;
                }
                BlockState current = level.getBlockState(position);
                if (!current.equals(resolved.state()))
                {
                    level.setBlock(position, resolved.state(),
                            Block.UPDATE_CLIENTS);
                    changed++;
                    changedThisTick++;
                }
                cursor++;
                visited++;
                visitedThisTick++;
            }
            data.updateReconciliation(pass, featureIndex, cursor,
                    visited, changed);
        }
        catch (RuntimeException exception)
        {
            releasePreparationTickets(level);
            data.failReconciliation(
                    exception.getClass().getSimpleName()
                            + ": " + exception.getMessage());
            ProjectSeele.LOGGER.error(
                    "GeoFrontFabric reconciliation failed", exception);
        }
    }

    private static boolean ensureChunkReady(
            ServerLevel level, BlockPos position)
    {
        ChunkPos chunk = new ChunkPos(position);
        long key = chunk.toLong();
        if (!level.hasChunkAt(position))
        {
            ensurePreparationTicket(level, chunk, key, key);
            if (FacilityWorldPolicy.isCleanRebuild(level.getServer()))
            {
                level.getChunkAt(position);
                return true;
            }
            return false;
        }
        return true;
    }

    private static void ensurePreparationTicket(
            ServerLevel level, ChunkPos chunk, long key, Long protectedKey)
    {
        if (PREPARATION_TICKETS.containsKey(key))
        {
            PREPARATION_TICKETS.get(key);
            /*
             * Region tickets expire after 200 ticks. The access-ordered map
             * deliberately outlives that timeout, so touching the map alone
             * does not keep the actual server ticket alive.
             */
            level.getChunkSource().addRegionTicket(
                    FABRIC_PREPARATION, chunk, 0, chunk);
            return;
        }
        int ticketBudget = FacilityWorldPolicy.isCleanRebuild(
                level.getServer())
                ? RESCUE_PREPARED_CHUNKS : MAX_PREPARED_CHUNKS;
        while (PREPARATION_TICKETS.size() >= ticketBudget)
        {
            Map.Entry<Long, ChunkPos> removable = null;
            for (Map.Entry<Long, ChunkPos> candidate
                    : PREPARATION_TICKETS.entrySet())
            {
                if (protectedKey == null
                        || !candidate.getKey().equals(protectedKey))
                {
                    removable = candidate;
                    break;
                }
            }
            if (removable == null)
            {
                break;
            }
            PREPARATION_TICKETS.remove(removable.getKey());
            level.getChunkSource().removeRegionTicket(
                    FABRIC_PREPARATION, removable.getValue(), 0,
                    removable.getValue());
        }
        PREPARATION_TICKETS.put(key, chunk);
        level.getChunkSource().addRegionTicket(
                FABRIC_PREPARATION, chunk, 0, chunk);
    }

    private static void releasePreparationTickets(ServerLevel level)
    {
        for (ChunkPos chunk : PREPARATION_TICKETS.values())
        {
            level.getChunkSource().removeRegionTicket(
                    FABRIC_PREPARATION, chunk, 0, chunk);
        }
        PREPARATION_TICKETS.clear();
    }

    private record CavernWriteStats(long visited, long changed) {}

    private static FacilitySchemaV2.IntBox pointBox(BlockPos position)
    {
        return new FacilitySchemaV2.IntBox(
                position.getX(), position.getY(), position.getZ(),
                position.getX() + 1, position.getY() + 1,
                position.getZ() + 1);
    }

    /**
     * A Fabric plan may only claim a clean air domain. This bounded check
     * rejects chunks generated by the retired solid-underground settings
     * instead of trying to excavate hundreds of millions of blocks.
     */
    private static void requireCleanFabricDomain(
            ServerLevel level, FacilitySchemaV2.ResolvedManifest manifest)
    {
        int[] samples = {-480, -240, 0, 240, 480};
        int occupied = 0;
        BlockPos firstOccupied = null;
        for (int relativeX : samples)
        {
            for (int relativeZ : samples)
            {
                BlockPos position = new BlockPos(
                        manifest.centre().getX() + relativeX,
                        -240,
                        manifest.centre().getZ() + relativeZ);
                if (!GeoFrontFabricPlan.insideCavern(
                        manifest.centre(), position)
                        || GeoFrontFabricPlan.ownerGuarded(
                        manifest, position))
                {
                    continue;
                }
                if (!level.getBlockState(position).isAir())
                {
                    occupied++;
                    if (firstOccupied == null)
                    {
                        firstOccupied = position;
                    }
                }
            }
        }
        if (occupied > 0)
        {
            throw new IllegalStateException(
                    "UNOWNED_LEGACY fabric domain: " + occupied
                            + " clean-air probes are occupied; first="
                            + firstOccupied.toShortString()
                            + ". Use a new world/clean candidate. Fabric "
                            + "will not excavate an old solid underground.");
        }
    }

}
