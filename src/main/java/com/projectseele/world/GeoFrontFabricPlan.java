package com.projectseele.world;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

import com.projectseele.registry.ModBlocks;
import com.projectseele.registry.ModFluids;
import net.minecraft.core.BlockPos;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.LightBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.ChunkPos;

/**
 * Deterministic, owner-aware exterior plan for the FacilitySchema v2 region.
 *
 * <p>The fabric deliberately describes only authored surfaces and fixtures.
 * It never scans or clears the complete cavern volume. Facility owners retain
 * exclusive authority over their AABBs plus a one-block guard band.</p>
 */
public final class GeoFrontFabricPlan
{
    public static final int FORMAT_VERSION = 2;
    public static final int FABRIC_REVISION = 8;
    public static final int GEOMETRY_VERSION = 1;

    public static final int CAVERN_CENTRE_Y = -336;
    public static final int CAVERN_RADIUS_XZ = 640;
    public static final int CAVERN_RADIUS_Y = 304;
    public static final int CAVERN_BOTTOM_Y = -640;
    public static final int CAVERN_TOP_Y = -32;

    private static final int SHELL_LEVELS =
            CAVERN_TOP_Y - CAVERN_BOTTOM_Y + 1;
    private static final int SHELL_X_SPAN =
            CAVERN_RADIUS_XZ * 2 + 1;
    private static final int SHELL_THICKNESS = 2;
    private static final long SHELL_SIDE_WORK = (long) SHELL_LEVELS
            * SHELL_X_SPAN * 2L * SHELL_THICKNESS;
    private static final long SHELL_CAP_WORK = (long) SHELL_X_SPAN
            * SHELL_X_SPAN * 2L * SHELL_THICKNESS;
    private static final long SHELL_WORK =
            SHELL_SIDE_WORK + SHELL_CAP_WORK;

    private static final int TERRAIN_SIDE = CAVERN_RADIUS_XZ * 2;
    private static final int TERRAIN_DEPTH = 4;
    private static final long TERRAIN_COLUMNS =
            (long) TERRAIN_SIDE * TERRAIN_SIDE;
    private static final long TERRAIN_WORK =
            TERRAIN_COLUMNS * TERRAIN_DEPTH;

    private static final int LIGHT_GRID_SIDE = 53;
    private static final int LIGHT_LEVELS = 12;
    private static final long LIGHT_WORK =
            (long) LIGHT_GRID_SIDE * LIGHT_GRID_SIDE * LIGHT_LEVELS;

    private static final int PYRAMID_LEVELS = 116;
    private static final int PYRAMID_Z_SPAN = 320;
    private static final int PYRAMID_X_SPAN = 304;
    private static final int PYRAMID_SHELL_THICKNESS = 4;
    private static final long PYRAMID_X_SIDES_WORK =
            (long) PYRAMID_LEVELS * PYRAMID_Z_SPAN * 2L
                    * PYRAMID_SHELL_THICKNESS;
    private static final long PYRAMID_Z_SIDES_WORK =
            (long) PYRAMID_LEVELS * PYRAMID_X_SPAN * 2L
                    * PYRAMID_SHELL_THICKNESS;
    private static final int PYRAMID_GRADE_MIN_X = -176;
    private static final int PYRAMID_GRADE_MAX_X = 176;
    private static final int PYRAMID_GRADE_MIN_Z = -144;
    private static final int PYRAMID_GRADE_MAX_Z = 244;
    private static final int PYRAMID_GRADE_MIN_Y = -369;
    private static final int PYRAMID_GRADE_SURFACE_Y = -361;
    private static final int PYRAMID_GRADE_CLEAR_MAX_Y = -348;
    private static final int PYRAMID_GRADE_X_SPAN =
            PYRAMID_GRADE_MAX_X - PYRAMID_GRADE_MIN_X;
    private static final int PYRAMID_GRADE_Z_SPAN =
            PYRAMID_GRADE_MAX_Z - PYRAMID_GRADE_MIN_Z;
    private static final int PYRAMID_GRADE_LAYERS =
            PYRAMID_GRADE_CLEAR_MAX_Y - PYRAMID_GRADE_MIN_Y + 1;
    private static final long PYRAMID_GRADE_WORK =
            (long) PYRAMID_GRADE_X_SPAN * PYRAMID_GRADE_Z_SPAN
                    * PYRAMID_GRADE_LAYERS;

    private static final RoadSegment[] ROAD_SEGMENTS = {
            new RoadSegment(-228, -176, 360, -176, 16),
            new RoadSegment(360, -176, 520, -136, 16),
            new RoadSegment(520, -136, 592, -64, 16),
            new RoadSegment(592, -64, 592, 96, 16),
            new RoadSegment(592, 96, 520, 176, 16),
            new RoadSegment(520, 176, 360, 260, 16),
            new RoadSegment(360, 260, -228, 260, 16),
            new RoadSegment(-228, 260, -228, -176, 16),
            new RoadSegment(-228, 32, -208, 32, 16),
            new RoadSegment(-288, 40, -228, 40, 16),
            new RoadSegment(-228, 204, -96, 204, 16),
            new RoadSegment(360, 232, 360, 260, 16),
            new RoadSegment(-152, 212, -152, 260, 16),
            new RoadSegment(0, -176, 0, -212, 16)
    };
    private static final int ROAD_MIN_Y = -369;
    private static final int ROAD_SURFACE_Y = -361;
    private static final int ROAD_CLEAR_MAX_Y = -348;
    private static final int ROAD_LAYERS =
            ROAD_CLEAR_MAX_Y - ROAD_MIN_Y + 1;
    private static final long ROAD_WORK = roadWork();

    private static final int LAKE_X_SPAN = 224;
    private static final int LAKE_Z_SPAN = 176;
    private static final int LAKE_LAYERS = 29;
    private static final long LAKE_WORK =
            (long) LAKE_X_SPAN * LAKE_Z_SPAN * LAKE_LAYERS;
    private static final int LCL_X_SPAN = 160;
    private static final int LCL_Z_SPAN = 96;
    private static final int LCL_LAYERS = 25;
    private static final long LCL_WORK =
            (long) LCL_X_SPAN * LCL_Z_SPAN * LCL_LAYERS;
    private static final int GARDEN_SIDE = 104;
    private static final int GARDEN_MIN_X = -336;
    private static final int GARDEN_MIN_Z = 128;
    private static final int GARDEN_MIN_Y = -369;
    private static final int GARDEN_SURFACE_Y = -361;
    private static final int GARDEN_CLEAR_MAX_Y = -348;
    private static final int GARDEN_LAYERS =
            GARDEN_CLEAR_MAX_Y - GARDEN_MIN_Y + 1;
    private static final long GARDEN_WORK =
            (long) GARDEN_SIDE * GARDEN_SIDE * GARDEN_LAYERS;
    private static final int NORTH_FOREST_SITES = 40 * 7;
    private static final int WEST_FOREST_SITES = 18 * 22;
    private static final int TREE_WORK = 106;
    private static final long FOREST_WORK =
            (long) (NORTH_FOREST_SITES + WEST_FOREST_SITES) * TREE_WORK;

    private static final int YARD_X_SPAN = 224;
    private static final int YARD_Z_SPAN = 112;
    private static final int YARD_MIN_Y = -369;
    private static final int YARD_SURFACE_Y = -361;
    private static final int YARD_CLEAR_MAX_Y = -340;
    private static final int YARD_LAYERS =
            YARD_CLEAR_MAX_Y - YARD_MIN_Y + 1;
    private static final long YARD_WORK =
            (long) YARD_X_SPAN * YARD_Z_SPAN * YARD_LAYERS;
    private static final FabricBox PUMP =
            new FabricBox(176, -360, 152, 224, -344, 192);
    private static final FabricBox WAREHOUSE =
            new FabricBox(240, -360, 144, 320, -340, 208);
    private static final FabricBox SUBSTATION =
            new FabricBox(336, -360, 152, 376, -344, 200);
    private static final long LOGISTICS_BUILDING_WORK =
            PUMP.volume() + WAREHOUSE.volume() + SUBSTATION.volume();

    private static final FabricBox WEST_SEAM =
            new FabricBox(-216, -361, 24, -208, -353, 40);

    private static final Map<String, OwnerMask> OWNER_MASKS =
            new ConcurrentHashMap<>();

    private GeoFrontFabricPlan() {}

