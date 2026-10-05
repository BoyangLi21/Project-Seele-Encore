package com.projectseele.world;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

import com.projectseele.ProjectSeele;
import com.projectseele.registry.ModBlocks;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.DoorBlock;
import net.minecraft.world.level.block.LeverBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.AttachFace;
import net.minecraft.world.level.block.state.properties.BlockStateProperties;
import net.minecraft.world.level.block.state.properties.DoubleBlockHalf;
import net.minecraft.world.level.levelgen.Heightmap;

/**
 * Deterministic original Tokyo-3 surface district around the three NERV bays.
 * The inner grid carries retractable armour towers while a wider permanent
 * ward gives EVA-scale streets enough depth to read as a city rather than a
 * compact test pad.
 */
public final class ThirdTokyoSurfaceBuilder
{
    public static final int DISTRICT_HALF_SIZE = 208;
    public static final int FOUNDATION_HALF_SIZE = 224;
    public static final int OBSERVATION_Z = 216;
    public static final int OBSERVATION_Y = 38;
    public static final int ARMOURED_LOT_HALF_SIZE = 12;
    private static final int ROAD_SPACING = 40;
    private static final int ROAD_OFFSET = 20;
    private static final int ROAD_HALF_WIDTH = 4;
    private static final int SIDEWALK_HALF_WIDTH = 7;
    private static final int LOT_HALF_SIZE = ARMOURED_LOT_HALF_SIZE;
    private static final int[] LOT_CENTRES =
            {-160, -120, -80, -40, 0, 40, 80, 120, 160};
    private static final int[] OUTER_LOT_CENTRES =
            {-200, -160, -120, -80, -40, 0, 40, 80, 120, 160, 200};

    private static final int[][] PYLONS = {
            {-180, -160}, {-180, 0}, {-180, 160},
            {180, -160}, {180, 0}, {180, 160},
    };
    private static final int[][] ROAD_AUDIT_POINTS = {
            {-180, -180}, {-180, 180}, {180, -180}, {180, 180},
            {-140, -180}, {140, 180}, {-180, 140}, {180, -140},
    };
    private static final int CEILING_SHELL_CLEARANCE = 4;
    private static final List<TowerSpec> ARMOURED_TOWERS = createArmouredTowers();
    private static final List<TowerSpec> OUTER_WARD_TOWERS = createOuterWardTowers();
    private static final List<TowerSpec> MOVABLE_BUILDINGS = createMovableBuildings();
    private static final List<TowerSpec> TV_MOVABLE_BUILDINGS = MOVABLE_BUILDINGS.stream()
            .map(TvTokyo3Architecture::spec).toList();
    private static final int EXPECTED_TOWERS = ARMOURED_TOWERS.size();
    private static final int EXPECTED_OUTER_WARDS = OUTER_WARD_TOWERS.size();
    private static final int MAX_RETRACTION_DEPTH = MOVABLE_BUILDINGS.stream()
            .mapToInt(tower -> ceilingTravelDepth(tower) + tower.height())
            .max().orElse(0);
    private static final int UPDATE_CLIENTS = Block.UPDATE_CLIENTS;
    // Journalled cargo includes doors, stairs and full block-entity NBT. Shape
    // updates are deferred while its complete measured component is in flight.
    private static final int UPDATE_TRAVEL =
            Block.UPDATE_CLIENTS | Block.UPDATE_KNOWN_SHAPE;
    /**
     * A buried receipt for the facade/retraction contract. It deliberately sits
     * outside the playable road grid, so upgrading an old save cannot replace a
     * tower core or a player-facing control.
     */
    private static final BlockPos REVISION_MARKER =
            new BlockPos(219, -5, 219);

    private ThirdTokyoSurfaceBuilder() {}

    public static void buildDistrict(ServerLevel level, BlockPos origin)
    {
        if(CityRigidTopologyR45.owns(level,origin))return;
        buildFoundation(level, origin);
        buildRoadGrid(level, origin);

        for (int x : LOT_CENTRES)
        {
            for (int z : LOT_CENTRES)
            {
                if (Math.abs(x) <= 40 && Math.abs(z) <= 40
                        || reservedPrivateSkyscraperLot(x, z))
                {
                    continue;
                }
                BlockPos centre = origin.offset(x, 0, z);
                if ((x == 0 && z == -80) || (x == 80 && z == 0))
                {
                    buildSubstation(level, centre);
                }
                else if (x == 0 && z == 80)
                {
                    buildBattlePlaza(level, centre);
                }
                else
                {
                    buildArmouredTower(level, centre, towerHeight(x, z), x, z);
                }
            }
        }

        for (int x : OUTER_LOT_CENTRES)
        {
            for (int z : OUTER_LOT_CENTRES)
            {
                if (Math.max(Math.abs(x), Math.abs(z)) != 200
                        || reservedOuterTransitLot(x, z))
                {
                    continue;
                }
                buildOuterWardTower(level, origin.offset(x, 0, z),
                        outerWardHeight(x, z), x, z);
            }
        }

        for (int[] pylon : PYLONS)
        {
            buildPowerPylon(level, origin.offset(pylon[0], 0, pylon[1]));
        }
        if(TvWorldPreviewTerrain.active(level))
            for(int index=0;index<TV_MOVABLE_BUILDINGS.size();index++)refineTvLot(level,origin,index);
        connectPowerGrid(level, origin, -100);
        connectPowerGrid(level, origin, 100);
        buildSortieGate(level, origin.offset(0, 1, 52));
        ensureLaunchControlQuarter(level, origin);
        // R47: the tall surface lookout is retired in the played TV city.
        if (!TvWorldPreviewTerrain.active(level))
            buildObservationDeck(level, origin.offset(0, 0, OBSERVATION_Z));
        set(level, origin.offset(REVISION_MARKER),
                Blocks.NETHERITE_BLOCK.defaultBlockState());
        set(level, origin.offset(REVISION_MARKER).above(),
                Blocks.WAXED_OXIDIZED_COPPER.defaultBlockState());
        set(level, origin.offset(REVISION_MARKER).north(),
                Blocks.LODESTONE.defaultBlockState());
    }

    /**
     * One-time installed-world migration for the real descending facade
     * sequence and the four distinct Tokyo-3 tower families.
     */
    public static boolean ensureDistrictRevision(ServerLevel level,
                                                 BlockPos origin,
                                                 int retractionDepth)
    {
        if(CityRigidTopologyR45.owns(level,origin))return false;
        if (districtRevisionPresent(level, origin))
        {
            return false;
        }
        buildDistrict(level, origin);
        int depth = Math.max(0, Math.min(MAX_RETRACTION_DEPTH,
                retractionDepth));
        for (int step = 1; step <= depth; step++)
        {
            applyRetractionDepth(level, origin, step - 1, step);
        }
        ProjectSeele.LOGGER.info(
                "Tokyo-3 district migrated to translated-building revision at {} depth={}",
                origin.toShortString(), depth);
        return true;
    }

    private static boolean districtRevisionPresent(ServerLevel level,
                                                   BlockPos origin)
    {
        return level.getBlockState(origin.offset(REVISION_MARKER))
                .is(Blocks.NETHERITE_BLOCK)
                && level.getBlockState(origin.offset(REVISION_MARKER).above())
                .is(Blocks.WAXED_OXIDIZED_COPPER)
                && level.getBlockState(origin.offset(REVISION_MARKER).north())
                .is(Blocks.LODESTONE);
    }

    /**
     * Restores the four permanent NERV control blocks around the open launch
     * court without rebuilding the retractable skyline.
     */
    public static void ensureLaunchControlQuarter(ServerLevel level,
                                                  BlockPos origin)
    {
        if(CityLegacyOwnershipR48.inhibits(level,origin,"ThirdTokyoSurfaceBuilder.ensureLaunchControlQuarter"))return;
        if(BattlefieldR21.concealed(level))return;
        for (int x : new int[] {-40, 40})
        {
            for (int z : new int[] {-40, 40})
            {
                BlockPos centre = origin.offset(x, 0, z);
                if (!level.getBlockState(centre.above(11))
                        .is(Blocks.REDSTONE_LAMP))
                {
                    buildLaunchControlBlock(level, centre, x, z);
                }
            }
        }
    }

    public static DistrictAudit inspect(ServerLevel level, BlockPos origin)
    {
        return inspect(level, origin, 0);
    }

