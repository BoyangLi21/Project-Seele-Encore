package com.projectseele.world;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.EnumMap;
import java.util.HashMap;
import java.util.Map;
import java.util.Set;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.EvaUnit01Entity;
import net.minecraft.core.BlockPos;
import net.minecraft.core.SectionPos;
import net.minecraft.core.Vec3i;
import net.minecraft.core.registries.Registries;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.nbt.NbtIo;
import net.minecraft.nbt.Tag;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.util.RandomSource;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.level.BlockGetter;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.Mirror;
import net.minecraft.world.level.block.Rotation;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.levelgen.structure.templatesystem.StructurePlaceSettings;
import net.minecraft.world.level.levelgen.structure.templatesystem.StructureTemplate;
import net.minecraft.world.phys.AABB;

/**
 * Loads private evaluation maps from the active game directory. These files
 * are intentionally absent from the distributable jar and have deterministic
 * clean-room fallbacks when a player has not installed them.
 */
public final class LocalMapAssetLoader
{
    private static final Path ASSET_DIRECTORY =
            com.projectseele.entity.CombatMotionResourcesR44.instancePath("projectseele-local-maps");
    private static final Path COMMAND_MODULE =
            ASSET_DIRECTORY.resolve("nerv_command_left.nbt");
    private static final Path TOKYO3_SKYSCRAPER =
            ASSET_DIRECTORY.resolve("tokyo3_skyscraper.nbt");
    private static final String STAGED_WORLD_MARKER =
            ".projectseele_local_map.json";

    private static final BlockPos COMMAND_OFFSET = new BlockPos(-28, -21, -33);
    private static final Vec3i COMMAND_SIZE = new Vec3i(56, 77, 129);
    /*
     * Facility v2 keeps the imported room at its authored 1:1 scale.  A
     * 180-degree rotation puts the old wall screens on the north/front wall
     * and the command tower on the south/rear axis.  The transformed extents
     * are x[-28,27], y[-368,-292], z[-64,64] relative to the v2 centre.
     */
    private static final BlockPos COMMAND_V2_OFFSET =
            new BlockPos(27, -368, 24);
    private static final Rotation COMMAND_V2_ROTATION =
            Rotation.CLOCKWISE_180;
    private static final BlockPos COMMAND_MARKER_A =
            new BlockPos(-30, -22, -35);
    private static final BlockPos COMMAND_MARKER_B =
            new BlockPos(29, 57, 97);
    private static final BlockPos TOKYO3_IMPORT_MARKER =
            new BlockPos(126, -20, 126);
    private static final BlockPos PRIVATE_GEOFRONT_MARKER =
            new BlockPos(126, 80, 126);
    private static final BlockPos SKYSCRAPER_STATE_MARKER =
            new BlockPos(132, -20, 120);
    /*
     * A Tokyo-3 building is a physical lift load, not a visibility toggle.
     * The director schedules the three imported structures on separate ticks,
     * so each accepted city layer translates every building by one real block
     * without making all three 5,996-block templates move together.
     */
    private static final int SKYSCRAPER_MOVE_QUANTUM = 1;
    /*
     * One imported high-rise is still journalled and advanced independently,
     * but the old 512-write slice made a Tokyo-3 emergency descent take many
     * minutes.  These budgets keep the operation bounded while allowing the
     * three 5,996-block towers to follow the same roughly one-minute cadence
     * as the generated district.
     */
    private static final int SKYSCRAPER_STEP_WRITE_BUDGET = 16384;
    private static final int SKYSCRAPER_STEP_SCAN_BUDGET = 32768;
    /* Legacy mover left copied roof cargo one block above the 82-block body. */
    private static final int SKYSCRAPER_ABANDONED_ROOF_MARGIN = 4;
    private static final Vec3i SKYSCRAPER_TEMPLATE_SIZE =
            new Vec3i(23, 82, 12);
    private static final int UPDATE_CLIENTS = Block.UPDATE_CLIENTS;
    /** Canonical transformed states; live world blocks never become cargo. */
    private static final Map<Rotation, Map<BlockPos, BlockState>>
            SKYSCRAPER_BLUEPRINTS = new EnumMap<>(Rotation.class);

    /**
     * Sparse, distinctive blocks sampled through the local 5,996-block
     * template. A state marker alone must never pass the city audit after the
     * building body was cleared or a travel placement failed.
     */
    private static final SkyscraperSignature[] SKYSCRAPER_SIGNATURES = {
            new SkyscraperSignature(new BlockPos(21, 8, 2),
                    Blocks.REDSTONE_LAMP),
            new SkyscraperSignature(new BlockPos(1, 9, 7),
                    Blocks.REDSTONE_LAMP),
            new SkyscraperSignature(new BlockPos(1, 53, 3),
                    Blocks.REDSTONE_LAMP),
            new SkyscraperSignature(new BlockPos(21, 53, 8),
                    Blocks.REDSTONE_LAMP),
            new SkyscraperSignature(new BlockPos(18, 74, 7),
                    Blocks.END_ROD),
            new SkyscraperSignature(new BlockPos(19, 74, 8),
                    Blocks.END_ROD),
            new SkyscraperSignature(new BlockPos(5, 80, 3),
                    Blocks.LIGHTNING_ROD),
    };

    private static final SkyscraperPlacement[] SKYSCRAPERS = {
            new SkyscraperPlacement(new BlockPos(-140, 1, -70),
                    Rotation.NONE, 0),
            new SkyscraperPlacement(new BlockPos(120, 1, -92),
                    Rotation.CLOCKWISE_90, 1),
            new SkyscraperPlacement(new BlockPos(112, 1, 82),
                    Rotation.CLOCKWISE_180, 2),
    };

    private LocalMapAssetLoader() {}

    public static boolean commandModuleAvailable()
    {
        return Files.isRegularFile(COMMAND_MODULE);
    }

    public static boolean skyscraperAvailable()
    {
        return Files.isRegularFile(TOKYO3_SKYSCRAPER);
    }

    /** Number of imported high-rises owned by the city travel scheduler. */
    public static int tokyo3SkyscraperCount()
    {
        return skyscraperAvailable() ? SKYSCRAPERS.length : 0;
    }

    /**
     * The legacy EVA-X save has this unusual iron/bedrock/iron vertical
     * signature at its city spawn. The persistent marker survives after the
     * central launch shaft deliberately cuts through that source column.
     */
    public static boolean importedTokyo3Present(BlockGetter level,
                                                BlockPos origin)
    {
        BlockPos marker = origin.offset(TOKYO3_IMPORT_MARKER);
        if (level.getBlockState(marker).is(Blocks.NETHERITE_BLOCK)
                && level.getBlockState(marker.east()).is(Blocks.LODESTONE))
        {
            return true;
        }
        return level.getBlockState(origin.below(2)).is(Blocks.IRON_BLOCK)
                && level.getBlockState(origin.below()).is(Blocks.BEDROCK)
                && level.getBlockState(origin).is(Blocks.IRON_BLOCK);
    }

    /**
     * The prepared evaluation save carries a local-only marker at its world
     * root.  Checking that marker is more reliable than inspecting legacy
     * 1.7 blocks after DataFixer has upgraded the first city chunk.
     */
    public static boolean stagedEvaWorld(ServerLevel level)
    {
        Path worldRoot = level.getServer().getWorldPath(LevelResource.ROOT);
        return Files.isRegularFile(worldRoot.resolve(STAGED_WORLD_MARKER));
    }

    public static void markPrivateGeoFrontShell(ServerLevel level,
                                                BlockPos geoFrontOrigin)
    {
        BlockPos marker = geoFrontOrigin.offset(PRIVATE_GEOFRONT_MARKER);
        set(level, marker, Blocks.NETHERITE_BLOCK.defaultBlockState());
        set(level, marker.above(), Blocks.IRON_BLOCK.defaultBlockState());
        set(level, marker.east(), Blocks.LODESTONE.defaultBlockState());
    }

