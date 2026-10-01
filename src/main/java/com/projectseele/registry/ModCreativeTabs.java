package com.projectseele.registry;

import com.projectseele.ProjectSeele;
import net.minecraft.core.registries.Registries;
import net.minecraft.network.chat.Component;
import net.minecraft.world.item.CreativeModeTab;
import net.minecraftforge.registries.DeferredRegister;
import net.minecraftforge.registries.RegistryObject;

public class ModCreativeTabs
{
    public static final DeferredRegister<CreativeModeTab> TABS =
            DeferredRegister.create(Registries.CREATIVE_MODE_TAB, ProjectSeele.MODID);

    public static final RegistryObject<CreativeModeTab> MAIN = TABS.register("main",
            () -> CreativeModeTab.builder()
                    .title(Component.translatable("itemGroup.projectseele"))
                    .icon(() -> ModItems.POSITRON_RIFLE.get().getDefaultInstance())
                    .displayItems((parameters, output) -> {
                        output.accept(ModItems.POSITRON_RIFLE.get());
                        output.accept(ModItems.CORE_FRAGMENT.get());
                        output.accept(ModItems.S2_ENGINE_FRAGMENT.get());
                        output.accept(ModItems.RETRACTABLE_BUILDING_CORE.get());
                        output.accept(ModItems.UMBILICAL_PYLON.get());
                        output.accept(ModItems.CLEAR_GLASS.get());
                        output.accept(ModItems.ONE_WAY_GLASS.get());
                        output.accept(ModItems.NERV_PYRAMID_PANEL.get());
                        output.accept(ModItems.NERV_PYRAMID_MARKING.get());
                        output.accept(ModItems.TERMINAL_DOGMA_ACCESS_CARD.get());
                        output.accept(ModItems.NERV_EMPLOYEE_CARD.get());
                        output.accept(ModItems.SATELLITE_PHONE.get());
                        output.accept(ModItems.UN_SATELLITE_PHONE.get());
                        output.accept(ModItems.NERV_WORKSTATION.get());
                        output.accept(ModItems.NERV_SERVER_RACK.get());
                        output.accept(ModItems.NERV_STORAGE_PANEL.get());
                        output.accept(ModItems.NERV_MEDICAL_PANEL.get());
                        output.accept(ModItems.NERV_OFFICE_CHAIR.get());
                        output.accept(ModItems.NERV_BRIEFING_TILE.get());
                        output.accept(ModItems.NERV_WALL_PANEL.get());
                        output.accept(ModItems.NERV_STRUCTURAL_PANEL.get());
                        output.accept(ModItems.RESIDENTIAL_PLASTER.get());
                        output.accept(ModItems.RESIDENTIAL_PLASTER_SLAB.get());
                        output.accept(ModItems.NERV_WALL_DATUM.get());
                        output.accept(ModItems.NERV_FLOOR_PANEL.get());
                        output.accept(ModItems.NERV_HAZARD_PAVING.get());
                        output.accept(ModItems.NERV_STRIP_LIGHT.get());
                        output.accept(ModItems.STATION_TACTILE_PATH.get());
                        output.accept(ModItems.STATION_TACTILE_WARNING.get());
                        output.accept(ModItems.PERIOD_STATION_FLOOR.get());
                        output.accept(ModItems.STATION_DRAIN.get());
                        for(var kind:com.projectseele.world.PeriodFixtureBlock.Kind.values())
                        {
                            var stack=new net.minecraft.world.item.ItemStack(ModItems.PERIOD_FIXTURE.get());
                            stack.getOrCreateTagElement("BlockStateTag").putString("kind",kind.getSerializedName());
                            stack.setHoverName(Component.translatable("period_fixture.projectseele."+kind.getSerializedName()));output.accept(stack);
                        }
                        output.accept(ModItems.BETA_CAPSULE.get());
                        output.accept(ModItems.COMMAND_SEAT_BACK.get());
                        output.accept(ModItems.EVA_PROGRESSIVE_KNIFE.get());
                        output.accept(ModItems.EVA_PALLET_RIFLE.get());
                        output.accept(ModItems.EVA_POSITRON_CANNON.get());
                        output.accept(ModItems.EVA_N2_DEVICE.get());
                        output.accept(ModItems.RAMIEL_SPAWN_EGG.get());
                        output.accept(ModItems.EVA_UNIT01_SPAWN_EGG.get());
                        output.accept(ModItems.EVA_UNIT00_SPAWN_EGG.get());
                        output.accept(ModItems.EVA_UNIT02_SPAWN_EGG.get());
                        output.accept(ModItems.SACHIEL_SPAWN_EGG.get());
                        output.accept(ModItems.SHAMSHEL_SPAWN_EGG.get());
                        output.accept(ModItems.ZERUEL_SPAWN_EGG.get());
                        output.accept(ModItems.ISRAFEL_SPAWN_EGG.get());
                        output.accept(ModItems.MASS_PRODUCTION_EVA_SPAWN_EGG.get());
                        output.accept(ModItems.NERV_CONSTRUCTION_KIT.get());
                        output.accept(ModItems.NERV_BEACON.get());
                        output.accept(ModItems.LANCE_OF_LONGINUS.get());
                        output.accept(ModItems.SEELE_SCENARIO.get());
                    })
                    .build());
}