    public static DistrictAudit inspect(ServerLevel level, BlockPos origin,
                                        int retractionDepth)
    {
        int depth = Math.max(0, Math.min(MAX_RETRACTION_DEPTH, retractionDepth));
        int roads = 0;
        for (int[] point : ROAD_AUDIT_POINTS)
        {
            if (isRoad(level.getBlockState(origin.offset(point[0], 0, point[1]))))
            {
                roads++;
            }
        }

        int towers = 0;
        for (int x : LOT_CENTRES)
        {
            for (int z : LOT_CENTRES)
            {
                if (Math.abs(x) <= 40 && Math.abs(z) <= 40
                        || (x == 0 && z == -80)
                        || (x == 80 && z == 0)
                        || (x == 0 && z == 80)
                        || reservedPrivateSkyscraperLot(x, z))
                {
                    continue;
                }
                int visibleHeight = Math.max(0, (TvWorldPreviewTerrain.active(level)
                        ? TvTokyo3Architecture.spec(new TowerSpec(x, z, towerHeight(x, z), LOT_HALF_SIZE, false)).height()
                        : towerHeight(x, z)) - depth);
                boolean signature = visibleHeight > 0
                        ? level.getBlockState(origin.offset(x, visibleHeight + 1, z))
                                .is(Blocks.REDSTONE_LAMP)
                        : level.getBlockState(origin.offset(x, 0, z))
                                .is(ModBlocks.RETRACTABLE_BUILDING_CORE.get())
                                && towerShellClear(level, origin.offset(x, 0, z));
                if (signature)
                {
                    towers++;
                }
            }
        }

        int outerWards = 0;
        for (int x : OUTER_LOT_CENTRES)
        {
            for (int z : OUTER_LOT_CENTRES)
            {
                if (Math.max(Math.abs(x), Math.abs(z)) != 200
                        || reservedOuterTransitLot(x, z))
                {
                    continue;
                }
                int height = TvWorldPreviewTerrain.active(level)
                        ? TvTokyo3Architecture.spec(new TowerSpec(x, z, outerWardHeight(x, z), 9, true)).height()
                        : outerWardHeight(x, z);
                int visibleHeight = Math.max(0, height - depth);
                boolean signature = visibleHeight > 0
                        ? level.getBlockState(origin.offset(x, visibleHeight + 1, z))
                                .is(Blocks.REDSTONE_LAMP)
                        : towerShellClear(level, origin.offset(x, 0, z), 9);
                if (signature)
                {
                    outerWards++;
                }
            }
        }

        int ceilingBuildings = 0;
        for (TowerSpec tower : movableBuildings(level))
        {
            if (ceilingStateMatches(level, origin, tower, depth))
            {
                ceilingBuildings++;
            }
        }

        int substations = 0;
        if (isSubstationCore(level.getBlockState(origin.offset(0, 1, -80))))
        {
            substations++;
        }
        if (isSubstationCore(level.getBlockState(origin.offset(80, 1, 0))))
        {
            substations++;
        }

        int pylons = 0;
        for (int[] pylon : PYLONS)
        {
            if (level.getBlockState(origin.offset(pylon[0], 28, pylon[1]))
                    .is(Blocks.IRON_BLOCK))
            {
                pylons++;
            }
        }

        // The plaza builder no longer places a beacon, and played S20 worlds
        // repurpose that footprint. It is not part of the moving-city contract.
        boolean sortieLane = isRoad(level.getBlockState(origin.offset(0, 0, 60)));
        boolean observationDeck = TvWorldPreviewTerrain.active(level)
                ? level.getBlockState(origin.offset(0, OBSERVATION_Y, OBSERVATION_Z)).isAir()
                : level.getBlockState(origin.offset(0, OBSERVATION_Y, OBSERVATION_Z)).is(Blocks.LODESTONE);
        boolean foundation = level.getBlockState(
                origin.offset(FOUNDATION_HALF_SIZE, -4, 0)).is(Blocks.DEEPSLATE_BRICKS);
        boolean valid = roads == ROAD_AUDIT_POINTS.length
                && towers == EXPECTED_TOWERS
                && outerWards == EXPECTED_OUTER_WARDS
                && ceilingBuildings == MOVABLE_BUILDINGS.size()
                && substations == 2
                && pylons == PYLONS.length
                && sortieLane && observationDeck && foundation;
        return new DistrictAudit(valid, roads, towers, outerWards,
                ceilingBuildings, substations, pylons,
                sortieLane, observationDeck, foundation);
    }

    public static List<TowerSpec> armouredTowers()
    {
        return ARMOURED_TOWERS;
    }

    /** Every generated building that physically travels into the GeoFront. */
    public static List<TowerSpec> movableBuildings()
    {
        return MOVABLE_BUILDINGS;
    }

    public static List<TowerSpec> movableBuildings(ServerLevel level)
    {
        return TvWorldPreviewTerrain.active(level) ? TV_MOVABLE_BUILDINGS : MOVABLE_BUILDINGS;
    }

    /** Explicit preview authoring: replace one old lot, preserving its controls. */
    public static void refineTvLot(ServerLevel level, BlockPos origin, int index)
    {
        if(CityRigidTopologyR45.owns(level,origin))return;
        if (!TvWorldPreviewTerrain.active(level)) throw new IllegalArgumentException("TV preview only");
        TowerSpec old = MOVABLE_BUILDINGS.get(index), tower = TV_MOVABLE_BUILDINGS.get(index);
        BlockPos centre = origin.offset(tower.x(), 0, tower.z());
        for (int y = 1; y <= Math.max(old.height(), tower.height()) + 3; y++)
            fillSquare(level, centre, y, old.halfSize(), Blocks.AIR.defaultBlockState(), UPDATE_TRAVEL);
        paintRetractedHatch(level, centre, tower.halfSize(), tower.outerWard());
        buildTowerInteriorLayerR44(level,centre,tower,0,0);
        for (int y = 1; y <= tower.height(); y++)
        {
            buildTowerWallLayer(level, centre, tower, y, y);
            buildTowerInteriorLayerR44(level,centre,tower,y,y);
        }
        fillSquare(level, centre, tower.height() + 1, tower.halfSize(),
                Blocks.SMOOTH_STONE.defaultBlockState(), UPDATE_TRAVEL);
        set(level, centre.offset(0, tower.height() + 1, 0), Blocks.REDSTONE_LAMP.defaultBlockState(), UPDATE_TRAVEL);
        if (!tower.outerWard())
            set(level, centre.offset(0, tower.height(), 0), Blocks.REDSTONE_BLOCK.defaultBlockState(), UPDATE_TRAVEL);
        setRoofMasts(level, centre, tower, tower.height() + 2, Blocks.LIGHTNING_ROD.defaultBlockState());
        for (int x : new int[]{-tower.halfSize(), tower.halfSize()})
            for (int z : new int[]{-tower.halfSize(), tower.halfSize()})
                for (int y = TvWorldPreviewTerrain.ROOF_Y - 3; y <= TvWorldPreviewTerrain.ROOF_Y; y++)
                    set(level, new BlockPos(centre.getX() + x, y, centre.getZ() + z),
                            Blocks.IRON_BLOCK.defaultBlockState(), UPDATE_TRAVEL);
    }

    public static void refineTvFoundation(ServerLevel level, BlockPos origin)
    {
        if(CityLegacyOwnershipR48.inhibits(level,origin,"ThirdTokyoSurfaceBuilder.refineTvFoundation"))return;
        if (!TvWorldPreviewTerrain.active(level)) throw new IllegalArgumentException("TV preview only");
        for (int depth = 1; depth <= 6; depth++)
            for (int span = -FOUNDATION_HALF_SIZE; span <= FOUNDATION_HALF_SIZE; span++)
            {
                var material = Blocks.DEEPSLATE_BRICKS.defaultBlockState();
                set(level, origin.offset(-FOUNDATION_HALF_SIZE, -depth, span), material, UPDATE_TRAVEL);
                set(level, origin.offset(FOUNDATION_HALF_SIZE, -depth, span), material, UPDATE_TRAVEL);
                set(level, origin.offset(span, -depth, -FOUNDATION_HALF_SIZE), material, UPDATE_TRAVEL);
                set(level, origin.offset(span, -depth, FOUNDATION_HALF_SIZE), material, UPDATE_TRAVEL);
            }
    }

    public static int maximumRetractionDepth()
    {
        return MAX_RETRACTION_DEPTH;
    }

    /** Runtime depth for the active surface frame; S22 uses its shallow dome. */
    public static int maximumRetractionDepth(BlockPos origin)
    {
        if (!origin.equals(IntegratedNervMapBuilder.S22_TOKYO3_ORIGIN))
        {
            return MAX_RETRACTION_DEPTH;
        }
        return MOVABLE_BUILDINGS.stream()
                .mapToInt(tower -> ceilingTravelDepth(tower, origin)
                        + tower.height())
                .max().orElse(0);
    }

    /** Applies exactly one globally synchronized layer of tower travel. */
    public static void applyRetractionDepth(ServerLevel level, BlockPos origin,
                                            int oldDepth, int newDepth)
    {
        if(CityRigidTopologyR45.owns(level,origin))return;
        for (int index = 0; index < MOVABLE_BUILDINGS.size(); index++)
        {
            applyRetractionDepth(level, origin, oldDepth, newDepth, index);
        }
    }

    /**
     * Applies one layer of travel to a single tower. The director spreads a
     * layer across consecutive ticks so no tick pays for the whole district;
     * every tower still travels exactly one block per layer period.
     */
    public static void applyRetractionDepth(ServerLevel level, BlockPos origin,
                                            int oldDepth, int newDepth, int towerIndex)
    {
        if(CityRigidTopologyR45.owns(level,origin))return;
        int maximumDepth = maximumRetractionDepth(origin);
        if (Math.abs(newDepth - oldDepth) != 1
                || oldDepth < 0 || oldDepth > maximumDepth
                || newDepth < 0 || newDepth > maximumDepth)
        {
            throw new IllegalArgumentException(
                    "Tokyo-3 retraction depth must move by one layer");
        }
        TowerSpec tower = movableBuildings(level).get(towerIndex);
        int cursor=0;
        do
        {
            Tokyo3BuildingArchiveR44.TravelStep step=stepRetractionDepthR44(
                    level,origin,oldDepth,newDepth,towerIndex,cursor);
            if(step.failed())throw new IllegalStateException(step.fault());
            if(step.complete())return;
            cursor=step.cursor();
        }
        while(true);
    }

    public static Tokyo3BuildingArchiveR44.TravelStep stepRetractionDepthR44(
            ServerLevel level,BlockPos origin,int oldDepth,int newDepth,int towerIndex,int cursor)
    {
        if(CityRigidTopologyR45.owns(level,origin))return new Tokyo3BuildingArchiveR44.TravelStep(false,true,cursor,0,"Rigid topology owns this complete city");
        if(Math.abs(newDepth-oldDepth)!=1||oldDepth<0||newDepth<0
                ||oldDepth>maximumRetractionDepth(origin)||newDepth>maximumRetractionDepth(origin))
            return new Tokyo3BuildingArchiveR44.TravelStep(false,true,cursor,0,"Invalid generated-tower depth step");
        TowerSpec tower=movableBuildings(level).get(towerIndex);
        int travel=Math.max(tower.height(),-ceilingRoofRelativeY(tower,origin));
        if(Math.max(0,tower.height()-oldDepth)==Math.max(0,tower.height()-newDepth)
                &&Math.max(0,Math.min(tower.height(),oldDepth-travel))==Math.max(0,Math.min(tower.height(),newDepth-travel)))
            return new Tokyo3BuildingArchiveR44.TravelStep(true,false,0,0,"");
        return Tokyo3BuildingArchiveR44.get(level,origin.offset(tower.x(),0,tower.z())).step(level,origin,
                tower,oldDepth,newDepth,cursor);
    }