    public static boolean privateGeoFrontShellPresent(BlockGetter level,
                                                       BlockPos geoFrontOrigin)
    {
        BlockPos marker = geoFrontOrigin.offset(PRIVATE_GEOFRONT_MARKER);
        return level.getBlockState(marker).is(Blocks.NETHERITE_BLOCK)
                && level.getBlockState(marker.above()).is(Blocks.IRON_BLOCK)
                && level.getBlockState(marker.east()).is(Blocks.LODESTONE);
    }

    public static void markImportedTokyo3(ServerLevel level, BlockPos origin)
    {
        BlockPos marker = origin.offset(TOKYO3_IMPORT_MARKER);
        set(level, marker, Blocks.NETHERITE_BLOCK.defaultBlockState());
        set(level, marker.east(), Blocks.LODESTONE.defaultBlockState());
    }

    public static boolean importedTokyo3MarkerPresent(BlockGetter level,
                                                      BlockPos origin)
    {
        BlockPos marker = origin.offset(TOKYO3_IMPORT_MARKER);
        return level.getBlockState(marker).is(Blocks.NETHERITE_BLOCK)
                && level.getBlockState(marker.east()).is(Blocks.LODESTONE);
    }

    public static boolean placeCommandModule(ServerLevel level,
                                             BlockPos geoFrontOrigin)
    {
        if (commandMarkersPresent(level, geoFrontOrigin))
        {
            return true;
        }
        StructureTemplate template = load(level, COMMAND_MODULE);
        if (template == null)
        {
            return false;
        }
        BlockPos base = geoFrontOrigin.offset(COMMAND_OFFSET);
        clearVolume(level, base, COMMAND_SIZE);
        boolean placed = place(level, template, base, Rotation.NONE);
        if (!placed)
        {
            ProjectSeele.LOGGER.error(
                    "Local NERV command module placement returned false at {}", base);
            return false;
        }
        TvLiftFinishR45.finishImportedCommandDoors(level);
        set(level, geoFrontOrigin.offset(COMMAND_MARKER_A),
                Blocks.NETHERITE_BLOCK.defaultBlockState());
        set(level, geoFrontOrigin.offset(COMMAND_MARKER_B),
                Blocks.LODESTONE.defaultBlockState());
        ProjectSeele.LOGGER.info(
                "Loaded private NERV command module at {} size={}x{}x{}",
                base, COMMAND_SIZE.getX(), COMMAND_SIZE.getY(),
                COMMAND_SIZE.getZ());
        return true;
    }

    /**
     * Installs the private command-room asset as the visual core of the
     * Facility v2 command owner.  The deterministic civil owner is built
     * first; this method is the single authorised post-pass and therefore
     * clears only the exact transformed template envelope.
     */
    public static boolean placeCommandModuleV2(ServerLevel level,
                                               BlockPos facilityCentre)
    {
        FacilityWorldPolicy.requireCleanRebuild(level.getServer(),
                "LocalMapAssetLoader.placeCommandModuleV2");
        FacilityV2SavedData facility = FacilityV2SavedData.get(level);
        if (!facility.commissioned()
                || !hasCompletionReceipt(facility, "COMMAND_VOLUME")
                || !hasCompletionReceipt(
                facility, "COMMAND_MODULE_CAP"))
        {
            throw new IllegalStateException(
                    "Command asset fusion requires both command-owner "
                            + "completion receipts");
        }
        StructureTemplate template = load(level, COMMAND_MODULE);
        if (template == null)
        {
            ProjectSeele.LOGGER.error(
                    "Facility v2 command fusion requires {}", COMMAND_MODULE);
            return false;
        }

        BlockPos base = facilityCentre.offset(COMMAND_V2_OFFSET);
        clearRotatedVolume(level, base, COMMAND_SIZE, COMMAND_V2_ROTATION);
        boolean placed = place(level, template, base, COMMAND_V2_ROTATION);
        if (!placed)
        {
            ProjectSeele.LOGGER.error(
                    "Facility v2 NERV command module placement returned false at {}",
                    base);
            return false;
        }
        int reopenedPorts = reopenCompletedCommandPorts(level, facility);
        ProjectSeele.LOGGER.info(
                "Installed 1:1 private NERV command core at {} rotation={} "
                        + "authoredSize={}x{}x{} transformedRelative="
                        + "x[-28,27] y[-368,-292] z[-64,64] "
                        + "reopenedPortBlocks={}",
                base, COMMAND_V2_ROTATION, COMMAND_SIZE.getX(),
                COMMAND_SIZE.getY(), COMMAND_SIZE.getZ(), reopenedPorts);
        return true;
    }

    /**
     * The private NBT is placed after the civil owner and can therefore cover
     * a declared aperture. Reopen only reciprocal routes whose peer already
     * has a completion receipt; unfinished destinations remain fail-closed.
     */
    private static int reopenCompletedCommandPorts(
            ServerLevel level, FacilityV2SavedData facility)
    {
        int writes = 0;
        for (FacilitySchemaV2.PortSpec port
                : facility.manifest().ports())
        {
            if (!"COMMAND_VOLUME".equals(port.zoneId())
                    || !hasCompletionReceipt(facility, port.peerZoneId()))
            {
                continue;
            }
            FacilitySchemaV2.IntBox aperture = port.aperture();
            FacilitySchemaV2.IntBox inner = aperture.offset(
                    -port.facing().getStepX(),
                    -port.facing().getStepY(),
                    -port.facing().getStepZ());
            writes += clearBox(level, aperture);
            writes += clearBox(level, inner);
        }
        return writes;
    }

    private static int clearBox(
            ServerLevel level, FacilitySchemaV2.IntBox box)
    {
        int writes = 0;
        BlockState air = Blocks.AIR.defaultBlockState();
        for (int x = box.minX(); x < box.maxX(); x++)
        {
            for (int y = box.minY(); y < box.maxY(); y++)
            {
                for (int z = box.minZ(); z < box.maxZ(); z++)
                {
                    BlockPos position = new BlockPos(x, y, z);
                    if (!level.getBlockState(position).isAir())
                    {
                        set(level, position, air);
                        writes++;
                    }
                }
            }
        }
        return writes;
    }

    private static boolean hasCompletionReceipt(
            FacilityV2SavedData facility, String zoneId)
    {
        FacilityV2SavedData.ZoneRecord receipt =
                facility.requireZone(zoneId);
        return receipt.state() == FacilityV2SavedData.ZoneState.COMPLETE
                && !receipt.generatorVersion().isBlank()
                && !receipt.buildPlanHash().isBlank();
    }

    public static boolean commandMarkersPresent(BlockGetter level,
                                                 BlockPos geoFrontOrigin)
    {
        return level.getBlockState(geoFrontOrigin.offset(COMMAND_MARKER_A))
                .is(Blocks.NETHERITE_BLOCK)
                && level.getBlockState(geoFrontOrigin.offset(COMMAND_MARKER_B))
                .is(Blocks.LODESTONE);
    }

    /** Package contract used when an enclosing shell is rebuilt around the asset. */
    static boolean commandEnvelopeContains(int relativeX, int relativeY,
                                           int relativeZ)
    {
        return relativeX >= COMMAND_OFFSET.getX()
                && relativeX < COMMAND_OFFSET.getX() + COMMAND_SIZE.getX()
                && relativeY >= COMMAND_OFFSET.getY()
                && relativeY < COMMAND_OFFSET.getY() + COMMAND_SIZE.getY()
                && relativeZ >= COMMAND_OFFSET.getZ()
                && relativeZ < COMMAND_OFFSET.getZ() + COMMAND_SIZE.getZ();
    }

    /** Asset markers live just outside its cleared NBT volume and must survive shell work. */
    static boolean isCommandMarkerOffset(int relativeX, int relativeY,
                                         int relativeZ)
    {
        return COMMAND_MARKER_A.equals(new BlockPos(relativeX, relativeY, relativeZ))
                || COMMAND_MARKER_B.equals(new BlockPos(relativeX, relativeY, relativeZ));
    }