    public enum Feature
    {
        CAVERN_SURFACE_FINISH(
                "cavern_surface_finish", "cavern-surface-finish-a2", 10),
        PYRAMID_PLAZA("pyramid_plaza", "pyramid-plaza-a3", 100),
        ROAD_NETWORK("road_network", "road-network-a4", 80),
        LOGISTICS("logistics", "logistics-a2", 90),
        LANDSCAPE("landscape", "landscape-a3", 70),
        LIGHTING("lighting", "lighting-a2", 110),
        WEST_SEAM("west_seam", "west-seam-exterior-a3", 90);

        private final String id;
        private final String revision;
        private final int priority;

        Feature(String id, String revision, int priority)
        {
            this.id = id;
            this.revision = revision;
            this.priority = priority;
        }

        public String id()
        {
            return this.id;
        }

        public String revision()
        {
            return this.revision;
        }

        public int priority()
        {
            return this.priority;
        }

        public List<Feature> dependencies()
        {
            return switch (this)
            {
                case CAVERN_SURFACE_FINISH -> List.of();
                case PYRAMID_PLAZA -> List.of(CAVERN_SURFACE_FINISH);
                case ROAD_NETWORK -> List.of(
                        CAVERN_SURFACE_FINISH, PYRAMID_PLAZA);
                case LOGISTICS -> List.of(
                        CAVERN_SURFACE_FINISH, ROAD_NETWORK);
                case LANDSCAPE -> List.of(
                        CAVERN_SURFACE_FINISH, PYRAMID_PLAZA, ROAD_NETWORK,
                        LOGISTICS);
                case LIGHTING -> List.of(
                        CAVERN_SURFACE_FINISH, PYRAMID_PLAZA, ROAD_NETWORK,
                        LOGISTICS, LANDSCAPE);
                case WEST_SEAM -> List.of(
                        ROAD_NETWORK, LIGHTING);
            };
        }

        public long authoredWork()
        {
            return GeoFrontFabricPlan.authoredWork(this);
        }

        public String contractHash()
        {
            return FacilityV2Hashing.fabricFeatureHash(
                    this.id, this.revision, this.priority, authoredWork());
        }

        public FeatureContract contract()
        {
            return new FeatureContract(this.id, this.revision,
                    this.priority, authoredWork(), GEOMETRY_VERSION,
                    contractHash());
        }

        public static Feature byId(String id)
        {
            for (Feature feature : values())
            {
                if (feature.id.equals(id))
                {
                    return feature;
                }
            }
            throw new IllegalArgumentException(
                    "Unknown GeoFront fabric feature " + id);
        }
    }

    public static long authoredWork(Feature feature)
    {
        return switch (feature)
        {
            case CAVERN_SURFACE_FINISH -> SHELL_WORK + TERRAIN_WORK;
            case PYRAMID_PLAZA -> PYRAMID_X_SIDES_WORK
                    + PYRAMID_Z_SIDES_WORK + PYRAMID_GRADE_WORK;
            case ROAD_NETWORK -> ROAD_WORK;
            case LANDSCAPE ->
                    LAKE_WORK + LCL_WORK + GARDEN_WORK + FOREST_WORK;
            case LOGISTICS -> YARD_WORK + LOGISTICS_BUILDING_WORK;
            case LIGHTING -> LIGHT_WORK;
            case WEST_SEAM -> WEST_SEAM.volume();
        };
    }

    public static List<FeatureContract> currentContracts()
    {
        List<FeatureContract> contracts = new ArrayList<>();
        for (Feature feature : Feature.values())
        {
            contracts.add(feature.contract());
        }
        return List.copyOf(contracts);
    }

    /**
     * Replays one frozen feature contract. A geometry implementation must
     * remain available for every version that can exist in SavedData.
     */
    public static FabricBlock blockAt(
            FacilitySchemaV2.ResolvedManifest manifest,
            FeatureContract contract, long cursor)
    {
        if (contract.geometryVersion() != GEOMETRY_VERSION)
        {
            throw new IllegalStateException(
                    "Unsupported GeoFront fabric geometry "
                            + contract.geometryVersion() + " for "
                            + contract.id());
        }
        Feature feature = Feature.byId(contract.id());
        if (contract.authoredWork() != authoredWork(feature))
        {
            throw new IllegalStateException(
                    "Geometry work mismatch for " + contract.id());
        }
        return blockAt(manifest, feature, cursor);
    }

    public static FabricBlock blockAt(
            FacilitySchemaV2.ResolvedManifest manifest,
            Feature feature, long cursor)
    {
        if (cursor < 0L || cursor >= authoredWork(feature))
        {
            throw new IndexOutOfBoundsException(
                    feature.id() + " cursor " + cursor);
        }
        FabricBlock block = switch (feature)
        {
            case CAVERN_SURFACE_FINISH ->
                    cavernSurfaceAt(manifest.centre(), cursor);
            case PYRAMID_PLAZA ->
                    pyramidPlazaAt(manifest.centre(), cursor);
            case ROAD_NETWORK ->
                    roadAt(manifest.centre(), cursor);
            case LANDSCAPE ->
                    landscapeAt(manifest.centre(), cursor);
            case LOGISTICS ->
                    logisticsAt(manifest.centre(), cursor);
            case LIGHTING ->
                    lightingAt(manifest.centre(), cursor);
            case WEST_SEAM ->
                    boxAt(manifest.centre(), WEST_SEAM, cursor,
                            Feature.WEST_SEAM);
        };
        if (block == null)
        {
            return null;
        }
        int relativeX = block.position().getX()
                - manifest.centre().getX();
        int relativeZ = block.position().getZ()
                - manifest.centre().getZ();
        if (blockedByHigherPriority(feature, relativeX,
                block.position().getY(), relativeZ))
        {
            return null;
        }
        if (legacyMechanicalExcluded(block.position()))
        {
            return null;
        }
        return block;
    }

    /**
     * Epoch-3 rescue worlds intentionally retain the proven three-line legacy
     * mechanical plant as their sole EVA authority.  It is not represented by
     * a Facility v2 owner, so every exterior compositor pass needs this fixed
     * exclusion or roads, terrain and forests can silently paint through cage,
     * carrier and launch-shaft swept volumes.
     */
    private static boolean legacyMechanicalExcluded(BlockPos position)
    {
        BlockPos origin = IntegratedNervMapBuilder.GEOFRONT_ORIGIN;
        int bedY = origin.getY() + EvaHangarBuilder.HANGAR_BED_ABOVE_ORIGIN;
        int hangarZ = origin.getZ() + EvaHangarBuilder.HANGAR_CENTRE_Z;
        int siloZ = IntegratedNervMapBuilder.lowerLiftBed(0).getZ();
        int shaftTop = IntegratedNervMapBuilder.surfaceLiftBed(0).getY()
                + IntegratedNervMapBuilder.SURFACE_HEADROOM;
        for (int variant = 0; variant < 3; variant++)
        {
            int x = origin.getX()
                    + IntegratedNervMapBuilder.LIFT_X[variant];
            boolean cageAndCarrier = position.getX() >= x - 23
                    && position.getX() <= x + 23
                    && position.getY() >= bedY - 3
                    && position.getY() <= bedY + 74
                    && position.getZ() >= hangarZ - 31
                    && position.getZ() <= siloZ + 20;
            boolean launchShaft = position.getX() >= x - 20
                    && position.getX() <= x + 20
                    && position.getY() >= bedY - 3
                    && position.getY() <= shaftTop
                    && position.getZ() >= siloZ - 20
                    && position.getZ() <= siloZ + 20;
            if (cageAndCarrier || launchShaft)
            {
                return true;
            }
        }

        // Permanent staff-lift -> wet-cage observation gallery.
        int relativeX = position.getX() - origin.getX();
        int relativeZ = position.getZ() - origin.getZ();
        return relativeX >= 48 && relativeX <= 60
                && relativeZ >= -170 && relativeZ <= 70
                && position.getY() >= -388 && position.getY() <= -376;
    }

    public static boolean ownerGuarded(
            FacilitySchemaV2.ResolvedManifest manifest, BlockPos position)
    {
        return ownerMask(manifest, 1).contains(position);
    }

    public static boolean ownerContains(
            FacilitySchemaV2.ResolvedManifest manifest, BlockPos position)
    {
        return ownerMask(manifest, 0).contains(position);
    }