    /* Retained only as the historical geometric reference for old receipts. */
    private static void applyLegacyShellRetractionDepth(ServerLevel level,BlockPos origin,
                                                       int oldDepth,int newDepth,int towerIndex)
    {
        TowerSpec tower=movableBuildings(level).get(towerIndex);
        int oldVisible = Math.max(0, tower.height() - oldDepth);
        int newVisible = Math.max(0, tower.height() - newDepth);
        int oldCeilingVisible = ceilingVisibleHeight(tower, oldDepth, origin);
        int newCeilingVisible = ceilingVisibleHeight(tower, newDepth, origin);
        if (oldVisible != newVisible)
        {
            BlockPos centre = origin.offset(tower.x(), 0, tower.z());
            if (newVisible < oldVisible)
            {
                descendTowerLayer(level, centre, tower, oldVisible, newVisible);
            }
            else
            {
                ascendTowerLayer(level, centre, tower, oldVisible, newVisible);
            }
        }
        if (oldCeilingVisible != newCeilingVisible)
        {
            if (newCeilingVisible > oldCeilingVisible)
            {
                emergeCeilingLayer(level, origin, tower,
                        oldCeilingVisible, newCeilingVisible);
            }
            else
            {
                withdrawCeilingLayer(level, origin, tower,
                        oldCeilingVisible, newCeilingVisible);
            }
        }
    }

    /**
     * Translates the complete visible building down by one real block.
     *
     * <p>The old implementation shortened the tower from its roof. That made
     * the antenna and roof appear to descend while the door and first floor
     * stayed frozen until the final tick. Moving bottom-to-top is safe because
     * every destination is below its unread source; the ground-floor doorway
     * now enters the armour hatch first, exactly like a telescoping Tokyo-3
     * building.</p>
     */
    private static void descendTowerLayer(ServerLevel level, BlockPos centre,
                                          TowerSpec tower,
                                          int oldVisible, int newVisible)
    {
        BlockState core = level.getBlockState(centre);
        boolean preserveCore = core.is(
                ModBlocks.RETRACTABLE_BUILDING_CORE.get());
        int half = tower.halfSize();
        setRoofMasts(level, centre, tower, oldVisible + 2,
                Blocks.AIR.defaultBlockState());
        fillSquare(level, centre, oldVisible + 1, half,
                Blocks.AIR.defaultBlockState(), UPDATE_TRAVEL);
        for (int y = 1; y <= oldVisible; y++)
        {
            copyTowerWallAndCentre(level, centre, half, y, y - 1);
        }

        paintRetractedHatch(level, centre, half, tower.outerWard());
        if (preserveCore)
        {
            set(level, centre, core, UPDATE_TRAVEL);
        }

        if (newVisible > 0)
        {
            fillSquare(level, centre, newVisible + 1, half,
                    Blocks.SMOOTH_STONE.defaultBlockState(), UPDATE_TRAVEL);
            set(level, centre.offset(0, newVisible + 1, 0),
                    Blocks.REDSTONE_LAMP.defaultBlockState(), UPDATE_TRAVEL);
            setRoofMasts(level, centre, tower, newVisible + 2,
                    Blocks.LIGHTNING_ROD.defaultBlockState());
            return;
        }

        // The final one-block building still carried its roof and antenna at
        // Y=1..2 after translation. Remove that complete last silhouette.
        for (int y = 1; y <= 3; y++)
        {
            fillSquare(level, centre, y, half,
                    Blocks.AIR.defaultBlockState(), UPDATE_TRAVEL);
        }
    }

    /**
     * Deletes lightning rods left standing in a mast column.
     *
     * <p>Until the ascent path learned to clear the previous layer's masts, a
     * restored district grew one rod per lot corner per layer travelled — a
     * three-hundred-block spike out of every building. The rods are the only
     * thing removed, and only inside the four known mast columns of each lot,
     * so nothing else in the district can be touched by this.
     *
     * @return how many stale rods were removed.
     */
    public static int sweepStrayMasts(ServerLevel level, BlockPos origin,
                                       int currentDepth)
    {
        if(CityRigidTopologyR45.owns(level,origin))return 0;
        int removed = 0;
        for (TowerSpec tower : movableBuildings(level))
        {
            BlockPos centre = origin.offset(tower.x(), 0, tower.z());
            int keepAt = Math.max(0, tower.height() - currentDepth) + 2;
            int ceilingY = ceilingRoofRelativeY(tower, origin);
            for (int y = Math.min(ceilingY, -1); y <= tower.height() + 3; y++)
            {
                if (y == keepAt)
                {
                    continue;
                }
                for (BlockPos mast : mastColumn(centre, tower, y))
                {
                    if (level.getBlockState(mast).is(Blocks.LIGHTNING_ROD))
                    {
                        set(level, mast, Blocks.AIR.defaultBlockState(),
                                UPDATE_TRAVEL);
                        removed++;
                    }
                }
            }
        }
        if (removed > 0)
        {
            ProjectSeele.LOGGER.info(
                    "Tokyo-3 swept {} stale tower masts at {} depth={}",
                    removed, origin.toShortString(), currentDepth);
        }
        return removed;
    }

    /**
     * Removes only complete roof/hatch planes left by the retired surface-Y
     * origin.  Older saves moved the same deterministic X/Z tower grid from a
     * higher street datum; retiring its SavedData stopped the mover but left
     * smooth-stone roofs and pressure hatches floating above the new city.
     *
     * <p>A candidate must match more than ninety percent of one canonical
     * generated plane, and the current district's legitimate roof is always
     * excluded.  This deliberately cannot recognise roads, hand-built
     * structures or imported skyscrapers.</p>
     *
     * @return number of stale planes removed.
     */
    public static int sweepLegacySurfaceCaps(ServerLevel level,
                                              BlockPos origin,
                                              int currentDepth)
    {
        if(CityRigidTopologyR45.owns(level,origin))return 0;
        int removedPlanes = 0;
        int minimumY = origin.getY() + 1;
        int maximumY = origin.getY() + 90;
        for (TowerSpec tower : movableBuildings(level))
        {
            BlockPos centre = origin.offset(tower.x(), 0, tower.z());
            int half = tower.halfSize();
            int visible = Math.max(0, tower.height() - currentDepth);
            int currentRoofY = origin.getY() + visible + 1;
            for (int worldY = minimumY; worldY <= maximumY; worldY++)
            {
                if (worldY == currentRoofY)
                {
                    continue;
                }
                BlockPos planeCentre = new BlockPos(
                        centre.getX(), worldY, centre.getZ());
                if (legacyRoofCap(level, planeCentre, half))
                {
                    if (TvWorldPreviewTerrain.active(level) && removedPlanes < 6)
                        ProjectSeele.LOGGER.info("TV stale cap location={} activeRoofY={} depth={}",
                                planeCentre, currentRoofY, currentDepth);
                    clearLegacyPlane(level, planeCentre, half);
                    removedPlanes++;
                    continue;
                }
                if (legacyRetractedHatch(level, planeCentre, half,
                        tower.outerWard()))
                {
                    clearLegacyPlane(level, planeCentre, half);
                    removedPlanes++;
                }
            }
        }
        if (removedPlanes > 0)
        {
            ProjectSeele.LOGGER.info(
                    "Tokyo-3 removed {} signed legacy roof/hatch planes at {} depth={}",
                    removedPlanes, origin.toShortString(), currentDepth);
        }
        return removedPlanes;
    }

    private static boolean legacyRoofCap(ServerLevel level, BlockPos centre,
                                         int half)
    {
        if (!level.getBlockState(centre).is(Blocks.REDSTONE_LAMP))
        {
            return false;
        }
        int area = (half * 2 + 1) * (half * 2 + 1);
        int matching = 0;
        for (int x = -half; x <= half; x++)
        {
            for (int z = -half; z <= half; z++)
            {
                BlockState state = level.getBlockState(centre.offset(x, 0, z));
                if (state.is(Blocks.SMOOTH_STONE)
                        || x == 0 && z == 0
                        && state.is(Blocks.REDSTONE_LAMP))
                {
                    matching++;
                }
            }
        }
        return matching * 10 >= area * 9;
    }

    private static boolean legacyRetractedHatch(ServerLevel level,
                                                 BlockPos centre, int half,
                                                 boolean outerWard)
    {
        for (int x : new int[] {-half, half})
        {
            for (int z : new int[] {-half, half})
            {
                if (!level.getBlockState(centre.offset(x, 0, z))
                        .is(Blocks.POLISHED_DEEPSLATE))
                {
                    return false;
                }
            }
        }
        int area = (half * 2 + 1) * (half * 2 + 1);
        int matching = 0;
        for (int x = -half; x <= half; x++)
        {
            for (int z = -half; z <= half; z++)
            {
                BlockState expected = retractedHatchState(
                        x, z, half, outerWard);
                if (level.getBlockState(centre.offset(x, 0, z))
                        .getBlock() == expected.getBlock())
                {
                    matching++;
                }
            }
        }
        return matching * 10 >= area * 9;
    }

    private static void clearLegacyPlane(ServerLevel level, BlockPos centre,
                                         int half)
    {
        fillSquare(level, centre, 0, half,
                Blocks.AIR.defaultBlockState(), UPDATE_TRAVEL);
        for (int y = 1; y <= 2; y++)
        {
            for (int x = -half; x <= half; x++)
            {
                for (int z = -half; z <= half; z++)
                {
                    BlockPos position = centre.offset(x, y, z);
                    BlockState state = level.getBlockState(position);
                    if (state.is(Blocks.LIGHTNING_ROD)
                            || state.is(Blocks.SNOW)
                            || state.is(Blocks.SNOW_BLOCK))
                    {
                        set(level, position, Blocks.AIR.defaultBlockState(),
                                UPDATE_TRAVEL);
                    }
                }
            }
        }
    }

    private static List<BlockPos> mastColumn(BlockPos centre, TowerSpec tower,
                                              int y)
    {
        if (tower.outerWard())
        {
            return List.of(centre.offset(0, y, 0));
        }
        return List.of(centre.offset(-8, y, -8), centre.offset(-8, y, 8),
                centre.offset(8, y, -8), centre.offset(8, y, 8));
    }

