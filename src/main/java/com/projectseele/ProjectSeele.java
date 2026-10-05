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
        com.projectseele.registry.SeeleConferenceEntitiesR47.bootstrap();
        ModEntities.ENTITY_TYPES.register(modEventBus);
        ModCreativeTabs.TABS.register(modEventBus);
        ModSounds.SOUNDS.register(modEventBus);
        ModWorldgen.CHUNK_GENERATORS.register(modEventBus);
        ModWorldgen.BIOME_SOURCES.register(modEventBus);

        ModLoadingContext.get().registerConfig(ModConfig.Type.COMMON, SeeleConfig.COMMON_SPEC);
        ModLoadingContext.get().registerConfig(ModConfig.Type.CLIENT, SeeleConfig.CLIENT_SPEC);

        if(Boolean.getBoolean("projectseele.r45BeValidityReview"))
        {
            net.minecraftforge.common.MinecraftForge.EVENT_BUS.addListener(com.projectseele.visual.BlockEntityValidityReviewR45::register);
            net.minecraftforge.common.MinecraftForge.EVENT_BUS.addListener(com.projectseele.visual.BlockEntityValidityReviewR45::exportOnStart);
        }

        modEventBus.addListener(this::commonSetup);
    }

    private void commonSetup(final FMLCommonSetupEvent event)
    {
        event.enqueueWork(() ->
        {
            SeeleNetwork.register();
            if(!System.getProperty("projectseele.r45CampaignAcceptancePlan", "").isBlank())
                net.minecraftforge.common.MinecraftForge.EVENT_BUS.register(com.projectseele.visual.TvCampaignNativeAcceptanceR45.class);
            EvaLiveCombatMotion.preload();
            ForgeChunkManager.setForcedChunkLoadingCallback(MODID,
                    NervRuntimeMaintenance::validateForcedChunkTickets);
        });
        LOGGER.info("Project SEELE initialized. God's in his heaven, all's right with the world.");
    }
}