    /**
     * Shared exclusion contract for the rescue world's chunk-major cavern
     * writer. It must preserve exactly the same high-priority scenes and
     * legacy mechanical swept volumes as the ordinary authored cursor.
     */
    public static boolean cavernFoundationExcluded(
            FacilitySchemaV2.ResolvedManifest manifest, BlockPos position)
    {
        int relativeX = position.getX() - manifest.centre().getX();
        int relativeZ = position.getZ() - manifest.centre().getZ();
        return blockedByHigherPriority(Feature.CAVERN_SURFACE_FINISH,
                relativeX, position.getY(), relativeZ)
                || legacyMechanicalExcluded(position);
    }

    public static BlockState cavernShellState()
    {
        return skyweaveState();
    }

    private static OwnerMask ownerMask(
            FacilitySchemaV2.ResolvedManifest manifest, int inflation)
    {
        String key = manifest.candidateIndex() + ":"
                + manifest.surfaceY() + ":" + inflation;
        return OWNER_MASKS.computeIfAbsent(key,
                ignored -> OwnerMask.create(manifest, inflation));
    }

    public static boolean insideCavern(BlockPos centre, BlockPos position)
    {
        double nx = (position.getX() - centre.getX())
                / (double) CAVERN_RADIUS_XZ;
        double ny = (position.getY() - CAVERN_CENTRE_Y)
                / (double) CAVERN_RADIUS_Y;
        double nz = (position.getZ() - centre.getZ())
                / (double) CAVERN_RADIUS_XZ;
        return nx * nx + ny * ny + nz * nz <= 1.002D;
    }

    public static int terrainHeight(int relativeX, int relativeZ)
    {
        int clampedX = Math.max(-640, Math.min(639, relativeX));
        int clampedZ = Math.max(-640, Math.min(639, relativeZ));
        int cellX = Math.floorDiv(clampedX + 640, 32);
        int cellZ = Math.floorDiv(clampedZ + 640, 32);
        int localX = Math.floorMod(clampedX + 640, 32);
        int localZ = Math.floorMod(clampedZ + 640, 32);
        int h00 = terrainSample(cellX, cellZ);
        int h10 = terrainSample(Math.min(40, cellX + 1), cellZ);
        int h01 = terrainSample(cellX, Math.min(40, cellZ + 1));
        int h11 = terrainSample(Math.min(40, cellX + 1),
                Math.min(40, cellZ + 1));
        int a = h00 * (32 - localX) + h10 * localX;
        int b = h01 * (32 - localX) + h11 * localX;
        int interpolated = (a * (32 - localZ) + b * localZ + 512)
                / 1024;
        return FacilitySchemaV2.GF_FLOOR_Y + interpolated;
    }

    private static int terrainSample(int x, int z)
    {
        long value = x * 341873128712L + z * 132897987541L
                + 0x5EE1E5EEL;
        value ^= value >>> 29;
        value *= 0x9E3779B97F4A7C15L;
        value ^= value >>> 32;
        return (int) Math.floorMod(value, 21L) - 8;
    }

    private static FabricBlock cavernSurfaceAt(BlockPos centre, long cursor)
    {
        if (cursor < SHELL_SIDE_WORK)
        {
            long item = cursor;
            int depth = (int) (item % SHELL_THICKNESS);
            item /= SHELL_THICKNESS;
            int side = (int) (item % 2L);
            item /= 2L;
            int xSlot = (int) (item % SHELL_X_SPAN);
            int yIndex = (int) (item / SHELL_X_SPAN);
            int y = CAVERN_BOTTOM_Y + yIndex;
            double normalizedY = (y - CAVERN_CENTRE_Y)
                    / (double) CAVERN_RADIUS_Y;
            double remaining = 1.0D - normalizedY * normalizedY;
            if (remaining < 0.0D)
            {
                return null;
            }
            int radius = (int) Math.floor(
                    CAVERN_RADIUS_XZ * Math.sqrt(remaining));
            int x = xSlot - CAVERN_RADIUS_XZ;
            if (Math.abs(x) > radius)
            {
                return null;
            }
            int zOuter = (int) Math.floor(Math.sqrt(
                    Math.max(0, radius * radius - x * x)));
            if (zOuter < depth)
            {
                return null;
            }
            int z = side == 0 ? zOuter - depth : -zOuter + depth;
            return relative(centre, x, y, z, skyweaveState());
        }
        cursor -= SHELL_SIDE_WORK;

        // The side sweep above does not cover the upper and lower elliptical
        // caps. Add both explicitly so the visible skyweave is a closed
        // sphere rather than two curved walls around an open ceiling.
        if (cursor < SHELL_CAP_WORK)
        {
            long item = cursor;
            int depth = (int) (item % SHELL_THICKNESS);
            item /= SHELL_THICKNESS;
            int side = (int) (item % 2L);
            item /= 2L;
            int xSlot = (int) (item % SHELL_X_SPAN);
            int zSlot = (int) (item / SHELL_X_SPAN);
            int x = xSlot - CAVERN_RADIUS_XZ;
            int z = zSlot - CAVERN_RADIUS_XZ;
            double dx = x / (double) CAVERN_RADIUS_XZ;
            double dz = z / (double) CAVERN_RADIUS_XZ;
            double remaining = 1.0D - dx * dx - dz * dz;
            if (remaining < 0.0D)
            {
                return null;
            }
            int verticalRadius = (int) Math.floor(
                    CAVERN_RADIUS_Y * Math.sqrt(remaining));
            int y = side == 0
                    ? CAVERN_CENTRE_Y + verticalRadius - depth
                    : CAVERN_CENTRE_Y - verticalRadius + depth;
            return relative(centre, x, y, z, skyweaveState());
        }

        long terrainCursor = cursor - SHELL_CAP_WORK;
        if (terrainCursor < TERRAIN_WORK)
        {
            int layer = (int) (terrainCursor / TERRAIN_COLUMNS);
            long column = terrainCursor % TERRAIN_COLUMNS;
            int x = (int) (column % TERRAIN_SIDE) - CAVERN_RADIUS_XZ;
            int z = (int) (column / TERRAIN_SIDE) - CAVERN_RADIUS_XZ;
            if ((long) x * x + (long) z * z > 632L * 632L)
            {
                return null;
            }
            int surface = terrainHeight(x, z);
            BlockState state = layer == 0
                    ? Blocks.GRASS_BLOCK.defaultBlockState()
                    : layer <= 2
                    ? Blocks.DIRT.defaultBlockState()
                    : Blocks.STONE.defaultBlockState();
            return relative(centre, x, surface - layer, z, state);
        }

        return null;
    }

    private static FabricBlock lightingAt(BlockPos centre, long cursor)
    {
        int level = (int) (cursor
                / (LIGHT_GRID_SIDE * LIGHT_GRID_SIDE));
        int point = (int) (cursor
                % (LIGHT_GRID_SIDE * LIGHT_GRID_SIDE));
        int gx = point % LIGHT_GRID_SIDE;
        int gz = point / LIGHT_GRID_SIDE;
        int x = -624 + gx * 24;
        int z = -624 + gz * 24;
        if ((long) x * x + (long) z * z > 620L * 620L)
        {
            return null;
        }
        int y = terrainHeight(x, z) + 8 + level * 24;
        BlockState light = Blocks.LIGHT.defaultBlockState()
                .setValue(LightBlock.LEVEL, 15);
        return relative(centre, x, y, z, light);
    }

