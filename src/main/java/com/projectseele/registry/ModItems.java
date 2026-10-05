package com.projectseele.registry;

import com.projectseele.ProjectSeele;
import com.projectseele.item.PositronRifleItem;
import com.projectseele.item.SeeleScenarioItem;
import com.projectseele.item.NervConstructionKitItem;
import com.projectseele.item.NervBeaconItem;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.BlockItem;
import net.minecraft.world.item.SwordItem;
import net.minecraft.world.item.Tiers;
import net.minecraftforge.common.ForgeSpawnEggItem;
import net.minecraftforge.registries.DeferredRegister;
import net.minecraftforge.registries.ForgeRegistries;
import net.minecraftforge.registries.RegistryObject;

public class ModItems
{
    public static final DeferredRegister<Item> ITEMS = DeferredRegister.create(ForgeRegistries.ITEMS, ProjectSeele.MODID);
    public static final RegistryObject<Item> DEAD_SEA_ARCHIVE=ITEMS.register("dead_sea_archive",()->new BlockItem(ModBlocks.DEAD_SEA_ARCHIVE.get(),new Item.Properties()));

    public static final RegistryObject<Item> SATELLITE_PHONE = ITEMS.register("satellite_phone",
            () -> new com.projectseele.item.SatellitePhoneItem(new Item.Properties().stacksTo(1)));
    public static final RegistryObject<Item> UN_SATELLITE_PHONE=ITEMS.register("un_satellite_phone",
            ()->new com.projectseele.item.UNSatellitePhoneItem(new Item.Properties().stacksTo(1)));