    /**
     * Exact visual inverse of descent: move the visible stack upward, then
     * reveal the next original wall layer at street level.
     *
     * <p>The source layer runs from the roof down to floor one. Consequently
     * the lobby doorway is the last feature to emerge during restoration.</p>
     */
    private static void ascendTowerLayer(ServerLevel level, BlockPos centre,
                                         TowerSpec tower,
                                         int oldVisible, int newVisible)
    {
        BlockState core = level.getBlockState(centre);
        boolean preserveCore = core.is(
                ModBlocks.RETRACTABLE_BUILDING_CORE.get());
        int half = tower.halfSize();
        if (oldVisible > 0)
        {
            setRoofMasts(level, centre, tower, oldVisible + 2,
                    Blocks.AIR.defaultBlockState());
            fillSquare(level, centre, oldVisible + 1, half,
                    Blocks.AIR.defaultBlockState(), UPDATE_TRAVEL);
            for (int y = oldVisible; y >= 1; y--)
            {
                copyTowerWallAndCentre(level, centre, half, y, y + 1);
            }
            clearTowerWallLayer(level, centre, 1, half);
            set(level, centre.offset(0, 1, 0),
                    Blocks.AIR.defaultBlockState(), UPDATE_TRAVEL);
        }

        int sourceY = tower.height() - newVisible + 1;
        buildTowerWallLayer(level, centre, tower, sourceY, 1);
        fillSquare(level, centre, newVisible + 1, half,
                Blocks.SMOOTH_STONE.defaultBlockState(), UPDATE_TRAVEL);
        set(level, centre.offset(0, newVisible + 1, 0),
                Blocks.REDSTONE_LAMP.defaultBlockState(), UPDATE_TRAVEL);
        setRoofMasts(level, centre, tower, newVisible + 2,
                Blocks.LIGHTNING_ROD.defaultBlockState());

        paintRetractedHatch(level, centre, half, tower.outerWard());
        if (preserveCore)
        {
            set(level, centre, core, UPDATE_TRAVEL);
        }
        if (!tower.outerWard())
        {
            set(level, centre.offset(0, newVisible, 0),
                    Blocks.REDSTONE_BLOCK.defaultBlockState(), UPDATE_TRAVEL);
        }
    }

    /**
     * Copies only the inhabited shell and its centre marker. Towers are hollow,
     * so translating every interior air cell would turn one animation layer
     * into tens of thousands of needless block updates.
     */
    private static void copyTowerWallAndCentre(ServerLevel level,
                                               BlockPos centre, int half,
                                               int sourceY, int targetY)
    {
        for (int span = -half; span <= half; span++)
        {
            set(level, centre.offset(-half, targetY, span),
                    level.getBlockState(centre.offset(-half, sourceY, span)),
                    UPDATE_TRAVEL);
            set(level, centre.offset(half, targetY, span),
                    level.getBlockState(centre.offset(half, sourceY, span)),
                    UPDATE_TRAVEL);
            set(level, centre.offset(span, targetY, -half),
                    level.getBlockState(centre.offset(span, sourceY, -half)),
                    UPDATE_TRAVEL);
            set(level, centre.offset(span, targetY, half),
                    level.getBlockState(centre.offset(span, sourceY, half)),
                    UPDATE_TRAVEL);
        }
        set(level, centre.offset(0, targetY, 0),
                level.getBlockState(centre.offset(0, sourceY, 0)),
                UPDATE_TRAVEL);
    }

    private static void setRoofMasts(ServerLevel level, BlockPos centre,
                                     TowerSpec tower, int y, BlockState state)
    {
        if (tower.outerWard())
        {
            set(level, centre.offset(0, y, 0), state, UPDATE_TRAVEL);
            return;
        }
        for (int x : new int[] {-8, 8})
        {
            for (int z : new int[] {-8, 8})
            {
                set(level, centre.offset(x, y, z), state, UPDATE_TRAVEL);
            }
        }
    }

    /**
     * Builds one more layer below the curved GeoFront ceiling. A temporary
     * solid underside moves with the building, so from the cavern the city
     * reads as real mass descending rather than wall rings appearing in air.
     */
    private static void emergeCeilingLayer(ServerLevel level, BlockPos origin,
                                           TowerSpec tower,
                                           int oldVisible, int newVisible)
    {
        int roofY = ceilingRoofRelativeY(tower, origin);
        BlockPos centre = origin.offset(tower.x(), 0, tower.z());
        if (oldVisible == 0)
        {
            fillSquare(level, centre, roofY, tower.halfSize(),
                    Blocks.SMOOTH_STONE.defaultBlockState(), UPDATE_TRAVEL);
            set(level, centre.offset(0, roofY, 0),
                    Blocks.REDSTONE_LAMP.defaultBlockState(), UPDATE_TRAVEL);
        }
        int wallY = roofY - newVisible;
        if (oldVisible > 0)
        {
            fillSquare(level, centre, wallY, tower.halfSize(),
                    Blocks.AIR.defaultBlockState(), UPDATE_TRAVEL);
        }
        int sourceY = tower.height() - newVisible + 1;
        buildTowerWallLayer(level, centre, tower, sourceY, wallY);
        fillSquare(level, centre, wallY - 1, tower.halfSize(),
                Blocks.POLISHED_DEEPSLATE.defaultBlockState(), UPDATE_TRAVEL);
        set(level, centre.offset(0, wallY - 1, 0),
                Blocks.SEA_LANTERN.defaultBlockState(), UPDATE_TRAVEL);
    }

    /** Exact inverse of {@link #emergeCeilingLayer}. */
    private static void withdrawCeilingLayer(ServerLevel level, BlockPos origin,
                                             TowerSpec tower,
                                             int oldVisible, int newVisible)
    {
        int roofY = ceilingRoofRelativeY(tower, origin);
        BlockPos centre = origin.offset(tower.x(), 0, tower.z());
        int oldWallY = roofY - oldVisible;
        fillSquare(level, centre, oldWallY - 1, tower.halfSize(),
                Blocks.AIR.defaultBlockState(), UPDATE_TRAVEL);
        clearTowerWallLayer(level, centre, oldWallY, tower.halfSize());
        if (newVisible > 0)
        {
            fillSquare(level, centre, oldWallY, tower.halfSize(),
                    Blocks.POLISHED_DEEPSLATE.defaultBlockState(), UPDATE_TRAVEL);
            set(level, centre.offset(0, oldWallY, 0),
                    Blocks.SEA_LANTERN.defaultBlockState(), UPDATE_TRAVEL);
        }
        else
        {
            fillSquare(level, centre, roofY, tower.halfSize(),
                    Blocks.AIR.defaultBlockState(), UPDATE_TRAVEL);
        }
    }

    private static void buildFoundation(ServerLevel level, BlockPos origin)
    {
        BlockState surface = Blocks.SMOOTH_STONE.defaultBlockState();
        BlockState retainingWall = Blocks.DEEPSLATE_BRICKS.defaultBlockState();
        for (int x = -FOUNDATION_HALF_SIZE; x <= FOUNDATION_HALF_SIZE; x++)
        {
            for (int z = -FOUNDATION_HALF_SIZE; z <= FOUNDATION_HALF_SIZE; z++)
            {
                int worldX = origin.getX() + x;
                int worldZ = origin.getZ() + z;
                int nativeSurface = level.getHeight(
                        Heightmap.Types.WORLD_SURFACE_WG, worldX, worldZ) - 1;
                nativeSurface = Math.max(level.getMinBuildHeight(),
                        Math.min(nativeSurface, origin.getY() + 64));
                if (nativeSurface < origin.getY())
                {
                    for (int y = nativeSurface + 1; y < origin.getY(); y++)
                    {
                        BlockState fill = y >= origin.getY() - 3
                                ? Blocks.DIRT.defaultBlockState()
                                : Blocks.STONE.defaultBlockState();
                        set(level, new BlockPos(worldX, y, worldZ), fill);
                    }
                }
                else if (nativeSurface > origin.getY())
                {
                    for (int y = origin.getY() + 1; y <= nativeSurface; y++)
                    {
                        set(level, new BlockPos(worldX, y, worldZ),
                                Blocks.AIR.defaultBlockState());
                    }
                }
                set(level, new BlockPos(worldX, origin.getY(), worldZ), surface);
            }
        }
        for (int depth = 1; depth <= 6; depth++)
        {
            for (int span = -FOUNDATION_HALF_SIZE; span <= FOUNDATION_HALF_SIZE; span++)
            {
                set(level, origin.offset(-FOUNDATION_HALF_SIZE, -depth, span),
                        retainingWall);
                set(level, origin.offset(FOUNDATION_HALF_SIZE, -depth, span),
                        retainingWall);
                set(level, origin.offset(span, -depth, -FOUNDATION_HALF_SIZE),
                        retainingWall);
                set(level, origin.offset(span, -depth, FOUNDATION_HALF_SIZE),
                        retainingWall);
            }
        }
    }