    private static FabricBlock pyramidPlazaAt(BlockPos centre, long cursor)
    {
        if (cursor < PYRAMID_X_SIDES_WORK)
        {
            long item = cursor;
            int depth = (int) (item % PYRAMID_SHELL_THICKNESS);
            item /= PYRAMID_SHELL_THICKNESS;
            int side = (int) (item % 2L);
            item /= 2L;
            int zSlot = (int) (item % PYRAMID_Z_SPAN);
            int level = (int) (item / PYRAMID_Z_SPAN);
            PyramidSlice slice = pyramidSlice(level);
            int z = -120 + zSlot;
            if (z < slice.zMin() || z >= slice.zMax()
                    || slice.xHalf() <= depth)
            {
                return null;
            }
            int x = side == 0 ? -slice.xHalf() + depth
                    : slice.xHalf() - 1 - depth;
            int y = -360 + level;
            return relative(centre, x, y, z,
                    pyramidShellState(x, y, z));
        }
        cursor -= PYRAMID_X_SIDES_WORK;

        if (cursor < PYRAMID_Z_SIDES_WORK)
        {
            long item = cursor;
            int depth = (int) (item % PYRAMID_SHELL_THICKNESS);
            item /= PYRAMID_SHELL_THICKNESS;
            int side = (int) (item % 2L);
            item /= 2L;
            int xSlot = (int) (item % PYRAMID_X_SPAN);
            int level = (int) (item / PYRAMID_X_SPAN);
            PyramidSlice slice = pyramidSlice(level);
            int x = -152 + xSlot;
            if (x < -slice.xHalf() || x >= slice.xHalf()
                    || slice.zMax() - slice.zMin() <= depth * 2)
            {
                return null;
            }
            int z = side == 0 ? slice.zMin() + depth
                    : slice.zMax() - 1 - depth;
            int y = -360 + level;
            return relative(centre, x, y, z,
                    pyramidShellState(x, y, z));
        }
        cursor -= PYRAMID_Z_SIDES_WORK;

        long gradePlane =
                (long) PYRAMID_GRADE_X_SPAN * PYRAMID_GRADE_Z_SPAN;
        int layer = (int) (cursor / gradePlane);
        long cell = cursor % gradePlane;
        int x = (int) (cell % PYRAMID_GRADE_X_SPAN)
                + PYRAMID_GRADE_MIN_X;
        int z = (int) (cell / PYRAMID_GRADE_X_SPAN)
                + PYRAMID_GRADE_MIN_Z;
        int y = PYRAMID_GRADE_MIN_Y + layer;
        BlockState state;
        if (y == PYRAMID_GRADE_SURFACE_Y)
        {
            if (insidePyramidFootprint(x, z))
            {
                state = Blocks.POLISHED_DEEPSLATE.defaultBlockState();
            }
            else
            {
                boolean frontPlaza = z >= 176;
                boolean guide = Math.floorMod(x, 24) < 2
                        || Math.floorMod(z - 176, 24) < 2;
                state = guide
                        ? Blocks.ORANGE_CONCRETE.defaultBlockState()
                        : frontPlaza
                        ? Blocks.SMOOTH_STONE.defaultBlockState()
                        : Blocks.DEEPSLATE_TILES.defaultBlockState();
            }
        }
        else if (y > PYRAMID_GRADE_SURFACE_Y)
        {
            if (pyramidShellStateAt(x, y, z) != null)
            {
                return null;
            }
            state = Blocks.AIR.defaultBlockState();
        }
        else
        {
            state = com.projectseele.world.NervMaterials.structuralBlock().defaultBlockState();
        }
        return relative(centre, x, y, z, state);
    }

    private static PyramidSlice pyramidSlice(int level)
    {
        double t = level / 116.0D;
        int xHalf = (int) Math.floor(152.0D - 136.0D * t);
        int zMin = (int) Math.floor(-120.0D + 144.0D * t);
        int zMax = (int) Math.ceil(200.0D - 144.0D * t);
        return new PyramidSlice(xHalf, zMin, zMax);
    }

    private static BlockState pyramidShellState(int x, int y, int z)
    {
        if (Math.floorMod(y + 360, 16) == 0
                || Math.floorMod(x + z, 48) == 0)
        {
            return Blocks.CRYING_OBSIDIAN.defaultBlockState();
        }
        if (Math.floorMod(y + 360, 8) == 0)
        {
            return Blocks.ORANGE_STAINED_GLASS.defaultBlockState();
        }
        return Blocks.CHISELED_DEEPSLATE.defaultBlockState();
    }

    private static FabricBlock roadAt(BlockPos centre, long cursor)
    {
        for (RoadSegment segment : ROAD_SEGMENTS)
        {
            long work = segment.work();
            if (cursor >= work)
            {
                cursor -= work;
                continue;
            }
            int layer = (int) (cursor
                    / ((long) segment.steps() * segment.width()));
            long cell = cursor
                    % ((long) segment.steps() * segment.width());
            int along = (int) (cell / segment.width());
            int lane = (int) (cell % segment.width());
            double t = segment.steps() <= 1 ? 0.0D
                    : along / (double) (segment.steps() - 1);
            double baseX = segment.x1()
                    + (segment.x2() - segment.x1()) * t;
            double baseZ = segment.z1()
                    + (segment.z2() - segment.z1()) * t;
            double dx = segment.x2() - segment.x1();
            double dz = segment.z2() - segment.z1();
            double length = Math.max(1.0D, Math.sqrt(dx * dx + dz * dz));
            double offset = lane - (segment.width() - 1) / 2.0D;
            int x = (int) Math.round(baseX - dz / length * offset);
            int z = (int) Math.round(baseZ + dx / length * offset);
            int y = ROAD_MIN_Y + layer;
            BlockState state;
            if (y == ROAD_SURFACE_Y)
            {
                boolean edge = lane == 0 || lane == segment.width() - 1;
                boolean centreLine = (lane == segment.width() / 2
                        || lane == segment.width() / 2 - 1)
                        && Math.floorMod(along, 14) < 7;
                state = edge || centreLine
                        ? Blocks.ORANGE_CONCRETE.defaultBlockState()
                        : Blocks.GRAY_CONCRETE.defaultBlockState();
            }
            else if (y > ROAD_SURFACE_Y)
            {
                state = Blocks.AIR.defaultBlockState();
            }
            else
            {
                state = com.projectseele.world.NervMaterials.structuralBlock().defaultBlockState();
            }
            return relative(centre, x, y, z, state);
        }
        return null;
    }

    private static FabricBlock landscapeAt(BlockPos centre, long cursor)
    {
        if (cursor < LAKE_WORK)
        {
            long plane = (long) LAKE_X_SPAN * LAKE_Z_SPAN;
            int layer = (int) (cursor / plane);
            long cell = cursor % plane;
            int x = (int) (cell % LAKE_X_SPAN) - 512;
            int z = (int) (cell / LAKE_X_SPAN) - 48;
            double nx = (x + 400) / 112.0D;
            double nz = (z - 40) / 88.0D;
            if (nx * nx + nz * nz > 1.0D)
            {
                return null;
            }
            int y = -376 + layer;
            BlockState state;
            if (layer < 8)
            {
                state = layer == 7
                        ? Blocks.CLAY.defaultBlockState()
                        : Blocks.STONE.defaultBlockState();
            }
            else if (layer < 16)
            {
                state = Blocks.WATER.defaultBlockState();
            }
            else
            {
                state = Blocks.AIR.defaultBlockState();
            }
            return relative(centre, x, y, z, state);
        }
        cursor -= LAKE_WORK;

        if (cursor < LCL_WORK)
        {
            long plane = (long) LCL_X_SPAN * LCL_Z_SPAN;
            int layer = (int) (cursor / plane);
            long cell = cursor % plane;
            int x = (int) (cell % LCL_X_SPAN) - 80;
            int z = (int) (cell / LCL_X_SPAN) - 308;
            double nx = x / 80.0D;
            double nz = (z + 260) / 48.0D;
            if (nx * nx + nz * nz > 1.0D)
            {
                return null;
            }
            int y = -372 + layer;
            BlockState state;
            if (layer < 5)
            {
                state = Math.floorMod(x * 17 + z * 31, 23) == 0
                        ? Blocks.SEA_LANTERN.defaultBlockState()
                        : layer == 4
                        ? Blocks.CLAY.defaultBlockState()
                        : Blocks.DEEPSLATE.defaultBlockState();
            }
            else if (layer < 12)
            {
                state = ModFluids.LCL_SOURCE.get()
                        .defaultFluidState().createLegacyBlock();
            }
            else
            {
                state = Blocks.AIR.defaultBlockState();
            }
            return relative(centre, x, y, z, state);
        }
        cursor -= LCL_WORK;

        if (cursor < GARDEN_WORK)
        {
            long plane = (long) GARDEN_SIDE * GARDEN_SIDE;
            int layer = (int) (cursor / plane);
            long cell = cursor % plane;
            int x = (int) (cell % GARDEN_SIDE) + GARDEN_MIN_X;
            int z = (int) (cell / GARDEN_SIDE) + GARDEN_MIN_Z;
            int y = GARDEN_MIN_Y + layer;
            if (y < GARDEN_SURFACE_Y)
            {
                return relative(centre, x, y, z,
                        com.projectseele.world.NervMaterials.structuralBlock().defaultBlockState());
            }
            if (y == GARDEN_SURFACE_Y)
            {
                boolean path = Math.floorMod(x - GARDEN_MIN_X, 24) < 3
                        || Math.floorMod(z - GARDEN_MIN_Z, 24) < 3;
                return relative(centre, x, y, z,
                        path ? Blocks.MOSSY_STONE_BRICKS.defaultBlockState()
                                : Blocks.MOSS_BLOCK.defaultBlockState());
            }
                boolean hedge = x == GARDEN_MIN_X
                        || x == GARDEN_MIN_X + GARDEN_SIDE - 1
                        || z == GARDEN_MIN_Z
                        || z == GARDEN_MIN_Z + GARDEN_SIDE - 1;
            if (y == GARDEN_SURFACE_Y + 1 && hedge)
            {
                return relative(centre, x, y, z,
                        Blocks.AZALEA_LEAVES.defaultBlockState());
            }
            int hash = positionHash(x, z);
            if (y == GARDEN_SURFACE_Y + 1
                    && Math.floorMod(hash, 41) == 0)
            {
                BlockState flower = Math.floorMod(hash, 2) == 0
                        ? Blocks.POPPY.defaultBlockState()
                        : Blocks.BLUE_ORCHID.defaultBlockState();
                return relative(centre, x, y, z, flower);
            }
            return relative(centre, x, y, z,
                    Blocks.AIR.defaultBlockState());
        }
        cursor -= GARDEN_WORK;

        int site = (int) (cursor / TREE_WORK);
        int local = (int) (cursor % TREE_WORK);
        TreeSite tree = treeSite(site);
        if (tree == null || Math.floorMod(
                positionHash(tree.x(), tree.z()), 10) < 3
                || excludedForestSite(tree.x(), tree.z()))
        {
            return null;
        }
        int baseY = terrainHeight(tree.x(), tree.z()) + 1;
        if (local < 6)
        {
            return relative(centre, tree.x(), baseY + local, tree.z(),
                    Blocks.SPRUCE_LOG.defaultBlockState());
        }
        int leaf = local - 6;
        int dx = leaf % 5 - 2;
        int dz = (leaf / 5) % 5 - 2;
        int dy = leaf / 25;
        if (Math.abs(dx) + Math.abs(dz) > 3
                || (dy == 3 && Math.abs(dx) + Math.abs(dz) > 1))
        {
            return null;
        }
        return relative(centre, tree.x() + dx, baseY + 3 + dy,
                tree.z() + dz, Blocks.SPRUCE_LEAVES.defaultBlockState());
    }