    public static int placeTokyo3Skyscrapers(ServerLevel level,
                                             BlockPos tokyo3Origin)
    {
        if(CityRigidTopologyR45.owns(level,tokyo3Origin))return 0;
        return placeTokyo3Skyscrapers(level, tokyo3Origin, 0);
    }

    /**
     * Places every private high-rise at its authoritative travel depth. The
     * source NBT stays local; only these deterministic placement rules ship.
     */
    public static int placeTokyo3Skyscrapers(ServerLevel level,
                                             BlockPos tokyo3Origin,
                                             int retractionDepth)
    {
        if(CityRigidTopologyR45.owns(level,tokyo3Origin))return 0;
        StructureTemplate template = load(level, TOKYO3_SKYSCRAPER);
        if (template == null)
        {
            return 0;
        }
        if (!template.getSize().equals(SKYSCRAPER_TEMPLATE_SIZE))
        {
            ProjectSeele.LOGGER.error(
                    "Private Tokyo-3 skyscraper template size changed: expected={} actual={}",
                    SKYSCRAPER_TEMPLATE_SIZE, template.getSize());
            return 0;
        }

        int placed = 0;
        for (int index = 0; index < SKYSCRAPERS.length; index++)
        {
            SkyscraperPlacement placement = SKYSCRAPERS[index];
            Vec3i rotatedSize = template.getSize(placement.rotation());
            int drop = skyscraperDrop(placement, rotatedSize, retractionDepth,
                    tokyo3Origin, level);
            BlockPos surfaceBase = tokyo3Origin.offset(placement.offset());
            BlockPos base = surfaceBase.below(drop);
            BlockPos travelMarker = skyscraperMarker(base, index);
            BlockPos stateMarker = skyscraperStateMarker(tokyo3Origin, index);

            boolean travelPresent = level.getBlockState(travelMarker)
                    .is(Blocks.NETHERITE_BLOCK);
            boolean bodyPresent = skyscraperBodyPresent(
                    level, base, placement.rotation());
            if (travelPresent && bodyPresent)
            {
                if (!level.getBlockState(stateMarker).is(Blocks.LODESTONE))
                {
                    set(level, stateMarker, Blocks.LODESTONE.defaultBlockState());
                }
                placed++;
                continue;
            }

            // The state marker is only a completion receipt. Invalidate it
            // before clearing or writing any part of the real building.
            set(level, stateMarker, Blocks.AIR.defaultBlockState());
            clearStaleSkyscraperCopies(level, tokyo3Origin, placement,
                    template.getSize(), index, base);
            clearSkyscraperVolume(level, base, template.getSize(),
                    placement.rotation());
            set(level, travelMarker, Blocks.AIR.defaultBlockState());

            boolean written = place(level, template, base, placement.rotation());
            if (written && skyscraperBodyPresent(
                    level, base, placement.rotation()))
            {
                set(level, travelMarker, Blocks.NETHERITE_BLOCK.defaultBlockState());
                set(level, stateMarker, Blocks.LODESTONE.defaultBlockState());
                placed++;
            }
            else
            {
                // A partial write must remain visibly incomplete so the next
                // setup/ensure pass retries it instead of trusting stale NBT.
                set(level, travelMarker, Blocks.AIR.defaultBlockState());
                set(level, stateMarker, Blocks.AIR.defaultBlockState());
                ProjectSeele.LOGGER.error(
                        "Private Tokyo-3 skyscraper {} failed structural placement at {} depth={}",
                        index, base, retractionDepth);
            }
        }
        if (placed > 0)
        {
            ProjectSeele.LOGGER.info(
                    "Tokyo-3 private skyscraper set present: {}/{} depth={}",
                    placed, SKYSCRAPERS.length, retractionDepth);
        }
        return placed;
    }

    /**
     * Whole-structure travel in one-block layers. Doorways, roofs and every
     * authored floor move together instead of the old four-block visual jump.
     */
    public static void applyTokyo3RetractionDepth(ServerLevel level,
                                                  BlockPos tokyo3Origin,
                                                  int oldDepth, int newDepth)
    {
        if (CityRigidTopologyR45.owns(level, tokyo3Origin))
        {
            return;
        }
        for (int index = 0; index < SKYSCRAPERS.length; index++)
        {
            applyTokyo3RetractionDepth(level, tokyo3Origin, oldDepth,
                    newDepth, index);
        }
    }