    private static void buildRoadGrid(ServerLevel level, BlockPos origin)
    {
        BlockState asphalt = Blocks.BLACK_CONCRETE.defaultBlockState();
        BlockState roadEdge = Blocks.GRAY_CONCRETE.defaultBlockState();
        BlockState sidewalk = Blocks.LIGHT_GRAY_CONCRETE.defaultBlockState();
        BlockState lane = Blocks.YELLOW_CONCRETE.defaultBlockState();

        for (int x = -DISTRICT_HALF_SIZE; x <= DISTRICT_HALF_SIZE; x++)
        {
            int roadX = distanceToRoadAxis(x);
            for (int z = -DISTRICT_HALF_SIZE; z <= DISTRICT_HALF_SIZE; z++)
            {
                if (insideSortieApron(x, z))
                {
                    continue;
                }
                int roadZ = distanceToRoadAxis(z);
                boolean verticalRoad = roadX <= ROAD_HALF_WIDTH;
                boolean horizontalRoad = roadZ <= ROAD_HALF_WIDTH;
                boolean sidewalkCell = roadX <= SIDEWALK_HALF_WIDTH
                        || roadZ <= SIDEWALK_HALF_WIDTH;
                if (!verticalRoad && !horizontalRoad && !sidewalkCell)
                {
                    continue;
                }

                BlockState state = sidewalk;
                if (verticalRoad || horizontalRoad)
                {
                    state = asphalt;
                    if (roadX == ROAD_HALF_WIDTH || roadZ == ROAD_HALF_WIDTH)
                    {
                        state = roadEdge;
                    }
                    boolean dashed = Math.floorMod(verticalRoad ? z : x, 10) < 5;
                    if (dashed && ((verticalRoad && roadX == 0 && !horizontalRoad)
                            || (horizontalRoad && roadZ == 0 && !verticalRoad)))
                    {
                        state = lane;
                    }
                }
                set(level, origin.offset(x, 0, z), state);
                if (verticalRoad || horizontalRoad)
                {
                    clearHeadroom(level, origin.offset(x, 0, z), 3);
                }
            }
        }
    }

    private static void buildArmouredTower(ServerLevel level, BlockPos centre,
                                           int height, int gridX, int gridZ)
    {
        paintRetractedHatch(level, centre, LOT_HALF_SIZE, false);
        set(level, centre, ModBlocks.RETRACTABLE_BUILDING_CORE.get()
                .defaultBlockState().setValue(RetractableBuildingCoreBlock.ARMED, false));
        for (int y = 1; y <= height; y++)
        {
            for (int i = -LOT_HALF_SIZE; i <= LOT_HALF_SIZE; i++)
            {
                set(level, centre.offset(-LOT_HALF_SIZE, y, i),
                        towerWall(y, i, gridX, gridZ));
                set(level, centre.offset(LOT_HALF_SIZE, y, i),
                        towerWall(y, i, gridX, gridZ));
                set(level, centre.offset(i, y, -LOT_HALF_SIZE),
                        towerWall(y, i, gridX, gridZ));
                set(level, centre.offset(i, y, LOT_HALF_SIZE),
                        towerWall(y, i, gridX, gridZ));
            }
        }
        cutInnerDoor(level, centre, gridX, gridZ);
        TowerSpec room=new TowerSpec(gridX,gridZ,height,LOT_HALF_SIZE,false);
        for(int y=1;y<=height;y++)buildTowerInteriorLayerR44(level,centre,room,y,y);
        fillSquare(level, centre, height + 1, LOT_HALF_SIZE,
                Blocks.SMOOTH_STONE.defaultBlockState());
        set(level, centre.offset(0, height, 0), Blocks.REDSTONE_BLOCK.defaultBlockState());
        set(level, centre.offset(0, height + 1, 0), Blocks.REDSTONE_LAMP.defaultBlockState());
        for (int x : new int[] {-8, 8})
        {
            for (int z : new int[] {-8, 8})
            {
                set(level, centre.offset(x, height + 2, z),
                        Blocks.LIGHTNING_ROD.defaultBlockState());
            }
        }
    }

    private static void buildOuterWardTower(ServerLevel level, BlockPos centre,
                                            int height, int gridX, int gridZ)
    {
        int half = 9;
        BlockState frame = Math.floorMod(gridX * 3 + gridZ, 5) < 2
                ? Blocks.LIGHT_GRAY_CONCRETE.defaultBlockState()
                : Blocks.GRAY_CONCRETE.defaultBlockState();
        BlockState glass = Math.floorMod(gridX + gridZ, 3) == 0
                ? Blocks.LIGHT_BLUE_STAINED_GLASS.defaultBlockState()
                : Blocks.CYAN_STAINED_GLASS.defaultBlockState();
        paintRetractedHatch(level, centre, half, true);
        for (int y = 1; y <= height; y++)
        {
            for (int span = -half; span <= half; span++)
            {
                BlockState state = y <= 4 || y % 10 == 0
                        || Math.abs(span) >= half - 1 ? frame : glass;
                set(level, centre.offset(-half, y, span), state);
                set(level, centre.offset(half, y, span), state);
                set(level, centre.offset(span, y, -half), state);
                set(level, centre.offset(span, y, half), state);
            }
        }
        fillSquare(level, centre, height + 1, half,
                Blocks.SMOOTH_STONE.defaultBlockState());
        set(level, centre.offset(0, height + 1, 0),
                Blocks.REDSTONE_LAMP.defaultBlockState());
        set(level, centre.offset(0, height + 2, 0),
                Blocks.LIGHTNING_ROD.defaultBlockState());
        for (int y = 1; y <= 4; y++)
        {
            set(level, centre.offset(0, y, -half),
                    Blocks.AIR.defaultBlockState());
            set(level, centre.offset(1, y, -half),
                    Blocks.AIR.defaultBlockState());
        }
        TowerSpec room=new TowerSpec(gridX,gridZ,height,half,true);
        for(int y=1;y<=height;y++)buildTowerInteriorLayerR44(level,centre,room,y,y);
    }

    private static BlockState towerWall(int y, int span, int gridX, int gridZ)
    {
        int style = Math.floorMod(gridX / ROAD_SPACING * 31
                + gridZ / ROAD_SPACING * 17, 4);
        BlockState armor = switch (style)
        {
            case 1 -> Blocks.LIGHT_GRAY_CONCRETE.defaultBlockState();
            case 2 -> Blocks.POLISHED_DEEPSLATE.defaultBlockState();
            case 3 -> Blocks.WHITE_CONCRETE.defaultBlockState();
            default -> Blocks.GRAY_CONCRETE.defaultBlockState();
        };
        BlockState dark = style == 3
                ? Blocks.GRAY_CONCRETE.defaultBlockState()
                : Blocks.DEEPSLATE_TILES.defaultBlockState();
        BlockState glass = switch (style)
        {
            case 1 -> Blocks.BLUE_STAINED_GLASS.defaultBlockState();
            case 2 -> Blocks.BLACK_STAINED_GLASS.defaultBlockState();
            case 3 -> Blocks.LIGHT_BLUE_STAINED_GLASS.defaultBlockState();
            default -> Blocks.CYAN_STAINED_GLASS.defaultBlockState();
        };
        if (y <= 5)
        {
            return dark;
        }
        if (y == 6 || (style == 2 ? y % 16 == 0 : y % 12 == 0))
        {
            return style == 1
                    ? Blocks.YELLOW_CONCRETE.defaultBlockState()
                    : Blocks.ORANGE_CONCRETE.defaultBlockState();
        }
        if (Math.abs(span) >= LOT_HALF_SIZE - 1)
        {
            return armor;
        }
        return switch (style)
        {
            // Long horizontal office bands.
            case 0 -> y % 4 == 1 || y % 4 == 2 ? glass : armor;
            // Narrow vertical window bays with bright structural mullions.
            case 1 -> Math.floorMod(span, 5) <= 2
                    && y % 5 != 0 ? glass : armor;
            // Heavy NERV bunker tower with restrained slit windows.
            case 2 -> y % 6 == 2
                    && Math.floorMod(span, 4) <= 1 ? glass : armor;
            // Pale residential facade: paired windows and broad floor plates.
            default -> y % 7 >= 2 && y % 7 <= 4
                    && Math.floorMod(span + 1, 6) <= 2 ? glass : armor;
        };
    }

    private static void cutInnerDoor(ServerLevel level, BlockPos centre, int gridX, int gridZ)
    {
        boolean doorOnX = Math.abs(gridX) >= Math.abs(gridZ);
        int wall = doorOnX
                ? (gridX > 0 ? -LOT_HALF_SIZE : LOT_HALF_SIZE)
                : (gridZ > 0 ? -LOT_HALF_SIZE : LOT_HALF_SIZE);
        for (int y = 1; y <= 5; y++)
        {
            for (int side = -2; side <= 2; side++)
            {
                BlockPos door = doorOnX ? centre.offset(wall, y, side)
                        : centre.offset(side, y, wall);
                set(level, door, Blocks.AIR.defaultBlockState());
            }
        }
    }

    private static void clearTowerWallLayer(ServerLevel level, BlockPos centre,
                                            int y, int halfSize)
    {
        BlockState air = Blocks.AIR.defaultBlockState();
        for (int i = -halfSize; i <= halfSize; i++)
        {
            set(level, centre.offset(-halfSize, y, i), air, UPDATE_TRAVEL);
            set(level, centre.offset(halfSize, y, i), air, UPDATE_TRAVEL);
            set(level, centre.offset(i, y, -halfSize), air, UPDATE_TRAVEL);
            set(level, centre.offset(i, y, halfSize), air, UPDATE_TRAVEL);
        }
    }

    private static void buildTowerWallLayer(ServerLevel level, BlockPos centre,
                                            TowerSpec tower,
                                            int sourceY, int targetY)
    {
        int half = tower.halfSize();
        for (int i = -half; i <= half; i++)
        {
            BlockState state = tower.tv() ? TvTokyo3Architecture.wall(sourceY, i, tower) : tower.outerWard()
                    ? outerWardWall(sourceY, i, tower)
                    : towerWall(sourceY, i, tower.x(), tower.z());
            set(level, centre.offset(-half, targetY, i), state, UPDATE_TRAVEL);
            set(level, centre.offset(half, targetY, i), state, UPDATE_TRAVEL);
            set(level, centre.offset(i, targetY, -half), state, UPDATE_TRAVEL);
            set(level, centre.offset(i, targetY, half), state, UPDATE_TRAVEL);
        }
        if (tower.tv() && sourceY <= 3)
        {
            for (int span = 0; span <= 1; span++)
            {
                BlockState door=TvTokyo3Architecture.entrance(span,sourceY,half,tower);
                set(level,centre.offset(span,targetY,half),door==null?Blocks.AIR.defaultBlockState():door,UPDATE_TRAVEL);
            }
        }
        else if (!tower.tv() && !tower.outerWard() && targetY == sourceY)
        {
            cutInnerDoor(level, centre, tower.x(), tower.z());
        }
    }