    private static FabricBlock logisticsAt(BlockPos centre, long cursor)
    {
        if (cursor < YARD_WORK)
        {
            long plane = (long) YARD_X_SPAN * YARD_Z_SPAN;
            int layer = (int) (cursor / plane);
            long cell = cursor % plane;
            int x = (int) (cell % YARD_X_SPAN) + 160;
            int z = (int) (cell / YARD_X_SPAN) + 120;
            int y = YARD_MIN_Y + layer;
            BlockState state;
            if (y == YARD_SURFACE_Y)
            {
                boolean stripe = Math.floorMod(x - 160, 32) < 2
                        || Math.floorMod(z - 120, 32) < 2;
                state = stripe
                        ? Blocks.YELLOW_CONCRETE.defaultBlockState()
                        : Blocks.SMOOTH_STONE.defaultBlockState();
            }
            else if (y > YARD_SURFACE_Y)
            {
                state = Blocks.AIR.defaultBlockState();
            }
            else
            {
                state = com.projectseele.world.NervMaterials.structuralBlock().defaultBlockState();
            }
            return relative(centre, x, y, z, state);
        }
        cursor -= YARD_WORK;
        for (FabricBox box : List.of(PUMP, WAREHOUSE, SUBSTATION))
        {
            if (cursor >= box.volume())
            {
                cursor -= box.volume();
                continue;
            }
            return boxAt(centre, box, cursor, Feature.LOGISTICS);
        }
        return null;
    }

    private static FabricBlock boxAt(BlockPos centre, FabricBox box,
                                     long cursor, Feature feature)
    {
        int x = box.minX() + (int) (cursor % box.sizeX());
        long yz = cursor / box.sizeX();
        int z = box.minZ() + (int) (yz % box.sizeZ());
        int y = box.minY() + (int) (yz / box.sizeZ());
        boolean floor = y == box.minY();
        boolean roof = y == box.maxY() - 1;
        boolean wall = x == box.minX() || x == box.maxX() - 1
                || z == box.minZ() || z == box.maxZ() - 1;
        boolean doorway;
        if (feature == Feature.WEST_SEAM)
        {
            doorway = (x == box.minX() || x == box.maxX() - 1)
                    && y >= -360 && y < -355 && z >= 28 && z < 36;
        }
        else
        {
            int doorCentre = (box.minX() + box.maxX()) / 2;
            doorway = z == box.maxZ() - 1
                    && x >= doorCentre - 2 && x <= doorCentre + 2
                    && y < box.minY() + 6;
        }
        BlockState state;
        if (doorway)
        {
            state = Blocks.AIR.defaultBlockState();
        }
        else if (floor)
        {
            state = com.projectseele.world.NervMaterials.structuralBlock().defaultBlockState();
        }
        else if (roof)
        {
            state = Math.floorMod(x + z, 11) == 0
                    ? Blocks.SEA_LANTERN.defaultBlockState()
                    : Blocks.SMOOTH_STONE.defaultBlockState();
        }
        else if (wall)
        {
            boolean window = y >= box.minY() + 5
                    && y <= box.minY() + 8
                    && Math.floorMod(x + z, 9) < 4;
            state = window
                    ? Blocks.LIGHT_BLUE_STAINED_GLASS.defaultBlockState()
                    : Blocks.IRON_BLOCK.defaultBlockState();
        }
        else
        {
            state = Blocks.AIR.defaultBlockState();
        }
        return relative(centre, x, y, z, state);
    }

    private static TreeSite treeSite(int site)
    {
        if (site < NORTH_FOREST_SITES)
        {
            int xIndex = site % 40;
            int zIndex = site / 40;
            return new TreeSite(-152 + xIndex * 16,
                    -312 + zIndex * 16);
        }
        site -= NORTH_FOREST_SITES;
        if (site >= WEST_FOREST_SITES)
        {
            return null;
        }
        int xIndex = site % 18;
        int zIndex = site / 18;
        return new TreeSite(-552 + xIndex * 16,
                -112 + zIndex * 16);
    }

    private static boolean excludedForestSite(int x, int z)
    {
        int canopyMargin = 3;
        return (x >= PYRAMID_GRADE_MIN_X - canopyMargin
                && x < PYRAMID_GRADE_MAX_X + canopyMargin
                && z >= PYRAMID_GRADE_MIN_Z - canopyMargin
                && z < PYRAMID_GRADE_MAX_Z + canopyMargin)
                || (x >= 160 - canopyMargin
                && x < 384 + canopyMargin
                && z >= 120 - canopyMargin
                && z < 232 + canopyMargin)
                || inGarden(x, z, canopyMargin)
                || inLake(x, z, 8.0D)
                || inLclLake(x, z, 8.0D)
                || nearRoad(x, z, 14.0D);
    }

    private static boolean blockedByHigherPriority(
            Feature feature, int x, int y, int z)
    {
        /*
         * Rescue construction deliberately suspends the enormous cavern pass
         * and promotes reviewable scenes.  When that foundation later resumes
         * it must not repaint the already-finished pyramid, roads, LCL lake or
         * logistics yard.  The original early return assumed dependency order
         * could never be interrupted, which is false in the rescue director.
         */
        if (feature == Feature.CAVERN_SURFACE_FINISH)
        {
            if (inPyramidEnvelope(x, y, z)
                    || inLogisticsEnvelope(x, y, z)
                    || y >= ROAD_MIN_Y && y <= ROAD_CLEAR_MAX_Y
                    && nearRoad(x, z, 9.0D)
                    || y >= -380 && y <= -348
                    && (inLake(x, z, 8.0D)
                    || inLclLake(x, z, 8.0D))
                    || y >= GARDEN_MIN_Y
                    && y <= GARDEN_CLEAR_MAX_Y
                    && inGarden(x, z, 2))
            {
                return true;
            }
            return false;
        }
        // Pyramid is the first authored scene above the foundation; roads and
        // landscape deliberately overwrite their own later masks.
        if (feature == Feature.PYRAMID_PLAZA)
        {
            return false;
        }
        if (feature != Feature.PYRAMID_PLAZA
                && inPyramidEnvelope(x, y, z))
        {
            return true;
        }
        if (feature == Feature.LANDSCAPE
                && inLogisticsEnvelope(x, y, z))
        {
            return true;
        }
        if (feature == Feature.LANDSCAPE
                && y >= ROAD_MIN_Y && y <= ROAD_CLEAR_MAX_Y
                && nearRoad(x, z, 9.0D))
        {
            return true;
        }
        return false;
    }

