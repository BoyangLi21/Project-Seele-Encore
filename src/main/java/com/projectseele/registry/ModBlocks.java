package com.projectseele.registry;

import com.projectseele.ProjectSeele;
import com.projectseele.world.CommandSeatBackBlock;
import com.projectseele.world.OneWayGlassBlock;
import com.projectseele.world.RetractableBuildingCoreBlock;
import com.projectseele.world.UmbilicalPylonBlock;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.GlassBlock;
import net.minecraft.world.level.block.LiquidBlock;
import net.minecraft.world.level.block.state.BlockBehaviour;
import net.minecraftforge.registries.DeferredRegister;
import net.minecraftforge.registries.ForgeRegistries;
import net.minecraftforge.registries.RegistryObject;

/** Blocks used by Project SEELE structures and map systems. */
public final class ModBlocks
{
    public static final DeferredRegister<Block> BLOCKS = DeferredRegister.create(
            ForgeRegistries.BLOCKS, ProjectSeele.MODID);

    public static final RegistryObject<Block> NERV_WORKSTATION = BLOCKS.register(
            "nerv_workstation", () -> new com.projectseele.world.NervWorkstationBlock(
                    BlockBehaviour.Properties.copy(Blocks.IRON_BLOCK).strength(1.5F).noOcclusion()));

    public static final RegistryObject<Block> NERV_WALL_PANEL=finish("nerv_wall_panel",Blocks.IRON_BLOCK,0);
    public static final RegistryObject<Block> NERV_STRUCTURAL_PANEL=BLOCKS.register("nerv_structural_panel",
            ()->new Block(BlockBehaviour.Properties.copy(Blocks.REINFORCED_DEEPSLATE)));
    public static final RegistryObject<Block> NERV_MACHINE_PANEL=structuralFinish("nerv_machine_panel");
    public static final RegistryObject<Block> NERV_SHAFT_PANEL=structuralFinish("nerv_shaft_panel");
    public static final RegistryObject<Block> NERV_MACHINE_EDGE=structuralFinish("nerv_machine_edge");
    public static final RegistryObject<Block> NERV_EDGE_RAIL=BLOCKS.register("nerv_edge_rail",()->new com.projectseele.world.FacilityEdgeRailR41(BlockBehaviour.Properties.copy(Blocks.IRON_BARS).strength(3F).noOcclusion()));
    public static final RegistryObject<Block> NERV_MACHINE_HAZARD=structuralFinish("nerv_machine_hazard");

