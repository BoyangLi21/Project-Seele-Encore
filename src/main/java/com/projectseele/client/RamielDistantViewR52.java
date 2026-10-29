package com.projectseele.client;

import com.mojang.blaze3d.systems.RenderSystem;
import com.mojang.blaze3d.vertex.BufferBuilder;
import com.projectseele.client.render.RamielRenderer;
import com.projectseele.network.ClientboundEncounterObserverPacket;
import java.util.UUID;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.phys.AABB;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.RenderLevelStageEvent;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import org.joml.Matrix4f;

/** World-space selected Ramiel, with actual decode/resource/frame acknowledgement. Never a HUD surrogate. */
@Mod.EventBusSubscriber(modid="projectseele",value=Dist.CLIENT)
public final class RamielDistantViewR52
{
    @Mod.EventBusSubscriber(modid="projectseele",value=Dist.CLIENT,bus=Mod.EventBusSubscriber.Bus.MOD)
    public static final class ReloadRegistration
    {
        @SubscribeEvent public static void register(net.minecraftforge.client.event.RegisterClientReloadListenersEvent event)
        {event.registerReloadListener((net.minecraft.server.packs.resources.ResourceManagerReloadListener)manager->{resources=null;resourceId="";reported=null;});}
        private ReloadRegistration(){}
    }
    private static final MultiBufferSource.BufferSource BUFFERS=MultiBufferSource.immediate(new BufferBuilder(8192));
    private static boolean installed;private static Object resources;private static String resourceId="";private static UUID reported;
    private static String availableResource()
    {
        var manager=Minecraft.getInstance().getResourceManager();if(resources==manager)return resourceId;
        resources=manager;
        resourceId=manager.getResource(new ResourceLocation("projectseele","mesh/ramiel_source_r53.json")).isPresent()
                ?"ramiel-source-r53-v1":manager.getResource(new ResourceLocation("projectseele","textures/entity/ramiel.png")).isPresent()?"ramiel-crystal-v1":"";
        return resourceId;
    }
    @SubscribeEvent public static void tick(TickEvent.ClientTickEvent event)
    {
        if(event.phase!=TickEvent.Phase.END)return;
        if(!installed)
        {
            EncounterObserverCacheR45.installRendererSupport(new EncounterObserverCacheR45.RendererSupport(){
                @Override public boolean supports(ResourceLocation type,int schema){return ClientboundEncounterObserverPacket.RAMIEL.equals(type)&&schema==ClientboundEncounterObserverPacket.SCHEMA;}
                @Override public boolean resourcesReady(ResourceLocation type){return ClientboundEncounterObserverPacket.RAMIEL.equals(type)&&!availableResource().isEmpty();}
                @Override public String resourceSha256(ResourceLocation type){return availableResource();}
                @Override public String rendererId(){return ClientboundEncounterObserverPacket.RENDERER_ID;}
            });installed=true;
        }
    }
    /** Extend the actual world projection only during an authorized distant frame, preserving ordinary depth/occlusion. */
    public static Matrix4f projection(Matrix4f original)
    {
        var view=EncounterObserverCacheR45.renderCandidate().orElse(null);var mc=Minecraft.getInstance();if(view==null||mc.level==null)return original;
        double distance=view.current().snapshot().position().distanceTo(mc.gameRenderer.getMainCamera().getPosition());if(distance<128)return original;
        float near=original.m32()/(original.m22()-1),far=(float)Math.min(8192,Math.max(512,distance+512));
        if(!Float.isFinite(near)||near<=0||near>1)return original;
        return new Matrix4f(original).m22(-(far+near)/(far-near)).m32(-2*far*near/(far-near));
    }
    @SubscribeEvent public static void render(RenderLevelStageEvent event)
    {
        if(event.getStage()!=RenderLevelStageEvent.Stage.AFTER_ENTITIES)return;
        var view=EncounterObserverCacheR45.renderCandidate().orElse(null);if(view==null)return;
        var packet=view.current();var state=packet.snapshot();if((state.flags()&ClientboundEncounterObserverPacket.ALIVE)==0)return;
        var camera=event.getCamera().getPosition();float scale=state.height()/15F,radius=16*scale;
        var box=new AABB(state.position().add(-radius,state.height()*.5-radius,-radius),state.position().add(radius,state.height()*.5+radius,radius));
        if(state.beamTicks()>view.ageClientTicks())box=box.minmax(new AABB(state.position(),state.beamEnd()).inflate(10));
        if(!event.getFrustum().isVisible(box))return;
        var poses=event.getPoseStack();float fogStart=RenderSystem.getShaderFogStart(),fogEnd=RenderSystem.getShaderFogEnd();
        poses.pushPose();poses.translate(state.position().x-camera.x,state.position().y-camera.y,state.position().z-camera.z);
        try
        {
            float distance=(float)state.position().distanceTo(camera);
            RenderSystem.setShaderFogStart(Math.max(fogStart,distance+64));RenderSystem.setShaderFogEnd(Math.max(fogEnd,distance+512));
            RamielRenderer.renderObservedR52(state,event.getPartialTick(),view.ageClientTicks(),poses,BUFFERS);BUFFERS.endBatch();
            if(EncounterObserverCacheR45.markDrawn(packet)&&!state.target().equals(reported))
            {reported=state.target();com.projectseele.ProjectSeele.LOGGER.info("R52 real distant Ramiel frame drawn: uuid={} generation={} distance={} scale={} sequence={}",state.target(),packet.generation(),distance,scale,packet.sequence());}
        }
        finally{RenderSystem.setShaderFogStart(fogStart);RenderSystem.setShaderFogEnd(fogEnd);poses.popPose();}
    }
    private RamielDistantViewR52(){}
}