    public static void buildTowerInteriorLayerR44(ServerLevel level,BlockPos centre,
                                                  TowerSpec tower,int sourceY,int targetY)
    {
        for(int x=-tower.halfSize()+1;x<tower.halfSize();x++)
            for(int z=-tower.halfSize()+1;z<tower.halfSize();z++)
            {
                BlockState state=TvTokyo3Architecture.interior(x,sourceY,z,tower);
                if(sourceY==0&&x==0&&z==0&&level.getBlockState(centre).is(ModBlocks.RETRACTABLE_BUILDING_CORE.get()))continue;
                if(state!=null)set(level,centre.offset(x,targetY,z),state,UPDATE_TRAVEL);
            }
    }

    public static BlockState retractedHatchStateR44(int x,int z,TowerSpec tower)
    {
        return retractedHatchState(x,z,tower.halfSize(),tower.outerWard());
    }

    private static BlockState outerWardWall(int y, int span, TowerSpec tower)
    {
        BlockState frame = Math.floorMod(tower.x() * 3 + tower.z(), 5) < 2
                ? Blocks.LIGHT_GRAY_CONCRETE.defaultBlockState()
                : Blocks.GRAY_CONCRETE.defaultBlockState();
        BlockState glass = Math.floorMod(tower.x() + tower.z(), 3) == 0
                ? Blocks.LIGHT_BLUE_STAINED_GLASS.defaultBlockState()
                : Blocks.CYAN_STAINED_GLASS.defaultBlockState();
        return y <= 4 || y % 10 == 0
                || Math.abs(span) >= tower.halfSize() - 1 ? frame : glass;
    }

    /**
     * Flush mechanical cover left behind when a Tokyo-3 tower descends. It is
     * intentionally readable from EVA height: a dark pressure rim, striped
     * interlock band and segmented steel leaves replace the old featureless
     * smooth-stone test grid.
     */
    private static void paintRetractedHatch(ServerLevel level, BlockPos centre,
                                            int halfSize,
                                            boolean outerWard)
    {
        for (int x = -halfSize; x <= halfSize; x++)
        {
            for (int z = -halfSize; z <= halfSize; z++)
            {
                if (!outerWard && x == 0 && z == 0
                        && level.getBlockState(centre)
                                .is(ModBlocks.RETRACTABLE_BUILDING_CORE.get()))
                {
                    continue;
                }
                set(level, centre.offset(x, 0, z),
                        retractedHatchState(x, z, halfSize, outerWard),
                        UPDATE_TRAVEL);
            }
        }
    }

    private static BlockState retractedHatchState(int x, int z,
                                                  int halfSize,
                                                  boolean outerWard)
    {
        int edge = Math.max(Math.abs(x), Math.abs(z));
        BlockState state;
        if (edge >= halfSize - 1)
        {
            state = Blocks.POLISHED_DEEPSLATE.defaultBlockState();
        }
        else if (edge == halfSize - 2)
        {
            state = Math.floorMod(x + z, 4) < 2
                    ? Blocks.ORANGE_CONCRETE.defaultBlockState()
                    : Blocks.BLACK_CONCRETE.defaultBlockState();
        }
        else if (Math.floorMod(x, 6) == 0
                || Math.floorMod(z, 6) == 0)
        {
            state = Blocks.IRON_BLOCK.defaultBlockState();
        }
        else
        {
            state = outerWard
                    ? Blocks.LIGHT_GRAY_CONCRETE.defaultBlockState()
                    : Blocks.GRAY_CONCRETE.defaultBlockState();
        }
        if (Math.abs(x) == halfSize - 3
                && Math.abs(z) == halfSize - 3)
        {
            state = Blocks.SEA_LANTERN.defaultBlockState();
        }
        return state;
    }

    /**
     * Low permanent launch-control architecture. Civilian high-rises travel
     * into the GeoFront, but these armoured observer cells remain around the
     * three shaft heads so battle configuration still reads as a real city
     * defence complex rather than an empty creative-mode platform.
     */
    private static void buildLaunchControlBlock(ServerLevel level,
                                                BlockPos centre,
                                                int gridX, int gridZ)
    {
        final int halfX = 7;
        final int halfZ = 7;
        final int height = 10;
        for (int x = -halfX; x <= halfX; x++)
        {
            for (int z = -halfZ; z <= halfZ; z++)
            {
                set(level, centre.offset(x, 0, z),
                        Blocks.POLISHED_DEEPSLATE.defaultBlockState());
                for (int y = 1; y <= height; y++)
                {
                    boolean shell = Math.abs(x) == halfX
                            || Math.abs(z) == halfZ;
                    if (!shell)
                    {
                        clear(level, centre.offset(x, y, z));
                        continue;
                    }
                    BlockState wall;
                    if (y == 3)
                    {
                        wall = Blocks.ORANGE_CONCRETE.defaultBlockState();
                    }
                    else if (y >= 5 && y <= 7
                            && Math.abs(x) < halfX - 1)
                    {
                        wall = Blocks.GRAY_STAINED_GLASS.defaultBlockState();
                    }
                    else if (Math.abs(x) == halfX
                            && Math.abs(z) == halfZ)
                    {
                        wall = Blocks.POLISHED_DEEPSLATE.defaultBlockState();
                    }
                    else
                    {
                        wall = Blocks.GRAY_CONCRETE.defaultBlockState();
                    }
                    set(level, centre.offset(x, y, z), wall);
                }
                BlockState roof = Math.floorMod(x + z, 6) == 0
                        ? Blocks.SEA_LANTERN.defaultBlockState()
                        : Blocks.SMOOTH_STONE.defaultBlockState();
                set(level, centre.offset(x, height + 1, z), roof);
            }
        }

        int inwardWall = gridZ < 0 ? halfZ : -halfZ;
        for (int x = -1; x <= 1; x++)
        {
            for (int y = 1; y <= 3; y++)
            {
                clear(level, centre.offset(x, y, inwardWall));
            }
        }
        set(level, centre.above(height + 1),
                Blocks.REDSTONE_LAMP.defaultBlockState());
        for (int y = height + 2; y <= height + 15; y++)
        {
            set(level, centre.above(y), y % 4 == 0
                    ? Blocks.REDSTONE_LAMP.defaultBlockState()
                    : Blocks.IRON_BARS.defaultBlockState());
        }
        set(level, centre.above(height + 16),
                Blocks.LIGHTNING_ROD.defaultBlockState());

        // Roof identification bars make the four cells legible in an
        // overhead command view and give each shaft a NERV-coloured quadrant.
        BlockState quadrant = gridX < 0
                ? Blocks.ORANGE_CONCRETE.defaultBlockState()
                : Blocks.RED_CONCRETE.defaultBlockState();
        for (int offset = -5; offset <= 5; offset++)
        {
            set(level, centre.offset(offset, height + 1, 0), quadrant);
        }
        set(level, centre.above(height + 1),
                Blocks.REDSTONE_LAMP.defaultBlockState());
    }

    private static void buildSubstation(ServerLevel level, BlockPos centre)
    {
        fillSquare(level, centre, 0, LOT_HALF_SIZE, Blocks.SMOOTH_STONE.defaultBlockState());
        for (int i = -LOT_HALF_SIZE; i <= LOT_HALF_SIZE; i++)
        {
            set(level, centre.offset(-LOT_HALF_SIZE, 1, i), Blocks.IRON_BARS.defaultBlockState());
            set(level, centre.offset(LOT_HALF_SIZE, 1, i), Blocks.IRON_BARS.defaultBlockState());
            set(level, centre.offset(i, 1, -LOT_HALF_SIZE), Blocks.IRON_BARS.defaultBlockState());
            set(level, centre.offset(i, 1, LOT_HALF_SIZE), Blocks.IRON_BARS.defaultBlockState());
        }
        for (int x : new int[] {-7, 0, 7})
        {
            for (int z : new int[] {-6, 6})
            {
                for (int y = 1; y <= 5; y++)
                {
                    set(level, centre.offset(x, y, z),
                            y == 3 ? Blocks.ORANGE_CONCRETE.defaultBlockState()
                                    : Blocks.CUT_COPPER.defaultBlockState());
                }
                set(level, centre.offset(x, 6, z), Blocks.LIGHTNING_ROD.defaultBlockState());
            }
        }
        for (int x = -9; x <= 9; x += 3)
        {
            set(level, centre.offset(x, 1, 0), Blocks.REDSTONE_LAMP.defaultBlockState());
        }
        // Place the audit/core block after the centre lamp strip so the strip
        // cannot silently overwrite both substation signatures.
        set(level, centre.above(), Blocks.WAXED_COPPER_BLOCK.defaultBlockState());
    }

    /** Migrates the two old weatherable audit cores without rebuilding Tokyo-3. */
    public static void repairSubstationCores(ServerLevel level, BlockPos origin)
    {
        if(CityLegacyOwnershipR48.inhibits(level,origin,"ThirdTokyoSurfaceBuilder.repairSubstationCores"))return;
        for (BlockPos core : new BlockPos[] {
                origin.offset(0, 1, -80), origin.offset(80, 1, 0)})
        {
            if (!level.getBlockState(core).is(Blocks.WAXED_COPPER_BLOCK))
            {
                set(level, core, Blocks.WAXED_COPPER_BLOCK.defaultBlockState());
            }
        }
    }

    private static boolean isSubstationCore(BlockState state)
    {
        return state.is(Blocks.COPPER_BLOCK)
                || state.is(Blocks.EXPOSED_COPPER)
                || state.is(Blocks.WEATHERED_COPPER)
                || state.is(Blocks.OXIDIZED_COPPER)
                || state.is(Blocks.WAXED_COPPER_BLOCK)
                || state.is(Blocks.WAXED_EXPOSED_COPPER)
                || state.is(Blocks.WAXED_WEATHERED_COPPER)
                || state.is(Blocks.WAXED_OXIDIZED_COPPER);
    }

