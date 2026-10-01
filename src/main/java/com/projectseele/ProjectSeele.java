package com.projectseele;

import com.mojang.logging.LogUtils;
import com.projectseele.config.SeeleConfig;
import com.projectseele.entity.EvaLiveCombatMotion;
import com.projectseele.network.SeeleNetwork;
import com.projectseele.registry.ModCreativeTabs;
import com.projectseele.registry.ModBlocks;
import com.projectseele.registry.ModBlockEntities;
import com.projectseele.registry.ModEntities;
import com.projectseele.registry.ModItems;
import com.projectseele.registry.ModFluids;
import com.projectseele.registry.ModSounds;
import com.projectseele.registry.ModWorldgen;
import com.projectseele.world.NervRuntimeMaintenance;
import net.minecraftforge.eventbus.api.IEventBus;
import net.minecraftforge.common.world.ForgeChunkManager;
import net.minecraftforge.fml.ModLoadingContext;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.fml.config.ModConfig;
import net.minecraftforge.fml.event.lifecycle.FMLCommonSetupEvent;
import net.minecraftforge.fml.javafmlmod.FMLJavaModLoadingContext;
import org.slf4j.Logger;

// The value here should match an entry in the META-INF/mods.toml file
@Mod(ProjectSeele.MODID)
public class ProjectSeele
{
    // Define mod id in a common place for everything to reference
    public static final String MODID = "projectseele";
    public static final Logger LOGGER = LogUtils.getLogger();

    public ProjectSeele(FMLJavaModLoadingContext context)
    {
        IEventBus modEventBus = context.getModEventBus();

        ModFluids.FLUID_TYPES.register(modEventBus);
        ModFluids.FLUIDS.register(modEventBus);
        ModBlocks.BLOCKS.register(modEventBus);
        ModBlockEntities.BLOCK_ENTITY_TYPES.register(modEventBus);
        ModItems.ITEMS.register(modEventBus);
        ModEntities.ENTITY_TYPES.register(modEventBus);
        ModCreativeTabs.TABS.register(modEventBus);
        ModSounds.SOUNDS.register(modEventBus);
        ModWorldgen.CHUNK_GENERATORS.register(modEventBus);
        ModWorldgen.BIOME_SOURCES.register(modEventBus);

        ModLoadingContext.get().registerConfig(ModConfig.Type.COMMON, SeeleConfig.COMMON_SPEC);
        ModLoadingContext.get().registerConfig(ModConfig.Type.CLIENT, SeeleConfig.CLIENT_SPEC);

        modEventBus.addListener(this::commonSetup);
    }

    private void commonSetup(final FMLCommonSetupEvent event)
    {
        event.enqueueWork(() ->
        {
            SeeleNetwork.register();
            EvaLiveCombatMotion.preload();
            ForgeChunkManager.setForcedChunkLoadingCallback(MODID,
                    NervRuntimeMaintenance::validateForcedChunkTickets);
        });
        LOGGER.info("Project SEELE initialized. God's in his heaven, all's right with the world.");
    }
}