    private static RegistryObject<Block> structuralFinish(String name)
    {
        return BLOCKS.register(name,()->new Block(BlockBehaviour.Properties.copy(Blocks.REINFORCED_DEEPSLATE)));
    }
    public static final RegistryObject<Block> NERV_WALL_DATUM=finish("nerv_wall_datum",Blocks.IRON_BLOCK,0);
    public static final RegistryObject<Block> NERV_FLOOR_PANEL=finish("nerv_floor_panel",Blocks.SMOOTH_STONE,0);
    public static final RegistryObject<Block> NERV_HAZARD_PAVING=finish("nerv_hazard_paving",Blocks.SMOOTH_STONE,0);
    public static final RegistryObject<Block> NERV_STRIP_LIGHT=finish("nerv_strip_light",Blocks.IRON_BLOCK,14);
    public static final RegistryObject<Block> NERV_CEILING_LIGHT=BLOCKS.register("nerv_ceiling_light",()->new com.projectseele.world.FacilityCeilingLightR30(BlockBehaviour.Properties.copy(Blocks.IRON_BLOCK).strength(1.5F).noOcclusion().lightLevel(s->s.getValue(net.minecraft.world.level.block.state.properties.BlockStateProperties.LIT)?15:0).emissiveRendering((s,l,p)->s.getValue(net.minecraft.world.level.block.state.properties.BlockStateProperties.LIT))));
    public static final RegistryObject<Block> NERV_ALERT_LIGHT=BLOCKS.register("nerv_alert_light",()->new com.projectseele.world.FacilityCeilingLightR30(BlockBehaviour.Properties.copy(Blocks.IRON_BLOCK).strength(1.5F).noOcclusion().lightLevel(s->s.getValue(net.minecraft.world.level.block.state.properties.BlockStateProperties.LIT)?15:0).emissiveRendering((s,l,p)->s.getValue(net.minecraft.world.level.block.state.properties.BlockStateProperties.LIT))));
    public static final RegistryObject<Block> NERV_MOVING_WALK=BLOCKS.register("nerv_moving_walk",()->new com.projectseele.world.MovingWalkwayBlock(BlockBehaviour.Properties.copy(Blocks.IRON_BLOCK).strength(2F).noOcclusion()));
    public static final RegistryObject<Block> NERV_SIGN_POST=BLOCKS.register("nerv_sign_post",()->new com.projectseele.world.FacilitySignPostR30(BlockBehaviour.Properties.copy(Blocks.IRON_BLOCK).strength(2F).noOcclusion()));
    public static final RegistryObject<Block> NERV_WARNING_BEACON=BLOCKS.register("nerv_warning_beacon",()->new com.projectseele.world.FacilityBeaconBlock(BlockBehaviour.Properties.copy(Blocks.IRON_BLOCK).strength(2F).lightLevel(s->s.getValue(net.minecraft.world.level.block.state.properties.BlockStateProperties.LIT)?15:0)));
    public static final RegistryObject<Block> NERV_SERVER_RACK=equipment("nerv_server_rack",3);
    public static final RegistryObject<Block> NERV_STORAGE_PANEL=equipment("nerv_storage_panel",0);
    public static final RegistryObject<Block> NERV_MEDICAL_PANEL=equipment("nerv_medical_panel",4);
    public static final RegistryObject<Block> NERV_OFFICE_CHAIR=BLOCKS.register("nerv_office_chair",()->new com.projectseele.world.NervOfficeChairBlock(BlockBehaviour.Properties.copy(Blocks.IRON_BLOCK).strength(1.5F).noOcclusion()));
    public static final RegistryObject<Block> ROAD_ASPHALT_SLAB=BLOCKS.register("road_asphalt_slab",()->new net.minecraft.world.level.block.SlabBlock(BlockBehaviour.Properties.copy(Blocks.BLACK_CONCRETE)));
    public static final RegistryObject<Block> ROAD_MARKING_SLAB=BLOCKS.register("road_marking_slab",()->new net.minecraft.world.level.block.SlabBlock(BlockBehaviour.Properties.copy(Blocks.WHITE_CONCRETE)));
    public static final RegistryObject<Block> STREET_LIGHT_HEAD=BLOCKS.register("street_light_head",()->new com.projectseele.world.StreetLightHeadBlock(BlockBehaviour.Properties.copy(Blocks.IRON_BLOCK).strength(1.5F).lightLevel(s->15).noOcclusion()));
    public static final RegistryObject<Block> PERIOD_STATION_FLOOR=BLOCKS.register("period_station_floor",()->new Block(BlockBehaviour.Properties.copy(Blocks.SMOOTH_STONE)));
    public static final RegistryObject<Block> STATION_DRAIN=BLOCKS.register("station_drain",()->new Block(BlockBehaviour.Properties.copy(Blocks.SMOOTH_STONE)));
    public static final RegistryObject<Block> PERIOD_FIXTURE_PART=BLOCKS.register("period_fixture_part",()->new com.projectseele.world.PeriodFixturePartBlock(BlockBehaviour.Properties.copy(Blocks.IRON_BLOCK).strength(2).noOcclusion().dynamicShape().noLootTable()));
    public static final RegistryObject<Block> STATION_SEAT=BLOCKS.register("station_seat",()->new com.projectseele.world.NervOfficeChairBlock(BlockBehaviour.Properties.copy(Blocks.IRON_BLOCK).strength(1.5F).noOcclusion()));
    public static final RegistryObject<Block> RESIDENTIAL_CHAIR=BLOCKS.register("residential_chair",()->new com.projectseele.world.NervOfficeChairBlock(BlockBehaviour.Properties.copy(Blocks.OAK_PLANKS).strength(1.5F).noOcclusion()));
    public static final RegistryObject<Block> MILITARY_SEAT=BLOCKS.register("military_seat",()->new com.projectseele.world.NervOfficeChairBlock(BlockBehaviour.Properties.copy(Blocks.IRON_BLOCK).strength(1.5F).noOcclusion()));
    public static final RegistryObject<Block> STATION_DEPARTURE_BOARD=BLOCKS.register("station_departure_board",()->new com.projectseele.world.StationDepartureBoardBlock(BlockBehaviour.Properties.copy(Blocks.IRON_BLOCK).strength(1.5F).noOcclusion()));
    public static final RegistryObject<Block> NERV_DIRECTION_PANEL=BLOCKS.register("nerv_direction_panel",()->new com.projectseele.world.StationDepartureBoardBlock(BlockBehaviour.Properties.copy(Blocks.IRON_BLOCK).strength(1.5F).noOcclusion(),true));
    public static final RegistryObject<Block> PERIOD_FIXTURE=BLOCKS.register("period_fixture",()->new com.projectseele.world.PeriodFixtureBlock(BlockBehaviour.Properties.copy(Blocks.IRON_BLOCK).strength(1.5F).noOcclusion()));
    public static final RegistryObject<Block> NERV_BRIEFING_TILE=BLOCKS.register("nerv_briefing_tile",()->new com.projectseele.world.NervBriefingTileBlock(BlockBehaviour.Properties.copy(Blocks.IRON_BLOCK).lightLevel(s->6)));
    public static final RegistryObject<Block> NERV_PYRAMID_PANEL=BLOCKS.register("nerv_pyramid_panel",
            ()->new Block(BlockBehaviour.Properties.copy(Blocks.REINFORCED_DEEPSLATE)));
    public static final RegistryObject<Block> NERV_PYRAMID_MARKING=BLOCKS.register("nerv_pyramid_marking",
            ()->new Block(BlockBehaviour.Properties.copy(Blocks.REINFORCED_DEEPSLATE)));
    public static final RegistryObject<Block> STATION_TACTILE_WARNING=finish("station_tactile_warning",Blocks.SMOOTH_STONE,0);
    public static final RegistryObject<Block> STATION_TACTILE_PATH=BLOCKS.register("station_tactile_path",
            ()->new com.projectseele.world.NervWayfindingTileBlock(BlockBehaviour.Properties.copy(Blocks.SMOOTH_STONE)));