    public static final RegistryObject<Item> CORE_FRAGMENT = ITEMS.register("core_fragment",
            () -> new Item(new Item.Properties()));
    public static final RegistryObject<Item> NERV_WORKSTATION = ITEMS.register("nerv_workstation",
            () -> new BlockItem(ModBlocks.NERV_WORKSTATION.get(),new Item.Properties()));
    public static final RegistryObject<Item> TV_STAFF_LIFT_PANEL_R45=ITEMS.register("tv_staff_lift_panel_r45",()->new BlockItem(ModBlocks.TV_STAFF_LIFT_PANEL_R45.get(),new Item.Properties()));
    public static final RegistryObject<Item> TV_STAFF_LIFT_BAND_R45=ITEMS.register("tv_staff_lift_band_r45",()->new BlockItem(ModBlocks.TV_STAFF_LIFT_BAND_R45.get(),new Item.Properties()));
    public static final RegistryObject<Item> TV_UTILITY_LIFT_CEILING_R45=ITEMS.register("tv_utility_lift_ceiling_r45",()->new BlockItem(ModBlocks.TV_UTILITY_LIFT_CEILING_R45.get(),new Item.Properties()));
    public static final RegistryObject<Item> NERV_WALL_PANEL=ITEMS.register("nerv_wall_panel",()->new BlockItem(ModBlocks.NERV_WALL_PANEL.get(),new Item.Properties()));
    public static final RegistryObject<Item> NERV_STRUCTURAL_PANEL=ITEMS.register("nerv_structural_panel",()->new BlockItem(ModBlocks.NERV_STRUCTURAL_PANEL.get(),new Item.Properties()));
    public static final RegistryObject<Item> RESIDENTIAL_PLASTER=ITEMS.register("residential_plaster",()->new BlockItem(ModBlocks.RESIDENTIAL_PLASTER.get(),new Item.Properties()));
    public static final RegistryObject<Item> RESIDENTIAL_PLASTER_SLAB=ITEMS.register("residential_plaster_slab",()->new BlockItem(ModBlocks.RESIDENTIAL_PLASTER_SLAB.get(),new Item.Properties()));
    public static final RegistryObject<Item> NERV_MACHINE_PANEL=ITEMS.register("nerv_machine_panel",()->new BlockItem(ModBlocks.NERV_MACHINE_PANEL.get(),new Item.Properties()));
    public static final RegistryObject<Item> NERV_SHAFT_PANEL=ITEMS.register("nerv_shaft_panel",()->new BlockItem(ModBlocks.NERV_SHAFT_PANEL.get(),new Item.Properties()));
    public static final RegistryObject<Item> NERV_MACHINE_EDGE=ITEMS.register("nerv_machine_edge",()->new BlockItem(ModBlocks.NERV_MACHINE_EDGE.get(),new Item.Properties()));
    public static final RegistryObject<Item> NERV_EDGE_RAIL=ITEMS.register("nerv_edge_rail",()->new BlockItem(ModBlocks.NERV_EDGE_RAIL.get(),new Item.Properties()));
    public static final RegistryObject<Item> NERV_MACHINE_HAZARD=ITEMS.register("nerv_machine_hazard",()->new BlockItem(ModBlocks.NERV_MACHINE_HAZARD.get(),new Item.Properties()));
    public static final RegistryObject<Item> NERV_SERVER_RACK=ITEMS.register("nerv_server_rack",()->new BlockItem(ModBlocks.NERV_SERVER_RACK.get(),new Item.Properties()));
    public static final RegistryObject<Item> NERV_STORAGE_PANEL=ITEMS.register("nerv_storage_panel",()->new BlockItem(ModBlocks.NERV_STORAGE_PANEL.get(),new Item.Properties()));
    public static final RegistryObject<Item> NERV_MEDICAL_PANEL=ITEMS.register("nerv_medical_panel",()->new BlockItem(ModBlocks.NERV_MEDICAL_PANEL.get(),new Item.Properties()));
    public static final RegistryObject<Item> NERV_OFFICE_CHAIR=ITEMS.register("nerv_office_chair",()->new BlockItem(ModBlocks.NERV_OFFICE_CHAIR.get(),new Item.Properties()));
    public static final RegistryObject<Item> NERV_ROOM_PARTITION_R47=ITEMS.register("nerv_room_partition",()->new BlockItem(ModBlocks.NERV_ROOM_PARTITION_R47.get(),new Item.Properties()));
    public static final RegistryObject<Item> ROAD_ASPHALT_SLAB=ITEMS.register("road_asphalt_slab",()->new BlockItem(ModBlocks.ROAD_ASPHALT_SLAB.get(),new Item.Properties()));
    public static final RegistryObject<Item> ROAD_MARKING_SLAB=ITEMS.register("road_marking_slab",()->new BlockItem(ModBlocks.ROAD_MARKING_SLAB.get(),new Item.Properties()));
    public static final RegistryObject<Item> STREET_LIGHT_HEAD=ITEMS.register("street_light_head",()->new BlockItem(ModBlocks.STREET_LIGHT_HEAD.get(),new Item.Properties()));
    public static final RegistryObject<Item> STATION_SEAT=ITEMS.register("station_seat",()->new BlockItem(ModBlocks.STATION_SEAT.get(),new Item.Properties()));
    public static final RegistryObject<Item> RESIDENTIAL_CHAIR=ITEMS.register("residential_chair",()->new BlockItem(ModBlocks.RESIDENTIAL_CHAIR.get(),new Item.Properties()));
    public static final RegistryObject<Item> MILITARY_SEAT=ITEMS.register("military_seat",()->new BlockItem(ModBlocks.MILITARY_SEAT.get(),new Item.Properties()));
    public static final RegistryObject<Item> STATION_DEPARTURE_BOARD=ITEMS.register("station_departure_board",()->new BlockItem(ModBlocks.STATION_DEPARTURE_BOARD.get(),new Item.Properties()));
    public static final RegistryObject<Item> NERV_DIRECTION_PANEL=ITEMS.register("nerv_direction_panel",()->new BlockItem(ModBlocks.NERV_DIRECTION_PANEL.get(),new Item.Properties()));
    public static final RegistryObject<Item> PERIOD_FIXTURE=ITEMS.register("period_fixture",()->new BlockItem(ModBlocks.PERIOD_FIXTURE.get(),new Item.Properties()));
    public static final RegistryObject<Item> PERIOD_STATION_FLOOR=ITEMS.register("period_station_floor",()->new BlockItem(ModBlocks.PERIOD_STATION_FLOOR.get(),new Item.Properties()));
    public static final RegistryObject<Item> STATION_DRAIN=ITEMS.register("station_drain",()->new BlockItem(ModBlocks.STATION_DRAIN.get(),new Item.Properties()));
    public static final RegistryObject<Item> NERV_BRIEFING_TILE=ITEMS.register("nerv_briefing_tile",()->new BlockItem(ModBlocks.NERV_BRIEFING_TILE.get(),new Item.Properties()));
    public static final RegistryObject<Item> NERV_WALL_DATUM=ITEMS.register("nerv_wall_datum",()->new BlockItem(ModBlocks.NERV_WALL_DATUM.get(),new Item.Properties()));
    public static final RegistryObject<Item> NERV_FLOOR_PANEL=ITEMS.register("nerv_floor_panel",()->new BlockItem(ModBlocks.NERV_FLOOR_PANEL.get(),new Item.Properties()));
    public static final RegistryObject<Item> NERV_HAZARD_PAVING=ITEMS.register("nerv_hazard_paving",()->new BlockItem(ModBlocks.NERV_HAZARD_PAVING.get(),new Item.Properties()));
    public static final RegistryObject<Item> NERV_STRIP_LIGHT=ITEMS.register("nerv_strip_light",()->new BlockItem(ModBlocks.NERV_STRIP_LIGHT.get(),new Item.Properties()));
    public static final RegistryObject<Item> NERV_SIGN_POST=ITEMS.register("nerv_sign_post",()->new BlockItem(ModBlocks.NERV_SIGN_POST.get(),new Item.Properties()));
    public static final RegistryObject<Item> NERV_CEILING_LIGHT=ITEMS.register("nerv_ceiling_light",()->new BlockItem(ModBlocks.NERV_CEILING_LIGHT.get(),new Item.Properties()));
    public static final RegistryObject<Item> NERV_ALERT_LIGHT=ITEMS.register("nerv_alert_light",()->new BlockItem(ModBlocks.NERV_ALERT_LIGHT.get(),new Item.Properties()));
    public static final RegistryObject<Item> STATION_TACTILE_PATH=ITEMS.register("station_tactile_path",()->new BlockItem(ModBlocks.STATION_TACTILE_PATH.get(),new Item.Properties()));
    public static final RegistryObject<Item> STATION_TACTILE_WARNING=ITEMS.register("station_tactile_warning",()->new BlockItem(ModBlocks.STATION_TACTILE_WARNING.get(),new Item.Properties()));
    public static final RegistryObject<Item> S2_ENGINE_FRAGMENT = ITEMS.register("s2_engine_fragment",
            () -> new Item(new Item.Properties().fireResistant()));
    public static final RegistryObject<Item> RETRACTABLE_BUILDING_CORE = ITEMS.register(
            "retractable_building_core",
            () -> new BlockItem(ModBlocks.RETRACTABLE_BUILDING_CORE.get(),
                    new Item.Properties().fireResistant()));