    /**
     * Advances one imported high-rise by a bounded part of a one-block move.
     * The returned cursor is persisted before the next server tick, so normal
     * save/reload continues the same bottom-up (or top-down) traversal rather
     * than replaying the complete building.
     */
    public static SkyscraperTravelStep stepTokyo3RetractionDepth(
            ServerLevel level, BlockPos tokyo3Origin, int oldDepth,
            int newDepth, int index, int voxelCursor)
    {
        if(CityRigidTopologyR45.owns(level,tokyo3Origin))return new SkyscraperTravelStep(false,true,voxelCursor,0);
        StructureTemplate template = load(level, TOKYO3_SKYSCRAPER);
        if (template == null)
        {
            return new SkyscraperTravelStep(false, true, voxelCursor, 0);
        }
        if (!template.getSize().equals(SKYSCRAPER_TEMPLATE_SIZE)
                || index < 0 || index >= SKYSCRAPERS.length)
        {
            ProjectSeele.LOGGER.error(
                    "Private Tokyo-3 bounded travel refused: index={} expectedSize={} actualSize={}",
                    index, SKYSCRAPER_TEMPLATE_SIZE, template.getSize());
            return new SkyscraperTravelStep(false, true, voxelCursor, 0);
        }

        SkyscraperPlacement placement = SKYSCRAPERS[index];
        Map<BlockPos, BlockState> blueprint = skyscraperBlueprint(
                template, placement.rotation());
        if (blueprint.isEmpty())
        {
            return new SkyscraperTravelStep(false, true, voxelCursor, 0);
        }
        Vec3i rotatedSize = template.getSize(placement.rotation());
        int oldDrop = skyscraperDrop(placement, rotatedSize, oldDepth,
                tokyo3Origin, level);
        int newDrop = skyscraperDrop(placement, rotatedSize, newDepth,
                tokyo3Origin, level);
        if (oldDrop == newDrop)
        {
            return new SkyscraperTravelStep(true, false, 0, 0);
        }

        BlockPos surfaceBase = tokyo3Origin.offset(placement.offset());
        BlockPos oldBase = surfaceBase.below(oldDrop);
        BlockPos newBase = surfaceBase.below(newDrop);
        int deltaY = newBase.getY() - oldBase.getY();
        if (deltaY != -1 && deltaY != 1)
        {
            return new SkyscraperTravelStep(false, true, voxelCursor, 0);
        }

        SkyscraperBounds bounds = skyscraperBounds(placement.rotation());
        int width = bounds.maximumX() - bounds.minimumX() + 1;
        int depth = bounds.maximumZ() - bounds.minimumZ() + 1;
        int footprint = width * depth;
        int bodyVoxels = footprint * SKYSCRAPER_TEMPLATE_SIZE.getY();
        int totalVoxels = bodyVoxels + footprint;
        if (voxelCursor < 0 || voxelCursor > totalVoxels)
        {
            ProjectSeele.LOGGER.error(
                    "Private Tokyo-3 bounded travel cursor out of range: tower={} cursor={}/{}",
                    index, voxelCursor, totalVoxels);
            return new SkyscraperTravelStep(false, true, voxelCursor, 0);
        }

        BlockPos lower = oldBase.offset(bounds.minimumX(),
                Math.min(0, deltaY), bounds.minimumZ());
        BlockPos upper = oldBase.offset(bounds.maximumX(),
                SKYSCRAPER_TEMPLATE_SIZE.getY() - 1 + Math.max(0, deltaY),
                bounds.maximumZ());
        if (!level.isInWorldBounds(lower) || !level.isInWorldBounds(upper))
        {
            return new SkyscraperTravelStep(false, true, voxelCursor, 0);
        }

        BlockPos stateMarker = skyscraperStateMarker(tokyo3Origin, index);
        if (voxelCursor == 0)
        {
            if (!level.getBlockState(skyscraperMarker(oldBase, index))
                    .is(Blocks.NETHERITE_BLOCK)
                    || !skyscraperBodyPresent(level, oldBase,
                    placement.rotation()))
            {
                // SavedData is authoritative for the depth.  A pre-fix
                // interrupted layer can leave the private tower clipped by
                // the cavern shell even though the rest of the district is
                // coherent. Repair only this exact transformed tower volume,
                // then execute the normal one-layer translation.
                ProjectSeele.LOGGER.warn(
                        "Private Tokyo-3 tower {} repairing incomplete authoritative source at depth {}",
                        index, oldDepth);
                set(level, stateMarker, Blocks.AIR.defaultBlockState());
                clearSkyscraperVolume(level, oldBase, template.getSize(),
                        placement.rotation());
                set(level, skyscraperMarker(oldBase, index),
                        Blocks.AIR.defaultBlockState());
                if (!place(level, template, oldBase, placement.rotation())
                        || !skyscraperBodyPresent(level, oldBase,
                        placement.rotation()))
                {
                    ProjectSeele.LOGGER.error(
                            "Private Tokyo-3 tower {} could not repair authoritative source at depth {}",
                            index, oldDepth);
                    return new SkyscraperTravelStep(false, true, 0, 0);
                }
                set(level, skyscraperMarker(oldBase, index),
                        Blocks.NETHERITE_BLOCK.defaultBlockState());
            }
            if (containsSkyscraperBlockEntity(level, oldBase,
                    placement.rotation()))
            {
                ProjectSeele.LOGGER.error(
                        "Private Tokyo-3 tower {} bounded travel refused: runtime block entity found",
                        index);
                return new SkyscraperTravelStep(false, true, 0, 0);
            }
            set(level, stateMarker, Blocks.AIR.defaultBlockState());
            set(level, skyscraperMarker(oldBase, index),
                    Blocks.AIR.defaultBlockState());
            set(level, skyscraperMarker(newBase, index),
                    Blocks.AIR.defaultBlockState());
        }

        int cursor = voxelCursor;
        int scanned = 0;
        int writes = 0;
        while (cursor < totalVoxels
                && scanned < SKYSCRAPER_STEP_SCAN_BUDGET
                && writes < SKYSCRAPER_STEP_WRITE_BUDGET)
        {
            if (cursor < bodyVoxels)
            {
                int yOrder = cursor / footprint;
                int planeIndex = cursor % footprint;
                int x = bounds.minimumX() + planeIndex / depth;
                int z = bounds.minimumZ() + planeIndex % depth;
                int y = deltaY < 0 ? yOrder
                        : SKYSCRAPER_TEMPLATE_SIZE.getY() - 1 - yOrder;
                BlockPos source = oldBase.offset(x, y, z);
                BlockState canonical = blueprint.getOrDefault(
                        new BlockPos(x, y, z),
                        Blocks.AIR.defaultBlockState());
                writes += setIfChangedTracked(level,
                        source.offset(0, deltaY, 0),
                        canonical);
            }
            else
            {
                int planeIndex = cursor - bodyVoxels;
                int x = bounds.minimumX() + planeIndex / depth;
                int z = bounds.minimumZ() + planeIndex % depth;
                int abandonedY = deltaY < 0
                        ? SKYSCRAPER_TEMPLATE_SIZE.getY() - 1 : 0;
                writes += setIfChangedTracked(level,
                        oldBase.offset(x, abandonedY, z),
                        Blocks.AIR.defaultBlockState());
            }
            cursor++;
            scanned++;
        }

        if (cursor < totalVoxels)
        {
            return new SkyscraperTravelStep(false, false, cursor, writes);
        }
        if (skyscraperBodyPresent(level, newBase, placement.rotation()))
        {
            finishSkyscraperTravelSurface(level, tokyo3Origin, oldBase,
                    newBase, bounds, deltaY);
            set(level, skyscraperMarker(newBase, index),
                    Blocks.NETHERITE_BLOCK.defaultBlockState());
            set(level, stateMarker, Blocks.LODESTONE.defaultBlockState());
            return new SkyscraperTravelStep(true, false, 0, writes);
        }

        // A legacy save can contain a half-travelled imported tower.  Runtime
        // chunk state and SavedData are persisted independently, so the upper
        // half may have been replaced by the cavern shell before the cursor
        // resumed.  Roll back only this tower's exact transformed cuboid to
        // the authoritative old depth.  With the full-tower bounded budget the
        // next tick completes the layer atomically; no district-wide rebuild
        // or road volume is touched.
        ProjectSeele.LOGGER.error(
                "Private Tokyo-3 bounded tower {} failed verification depth {} -> {}; world left fail-closed at terminal cursor",
                index, oldDepth, newDepth);
        logSkyscraperSignatureMismatches(level, newBase,
                placement.rotation(), index);
        set(level, stateMarker, Blocks.AIR.defaultBlockState());
        clearSkyscraperVolume(level, newBase, template.getSize(),
                placement.rotation());
        boolean restored = place(level, template, oldBase,
                placement.rotation()) && skyscraperBodyPresent(
                level, oldBase, placement.rotation());
        set(level, skyscraperMarker(oldBase, index), restored
                ? Blocks.NETHERITE_BLOCK.defaultBlockState()
                : Blocks.AIR.defaultBlockState());
        if (restored)
        {
            ProjectSeele.LOGGER.warn(
                    "Private Tokyo-3 tower {} rolled back incomplete layer {} -> {}; retrying from cursor zero",
                    index, oldDepth, newDepth);
            return new SkyscraperTravelStep(false, false, 0, writes);
        }
        return new SkyscraperTravelStep(false, true, totalVoxels, writes);
    }

    /**
     * Closes the fixed street plane after a complete tower translation.
     *
     * <p>The private template contains intentional air inside its footprint.
     * Copying that air through world Y=Tokyo-3 ground carved a building-sized
     * pit, while an interrupted legacy layer could leave its old top cap
     * floating at the original height.  The moving shell still owns every
     * non-air surface voxel; only exposed air is replaced by a flush segmented
     * armour hatch.</p>
     */
    private static void finishSkyscraperTravelSurface(
            ServerLevel level, BlockPos tokyo3Origin, BlockPos oldBase,
            BlockPos newBase, SkyscraperBounds bounds, int deltaY)
    {
        if (deltaY < 0)
        {
            int oldTopY = oldBase.getY()
                    + SKYSCRAPER_TEMPLATE_SIZE.getY() - 1;
            for (int x = bounds.minimumX(); x <= bounds.maximumX(); x++)
            {
                for (int z = bounds.minimumZ(); z <= bounds.maximumZ(); z++)
                {
                    setIfChanged(level, new BlockPos(oldBase.getX() + x,
                            oldTopY, oldBase.getZ() + z),
                            Blocks.AIR.defaultBlockState());
                }
            }
        }

        int groundY = tokyo3Origin.getY();
        int width = bounds.maximumX() - bounds.minimumX();
        int depth = bounds.maximumZ() - bounds.minimumZ();
        for (int x = bounds.minimumX(); x <= bounds.maximumX(); x++)
        {
            for (int z = bounds.minimumZ(); z <= bounds.maximumZ(); z++)
            {
                BlockPos surface = new BlockPos(newBase.getX() + x,
                        groundY, newBase.getZ() + z);
                if (!level.getBlockState(surface).isAir())
                {
                    continue;
                }
                boolean rim = x == bounds.minimumX()
                        || x == bounds.maximumX()
                        || z == bounds.minimumZ()
                        || z == bounds.maximumZ();
                boolean seam = Math.floorMod(x - bounds.minimumX(), 5) == 0
                        || Math.floorMod(z - bounds.minimumZ(), 5) == 0;
                BlockState hatch = rim
                        ? Blocks.POLISHED_DEEPSLATE.defaultBlockState()
                        : seam
                        ? Blocks.IRON_BLOCK.defaultBlockState()
                        : Blocks.GRAY_CONCRETE.defaultBlockState();
                setIfChanged(level, surface, hatch);
            }
        }
    }

