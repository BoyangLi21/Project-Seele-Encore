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
        // The drill reaches from the core down to the armour front, which can lie below the body's box.
        if((state.flags()&ClientboundEncounterObserverPacket.DRILLING)!=0&&state.drillDepth()>0)
            box=box.minmax(new AABB(state.position().add(-3,state.height()*.5-state.drillDepth()-3,-3),state.position().add(3,state.height()*.5,3)));
        if(state.beamTicks()>view.ageClientTicks())box=box.minmax(new AABB(state.position(),state.beamEnd()).inflate(10));
        if(!event.getFrustum().isVisible(box))return;
        var poses=event.getPoseStack();float fogStart=RenderSystem.getShaderFogStart(),fogEnd=RenderSystem.getShaderFogEnd();
        poses.pushPose();poses.translate(state.position().x-camera.x,state.position().y-camera.y,state.position().z-camera.z);
        try
        {
            float distance=(float)state.position().distanceTo(camera);
            float haze=hazeR64(distance);
            if(haze<=0){RenderSystem.setShaderFogStart(Math.max(fogStart,distance+64));RenderSystem.setShaderFogEnd(Math.max(fogEnd,distance+512));}
            else{RenderSystem.setShaderFogStart(0);RenderSystem.setShaderFogEnd(distance/haze);}
            var horizon=RamielHorizonClipR64.profile(camera,state);
            if(horizon==null||!horizon.any())
            {RamielRenderer.renderObservedR52(state,event.getPartialTick(),view.ageClientTicks(),poses,BUFFERS);BUFFERS.endBatch();}
            else
            {
                drawAboveHorizonR64(event,horizon,state,poses,view.ageClientTicks());
                RamielRenderer.renderObservedR52(state,event.getPartialTick(),view.ageClientTicks(),poses,BUFFERS,false,true);BUFFERS.endBatch();
            }
            if(EncounterObserverCacheR45.markDrawn(packet)&&!state.target().equals(reported))
            {reported=state.target();com.projectseele.ProjectSeele.LOGGER.info("R52 real distant Ramiel frame drawn: uuid={} generation={} distance={} scale={} sequence={}",state.target(),packet.generation(),distance,scale,packet.sequence());}
        }
        finally{RenderSystem.setShaderFogStart(fogStart);RenderSystem.setShaderFogEnd(fogEnd);poses.popPose();}
    }
    /**
     * The body and drill drawn in vertical slices, each under a scissor that keeps only what lies above the far
     * horizon in that slice (RamielHorizonClipR64). Scissor touches neither depth nor colour targets, so it behaves
     * the same with and without a shader pack.
     */
    private static void drawAboveHorizonR64(RenderLevelStageEvent event,RamielHorizonClipR64.Profile h,
            ClientboundEncounterObserverPacket.Snapshot state,com.mojang.blaze3d.vertex.PoseStack poses,long age)
    {
        var target=Minecraft.getInstance().getMainRenderTarget();int width=target.width,height=target.height;
        var view=new Matrix4f(event.getPoseStack().last().pose());var projection=event.getProjectionMatrix();
        var camera=event.getCamera().getPosition();
        int n=RamielHorizonClipR64.COLUMNS;double step=2*h.halfAngle()/(n-1);
        boolean scissor=false;
        try
        {
            for(int i=0;i<n;i++)
            {
                double e=h.elevation()[i];
                if(e==Double.POSITIVE_INFINITY)continue;
                double az=h.azimuth(i);
                // the slice's left and right edges (the outer slices reach well past the body), and its horizon height
                double a0=az-step*(i==0?40:.5),a1=az+step*(i==n-1?40:.5);
                float[] p0=screen(view,projection,camera,h,a0,0,width,height),p1=screen(view,projection,camera,h,a1,0,width,height);
                if(p0==null||p1==null)continue;
                int x0=(int)Math.floor(Math.max(0,Math.min(p0[0],p1[0]))),x1=(int)Math.ceil(Math.min(width,Math.max(p0[0],p1[0])));
                if(x1<=x0)continue;
                int y0=0;
                if(!Double.isNaN(e))
                {
                    float[] ph=screen(view,projection,camera,h,az,e,width,height);
                    if(ph==null)continue;
                    y0=(int)Math.max(0,Math.min(height,Math.ceil(ph[1])));
                }
                if(y0>=height)continue;
                com.mojang.blaze3d.systems.RenderSystem.enableScissor(x0,y0,x1-x0,height-y0);scissor=true;
                RamielRenderer.renderObservedR52(state,event.getPartialTick(),age,poses,BUFFERS,true,false);BUFFERS.endBatch();
            }
        }
        finally{if(scissor)com.mojang.blaze3d.systems.RenderSystem.disableScissor();}
    }
    /** Framebuffer pixel (origin bottom left) of the point at the Angel's axis distance in this direction. */
    private static float[] screen(Matrix4f view,Matrix4f projection,net.minecraft.world.phys.Vec3 camera,RamielHorizonClipR64.Profile h,double azimuth,double elevation,int width,int height)
    {
        double d=h.horizontal();
        var p=new org.joml.Vector4f((float)(h.camera().x+Math.cos(azimuth)*d-camera.x),(float)(h.camera().y+Math.tan(elevation)*d-camera.y),(float)(h.camera().z+Math.sin(azimuth)*d-camera.z),1);
        view.transform(p);projection.transform(p);
        if(p.w<=1e-4F)return null;
        return new float[]{(p.x/p.w*.5F+.5F)*width,(p.y/p.w*.5F+.5F)*height};
    }
    /**
     * Share of the fog colour laid over the far Angel: none within 384 blocks, rising to 35 % at about 2.2 km, so at the
     * Yashima range it reads as standing out in the air over the city instead of sharp just behind the ridge, while the
     * body stays clearly visible. Linear fog from 0 to distance/haze gives exactly this share at the Angel's distance.
     */
    static float hazeR64(float distance)
    {return Math.min(.35F,Math.max(0F,(distance-384F)/5200F));}
    private RamielDistantViewR52(){}
}