    private static void buildBattlePlaza(ServerLevel level, BlockPos centre)
    {
        fillSquare(level, centre, 0, LOT_HALF_SIZE, Blocks.SMOOTH_STONE.defaultBlockState());
        for (int ring = 4; ring <= 12; ring += 4)
        {
            for (int i = -ring; i <= ring; i++)
            {
                BlockState warning = Math.floorMod(i + ring, 4) < 2
                        ? Blocks.YELLOW_CONCRETE.defaultBlockState()
                        : Blocks.BLACK_CONCRETE.defaultBlockState();
                set(level, centre.offset(-ring, 0, i), warning);
                set(level, centre.offset(ring, 0, i), warning);
                set(level, centre.offset(i, 0, -ring), warning);
                set(level, centre.offset(i, 0, ring), warning);
            }
        }
    }


    /** Complete original six-pylon identity mask; independent of present material/state. */
    public static boolean fixedPowerPylonCell(BlockPos origin, BlockPos position)
    {
        int y = position.getY() - origin.getY();
        if (y < 1 || y > 28) return false;
        for (int[] pylon : PYLONS)
        {
            if (position.getZ() != origin.getZ() + pylon[1]) continue;
            int x = position.getX() - origin.getX() - pylon[0];
            if ((y == 22 || y == 27) && Math.abs(x) <= 5) return true;
            int spread = Math.max(0, 4 - y / 7);
            if (Math.abs(x) == spread || y % 6 == 0 && Math.abs(x) <= spread) return true;
        }
        return false;
    }

    private static void buildPowerPylon(ServerLevel level, BlockPos centre)
    {
        for (int y = 1; y <= 28; y++)
        {
            int spread = Math.max(0, 4 - y / 7);
            set(level, centre.offset(-spread, y, 0), Blocks.IRON_BLOCK.defaultBlockState());
            set(level, centre.offset(spread, y, 0), Blocks.IRON_BLOCK.defaultBlockState());
            if (y % 6 == 0)
            {
                for (int x = -spread; x <= spread; x++)
                {
                    set(level, centre.offset(x, y, 0), Blocks.IRON_BARS.defaultBlockState());
                }
            }
        }
        for (int x = -5; x <= 5; x++)
        {
            set(level, centre.offset(x, 22, 0), Blocks.IRON_BARS.defaultBlockState());
            set(level, centre.offset(x, 27, 0), Blocks.IRON_BARS.defaultBlockState());
        }
        set(level, centre.offset(0, 28, 0), Blocks.IRON_BLOCK.defaultBlockState());
    }

    private static void connectPowerGrid(ServerLevel level, BlockPos origin, int x)
    {
        for (int startZ : new int[] {-80, 0})
        {
            for (int z = startZ + 1; z < startZ + 80; z++)
            {
                for (int wireX : new int[] {-4, 0, 4})
                {
                    set(level, origin.offset(x + wireX, 27, z),
                            Blocks.IRON_BARS.defaultBlockState());
                }
            }
        }
    }

    private static void buildSortieGate(ServerLevel level, BlockPos centre)
    {
        for (int y = 0; y <= 18; y++)
        {
            set(level, centre.offset(-10, y, 0), Blocks.IRON_BLOCK.defaultBlockState());
            set(level, centre.offset(10, y, 0), Blocks.IRON_BLOCK.defaultBlockState());
        }
        for (int x = -10; x <= 10; x++)
        {
            set(level, centre.offset(x, 18, 0), x % 4 == 0
                    ? Blocks.REDSTONE_LAMP.defaultBlockState()
                    : Blocks.BLACK_CONCRETE.defaultBlockState());
        }
    }

    private static void buildObservationDeck(ServerLevel level, BlockPos centre)
    {
        for (int y = 1; y <= OBSERVATION_Y; y++)
        {
            for (int x : new int[] {-4, 4})
            {
                for (int z : new int[] {-4, 4})
                {
                    set(level, centre.offset(x, y, z), Blocks.IRON_BLOCK.defaultBlockState());
                }
            }
        }
        fillSquare(level, centre, OBSERVATION_Y, 6, Blocks.SMOOTH_STONE.defaultBlockState());
        for (int i = -6; i <= 6; i++)
        {
            set(level, centre.offset(-6, OBSERVATION_Y + 1, i), Blocks.IRON_BARS.defaultBlockState());
            set(level, centre.offset(6, OBSERVATION_Y + 1, i), Blocks.IRON_BARS.defaultBlockState());
            set(level, centre.offset(i, OBSERVATION_Y + 1, -6), Blocks.IRON_BARS.defaultBlockState());
            set(level, centre.offset(i, OBSERVATION_Y + 1, 6), Blocks.IRON_BARS.defaultBlockState());
        }
        set(level, centre.offset(0, OBSERVATION_Y, 0), Blocks.LODESTONE.defaultBlockState());
    }

    private static int towerHeight(int x, int z)
    {
        int gridX = x / 40;
        int gridZ = z / 40;
        return 22 + Math.floorMod(gridX * 31 + gridZ * 17, 6) * 4;
    }

    private static int outerWardHeight(int x, int z)
    {
        return 18 + Math.floorMod(x * 13 + z * 29, 5) * 5;
    }

    private static boolean reservedPrivateSkyscraperLot(int x, int z)
    {
        return x == -120 && z == -80
                || x == 120 && z == -80
                || x == 120 && z == 80
                // The local high-rise rotated into this neighbouring lot.
                // Keeping the generated 22-block tower here made both shells
                // intersect around world (120,100,294).
                || x == 80 && z == 80
                // Dedicated footprint for the S20 public surface lift. The
                // former generated tower intersected the west pavilion wall.
                || x == 80 && z == 40;
    }

    /**
     * Removes one deterministic armoured tower without rebuilding the whole
     * district. Used only by the bounded S20 migration which resolves old
     * overlapping lots in an already-generated local world.
     */
    public static void removeArmouredTower(ServerLevel level, BlockPos origin,
                                            int gridX, int gridZ,
                                            boolean restoreGrass)
    {
        if(CityLegacyOwnershipR48.inhibits(level,origin,"ThirdTokyoSurfaceBuilder.removeArmouredTower"))return;
        BlockPos centre = origin.offset(gridX, 0, gridZ);
        int height = towerHeight(gridX, gridZ) + 3;
        clearPrism(level, centre, LOT_HALF_SIZE, height, restoreGrass);
    }

    /** Removes one old outer-ward tower from a superseded district origin. */
    public static void removeOuterWardTower(ServerLevel level, BlockPos origin,
                                             int gridX, int gridZ,
                                             boolean restoreGrass)
    {
        if(CityLegacyOwnershipR48.inhibits(level,origin,"ThirdTokyoSurfaceBuilder.removeOuterWardTower"))return;
        BlockPos centre = origin.offset(gridX, 0, gridZ);
        int height = outerWardHeight(gridX, gridZ) + 2;
        clearPrism(level, centre, 9, height, restoreGrass);
    }

    /** Removes one old pylon, including its widest cross-arms. */
    public static void removePowerPylon(ServerLevel level, BlockPos origin,
                                        int gridX, int gridZ,
                                        boolean restoreGrass)
    {
        if(CityLegacyOwnershipR48.inhibits(level,origin,"ThirdTokyoSurfaceBuilder.removePowerPylon"))return;
        BlockPos centre = origin.offset(gridX, 0, gridZ);
        clearPrism(level, centre, 5, 29, restoreGrass);
    }

    private static void clearPrism(ServerLevel level, BlockPos centre,
                                   int halfSize, int height,
                                   boolean restoreGrass)
    {
        for (int x = -halfSize; x <= halfSize; x++)
        {
            for (int z = -halfSize; z <= halfSize; z++)
            {
                if (restoreGrass)
                {
                    set(level, centre.offset(x, 0, z),
                            Blocks.GRASS_BLOCK.defaultBlockState());
                }
                for (int y = 1; y <= height; y++)
                {
                    set(level, centre.offset(x, y, z),
                            Blocks.AIR.defaultBlockState());
                }
            }
        }
    }

    private static boolean reservedOuterTransitLot(int x, int z)
    {
        // The east perimeter is the dedicated elevated-rail corridor. Building
        // towers there first only lets the railway cut their roofs and doors.
        return x == 200;
    }

    private static List<TowerSpec> createArmouredTowers()
    {
        List<TowerSpec> towers = new ArrayList<>();
        for (int x : LOT_CENTRES)
        {
            for (int z : LOT_CENTRES)
            {
                if (Math.abs(x) <= 40 && Math.abs(z) <= 40
                        || (x == 0 && z == -80)
                        || (x == 80 && z == 0)
                        || (x == 0 && z == 80)
                        || reservedPrivateSkyscraperLot(x, z))
                {
                    continue;
                }
                towers.add(new TowerSpec(x, z, towerHeight(x, z),
                        LOT_HALF_SIZE, false));
            }
        }
        return List.copyOf(towers);
    }

    private static List<TowerSpec> createOuterWardTowers()
    {
        List<TowerSpec> towers = new ArrayList<>();
        for (int x : OUTER_LOT_CENTRES)
        {
            for (int z : OUTER_LOT_CENTRES)
            {
                if (Math.max(Math.abs(x), Math.abs(z)) != 200
                        || reservedOuterTransitLot(x, z))
                {
                    continue;
                }
                towers.add(new TowerSpec(x, z, outerWardHeight(x, z),
                        9, true));
            }
        }
        return List.copyOf(towers);
    }

    private static List<TowerSpec> createMovableBuildings()
    {
        List<TowerSpec> towers = new ArrayList<>(
                ARMOURED_TOWERS.size() + OUTER_WARD_TOWERS.size());
        towers.addAll(ARMOURED_TOWERS);
        towers.addAll(OUTER_WARD_TOWERS);
        return List.copyOf(towers);
    }

    private static int ceilingVisibleHeight(TowerSpec tower, int depth)
    {
        return Math.max(0, Math.min(tower.height(),
                depth - ceilingTravelDepth(tower)));
    }

    private static boolean compatBlockAvailable(String namespace, String path)
    {
        return BuiltInRegistries.BLOCK.getOptional(
                        new ResourceLocation(namespace, path))
                .filter(block -> block != Blocks.AIR)
                .isPresent();
    }