    private static void logSkyscraperSignatureMismatches(
            BlockGetter level, BlockPos base, Rotation rotation, int index)
    {
        for (SkyscraperSignature signature : SKYSCRAPER_SIGNATURES)
        {
            BlockPos transformed = StructureTemplate.transform(
                    signature.offset(), Mirror.NONE, rotation, BlockPos.ZERO);
            BlockPos position = base.offset(transformed);
            BlockState actual = level.getBlockState(position);
            if (!actual.is(signature.block()))
            {
                ProjectSeele.LOGGER.error(
                        "Private Tokyo-3 tower {} signature mismatch at {} expected={} actual={}",
                        index, position.toShortString(),
                        signature.block(), actual.getBlock());
            }
        }
    }

    /**
     * Moves one imported high-rise for the current one-block city layer.
     * The city director calls the three indices on separate ticks so the
     * complete buildings visibly descend without one large write spike.
     */
    public static void applyTokyo3RetractionDepth(ServerLevel level,
                                                  BlockPos tokyo3Origin,
                                                  int oldDepth, int newDepth,
                                                  int index)
    {
        if (CityRigidTopologyR45.owns(level, tokyo3Origin))
        {
            return;
        }
        StructureTemplate template = load(level, TOKYO3_SKYSCRAPER);
        if (template == null)
        {
            return;
        }
        if (!template.getSize().equals(SKYSCRAPER_TEMPLATE_SIZE))
        {
            ProjectSeele.LOGGER.error(
                    "Private Tokyo-3 skyscraper travel refused: expected size={} actual={}",
                    SKYSCRAPER_TEMPLATE_SIZE, template.getSize());
            return;
        }
        if (index < 0 || index >= SKYSCRAPERS.length)
        {
            throw new IndexOutOfBoundsException(
                    "Tokyo-3 skyscraper index " + index);
        }

        SkyscraperPlacement placement = SKYSCRAPERS[index];
        Vec3i rotatedSize = template.getSize(placement.rotation());
        int oldDrop = skyscraperDrop(placement, rotatedSize, oldDepth,
                tokyo3Origin, level);
        int newDrop = skyscraperDrop(placement, rotatedSize, newDepth,
                tokyo3Origin, level);
        BlockPos surfaceBase = tokyo3Origin.offset(placement.offset());
        BlockPos oldBase = surfaceBase.below(oldDrop);
        BlockPos newBase = surfaceBase.below(newDrop);
        BlockPos stateMarker = skyscraperStateMarker(tokyo3Origin, index);

        if (oldDrop == newDrop)
        {
            BlockPos travelMarker = skyscraperMarker(newBase, index);
            if (level.getBlockState(travelMarker).is(Blocks.NETHERITE_BLOCK)
                    && skyscraperBodyPresent(
                    level, newBase, placement.rotation()))
            {
                set(level, stateMarker, Blocks.LODESTONE.defaultBlockState());
                return;
            }

            set(level, stateMarker, Blocks.AIR.defaultBlockState());
            clearStaleSkyscraperCopies(level, tokyo3Origin, placement,
                    template.getSize(), index, newBase);
            clearSkyscraperVolume(level, newBase, template.getSize(),
                    placement.rotation());
            set(level, travelMarker, Blocks.AIR.defaultBlockState());
            if (place(level, template, newBase, placement.rotation())
                    && skyscraperBodyPresent(
                    level, newBase, placement.rotation()))
            {
                set(level, travelMarker,
                        Blocks.NETHERITE_BLOCK.defaultBlockState());
                set(level, stateMarker, Blocks.LODESTONE.defaultBlockState());
            }
            else
            {
                set(level, travelMarker, Blocks.AIR.defaultBlockState());
                ProjectSeele.LOGGER.error(
                        "Private Tokyo-3 skyscraper {} failed repair at depth {}",
                        index, newDepth);
            }
            return;
        }

        if (!level.getBlockState(skyscraperMarker(oldBase, index))
                .is(Blocks.NETHERITE_BLOCK)
                || !skyscraperBodyPresent(level, oldBase,
                placement.rotation()))
        {
            // Recover only at the SavedData-authoritative source. Never guess
            // a destination after a crash: a remote receipt cannot make a
            // half-written tower safe to translate.
            set(level, stateMarker, Blocks.AIR.defaultBlockState());
            clearStaleSkyscraperCopies(level, tokyo3Origin, placement,
                    template.getSize(), index, oldBase);
            clearSkyscraperVolume(level, oldBase, template.getSize(),
                    placement.rotation());
            set(level, skyscraperMarker(oldBase, index),
                    Blocks.AIR.defaultBlockState());
            if (!place(level, template, oldBase, placement.rotation())
                    || !skyscraperBodyPresent(level, oldBase,
                    placement.rotation()))
            {
                ProjectSeele.LOGGER.error(
                        "Private Tokyo-3 skyscraper {} cannot recover source at depth {}",
                        index, oldDepth);
                return;
            }
            set(level, skyscraperMarker(oldBase, index),
                    Blocks.NETHERITE_BLOCK.defaultBlockState());
        }

        if (containsSkyscraperBlockEntity(level, oldBase,
                placement.rotation()))
        {
            ProjectSeele.LOGGER.error(
                    "Private Tokyo-3 skyscraper {} travel refused: runtime block entity found",
                    index);
            set(level, stateMarker, Blocks.AIR.defaultBlockState());
            return;
        }

        set(level, stateMarker, Blocks.AIR.defaultBlockState());
        set(level, skyscraperMarker(oldBase, index),
                Blocks.AIR.defaultBlockState());
        set(level, skyscraperMarker(newBase, index),
                Blocks.AIR.defaultBlockState());

        boolean moved = translateSkyscraperOneBlock(level, oldBase, newBase,
                placement.rotation()) && skyscraperBodyPresent(
                level, newBase, placement.rotation());
        if (moved)
        {
            set(level, skyscraperMarker(newBase, index),
                    Blocks.NETHERITE_BLOCK.defaultBlockState());
            set(level, stateMarker, Blocks.LODESTONE.defaultBlockState());
            return;
        }

        // Translation mutates only the one-block frontier and vertically
        // shifted body. Rebuild the authoritative source as the bounded crash
        // fallback; unlike the old path it never clears the destination's
        // complete 23x82x12 cuboid before knowing a move can succeed.
        clearSkyscraperVolume(level, newBase, template.getSize(),
                placement.rotation());
        boolean restored = place(level, template, oldBase,
                placement.rotation()) && skyscraperBodyPresent(level,
                oldBase, placement.rotation());
        set(level, skyscraperMarker(oldBase, index), restored
                ? Blocks.NETHERITE_BLOCK.defaultBlockState()
                : Blocks.AIR.defaultBlockState());
        set(level, stateMarker, Blocks.AIR.defaultBlockState());
        ProjectSeele.LOGGER.error(
                "Private Tokyo-3 skyscraper {} failed to move depth {} -> {}; restoredOld={}",
                index, oldDepth, newDepth, restored);
    }

