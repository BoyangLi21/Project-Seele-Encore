package com.projectseele.registry;

import com.projectseele.ProjectSeele;
import com.projectseele.world.UmbilicalPylonBlockEntity;
import net.minecraft.world.level.block.entity.BlockEntityType;
import net.minecraftforge.registries.DeferredRegister;
import net.minecraftforge.registries.ForgeRegistries;
import net.minecraftforge.registries.RegistryObject;

/** Block entities used by interactive NERV infrastructure. */
public final class ModBlockEntities
{
    public static final DeferredRegister<BlockEntityType<?>> BLOCK_ENTITY_TYPES =
            DeferredRegister.create(ForgeRegistries.BLOCK_ENTITY_TYPES,
                    ProjectSeele.MODID);
    public static final RegistryObject<BlockEntityType<com.projectseele.world.NervAccessReaderEntityR44>> NERV_ACCESS_READER=
            BLOCK_ENTITY_TYPES.register("nerv_access_reader",()->BlockEntityType.Builder.of(com.projectseele.world.NervAccessReaderEntityR44::new,ModBlocks.NERV_ACCESS_READER.get()).build(null));

    public static final RegistryObject<BlockEntityType<UmbilicalPylonBlockEntity>>
            UMBILICAL_PYLON = BLOCK_ENTITY_TYPES.register("umbilical_pylon",
            () -> BlockEntityType.Builder.of(UmbilicalPylonBlockEntity::new,
                    ModBlocks.UMBILICAL_PYLON.get()).build(null));

    public static final RegistryObject<BlockEntityType<com.projectseele.world.OneWayGlassBlockEntity>> ONE_WAY_GLASS=
            BLOCK_ENTITY_TYPES.register("one_way_glass",()->BlockEntityType.Builder.of(com.projectseele.world.OneWayGlassBlockEntity::new,ModBlocks.ONE_WAY_GLASS.get()).build(null));

    private ModBlockEntities() {}
    public static final RegistryObject<BlockEntityType<com.projectseele.world.StationDepartureBoardBlockEntity>> STATION_DEPARTURE_BOARD=
            BLOCK_ENTITY_TYPES.register("station_departure_board",()->BlockEntityType.Builder.of(com.projectseele.world.StationDepartureBoardBlockEntity::new,ModBlocks.STATION_DEPARTURE_BOARD.get(),ModBlocks.NERV_DIRECTION_PANEL.get()).build(null));
    public static final RegistryObject<BlockEntityType<com.projectseele.world.PeriodFixtureBlockEntity>> PERIOD_FIXTURE=
            BLOCK_ENTITY_TYPES.register("period_fixture",()->BlockEntityType.Builder.of(com.projectseele.world.PeriodFixtureBlockEntity::new,ModBlocks.PERIOD_FIXTURE.get()).build(null));
    public static final RegistryObject<BlockEntityType<com.projectseele.world.WallArtworkBlockEntity>> WALL_ARTWORK=
            BLOCK_ENTITY_TYPES.register("wall_artwork",()->BlockEntityType.Builder.of(com.projectseele.world.WallArtworkBlockEntity::new,ModBlocks.WALL_ARTWORK.get()).build(null));
}