    private static BlockState compatBlock(String namespace, String path,
                                          BlockState fallback)
    {
        return BuiltInRegistries.BLOCK.getOptional(
                        new ResourceLocation(namespace, path))
                .filter(block -> block != Blocks.AIR)
                .map(Block::defaultBlockState)
                .orElse(fallback);
    }

    private static BlockState facingIfPresent(BlockState state,
                                               Direction facing)
    {
        return state.hasProperty(BlockStateProperties.FACING)
                ? state.setValue(BlockStateProperties.FACING, facing)
                : state;
    }

    private static BlockState axisIfPresent(BlockState state,
                                            Direction.Axis axis)
    {
        return state.hasProperty(BlockStateProperties.AXIS)
                ? state.setValue(BlockStateProperties.AXIS, axis)
                : state;
    }

    private static int ceilingVisibleHeight(TowerSpec tower, int depth,
                                            BlockPos origin)
    {
        return Math.max(0, Math.min(tower.height(),
                depth - ceilingTravelDepth(tower, origin)));
    }

    private static int ceilingTravelDepth(TowerSpec tower)
    {
        return Math.max(tower.height(), -ceilingRoofRelativeY(tower));
    }

    private static int ceilingTravelDepth(TowerSpec tower, BlockPos origin)
    {
        return Math.max(tower.height(), -ceilingRoofRelativeY(tower, origin));
    }

    /**
     * Relative Y of the roof cap just inside the real spherical shell. Outer
     * wards therefore hang lower than the central skyline instead of punching
     * through the curved GeoFront wall.
     */
    public static int ceilingRoofRelativeY(TowerSpec tower)
    {
        // The complete rectangular tower, not merely its centre column, must
        // stay inside the curved Skyweave shell. Using the centre radius put
        // the outward edge of eleven east-side towers directly on the
        // discretised sphere, so rebuilding GeoFront replaced their expected
        // air/ceiling state and made the integrated map fail 84/95. The
        // farthest footprint corner is the limiting radius for a level cap.
        return ceilingRoofRelativeYForBounds(
                tower.x() - tower.halfSize(),
                tower.x() + tower.halfSize(),
                tower.z() - tower.halfSize(),
                tower.z() + tower.halfSize());
    }

    public static int ceilingRoofRelativeY(TowerSpec tower, BlockPos origin)
    {
        if (tower.tv()) return TvWorldPreviewTerrain.ROOF_Y - CEILING_SHELL_CLEARANCE - origin.getY();
        return ceilingRoofRelativeYForBounds(
                tower.x() - tower.halfSize(),
                tower.x() + tower.halfSize(),
                tower.z() - tower.halfSize(),
                tower.z() + tower.halfSize(), origin);
    }

    /** Curved-ceiling clearance for an arbitrary, possibly rotated footprint. */
    public static int ceilingRoofRelativeYForBounds(int minimumX, int maximumX,
                                                     int minimumZ, int maximumZ)
    {
        int farthestX = Math.max(Math.abs(minimumX), Math.abs(maximumX));
        int farthestZ = Math.max(Math.abs(minimumZ), Math.abs(maximumZ));
        int horizontalSqr = farthestX * farthestX + farthestZ * farthestZ;
        int radiusSqr = GeoFrontBuilder.CAVERN_RADIUS * GeoFrontBuilder.CAVERN_RADIUS;
        int shellRise = (int) Math.floor(Math.sqrt(
                Math.max(0, radiusSqr - horizontalSqr)));
        int worldY = IntegratedNervMapBuilder.GEOFRONT_ORIGIN.getY()
                + GeoFrontBuilder.CAVERN_CENTRE_Y + shellRise
                - CEILING_SHELL_CLEARANCE;
        return worldY - IntegratedNervMapBuilder.TOKYO3_ORIGIN.getY();
    }

    /** Roof cap for an arbitrary footprint in the supplied Tokyo-3 frame. */
    public static int ceilingRoofRelativeYForBounds(int minimumX, int maximumX,
                                                     int minimumZ, int maximumZ,
                                                     BlockPos origin)
    {
        if (!origin.equals(IntegratedNervMapBuilder.S22_TOKYO3_ORIGIN))
        {
            return ceilingRoofRelativeYForBounds(
                    minimumX, maximumX, minimumZ, maximumZ);
        }
        BlockPos dome = FacilitySchemaV2.CANDIDATE_CENTRES.get(
                FacilitySchemaV2.ACTIVE_CANDIDATE_INDEX);
        int roof = Integer.MAX_VALUE;
        int[] xs = {minimumX, maximumX};
        int[] zs = {minimumZ, maximumZ};
        for (int x : xs)
        {
            for (int z : zs)
            {
                int relativeX = origin.getX() + x - dome.getX();
                int relativeZ = origin.getZ() + z - dome.getZ();
                roof = Math.min(roof,
                        GeoFrontBoundedChunkGenerator.canonicalRoofHeight(
                                relativeX, relativeZ, origin.getY()));
            }
        }
        return roof - CEILING_SHELL_CLEARANCE - origin.getY();
    }

    private static int distanceToRoadAxis(int value)
    {
        int phase = Math.floorMod(value + ROAD_OFFSET, ROAD_SPACING);
        return Math.min(phase, ROAD_SPACING - phase);
    }

    private static boolean insideSortieApron(int x, int z)
    {
        return Math.abs(x) <= 48 && z >= -36 && z <= 44;
    }

    private static boolean isRoad(BlockState state)
    {
        return state.is(Blocks.BLACK_CONCRETE) || state.is(Blocks.GRAY_CONCRETE)
                || state.is(Blocks.YELLOW_CONCRETE)
                || state.is(Blocks.LIGHT_GRAY_CONCRETE);
    }

    private static boolean towerShellClear(ServerLevel level, BlockPos centre)
    {
        return towerShellClear(level, centre, LOT_HALF_SIZE);
    }

    private static boolean towerShellClear(ServerLevel level, BlockPos centre,
                                           int halfSize)
    {
        return level.getBlockState(centre.offset(-halfSize, 1, 0)).isAir()
                && level.getBlockState(centre.offset(halfSize, 1, 0)).isAir()
                && level.getBlockState(centre.offset(0, 1, -halfSize)).isAir()
                && level.getBlockState(centre.offset(0, 1, halfSize)).isAir();
    }

    private static boolean ceilingStateMatches(ServerLevel level, BlockPos origin,
                                               TowerSpec tower, int depth)
    {
        int visible = ceilingVisibleHeight(tower, depth, origin);
        int roofY = ceilingRoofRelativeY(tower, origin);
        BlockPos centre = origin.offset(tower.x(), 0, tower.z());
        if (visible == 0)
        {
            return level.getBlockState(centre.offset(0, roofY, 0)).isAir()
                    && level.getBlockState(
                            centre.offset(tower.halfSize(), roofY - 1, 0)).isAir();
        }
        int wallY = roofY - visible;
        return level.getBlockState(centre.offset(0, roofY, 0))
                        .is(Blocks.REDSTONE_LAMP)
                && level.getBlockState(centre.offset(0, wallY - 1, 0))
                        .is(Blocks.SEA_LANTERN)
                && !level.getBlockState(
                        centre.offset(tower.halfSize(), wallY, 0)).isAir();
    }

    private static void clearHeadroom(ServerLevel level, BlockPos floor, int height)
    {
        for (int y = 1; y <= height; y++)
        {
            BlockPos position = floor.above(y);
            if (!level.getBlockState(position).isAir())
            {
                set(level, position, Blocks.AIR.defaultBlockState());
            }
        }
    }

    private static void clear(ServerLevel level, BlockPos position)
    {
        if (!level.getBlockState(position).isAir())
        {
            set(level, position, Blocks.AIR.defaultBlockState());
        }
    }

    private static void fillSquare(ServerLevel level, BlockPos centre, int y,
                                   int halfSize, BlockState state)
    {
        fillSquare(level, centre, y, halfSize, state, UPDATE_CLIENTS);
    }

    private static void fillSquare(ServerLevel level, BlockPos centre, int y,
                                   int halfSize, BlockState state, int flags)
    {
        for (int x = -halfSize; x <= halfSize; x++)
        {
            for (int z = -halfSize; z <= halfSize; z++)
            {
                set(level, centre.offset(x, y, z), state, flags);
            }
        }
    }

    private static void set(ServerLevel level, BlockPos position, BlockState state)
    {
        set(level, position, state, UPDATE_CLIENTS);
    }

    private static void set(ServerLevel level, BlockPos position, BlockState state,
                            int flags)
    {
        if (!level.getBlockState(position).equals(state))
        {
            level.setBlock(position, state, flags);
            PerformanceCounters.recordWorldBlockWrites(1);
        }
    }

    public record TowerSpec(int x, int z, int height,
                            int halfSize, boolean outerWard, boolean tv)
    {
        public TowerSpec(int x, int z, int height, int halfSize, boolean outerWard)
        {
            this(x, z, height, halfSize, outerWard, false);
        }
    }

    public record DistrictAudit(boolean valid, int roads, int towers,
                                int outerWards, int ceilingBuildings,
                                int substations, int pylons,
                                boolean sortieLane, boolean observationDeck,
                                boolean foundation)
    {
        public static DistrictAudit imported()
        {
            return new DistrictAudit(true, 8, EXPECTED_TOWERS,
                    EXPECTED_OUTER_WARDS, MOVABLE_BUILDINGS.size(), 2, 6,
                    true, true, true);
        }

        public String summary()
        {
            return String.format(Locale.ROOT,
                    "valid=%s roads=%d/8 towers=%d/%d outerWards=%d/%d "
                            + "ceilingBuildings=%d/%d substations=%d/2 "
                            + "pylons=%d/6 sortieLane=%s "
                            + "observationDeck=%s foundation=%s",
                    this.valid, this.roads, this.towers, EXPECTED_TOWERS,
                    this.outerWards, EXPECTED_OUTER_WARDS,
                    this.ceilingBuildings, MOVABLE_BUILDINGS.size(),
                    this.substations, this.pylons,
                    this.sortieLane,
                    this.observationDeck, this.foundation);
        }
    }
}