    /**
     * Physically translates the already-placed high-rise by one block.
     *
     * <p>Replaying the complete structure on every layer used to clear two
     * overlapping 23x82x12 cuboids and then write all 5,996 authored blocks.
     * Apart from the severe tick spike, that could erase unrelated ground at
     * the destination.  A one-block vertical shift only owns one new frontier
     * slice.  Copy order keeps every source unread until it has been consumed;
     * equal repeating facade states produce no world write.</p>
     */
    private static boolean translateSkyscraperOneBlock(ServerLevel level,
                                                        BlockPos oldBase,
                                                        BlockPos newBase,
                                                        Rotation rotation)
    {
        int deltaY = newBase.getY() - oldBase.getY();
        if (deltaY != -1 && deltaY != 1)
        {
            ProjectSeele.LOGGER.error(
                    "Private Tokyo-3 skyscraper translation must be one block: {} -> {}",
                    oldBase, newBase);
            return false;
        }
        SkyscraperBounds bounds = skyscraperBounds(rotation);
        BlockPos lower = oldBase.offset(bounds.minimumX(),
                Math.min(0, deltaY), bounds.minimumZ());
        BlockPos upper = oldBase.offset(bounds.maximumX(),
                SKYSCRAPER_TEMPLATE_SIZE.getY() - 1 + Math.max(0, deltaY),
                bounds.maximumZ());
        if (!level.isInWorldBounds(lower) || !level.isInWorldBounds(upper))
        {
            return false;
        }

        int firstY = deltaY < 0 ? 0 : SKYSCRAPER_TEMPLATE_SIZE.getY() - 1;
        int endY = deltaY < 0 ? SKYSCRAPER_TEMPLATE_SIZE.getY() : -1;
        int stepY = deltaY < 0 ? 1 : -1;
        for (int y = firstY; y != endY; y += stepY)
        {
            for (int x = bounds.minimumX(); x <= bounds.maximumX(); x++)
            {
                for (int z = bounds.minimumZ(); z <= bounds.maximumZ(); z++)
                {
                    BlockPos source = oldBase.offset(x, y, z);
                    BlockPos target = source.offset(0, deltaY, 0);
                    setIfChanged(level, target, level.getBlockState(source));
                }
            }
        }

        int abandonedY = deltaY < 0
                ? SKYSCRAPER_TEMPLATE_SIZE.getY() - 1 : 0;
        for (int x = bounds.minimumX(); x <= bounds.maximumX(); x++)
        {
            for (int z = bounds.minimumZ(); z <= bounds.maximumZ(); z++)
            {
                setIfChanged(level, oldBase.offset(x, abandonedY, z),
                        Blocks.AIR.defaultBlockState());
            }
        }
        return true;
    }

    private static boolean containsSkyscraperBlockEntity(ServerLevel level,
                                                           BlockPos base,
                                                           Rotation rotation)
    {
        SkyscraperBounds bounds = skyscraperBounds(rotation);
        for (int x = bounds.minimumX(); x <= bounds.maximumX(); x++)
        {
            for (int z = bounds.minimumZ(); z <= bounds.maximumZ(); z++)
            {
                for (int y = 0; y < SKYSCRAPER_TEMPLATE_SIZE.getY(); y++)
                {
                    if (level.getBlockEntity(base.offset(x, y, z)) != null)
                    {
                        return true;
                    }
                }
            }
        }
        return false;
    }

    public static int inspectTokyo3Skyscrapers(BlockGetter level,
                                               BlockPos tokyo3Origin)
    {
        return inspectTokyo3Skyscrapers(level, tokyo3Origin, 0);
    }

    /**
     * Counts only complete buildings at the position implied by the current
     * persisted retraction depth. A remote completion marker cannot mask a
     * missing body or a tower stranded at a previous travel quantum.
     */
    public static int inspectTokyo3Skyscrapers(BlockGetter level,
                                               BlockPos tokyo3Origin,
                                               int retractionDepth)
    {
        int found = 0;
        for (int index = 0; index < SKYSCRAPERS.length; index++)
        {
            SkyscraperPlacement placement = SKYSCRAPERS[index];
            Vec3i rotatedSize = rotatedSkyscraperSize(placement.rotation());
            int drop = skyscraperDrop(placement, rotatedSize, retractionDepth,
                    tokyo3Origin, level);
            BlockPos base = tokyo3Origin.offset(placement.offset()).below(drop);
            if (level.getBlockState(skyscraperStateMarker(tokyo3Origin, index))
                    .is(Blocks.LODESTONE)
                    && level.getBlockState(skyscraperMarker(base, index))
                    .is(Blocks.NETHERITE_BLOCK)
                    && skyscraperBodyPresent(
                    level, base, placement.rotation()))
            {
                found++;
            }
        }
        return found;
    }

    /** Complete cargo check, including fragile lights omitted by old marker probes. */
    public static int inspectTokyo3CargoMismatches(ServerLevel level, BlockPos origin, int depth)
    {
        StructureTemplate template = load(level, TOKYO3_SKYSCRAPER);
        if (template == null) return -1;
        int mismatches = 0;
        for (int i = 0; i < SKYSCRAPERS.length; i++)
        {
            SkyscraperPlacement placement = SKYSCRAPERS[i];
            int drop = skyscraperDrop(placement, rotatedSkyscraperSize(placement.rotation()), depth, origin, level);
            BlockPos base = origin.offset(placement.offset()).below(drop);
            for (var block : skyscraperBlueprint(template, placement.rotation()).entrySet())
            {
                BlockPos position = base.offset(block.getKey());
                if (position.equals(skyscraperMarker(base, i))) continue;
                if (!level.getBlockState(position).equals(block.getValue()))
                {
                    if (mismatches < 8) ProjectSeele.LOGGER.warn("Private Tokyo-3 cargo mismatch: {} actual={} expected={}",
                            position, level.getBlockState(position), block.getValue());
                    mismatches++;
                }
            }
        }
        return mismatches;
    }

    /** Repairs only the three private towers' abandoned vertical travel
     * shafts. This is safe for a hand-edited city because no road or block
     * outside the exact imported footprints is touched. */
    public static void repairTokyo3TravelArtifacts(ServerLevel level,
                                                    BlockPos tokyo3Origin,
                                                    int retractionDepth)
    {
        if(CityRigidTopologyR45.owns(level,tokyo3Origin))return;
        for (int index = 0; index < SKYSCRAPERS.length; index++)
        {
            SkyscraperPlacement placement = SKYSCRAPERS[index];
            Vec3i rotatedSize = rotatedSkyscraperSize(placement.rotation());
            int drop = skyscraperDrop(placement, rotatedSize,
                    retractionDepth, tokyo3Origin, level);
            BlockPos surfaceBase = tokyo3Origin.offset(placement.offset());
            BlockPos expectedBase = surfaceBase.below(drop);
            SkyscraperBounds bounds = skyscraperBounds(placement.rotation());
            int expectedTop = expectedBase.getY()
                    + SKYSCRAPER_TEMPLATE_SIZE.getY() - 1;
            int originalTop = surfaceBase.getY()
                    + SKYSCRAPER_TEMPLATE_SIZE.getY() - 1;
            int lowestBase = surfaceBase.getY()
                    - ThirdTokyoSurfaceBuilder.maximumRetractionDepth(tokyo3Origin);
            int belowCurrentTop = Math.min(expectedBase.getY() - 1,
                    tokyo3Origin.getY() - 1);
            for (int y = lowestBase; y <= belowCurrentTop; y++)
            {
                for (int x = bounds.minimumX(); x <= bounds.maximumX(); x++)
                {
                    for (int z = bounds.minimumZ(); z <= bounds.maximumZ(); z++)
                    {
                        BlockPos abandoned = new BlockPos(surfaceBase.getX() + x, y,
                                surfaceBase.getZ() + z);
                        // The current marker sits one block below the cargo.
                        // Erasing it here forced a healthy tower to rebuild
                        // at the first upward layer after every reversal.
                        if (!abandoned.equals(skyscraperMarker(expectedBase, index)))
                            setIfChanged(level, abandoned, Blocks.AIR.defaultBlockState());
                    }
                }
            }
            for (int y = expectedTop + 1;
                 y <= originalTop + SKYSCRAPER_ABANDONED_ROOF_MARGIN; y++)
            {
                for (int x = bounds.minimumX(); x <= bounds.maximumX(); x++)
                {
                    for (int z = bounds.minimumZ(); z <= bounds.maximumZ(); z++)
                    {
                        BlockPos abandoned = new BlockPos(
                                surfaceBase.getX() + x, y,
                                surfaceBase.getZ() + z);
                        setIfChanged(level, abandoned,
                                Blocks.AIR.defaultBlockState());
                    }
                }
            }
            finishSkyscraperTravelSurface(level, tokyo3Origin,
                    expectedBase, expectedBase, bounds, 0);
        }
    }

