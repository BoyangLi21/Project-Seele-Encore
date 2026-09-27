package com.projectseele.client;

import com.projectseele.ProjectSeele;
import com.projectseele.client.render.EntryPlugCarrierRenderer;
import com.projectseele.client.render.EvaUnit01Renderer;
import com.projectseele.client.render.EvaMotionEngineV2;
import com.projectseele.client.render.EvaManifoldInnerBody;
import com.projectseele.client.render.EvaPoseGraph;
import com.projectseele.client.render.EvaSkinnedMeshRuntime;
import com.projectseele.client.render.EvaWeightedInnerProxy;
import com.projectseele.client.render.LocalTriangleMeshLayer;
import com.projectseele.client.render.LocalVisualAssetFingerprint;
import com.projectseele.client.render.NervCarrierPlatformRenderer;
import com.projectseele.client.render.NervCommandSeatRenderer;
import com.projectseele.client.render.GendoPoseArmLayer;
import com.projectseele.client.render.NervArmamentStationRenderer;
import com.projectseele.client.render.NervSiloDoorRenderer;
import com.projectseele.client.render.NervHangarDoorRenderer;
import com.projectseele.client.render.NervSlidingDoorRenderer;
import com.projectseele.client.render.NervLiftDoorRenderer;
import com.projectseele.client.render.RamielRenderer;
import com.projectseele.client.render.TrainingPilotRenderer;
import com.projectseele.client.render.UltramanAvatarRenderer;
import com.projectseele.client.render.LilithRenderer;
import com.projectseele.client.render.ColossalHumanoidRenderer;
import com.projectseele.client.render.HybridAddonRenderer;
import com.projectseele.client.render.RiggedAngelLayer;
import com.projectseele.registry.ModEntities;
import com.projectseele.registry.ModFluids;
import com.projectseele.registry.ModBlocks;
import net.minecraft.client.renderer.ItemBlockRenderTypes;
import net.minecraft.client.renderer.RenderType;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.EntityRenderersEvent;
import net.minecraft.client.renderer.entity.player.PlayerRenderer;
import net.minecraftforge.client.event.RegisterGuiOverlaysEvent;
import net.minecraftforge.client.event.RegisterKeyMappingsEvent;
import net.minecraftforge.client.event.RegisterClientReloadListenersEvent;
import net.minecraft.server.packs.resources.ResourceManagerReloadListener;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.fml.event.lifecycle.FMLClientSetupEvent;

@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, bus = Mod.EventBusSubscriber.Bus.MOD, value = Dist.CLIENT)
public class ClientEvents
{
    @SubscribeEvent
    public static void onClientSetup(FMLClientSetupEvent event)
    {
        event.enqueueWork(() ->
        {
            ItemBlockRenderTypes.setRenderLayer(ModFluids.LCL_SOURCE.get(),
                    RenderType.translucent());
            ItemBlockRenderTypes.setRenderLayer(ModFluids.FLOWING_LCL.get(),
                    RenderType.translucent());
            ItemBlockRenderTypes.setRenderLayer(ModBlocks.CLEAR_GLASS.get(),
                    RenderType.translucent());
            ItemBlockRenderTypes.setRenderLayer(ModBlocks.ONE_WAY_GLASS.get(),
                    RenderType.cutout());
            // Cutout avoids sorting millions of translucent shell faces while
            // transparent texels still reveal the real dimension sky.
            ItemBlockRenderTypes.setRenderLayer(
                    ModBlocks.GEOFRONT_SKYWEAVE.get(), RenderType.cutout());
        });
    }