    private static boolean inPyramidEnvelope(int x, int y, int z)
    {
        return x >= PYRAMID_GRADE_MIN_X
                && x < PYRAMID_GRADE_MAX_X
                && y >= PYRAMID_GRADE_MIN_Y && y < -244
                && z >= PYRAMID_GRADE_MIN_Z
                && z < PYRAMID_GRADE_MAX_Z;
    }

    private static boolean inLogisticsEnvelope(int x, int y, int z)
    {
        return x >= 160 && x < 384
                && y >= YARD_MIN_Y && y <= YARD_CLEAR_MAX_Y
                && z >= 120 && z < 232;
    }

    private static boolean inGarden(int x, int z)
    {
        return inGarden(x, z, 0);
    }

    private static boolean inGarden(int x, int z, int margin)
    {
        return x >= GARDEN_MIN_X - margin
                && x < GARDEN_MIN_X + GARDEN_SIDE + margin
                && z >= GARDEN_MIN_Z - margin
                && z < GARDEN_MIN_Z + GARDEN_SIDE + margin;
    }

    private static boolean inLake(int x, int z, double margin)
    {
        double nx = (x + 400) / (112.0D + margin);
        double nz = (z - 40) / (88.0D + margin);
        return nx * nx + nz * nz <= 1.0D;
    }

    private static boolean inLclLake(int x, int z, double margin)
    {
        double nx = x / (80.0D + margin);
        double nz = (z + 260) / (48.0D + margin);
        return nx * nx + nz * nz <= 1.0D;
    }

    private static boolean nearRoad(int x, int z, double radius)
    {
        for (RoadSegment segment : ROAD_SEGMENTS)
        {
            if (distanceSquaredToSegment(x, z, segment) <= radius * radius)
            {
                return true;
            }
        }
        return false;
    }

    private static double distanceSquaredToSegment(
            int x, int z, RoadSegment segment)
    {
        double dx = segment.x2() - segment.x1();
        double dz = segment.z2() - segment.z1();
        double lengthSquared = dx * dx + dz * dz;
        double t = lengthSquared == 0.0D ? 0.0D
                : ((x - segment.x1()) * dx
                + (z - segment.z1()) * dz) / lengthSquared;
        t = Math.max(0.0D, Math.min(1.0D, t));
        double closestX = segment.x1() + dx * t;
        double closestZ = segment.z1() + dz * t;
        double offsetX = x - closestX;
        double offsetZ = z - closestZ;
        return offsetX * offsetX + offsetZ * offsetZ;
    }

    /**
     * Single final-state resolver used by old/new-mask reconciliation.
     * Feature priority is explicit; execution order is not an authority.
     */
    public static ResolvedFabricBlock desiredBlock(
            FacilitySchemaV2.ResolvedManifest manifest, BlockPos position)
    {
        if (ownerContains(manifest, position))
        {
            return new ResolvedFabricBlock(false,
                    Blocks.AIR.defaultBlockState());
        }

        int x = position.getX() - manifest.centre().getX();
        int y = position.getY();
        int z = position.getZ() - manifest.centre().getZ();
        BlockState westSeam = westSeamStateAt(x, y, z);
        if (ownerGuarded(manifest, position) && westSeam == null)
        {
            return new ResolvedFabricBlock(false,
                    Blocks.AIR.defaultBlockState());
        }

        BlockState desired = pyramidStateAt(x, y, z);
        if (desired == null)
        {
            desired = logisticsStateAt(x, y, z);
        }
        if (desired == null)
        {
            desired = westSeam;
        }
        if (desired == null)
        {
            desired = roadStateAt(x, y, z);
        }
        if (desired == null)
        {
            desired = landscapeStateAt(x, y, z);
        }
        if (desired == null)
        {
            desired = cavernStateAt(x, y, z);
        }
        if (desired == null)
        {
            desired = Blocks.AIR.defaultBlockState();
        }

        BlockState light = lightingStateAt(x, y, z);
        if (desired.isAir() && light != null)
        {
            desired = light;
        }
        return new ResolvedFabricBlock(true, desired);
    }

    private static BlockState cavernStateAt(int x, int y, int z)
    {
        if (x >= -CAVERN_RADIUS_XZ && x < CAVERN_RADIUS_XZ
                && z >= -CAVERN_RADIUS_XZ && z < CAVERN_RADIUS_XZ
                && (long) x * x + (long) z * z <= 632L * 632L)
        {
            int surface = terrainHeight(x, z);
            int layer = surface - y;
            if (layer >= 0 && layer < TERRAIN_DEPTH)
            {
                return layer == 0
                        ? Blocks.GRASS_BLOCK.defaultBlockState()
                        : layer <= 2
                        ? Blocks.DIRT.defaultBlockState()
                        : Blocks.STONE.defaultBlockState();
            }
        }

        if (y < CAVERN_BOTTOM_Y || y > CAVERN_TOP_Y
                || x < -CAVERN_RADIUS_XZ || x > CAVERN_RADIUS_XZ
                || z < -CAVERN_RADIUS_XZ || z > CAVERN_RADIUS_XZ)
        {
            return null;
        }
        double normalizedY = (y - CAVERN_CENTRE_Y)
                / (double) CAVERN_RADIUS_Y;
        double sideRemaining = 1.0D
                - normalizedY * normalizedY;
        if (sideRemaining >= 0.0D)
        {
            int radius = (int) Math.floor(
                    CAVERN_RADIUS_XZ * Math.sqrt(sideRemaining));
            if (Math.abs(x) <= radius)
            {
                int outerZ = (int) Math.floor(Math.sqrt(
                        Math.max(0, radius * radius - x * x)));
                for (int depth = 0; depth < SHELL_THICKNESS; depth++)
                {
                    if (outerZ >= depth
                            && (z == outerZ - depth
                            || z == -outerZ + depth))
                    {
                        return skyweaveState();
                    }
                }
            }
        }

        double nx = x / (double) CAVERN_RADIUS_XZ;
        double nz = z / (double) CAVERN_RADIUS_XZ;
        double capRemaining = 1.0D - nx * nx - nz * nz;
        if (capRemaining >= 0.0D)
        {
            int verticalRadius = (int) Math.floor(
                    CAVERN_RADIUS_Y * Math.sqrt(capRemaining));
            for (int depth = 0; depth < SHELL_THICKNESS; depth++)
            {
                if (y == CAVERN_CENTRE_Y + verticalRadius - depth
                        || y == CAVERN_CENTRE_Y
                        - verticalRadius + depth)
                {
                    return skyweaveState();
                }
            }
        }
        return null;
    }

    private static BlockState lightingStateAt(int x, int y, int z)
    {
        int offsetX = x + 624;
        int offsetZ = z + 624;
        if (offsetX < 0 || offsetZ < 0
                || offsetX % 24 != 0 || offsetZ % 24 != 0)
        {
            return null;
        }
        int gx = offsetX / 24;
        int gz = offsetZ / 24;
        if (gx >= LIGHT_GRID_SIDE || gz >= LIGHT_GRID_SIDE
                || (long) x * x + (long) z * z > 620L * 620L)
        {
            return null;
        }
        int delta = y - terrainHeight(x, z) - 8;
        if (delta < 0 || delta % 24 != 0
                || delta / 24 >= LIGHT_LEVELS)
        {
            return null;
        }
        return Blocks.LIGHT.defaultBlockState()
                .setValue(LightBlock.LEVEL, 15);
    }