    /**
     * Returns every transformed non-air template state. Missing cells inside
     * the transformed cuboid are canonical air. Reading this immutable source
     * instead of the live tower prevents roads, temporary roofs or player
     * blocks from becoming part of the moving load.
     */
    private static Map<BlockPos, BlockState> skyscraperBlueprint(
            StructureTemplate template, Rotation rotation)
    {
        Map<BlockPos, BlockState> cached = SKYSCRAPER_BLUEPRINTS.get(rotation);
        if (cached != null)
        {
            return cached;
        }
        StructurePlaceSettings settings = new StructurePlaceSettings()
                .setMirror(Mirror.NONE)
                .setRotation(rotation)
                .setIgnoreEntities(true)
                .setKnownShape(true);
        CompoundTag saved = template.save(new CompoundTag());
        ListTag palette = saved.getList("palette", Tag.TAG_COMPOUND);
        Map<BlockPos, BlockState> blueprint = new HashMap<>();
        for (int index = 0; index < palette.size(); index++)
        {
            ResourceLocation id = ResourceLocation.tryParse(
                    palette.getCompound(index).getString("Name"));
            if (id == null)
            {
                continue;
            }
            Block block = BuiltInRegistries.BLOCK.get(id);
            if (block == Blocks.AIR)
            {
                continue;
            }
            for (StructureTemplate.StructureBlockInfo info
                    : template.filterBlocks(BlockPos.ZERO, settings,
                    block, true))
            {
                blueprint.put(info.pos().immutable(), info.state());
            }
        }
        Map<BlockPos, BlockState> immutable = Map.copyOf(blueprint);
        SKYSCRAPER_BLUEPRINTS.put(rotation, immutable);
        return immutable;
    }

    /** Adds every chunk touched by the three rotated private high-rises. */
    public static void addTokyo3SkyscraperTravelChunks(
            BlockPos tokyo3Origin, Set<Long> chunks)
    {
        for (SkyscraperPlacement placement : SKYSCRAPERS)
        {
            SkyscraperBounds bounds = skyscraperBounds(placement.rotation());
            int baseX = tokyo3Origin.getX() + placement.offset().getX();
            int baseZ = tokyo3Origin.getZ() + placement.offset().getZ();
            for (int chunkX = SectionPos.blockToSectionCoord(
                    baseX + bounds.minimumX());
                 chunkX <= SectionPos.blockToSectionCoord(
                         baseX + bounds.maximumX()); chunkX++)
            {
                for (int chunkZ = SectionPos.blockToSectionCoord(
                        baseZ + bounds.minimumZ());
                     chunkZ <= SectionPos.blockToSectionCoord(
                             baseZ + bounds.maximumZ()); chunkZ++)
                {
                    chunks.add(net.minecraft.world.level.ChunkPos.asLong(
                            chunkX, chunkZ));
                }
            }
        }
    }

    /**
     * True when a player or EVA occupies any imported building's complete
     * source/destination envelope. A block building is never allowed to move
     * around a rider; a future smooth carrier may relax this explicitly.
     */
    public static boolean tokyo3SkyscraperTravelOccupied(
            ServerLevel level, BlockPos tokyo3Origin,
            int oldDepth, int newDepth)
    {
        for (SkyscraperPlacement placement : SKYSCRAPERS)
        {
            Vec3i rotatedSize = rotatedSkyscraperSize(placement.rotation());
            int oldDrop = skyscraperDrop(placement, rotatedSize, oldDepth,
                    tokyo3Origin, level);
            int newDrop = skyscraperDrop(placement, rotatedSize, newDepth,
                    tokyo3Origin, level);
            SkyscraperBounds bounds = skyscraperBounds(placement.rotation());
            BlockPos surfaceBase = tokyo3Origin.offset(placement.offset());
            int minimumY = surfaceBase.getY() - Math.max(oldDrop, newDrop);
            int maximumY = surfaceBase.getY() - Math.min(oldDrop, newDrop)
                    + SKYSCRAPER_TEMPLATE_SIZE.getY();
            AABB envelope = new AABB(
                    surfaceBase.getX() + bounds.minimumX(), minimumY,
                    surfaceBase.getZ() + bounds.minimumZ(),
                    surfaceBase.getX() + bounds.maximumX() + 1, maximumY,
                    surfaceBase.getZ() + bounds.maximumZ() + 1);
            if (!level.getEntitiesOfClass(LivingEntity.class, envelope,
                    entity -> entity.isAlive() && !entity.isSpectator()
                            && (entity instanceof Player
                            || entity instanceof EvaUnit01Entity)).isEmpty())
            {
                return true;
            }
        }
        return false;
    }

    private static boolean skyscraperBodyPresent(BlockGetter level,
                                                  BlockPos base,
                                                  Rotation rotation)
    {
        for (SkyscraperSignature signature : SKYSCRAPER_SIGNATURES)
        {
            BlockPos transformed = StructureTemplate.transform(
                    signature.offset(), Mirror.NONE, rotation, BlockPos.ZERO);
            if (!level.getBlockState(base.offset(transformed))
                    .is(signature.block()))
            {
                return false;
            }
        }
        return true;
    }

    private static Vec3i rotatedSkyscraperSize(Rotation rotation)
    {
        if (rotation == Rotation.CLOCKWISE_90
                || rotation == Rotation.COUNTERCLOCKWISE_90)
        {
            return new Vec3i(SKYSCRAPER_TEMPLATE_SIZE.getZ(),
                    SKYSCRAPER_TEMPLATE_SIZE.getY(),
                    SKYSCRAPER_TEMPLATE_SIZE.getX());
        }
        return SKYSCRAPER_TEMPLATE_SIZE;
    }

    /**
     * Removes complete private-template copies left at an earlier travel quantum.
     * Either our receipt or all seven body signatures is required, allowing
     * schema upgrades to remove legacy unmarked surface duplicates safely.
     */
    private static void clearStaleSkyscraperCopies(ServerLevel level,
                                                   BlockPos tokyo3Origin,
                                                   SkyscraperPlacement placement,
                                                   Vec3i templateSize,
                                                   int index,
                                                   BlockPos expectedBase)
    {
        Vec3i rotatedSize = rotatedSkyscraperSize(placement.rotation());
        BlockPos surfaceBase = tokyo3Origin.offset(placement.offset());
        int previousDrop = Integer.MIN_VALUE;
        int maximumDepth = ThirdTokyoSurfaceBuilder.maximumRetractionDepth(
                tokyo3Origin);
        for (int depth = 0; depth <= maximumDepth; depth++)
        {
            int drop = skyscraperDrop(placement, rotatedSize, depth,
                    tokyo3Origin, level);
            if (drop == previousDrop)
            {
                continue;
            }
            previousDrop = drop;
            BlockPos candidate = surfaceBase.below(drop);
            if (!candidate.equals(expectedBase)
                    && (level.getBlockState(skyscraperMarker(candidate, index))
                    .is(Blocks.NETHERITE_BLOCK)
                    || skyscraperBodyPresent(
                            level, candidate, placement.rotation())))
            {
                clearSkyscraperVolume(level, candidate, templateSize,
                        placement.rotation());
                set(level, skyscraperMarker(candidate, index),
                        Blocks.AIR.defaultBlockState());
            }
        }
    }

    /**
     * Rotation happens around the template origin, so clockwise variants can
     * occupy negative relative X/Z. Clear the transformed bounds rather than a
     * positive-only box beginning at the placement origin.
     */
    private static void clearSkyscraperVolume(ServerLevel level, BlockPos base,
                                              Vec3i templateSize,
                                              Rotation rotation)
    {
        int maximumX = templateSize.getX() - 1;
        int maximumZ = templateSize.getZ() - 1;
        int minimumRelativeX = Integer.MAX_VALUE;
        int maximumRelativeX = Integer.MIN_VALUE;
        int minimumRelativeZ = Integer.MAX_VALUE;
        int maximumRelativeZ = Integer.MIN_VALUE;
        for (int x : new int[] {0, maximumX})
        {
            for (int z : new int[] {0, maximumZ})
            {
                BlockPos transformed = StructureTemplate.transform(
                        new BlockPos(x, 0, z), Mirror.NONE, rotation,
                        BlockPos.ZERO);
                minimumRelativeX = Math.min(minimumRelativeX, transformed.getX());
                maximumRelativeX = Math.max(maximumRelativeX, transformed.getX());
                minimumRelativeZ = Math.min(minimumRelativeZ, transformed.getZ());
                maximumRelativeZ = Math.max(maximumRelativeZ, transformed.getZ());
            }
        }

        for (int x = minimumRelativeX; x <= maximumRelativeX; x++)
        {
            for (int z = minimumRelativeZ; z <= maximumRelativeZ; z++)
            {
                for (int y = 0; y < templateSize.getY(); y++)
                {
                    BlockPos position = base.offset(x, y, z);
                    if (!level.getBlockState(position).isAir())
                    {
                        setIfChanged(level, position, Blocks.AIR.defaultBlockState());
                    }
                }
            }
        }
    }