    @SubscribeEvent
    public static void onRegisterRenderers(EntityRenderersEvent.RegisterRenderers event)
    {
        event.registerEntityRenderer(ModEntities.RAMIEL.get(), RamielRenderer::new);
        event.registerEntityRenderer(ModEntities.EVA_UNIT01.get(), EvaUnit01Renderer::new);
        event.registerEntityRenderer(ModEntities.EVA_UNIT00.get(), EvaUnit01Renderer::new);
        event.registerEntityRenderer(ModEntities.EVA_UNIT02.get(), EvaUnit01Renderer::new);
        event.registerEntityRenderer(ModEntities.EVA_PROTOTYPE.get(), EvaUnit01Renderer::new);
        event.registerEntityRenderer(ModEntities.INDUSTRIAL_MEMBER.get(), com.projectseele.client.render.IndustrialMemberRenderer::new);
        event.registerBlockEntityRenderer(com.projectseele.registry.ModBlockEntities.ONE_WAY_GLASS.get(),com.projectseele.client.render.OneWayGlassRenderer::new);
        event.registerBlockEntityRenderer(com.projectseele.registry.ModBlockEntities.STATION_DEPARTURE_BOARD.get(),com.projectseele.client.render.StationDepartureBoardRenderer::new);
        event.registerBlockEntityRenderer(com.projectseele.registry.ModBlockEntities.PERIOD_FIXTURE.get(),com.projectseele.client.render.PeriodFixtureRenderer::new);
        event.registerBlockEntityRenderer(com.projectseele.registry.ModBlockEntities.WALL_ARTWORK.get(),com.projectseele.client.render.WallArtworkRenderer::new);
        event.registerEntityRenderer(ModEntities.ENTRY_PLUG_CARRIER.get(),
                EntryPlugCarrierRenderer::new);
        event.registerEntityRenderer(ModEntities.TRAINING_PILOT.get(),
                TrainingPilotRenderer::new);
        event.registerEntityRenderer(ModEntities.NERV_STAFF.get(),com.projectseele.client.render.NervStaffRenderer::new);
        event.registerEntityRenderer(ModEntities.NERV_CARRIER_PLATFORM.get(),
                NervCarrierPlatformRenderer::new);
        event.registerEntityRenderer(ModEntities.NERV_LIFT_CABIN.get(),
                NervCarrierPlatformRenderer::new);
        event.registerEntityRenderer(ModEntities.NERV_COMMAND_SEAT.get(),
                NervCommandSeatRenderer::new);
        event.registerEntityRenderer(ModEntities.NERV_ARMAMENT_STATION.get(),
                NervArmamentStationRenderer::new);
        event.registerEntityRenderer(ModEntities.NERV_SILO_DOOR.get(),
                NervSiloDoorRenderer::new);
        event.registerEntityRenderer(ModEntities.NERV_HANGAR_DOOR.get(),
                NervHangarDoorRenderer::new);
        event.registerEntityRenderer(ModEntities.UN_TRANSPORT.get(),com.projectseele.client.render.UNTransportRenderer::new);
        event.registerEntityRenderer(ModEntities.NERV_SLIDING_DOOR.get(),
                NervSlidingDoorRenderer::new);
        event.registerEntityRenderer(ModEntities.NERV_LIFT_DOOR.get(),
                NervLiftDoorRenderer::new);
        event.registerEntityRenderer(ModEntities.ULTRAMAN_AVATAR.get(),
                UltramanAvatarRenderer::new);
        event.registerEntityRenderer(ModEntities.SACHIEL.get(), context -> new HybridAddonRenderer<>(context,
                ColossalHumanoidRenderer.Style.SACHIEL, "sachiel", 5.0F));
        event.registerEntityRenderer(ModEntities.SHAMSHEL.get(),
                context -> new HybridAddonRenderer<>(context, ColossalHumanoidRenderer.Style.SHAMSHEL,"shamshel",5.0F));
        event.registerEntityRenderer(ModEntities.ZERUEL.get(),
                context -> new HybridAddonRenderer<>(context, ColossalHumanoidRenderer.Style.ZERUEL,"zeruel",5.0F));
        event.registerEntityRenderer(ModEntities.ISRAFEL.get(), context -> new HybridAddonRenderer<>(context,
                ColossalHumanoidRenderer.Style.SACHIEL, "israfel", 5.0F));
        event.registerEntityRenderer(ModEntities.LILITH.get(), LilithRenderer::new);
        event.registerEntityRenderer(ModEntities.MASS_PRODUCTION_EVA.get(), context -> new HybridAddonRenderer<>(context,
                ColossalHumanoidRenderer.Style.MASS_PRODUCTION, "mass_production_eva", 6.5F));
    }

    @SubscribeEvent
    public static void onAddRenderLayers(EntityRenderersEvent.AddLayers event)
    {
        PlayerRenderer standard = event.getSkin("default");
        if (standard != null)
        {
            standard.addLayer(new GendoPoseArmLayer(standard, false));
        }
        PlayerRenderer slim = event.getSkin("slim");
        if (slim != null)
        {
            slim.addLayer(new GendoPoseArmLayer(slim, true));
        }
    }

    @SubscribeEvent
    public static void onRegisterGuiOverlays(RegisterGuiOverlaysEvent event)
    {
        event.registerAboveAll("angel_alarm", AlarmOverlay.INSTANCE);
        event.registerAboveAll("eva_cockpit",(gui,g,p,w,h)->{if(!FirstBattleClient.active())EvaHud.COCKPIT.render(gui,g,p,w,h);});
        event.registerAboveAll("eva_combat_r31",EvaCombatHudR31.OVERLAY);
        event.registerAboveAll("sniper_scope", EvaHud.SCOPE);
        event.registerAboveAll("plug_insertion", EvaHud.INSERTION);
        event.registerAboveAll("nuclear_flash", EvaHud.NUCLEAR_FLASH);
        event.registerAboveAll("eva_command_feed_capture", EvaCommandFeedClient.CAPTURE_OVERLAY);
        event.registerAboveAll("first_battle",FirstBattleClient.OVERLAY);
    }

    @SubscribeEvent
    public static void onRegisterKeyMappings(RegisterKeyMappingsEvent event)
    {
        event.register(Keybinds.CYCLE_WEAPON);
        event.register(Keybinds.COMMAND_RADIO);
        event.register(Keybinds.TOGGLE_AT_FIELD);
        event.register(Keybinds.EXIT_EVA);
        event.register(Keybinds.STOMP);
        event.register(Keybinds.TOGGLE_PRONE);
        event.register(Keybinds.CANCEL_LAUNCH);
        event.register(Keybinds.SELF_LAUNCH);
        event.register(Keybinds.COMMANDER_POSE);
        event.register(Keybinds.UN_EYE_LASER);
        event.register(Keybinds.UN_FLIGHT);
        event.register(Keybinds.EVA_GRAPPLE);
        event.register(Keybinds.ULTRAMAN_TRANSFORM);
    }

    @SubscribeEvent
    public static void onRegisterReloadListeners(RegisterClientReloadListenersEvent event)
    {
        event.registerReloadListener((ResourceManagerReloadListener) resourceManager ->
        {
            LocalTriangleMeshLayer.clearCache();
            RiggedAngelLayer.clearCache();
            com.projectseele.client.render.EvaFootPlacement.clear();
            LocalVisualAssetFingerprint.clearCache();
            EvaPoseGraph.reload(resourceManager);
            EvaSkinnedMeshRuntime.reload(resourceManager);
            EvaWeightedInnerProxy.reload(resourceManager);
            EvaManifoldInnerBody.reload(resourceManager);
            EvaMotionEngineV2.reload(resourceManager);
            EvaUnit01Renderer.prewarmLocalBodyMeshes(resourceManager);
        });
    }
}