    public static final RegistryObject<Item> EVA_PROGRESSIVE_KNIFE = ITEMS.register(
            "eva_progressive_knife",
            () -> new Item(new Item.Properties().stacksTo(1).fireResistant()));
    public static final RegistryObject<Item> EVA_PALLET_RIFLE = ITEMS.register(
            "eva_pallet_rifle",
            () -> new Item(new Item.Properties().stacksTo(1).fireResistant()));
    public static final RegistryObject<Item> EVA_POSITRON_CANNON = ITEMS.register(
            "eva_positron_cannon",
            () -> new Item(new Item.Properties().stacksTo(1).fireResistant()));
    /** Physical one-stack cargo; field protection still requires the real shield bridge. */
    public static final RegistryObject<Item> YASHIMA_SHIELD = ITEMS.register(
            "yashima_shield",
            () -> new Item(new Item.Properties().stacksTo(1).fireResistant()));

    public static final RegistryObject<Item> EVA_N2_DEVICE = ITEMS.register(
            "eva_n2_device",
            () -> new Item(new Item.Properties().stacksTo(1).fireResistant()));

    public static final RegistryObject<Item> UMBILICAL_PYLON = ITEMS.register(
            "umbilical_pylon",
            () -> new BlockItem(ModBlocks.UMBILICAL_PYLON.get(),
                    new Item.Properties().fireResistant()));

    public static final RegistryObject<Item> CLEAR_GLASS = ITEMS.register(
            "clear_glass",
            () -> new BlockItem(ModBlocks.CLEAR_GLASS.get(),
                    new Item.Properties()));

    public static final RegistryObject<Item> ONE_WAY_GLASS = ITEMS.register(
            "one_way_glass",
            () -> new BlockItem(ModBlocks.ONE_WAY_GLASS.get(),
                    new Item.Properties()));

    public static final RegistryObject<Item> NERV_PYRAMID_PANEL=ITEMS.register("nerv_pyramid_panel",
            ()->new BlockItem(ModBlocks.NERV_PYRAMID_PANEL.get(),new Item.Properties()));
    public static final RegistryObject<Item> NERV_PYRAMID_MARKING=ITEMS.register("nerv_pyramid_marking",
            ()->new BlockItem(ModBlocks.NERV_PYRAMID_MARKING.get(),new Item.Properties()));

    public static final RegistryObject<Item> TERMINAL_DOGMA_ACCESS_CARD =
            ITEMS.register("terminal_dogma_access_card",
                    () -> new com.projectseele.item.NervAccessCardR44(new Item.Properties().stacksTo(1),3));
    public static final RegistryObject<Item> NERV_EMPLOYEE_CARD =
            ITEMS.register("nerv_employee_card",
                    () -> new com.projectseele.item.NervAccessCardR44(new Item.Properties().stacksTo(1),1));
    public static final RegistryObject<Item> NERV_ACCESS_READER=ITEMS.register("nerv_access_reader",()->new BlockItem(ModBlocks.NERV_ACCESS_READER.get(),new Item.Properties()));
    public static final RegistryObject<Item> CITY_PERSONNEL_DOOR=ITEMS.register("city_personnel_door",()->new BlockItem(ModBlocks.CITY_PERSONNEL_DOOR.get(),new Item.Properties()));
    public static final RegistryObject<Item> CITY_RAIN_PIPE=ITEMS.register("city_rain_pipe",()->new BlockItem(ModBlocks.CITY_RAIN_PIPE.get(),new Item.Properties()));
    public static final RegistryObject<Item> CITY_RAIN_GUTTER=ITEMS.register("city_rain_gutter",()->new BlockItem(ModBlocks.CITY_RAIN_GUTTER.get(),new Item.Properties()));
    public static final RegistryObject<Item> BETA_CAPSULE =
            ITEMS.register("beta_capsule",
                    () -> new Item(new Item.Properties().stacksTo(1)));