    private static int skyscraperDrop(SkyscraperPlacement placement,
                                      Vec3i size, int depth,
                                      BlockPos tokyo3Origin, BlockGetter level)
    {
        SkyscraperBounds bounds = skyscraperBounds(placement.rotation());
        int minimumX = placement.offset().getX() + bounds.minimumX();
        int maximumX = placement.offset().getX() + bounds.maximumX();
        int minimumZ = placement.offset().getZ() + bounds.minimumZ();
        int maximumZ = placement.offset().getZ() + bounds.maximumZ();
        int topAtSurface = placement.offset().getY() + size.getY() - 1;
        int ceiling = level instanceof ServerLevel serverLevel && TvWorldPreviewTerrain.active(serverLevel)
                ? TvWorldPreviewTerrain.ROOF_Y - 4 - tokyo3Origin.getY()
                : ThirdTokyoSurfaceBuilder.ceilingRoofRelativeYForBounds(
                        minimumX, maximumX, minimumZ, maximumZ,
                        tokyo3Origin);
        int targetDrop = Math.max(0, topAtSurface - ceiling);
        int bounded = Math.max(0, Math.min(depth, targetDrop));
        if (bounded == targetDrop)
        {
            return targetDrop;
        }
        return bounded - Math.floorMod(bounded,
                SKYSCRAPER_MOVE_QUANTUM);
    }

    private static SkyscraperBounds skyscraperBounds(Rotation rotation)
    {
        int maximumX = SKYSCRAPER_TEMPLATE_SIZE.getX() - 1;
        int maximumZ = SKYSCRAPER_TEMPLATE_SIZE.getZ() - 1;
        int minimumRelativeX = Integer.MAX_VALUE;
        int maximumRelativeX = Integer.MIN_VALUE;
        int minimumRelativeZ = Integer.MAX_VALUE;
        int maximumRelativeZ = Integer.MIN_VALUE;
        for (int x : new int[] {0, maximumX})
        {
            for (int z : new int[] {0, maximumZ})
            {
                BlockPos transformed = StructureTemplate.transform(
                        new BlockPos(x, 0, z), Mirror.NONE, rotation,
                        BlockPos.ZERO);
                minimumRelativeX = Math.min(minimumRelativeX, transformed.getX());
                maximumRelativeX = Math.max(maximumRelativeX, transformed.getX());
                minimumRelativeZ = Math.min(minimumRelativeZ, transformed.getZ());
                maximumRelativeZ = Math.max(maximumRelativeZ, transformed.getZ());
            }
        }
        return new SkyscraperBounds(minimumRelativeX, maximumRelativeX,
                minimumRelativeZ, maximumRelativeZ);
    }

    private static BlockPos skyscraperMarker(BlockPos base, int index)
    {
        return base.below().offset(index, 0, 0);
    }

    private static BlockPos skyscraperStateMarker(BlockPos origin, int index)
    {
        return origin.offset(SKYSCRAPER_STATE_MARKER).offset(index * 2, 0, 0);
    }
    private static StructureTemplate load(ServerLevel level, Path path)
    {
        if (!Files.isRegularFile(path))
        {
            return null;
        }
        try
        {
            CompoundTag root = NbtIo.readCompressed(path.toFile());
            StructureTemplate template = new StructureTemplate();
            template.load(level.registryAccess().lookup(Registries.BLOCK)
                    .orElseThrow(), root);
            return template;
        }
        catch (IOException | RuntimeException exception)
        {
            ProjectSeele.LOGGER.error("Unable to load private map asset {}",
                    path.toAbsolutePath(), exception);
            return null;
        }
    }

    private static boolean place(ServerLevel level, StructureTemplate template,
                                 BlockPos base, Rotation rotation)
    {
        StructurePlaceSettings settings = new StructurePlaceSettings()
                .setMirror(Mirror.NONE)
                .setRotation(rotation)
                .setIgnoreEntities(false)
                .setKnownShape(true);
        return template.placeInWorld(level, base, base, settings,
                RandomSource.create(0x5345454c45L), UPDATE_CLIENTS);
    }

    private static void clearVolume(ServerLevel level, BlockPos base,
                                    Vec3i size)
    {
        for (int x = 0; x < size.getX(); x++)
        {
            for (int z = 0; z < size.getZ(); z++)
            {
                for (int y = 0; y < size.getY(); y++)
                {
                    BlockPos position = base.offset(x, y, z);
                    if (!level.getBlockState(position).isAir())
                    {
                        set(level, position, Blocks.AIR.defaultBlockState());
                    }
                }
            }
        }
    }

    private static void clearRotatedVolume(ServerLevel level, BlockPos base,
                                           Vec3i size, Rotation rotation)
    {
        int minimumX = Integer.MAX_VALUE;
        int maximumX = Integer.MIN_VALUE;
        int minimumZ = Integer.MAX_VALUE;
        int maximumZ = Integer.MIN_VALUE;
        for (int x : new int[] {0, size.getX() - 1})
        {
            for (int z : new int[] {0, size.getZ() - 1})
            {
                BlockPos transformed = StructureTemplate.transform(
                        new BlockPos(x, 0, z), Mirror.NONE, rotation,
                        BlockPos.ZERO);
                minimumX = Math.min(minimumX, transformed.getX());
                maximumX = Math.max(maximumX, transformed.getX());
                minimumZ = Math.min(minimumZ, transformed.getZ());
                maximumZ = Math.max(maximumZ, transformed.getZ());
            }
        }
        BlockPos minimum = base.offset(minimumX, 0, minimumZ);
        Vec3i transformedSize = new Vec3i(
                maximumX - minimumX + 1, size.getY(),
                maximumZ - minimumZ + 1);
        clearVolume(level, minimum, transformedSize);
    }

    private static void set(ServerLevel level, BlockPos position,
                            net.minecraft.world.level.block.state.BlockState state)
    {
        if (level.setBlock(position, state, UPDATE_CLIENTS))
        {
            PerformanceCounters.recordWorldBlockWrites(1);
        }
    }

    private static void setIfChanged(ServerLevel level, BlockPos position,
                                     BlockState state)
    {
        setIfChangedTracked(level, position, state);
    }

    private static int setIfChangedTracked(ServerLevel level,
                                           BlockPos position,
                                           BlockState state)
    {
        if (level.getBlockState(position).equals(state))
        {
            return 0;
        }
        // A translated template is temporarily unsupported while its next
        // rows are written. Shape updates here popped every wall torch into
        // an item on every layer, producing tens of thousands of drops.
        if (level.setBlock(position, state, Block.UPDATE_CLIENTS | Block.UPDATE_KNOWN_SHAPE | Block.UPDATE_SUPPRESS_DROPS))
        {
            PerformanceCounters.recordWorldBlockWrites(1);
        }
        return 1;
    }

    public record SkyscraperTravelStep(boolean complete, boolean failed,
                                       int cursor, int writes) {}

    private record SkyscraperPlacement(BlockPos offset, Rotation rotation,
                                       int travelPhase) {}

    private record SkyscraperSignature(BlockPos offset, Block block) {}

    private record SkyscraperBounds(int minimumX, int maximumX,
                                    int minimumZ, int maximumZ) {}
}