    private static BlockState pyramidStateAt(int x, int y, int z)
    {
        BlockState shell = pyramidShellStateAt(x, y, z);
        if (shell != null)
        {
            return shell;
        }

        if (x >= PYRAMID_GRADE_MIN_X
                && x < PYRAMID_GRADE_MAX_X
                && z >= PYRAMID_GRADE_MIN_Z
                && z < PYRAMID_GRADE_MAX_Z
                && y >= PYRAMID_GRADE_MIN_Y
                && y <= PYRAMID_GRADE_CLEAR_MAX_Y)
        {
            if (y == PYRAMID_GRADE_SURFACE_Y)
            {
                if (insidePyramidFootprint(x, z))
                {
                    return Blocks.POLISHED_DEEPSLATE.defaultBlockState();
                }
                boolean frontPlaza = z >= 176;
                boolean guide = Math.floorMod(x, 24) < 2
                        || Math.floorMod(z - 176, 24) < 2;
                return guide
                        ? Blocks.ORANGE_CONCRETE.defaultBlockState()
                        : frontPlaza
                        ? Blocks.SMOOTH_STONE.defaultBlockState()
                        : Blocks.DEEPSLATE_TILES.defaultBlockState();
            }
            if (y > PYRAMID_GRADE_SURFACE_Y)
            {
                return Blocks.AIR.defaultBlockState();
            }
            return com.projectseele.world.NervMaterials.structuralBlock().defaultBlockState();
        }

        return null;
    }

    private static BlockState pyramidShellStateAt(int x, int y, int z)
    {
        int level = y + 360;
        if (level < 0 || level >= PYRAMID_LEVELS)
        {
            return null;
        }
        PyramidSlice slice = pyramidSlice(level);
        boolean xSide = z >= slice.zMin() && z < slice.zMax()
                && ((x >= -slice.xHalf()
                && x < -slice.xHalf() + PYRAMID_SHELL_THICKNESS)
                || (x < slice.xHalf()
                && x >= slice.xHalf() - PYRAMID_SHELL_THICKNESS));
        boolean zSide = x >= -slice.xHalf() && x < slice.xHalf()
                && ((z >= slice.zMin()
                && z < slice.zMin() + PYRAMID_SHELL_THICKNESS)
                || (z < slice.zMax()
                && z >= slice.zMax() - PYRAMID_SHELL_THICKNESS));
        return xSide || zSide ? pyramidShellState(x, y, z) : null;
    }

    private static boolean insidePyramidFootprint(int x, int z)
    {
        return x >= -152 && x < 152 && z >= -120 && z < 200;
    }

    private static BlockState roadStateAt(int x, int y, int z)
    {
        if (y < ROAD_MIN_Y || y > ROAD_CLEAR_MAX_Y)
        {
            return null;
        }
        RoadSegment selected = null;
        double selectedDistance = Double.MAX_VALUE;
        double selectedT = 0.0D;
        for (RoadSegment segment : ROAD_SEGMENTS)
        {
            double distance = distanceSquaredToSegment(x, z, segment);
            double halfWidth = segment.width() / 2.0D;
            if (distance <= (halfWidth + 0.75D)
                    * (halfWidth + 0.75D)
                    && distance < selectedDistance)
            {
                selected = segment;
                selectedDistance = distance;
                double dx = segment.x2() - segment.x1();
                double dz = segment.z2() - segment.z1();
                double lengthSquared = dx * dx + dz * dz;
                selectedT = lengthSquared == 0.0D ? 0.0D
                        : Math.max(0.0D, Math.min(1.0D,
                        ((x - segment.x1()) * dx
                                + (z - segment.z1()) * dz)
                                / lengthSquared));
            }
        }
        if (selected == null)
        {
            return null;
        }
        if (y < ROAD_SURFACE_Y)
        {
            return com.projectseele.world.NervMaterials.structuralBlock().defaultBlockState();
        }
        if (y > ROAD_SURFACE_Y)
        {
            return Blocks.AIR.defaultBlockState();
        }
        double offset = Math.sqrt(selectedDistance);
        int along = (int) Math.round(
                selectedT * Math.max(0, selected.steps() - 1));
        boolean edge = offset >= selected.width() / 2.0D - 1.25D;
        boolean centreLine = offset <= 1.2D
                && Math.floorMod(along, 14) < 7;
        return edge || centreLine
                ? Blocks.ORANGE_CONCRETE.defaultBlockState()
                : Blocks.GRAY_CONCRETE.defaultBlockState();
    }

    private static BlockState landscapeStateAt(int x, int y, int z)
    {
        BlockState tree = treeStateAt(x, y, z);
        if (tree != null)
        {
            return tree;
        }
        if (inGarden(x, z))
        {
            if (y >= GARDEN_MIN_Y && y <= GARDEN_CLEAR_MAX_Y)
            {
                if (y < GARDEN_SURFACE_Y)
                {
                    return com.projectseele.world.NervMaterials.structuralBlock()
                            .defaultBlockState();
                }
                if (y == GARDEN_SURFACE_Y)
                {
                    boolean path =
                            Math.floorMod(x - GARDEN_MIN_X, 24) < 3
                            || Math.floorMod(z - GARDEN_MIN_Z, 24) < 3;
                    return path
                            ? Blocks.MOSSY_STONE_BRICKS.defaultBlockState()
                            : Blocks.MOSS_BLOCK.defaultBlockState();
                }
                if (y == GARDEN_SURFACE_Y + 1)
                {
                    boolean hedge = x == GARDEN_MIN_X
                            || x == GARDEN_MIN_X + GARDEN_SIDE - 1
                            || z == GARDEN_MIN_Z
                            || z == GARDEN_MIN_Z + GARDEN_SIDE - 1;
                    if (hedge)
                    {
                        return Blocks.AZALEA_LEAVES.defaultBlockState();
                    }
                    int hash = positionHash(x, z);
                    if (Math.floorMod(hash, 41) == 0)
                    {
                        return Math.floorMod(hash, 2) == 0
                                ? Blocks.POPPY.defaultBlockState()
                                : Blocks.BLUE_ORCHID.defaultBlockState();
                    }
                }
                return Blocks.AIR.defaultBlockState();
            }
        }
        if (x >= -80 && x < 80 && z >= -308 && z < -212)
        {
            double nx = x / 80.0D;
            double nz = (z + 260) / 48.0D;
            int layer = y + 372;
            if (nx * nx + nz * nz <= 1.0D
                    && layer >= 0 && layer < LCL_LAYERS)
            {
                if (layer < 5)
                {
                    return Math.floorMod(x * 17 + z * 31, 23) == 0
                            ? Blocks.SEA_LANTERN.defaultBlockState()
                            : layer == 4
                            ? Blocks.CLAY.defaultBlockState()
                            : Blocks.DEEPSLATE.defaultBlockState();
                }
                if (layer < 12)
                {
                    return ModFluids.LCL_SOURCE.get()
                            .defaultFluidState().createLegacyBlock();
                }
                return Blocks.AIR.defaultBlockState();
            }
        }
        if (x >= -512 && x < -288 && z >= -48 && z < 128)
        {
            double nx = (x + 400) / 112.0D;
            double nz = (z - 40) / 88.0D;
            int layer = y + 376;
            if (nx * nx + nz * nz <= 1.0D
                    && layer >= 0 && layer < LAKE_LAYERS)
            {
                if (layer < 8)
                {
                    return layer == 7
                        ? Blocks.CLAY.defaultBlockState()
                        : Blocks.STONE.defaultBlockState();
                }
                return layer < 16
                        ? Blocks.WATER.defaultBlockState()
                        : Blocks.AIR.defaultBlockState();
            }
        }
        return null;
    }

    private static BlockState treeStateAt(int x, int y, int z)
    {
        BlockState state = treeStateAtGrid(
                x, y, z, -152, -312, 40, 7);
        return state != null ? state : treeStateAtGrid(
                x, y, z, -552, -112, 18, 22);
    }