    private static RegistryObject<Block> finish(String name,Block material,int light)
    {
        return BLOCKS.register(name,()->new Block(BlockBehaviour.Properties.copy(material).strength(2F).lightLevel(s->light)));
    }
    private static RegistryObject<Block> equipment(String name,int light)
    {
        return BLOCKS.register(name,()->new com.projectseele.world.NervWayfindingTileBlock(BlockBehaviour.Properties.copy(Blocks.IRON_BLOCK).strength(2F).lightLevel(s->light)));
    }

    public static final RegistryObject<Block> RETRACTABLE_BUILDING_CORE = BLOCKS.register(
            "retractable_building_core",
            () -> new RetractableBuildingCoreBlock(BlockBehaviour.Properties.copy(
                    Blocks.POLISHED_DEEPSLATE).strength(8.0F, 1200.0F)
                    .lightLevel(state -> state.getValue(
                            RetractableBuildingCoreBlock.ARMED) ? 10 : 3)));

    public static final RegistryObject<Block> UMBILICAL_PYLON = BLOCKS.register(
            "umbilical_pylon",
            () -> new UmbilicalPylonBlock(BlockBehaviour.Properties.copy(
                    Blocks.POLISHED_DEEPSLATE).strength(8.0F, 1200.0F)
                    .lightLevel(state -> 6).noOcclusion()));

    /** Scratch-free structural glazing for command-room sight lines. */
    public static final RegistryObject<Block> CLEAR_GLASS = BLOCKS.register(
            "clear_glass",
            () -> new GlassBlock(BlockBehaviour.Properties.copy(Blocks.GLASS)
                    .strength(1.2F, 8.0F).noOcclusion()
                    .isValidSpawn((state, level, position, type) -> false)
                    .isRedstoneConductor((state, level, position) -> false)
                    .isSuffocating((state, level, position) -> false)
                    .isViewBlocking((state, level, position) -> false)));

    /** Commander-office glazing: clear inward, pyramid skin outward. */
    public static final RegistryObject<Block> ONE_WAY_GLASS = BLOCKS.register(
            "one_way_glass",
            () -> new OneWayGlassBlock(
                    BlockBehaviour.Properties.copy(Blocks.GLASS)
                            .strength(2.0F, 12.0F).noOcclusion()
                            .isValidSpawn((state, level, position, type) -> false)
                            .isRedstoneConductor((state, level, position) -> false)
                            .isSuffocating((state, level, position) -> false)
                            .isViewBlocking((state, level, position) -> false)));

    /**
     * Non-ticking GeoFront equivalent of Ars Nouveau Skyweave. The Ars block
     * creates one animated block entity per voxel; a 640-diameter sphere has
     * over 1.8 million shell voxels, so the original material is not viable.
     */
    public static final RegistryObject<Block> GEOFRONT_SKYWEAVE = BLOCKS.register(
            "geofront_skyweave",
            () -> new GlassBlock(BlockBehaviour.Properties.copy(Blocks.GLASS)
                    .strength(4.0F, 30.0F).lightLevel(state -> 4)
                    .noOcclusion()
                    .isValidSpawn((state, level, position, type) -> false)
                    .isRedstoneConductor((state, level, position) -> false)
                    .isSuffocating((state, level, position) -> false)
                    .isViewBlocking((state, level, position) -> false)));

    /**
     * Inert two-block command-chair backrest.  Replaces the iron trapdoors the
     * command dais used to lean on, which every redstone pulse in the console
     * bank swung open.
     */
    public static final RegistryObject<Block> COMMAND_SEAT_BACK = BLOCKS.register(
            "command_seat_back",
            () -> new CommandSeatBackBlock(BlockBehaviour.Properties.copy(
                    Blocks.POLISHED_DEEPSLATE).strength(2.0F, 12.0F)
                    .noOcclusion()
                    .isRedstoneConductor((state, level, position) -> false)
                    .isSuffocating((state, level, position) -> false)
                    .isViewBlocking((state, level, position) -> false)));

    public static final RegistryObject<LiquidBlock> LCL_BLOCK = BLOCKS.register(
            "lcl",
            () -> new LiquidBlock(ModFluids.LCL_SOURCE,
                    BlockBehaviour.Properties.copy(Blocks.WATER)
                            .mapColor(net.minecraft.world.level.material.MapColor.COLOR_ORANGE)
                            .lightLevel(state -> 4).noLootTable()));

    private ModBlocks() {}
}