    public static final RegistryObject<Item> GEOFRONT_SKYWEAVE = ITEMS.register(
            "geofront_skyweave",
            () -> new BlockItem(ModBlocks.GEOFRONT_SKYWEAVE.get(),
                    new Item.Properties().fireResistant()));

    public static final RegistryObject<Item> COMMAND_SEAT_BACK = ITEMS.register(
            "command_seat_back",
            () -> new BlockItem(ModBlocks.COMMAND_SEAT_BACK.get(),
                    new Item.Properties()));

    public static final RegistryObject<Item> POSITRON_RIFLE = ITEMS.register("positron_rifle",
            () -> new PositronRifleItem(new Item.Properties().stacksTo(1)));

    public static final RegistryObject<Item> RAMIEL_SPAWN_EGG = ITEMS.register("ramiel_spawn_egg",
            () -> new ForgeSpawnEggItem(ModEntities.RAMIEL, 0x4A7FD4, 0xE3242B, new Item.Properties()));

    public static final RegistryObject<Item> EVA_UNIT01_SPAWN_EGG = ITEMS.register("eva_unit01_spawn_egg",
            () -> new ForgeSpawnEggItem(ModEntities.EVA_UNIT01, 0x57288A, 0x39FF6E, new Item.Properties()));
    public static final RegistryObject<Item> EVA_UNIT00_SPAWN_EGG = ITEMS.register("eva_unit00_spawn_egg",
            () -> new ForgeSpawnEggItem(ModEntities.EVA_UNIT00, 0xE89B2C, 0xF5F5E8, new Item.Properties()));
    public static final RegistryObject<Item> EVA_UNIT02_SPAWN_EGG = ITEMS.register("eva_unit02_spawn_egg",
            () -> new ForgeSpawnEggItem(ModEntities.EVA_UNIT02, 0xB51F28, 0xF2C230, new Item.Properties()));

    public static final RegistryObject<Item> SACHIEL_SPAWN_EGG = ITEMS.register("sachiel_spawn_egg",
            () -> new ForgeSpawnEggItem(ModEntities.SACHIEL, 0x202623, 0xEAF0E5, new Item.Properties()));
    public static final RegistryObject<Item> SHAMSHEL_SPAWN_EGG = ITEMS.register("shamshel_spawn_egg",
            () -> new ForgeSpawnEggItem(ModEntities.SHAMSHEL, 0x5B162A, 0xEF3C4A, new Item.Properties()));
    public static final RegistryObject<Item> ZERUEL_SPAWN_EGG = ITEMS.register("zeruel_spawn_egg",
            () -> new ForgeSpawnEggItem(ModEntities.ZERUEL, 0xE4E2D8, 0x181414, new Item.Properties()));
    public static final RegistryObject<Item> ISRAFEL_SPAWN_EGG = ITEMS.register("israfel_spawn_egg",
            () -> new ForgeSpawnEggItem(ModEntities.ISRAFEL, 0x173B25, 0xD8D8D0, new Item.Properties()));
    public static final RegistryObject<Item> MASS_PRODUCTION_EVA_SPAWN_EGG = ITEMS.register("mass_production_eva_spawn_egg",
            () -> new ForgeSpawnEggItem(ModEntities.MASS_PRODUCTION_EVA, 0xE2DED2, 0xA51620, new Item.Properties()));
    public static final RegistryObject<Item> SEELE_SCENARIO = ITEMS.register("seele_scenario",
            () -> new SeeleScenarioItem(new Item.Properties().stacksTo(1).fireResistant()));
    public static final RegistryObject<Item> NERV_CONSTRUCTION_KIT = ITEMS.register("nerv_construction_kit",
            () -> new NervConstructionKitItem(new Item.Properties().stacksTo(1)));
    public static final RegistryObject<Item> NERV_BEACON = ITEMS.register("nerv_beacon",
            () -> new NervBeaconItem(new Item.Properties().stacksTo(1).fireResistant()));
    public static final RegistryObject<Item> LANCE_OF_LONGINUS = ITEMS.register("lance_of_longinus",
            () -> new SwordItem(Tiers.NETHERITE, 116, -2.8F,
                    new Item.Properties().stacksTo(1).durability(2031).fireResistant()));
}