    private static BlockState treeStateAtGrid(
            int x, int y, int z, int originX, int originZ,
            int countX, int countZ)
    {
        int centreX = (int) Math.round((x - originX) / 16.0D);
        int centreZ = (int) Math.round((z - originZ) / 16.0D);
        for (int iz = centreZ - 1; iz <= centreZ + 1; iz++)
        {
            if (iz < 0 || iz >= countZ)
            {
                continue;
            }
            for (int ix = centreX - 1; ix <= centreX + 1; ix++)
            {
                if (ix < 0 || ix >= countX)
                {
                    continue;
                }
                int treeX = originX + ix * 16;
                int treeZ = originZ + iz * 16;
                if (Math.floorMod(positionHash(treeX, treeZ), 10) < 3
                        || excludedForestSite(treeX, treeZ))
                {
                    continue;
                }
                int baseY = terrainHeight(treeX, treeZ) + 1;
                int dx = x - treeX;
                int dz = z - treeZ;
                int dy = y - (baseY + 3);
                if (dy >= 0 && dy < 4
                        && Math.abs(dx) <= 2 && Math.abs(dz) <= 2
                        && Math.abs(dx) + Math.abs(dz) <= 3
                        && (dy < 3
                        || Math.abs(dx) + Math.abs(dz) <= 1))
                {
                    return Blocks.SPRUCE_LEAVES.defaultBlockState();
                }
                if (dx == 0 && dz == 0
                        && y >= baseY && y < baseY + 6)
                {
                    return Blocks.SPRUCE_LOG.defaultBlockState();
                }
            }
        }
        return null;
    }

    private static BlockState logisticsStateAt(int x, int y, int z)
    {
        for (FabricBox box : List.of(PUMP, WAREHOUSE, SUBSTATION))
        {
            if (box.contains(x, y, z))
            {
                return boxStateAt(box, x, y, z, Feature.LOGISTICS);
            }
        }
        if (x >= 160 && x < 384 && z >= 120 && z < 232
                && y >= YARD_MIN_Y && y <= YARD_CLEAR_MAX_Y)
        {
            if (y == YARD_SURFACE_Y)
            {
                boolean stripe = Math.floorMod(x - 160, 32) < 2
                        || Math.floorMod(z - 120, 32) < 2;
                return stripe
                        ? Blocks.YELLOW_CONCRETE.defaultBlockState()
                        : Blocks.SMOOTH_STONE.defaultBlockState();
            }
            if (y > YARD_SURFACE_Y)
            {
                return Blocks.AIR.defaultBlockState();
            }
            return com.projectseele.world.NervMaterials.structuralBlock().defaultBlockState();
        }
        return null;
    }

    private static BlockState westSeamStateAt(int x, int y, int z)
    {
        return WEST_SEAM.contains(x, y, z)
                ? boxStateAt(WEST_SEAM, x, y, z, Feature.WEST_SEAM)
                : null;
    }

    private static BlockState boxStateAt(
            FabricBox box, int x, int y, int z, Feature feature)
    {
        boolean floor = y == box.minY();
        boolean roof = y == box.maxY() - 1;
        boolean wall = x == box.minX() || x == box.maxX() - 1
                || z == box.minZ() || z == box.maxZ() - 1;
        boolean doorway;
        if (feature == Feature.WEST_SEAM)
        {
            doorway = (x == box.minX() || x == box.maxX() - 1)
                    && y >= -360 && y < -355 && z >= 28 && z < 36;
        }
        else
        {
            int doorCentre = (box.minX() + box.maxX()) / 2;
            doorway = z == box.maxZ() - 1
                    && x >= doorCentre - 2 && x <= doorCentre + 2
                    && y < box.minY() + 6;
        }
        if (doorway)
        {
            return Blocks.AIR.defaultBlockState();
        }
        if (floor)
        {
            return com.projectseele.world.NervMaterials.structuralBlock().defaultBlockState();
        }
        if (roof)
        {
            return Math.floorMod(x + z, 11) == 0
                    ? Blocks.SEA_LANTERN.defaultBlockState()
                    : Blocks.SMOOTH_STONE.defaultBlockState();
        }
        if (wall)
        {
            boolean window = y >= box.minY() + 5
                    && y <= box.minY() + 8
                    && Math.floorMod(x + z, 9) < 4;
            return window
                    ? Blocks.LIGHT_BLUE_STAINED_GLASS.defaultBlockState()
                    : Blocks.IRON_BLOCK.defaultBlockState();
        }
        return Blocks.AIR.defaultBlockState();
    }

    private static long roadWork()
    {
        long total = 0L;
        for (RoadSegment segment : ROAD_SEGMENTS)
        {
            total += segment.work();
        }
        return total;
    }

    private static int positionHash(int x, int z)
    {
        int value = x * 73428767 ^ z * 912931;
        value ^= value >>> 16;
        value *= 0x45D9F3B;
        return value ^ value >>> 16;
    }

    private static BlockState skyweaveState()
    {
        return ModBlocks.GEOFRONT_SKYWEAVE.get().defaultBlockState();
    }

    private static FabricBlock relative(BlockPos centre, int x, int y,
                                        int z, BlockState state)
    {
        return new FabricBlock(
                new BlockPos(centre.getX() + x, y,
                        centre.getZ() + z), state);
    }

    public record FabricBlock(BlockPos position, BlockState state) {}

    public record ResolvedFabricBlock(boolean writable, BlockState state) {}

    public record FeatureContract(String id, String revision, int priority,
                                  long authoredWork, int geometryVersion,
                                  String contractHash) {}

    private record PyramidSlice(int xHalf, int zMin, int zMax) {}

    private record TreeSite(int x, int z) {}

    private record RoadSegment(int x1, int z1, int x2, int z2, int width)
    {
        private int steps()
        {
            return Math.max(Math.abs(this.x2 - this.x1),
                    Math.abs(this.z2 - this.z1)) + 1;
        }

        private long work()
        {
            return (long) steps() * this.width * ROAD_LAYERS;
        }
    }

    private record FabricBox(int minX, int minY, int minZ,
                             int maxX, int maxY, int maxZ)
    {
        private int sizeX()
        {
            return this.maxX - this.minX;
        }

        private int sizeY()
        {
            return this.maxY - this.minY;
        }

        private int sizeZ()
        {
            return this.maxZ - this.minZ;
        }

        private long volume()
        {
            return (long) sizeX() * sizeY() * sizeZ();
        }

        private boolean contains(int x, int y, int z)
        {
            return x >= minX && x < maxX
                    && y >= minY && y < maxY
                    && z >= minZ && z < maxZ;
        }
    }

    private record OwnerMask(
            Map<Long, List<FacilitySchemaV2.IntBox>> boxesByChunk)
    {
        private static OwnerMask create(
                FacilitySchemaV2.ResolvedManifest manifest, int inflation)
        {
            Map<Long, List<FacilitySchemaV2.IntBox>> mutable =
                    new HashMap<>();
            for (FacilitySchemaV2.ZoneSpec zone : manifest.zones())
            {
                FacilitySchemaV2.IntBox owner = zone.owner();
                FacilitySchemaV2.IntBox box = new FacilitySchemaV2.IntBox(
                        owner.minX() - inflation,
                        owner.minY() - inflation,
                        owner.minZ() - inflation,
                        owner.maxX() + inflation,
                        owner.maxY() + inflation,
                        owner.maxZ() + inflation);
                int minChunkX = Math.floorDiv(box.minX(), 16);
                int maxChunkX = Math.floorDiv(box.maxX() - 1, 16);
                int minChunkZ = Math.floorDiv(box.minZ(), 16);
                int maxChunkZ = Math.floorDiv(box.maxZ() - 1, 16);
                for (int chunkX = minChunkX;
                     chunkX <= maxChunkX; chunkX++)
                {
                    for (int chunkZ = minChunkZ;
                         chunkZ <= maxChunkZ; chunkZ++)
                    {
                        mutable.computeIfAbsent(
                                ChunkPos.asLong(chunkX, chunkZ),
                                ignored -> new ArrayList<>()).add(box);
                    }
                }
            }
            Map<Long, List<FacilitySchemaV2.IntBox>> immutable =
                    new HashMap<>();
            mutable.forEach((key, value) ->
                    immutable.put(key, List.copyOf(value)));
            return new OwnerMask(Map.copyOf(immutable));
        }

        private boolean contains(BlockPos position)
        {
            List<FacilitySchemaV2.IntBox> boxes =
                    this.boxesByChunk.get(ChunkPos.asLong(
                            position.getX() >> 4,
                            position.getZ() >> 4));
            if (boxes == null)
            {
                return false;
            }
            for (FacilitySchemaV2.IntBox box : boxes)
            {
                if (position.getX() >= box.minX()
                        && position.getX() < box.maxX()
                        && position.getY() >= box.minY()
                        && position.getY() < box.maxY()
                        && position.getZ() >= box.minZ()
                        && position.getZ() < box.maxZ())
                {
                    return true;
                }
            }
            return false;
        }
    }
}
