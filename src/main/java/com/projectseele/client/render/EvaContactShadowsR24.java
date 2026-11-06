package com.projectseele.client.render;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.EvaUnit01Entity;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.*;
import net.minecraft.client.renderer.texture.OverlayTexture;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.level.ClipContext;
import net.minecraft.world.phys.*;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.RenderLevelStageEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import org.joml.Matrix4f;
import org.joml.Vector3f;
import java.util.*;
import com.projectseele.entity.FirstBattleSignals;
import com.mojang.blaze3d.vertex.BufferBuilder;
import com.mojang.blaze3d.vertex.DefaultVertexFormat;
import com.mojang.blaze3d.vertex.VertexFormat;
import net.minecraftforge.eventbus.api.EventPriority;

/** Contact shade under the actual submitted toes/kneepads in the directed ground grapple. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID,value=Dist.CLIENT)
public final class EvaContactShadowsR24
{
    private record Contact(Vec3 point,float radius,float alpha,long frame,float sole,double floor){}
    private static final Map<EvaUnit01Entity,Map<String,Contact>> CONTACTS=new WeakHashMap<>();
    private static final ResourceLocation TEXTURE=new ResourceLocation("minecraft","textures/misc/shadow.png");
    // Oculus defers the global entity buffer and its endBatch(type) is a no-op.
    // Draw after Iris's deferred pass, which begins at the translucent phase.
    private static final MultiBufferSource.BufferSource DECALS=MultiBufferSource.immediate(new BufferBuilder(4096));
    public static void capture(EvaUnit01Entity eva,String part,float[] vertices,int stride,float px,float py,float pz,Matrix4f matrix)
    {
        if(!eva.isFirstBattleActive()||ShaderShadowPassR44.active()||!(part.startsWith("foot_")||part.startsWith("shin_")))return;
        long frame=FirstBattleSignals.clientFrameTime();var slots=CONTACTS.computeIfAbsent(eva,key->new HashMap<>());var old=slots.get(part);
        if(old!=null&&old.frame==frame)return;
        float minimum=Float.POSITIVE_INFINITY;Vector3f point=new Vector3f();
        for(int i=0;i<vertices.length;i+=stride)
        {matrix.transformPosition(point.set(-(vertices[i]+px)/16,(vertices[i+1]+py)/16,(vertices[i+2]+pz)/16));minimum=Math.min(minimum,point.y);}
        double x=0,z=0;int count=0;
        for(int i=0;i<vertices.length;i+=stride)
        {
            matrix.transformPosition(point.set(-(vertices[i]+px)/16,(vertices[i+1]+py)/16,(vertices[i+2]+pz)/16));
            if(point.y<=minimum+.30){x+=point.x;z+=point.z;count++;}
        }
        if(count==0)return;x/=count;z/=count;float radius=part.startsWith("foot_")?4.1F:2.5F;
        Vec3 centre=new Vec3(x,minimum,z);double floor=ground(eva,centre);
        float alpha=Double.isFinite(floor)?(float)(.34*Math.max(0,1-Math.max(0,minimum-floor)/1.8)):0;
        if(alpha>0)
            for(double[] edge:new double[][]{{-radius,-radius},{radius,-radius},{-radius,radius},{radius,radius}})
            {
                double height=ground(eva,centre.add(edge[0],0,edge[1]));
                if(!Double.isFinite(height)||Math.abs(height-floor)>.15){alpha=0;break;}
            }
        slots.put(part,new Contact(new Vec3(x,Double.isFinite(floor)?floor+.018:minimum,z),radius,alpha,frame,minimum,floor));
    }
    private static double ground(EvaUnit01Entity eva,Vec3 near)
    {
        var hit=eva.level().clip(new ClipContext(near.add(0,.35,0),near.add(0,-2,0),ClipContext.Block.COLLIDER,ClipContext.Fluid.NONE,eva));
        return hit.getType()==HitResult.Type.BLOCK?hit.getLocation().y:Double.NaN;
    }
    @SubscribeEvent(priority=EventPriority.LOWEST) public static void render(RenderLevelStageEvent event)
    {
        if(event.getStage()!=RenderLevelStageEvent.Stage.AFTER_TRANSLUCENT_BLOCKS||ShaderShadowPassR44.active()||CONTACTS.isEmpty())return;var mc=Minecraft.getInstance();if(mc.level==null)return;
        var pose=event.getPoseStack();var camera=event.getCamera().getPosition();long frame=FirstBattleSignals.clientFrameTime();var type=ContactLayer.TYPE;var target=DECALS.getBuffer(type);
        pose.pushPose();pose.translate(-camera.x,-camera.y,-camera.z);
        for(var entry:List.copyOf(CONTACTS.entrySet()))
        {
            var actor=entry.getKey();if(actor==null||actor.level()!=mc.level||!actor.isFirstBattleActive())continue;
            for(var sample:entry.getValue().entrySet())
            {
                var contact=sample.getValue();
                if(contact.alpha<=0||contact.frame!=frame)continue;
                float x=(float)contact.point.x,y=(float)contact.point.y,z=(float)contact.point.z,r=contact.radius;
                vertex(target,pose,x-r,y,z-r,0,0,contact.alpha);vertex(target,pose,x-r,y,z+r,0,1,contact.alpha);
                vertex(target,pose,x+r,y,z+r,1,1,contact.alpha);vertex(target,pose,x+r,y,z-r,1,0,contact.alpha);
            }
        }
        pose.popPose();
        DECALS.endBatch(type);
    }
    private static void vertex(com.mojang.blaze3d.vertex.VertexConsumer target,com.mojang.blaze3d.vertex.PoseStack pose,float x,float y,float z,float u,float v,float alpha)
    {target.vertex(pose.last().pose(),x,y,z).color(0F,0F,0F,alpha).uv(u,v).overlayCoords(OverlayTexture.NO_OVERLAY).uv2(LightTexture.FULL_BRIGHT).normal(pose.last().normal(),0,1,0).endVertex();}
    private abstract static class ContactLayer extends RenderType
    {
        // Keep Iris's entity shader override, but do not replace the ground's
        // depth with the transparent rectangle surrounding a radial shadow.
        private static final RenderType TYPE=create("seele_ground_contact_r52",DefaultVertexFormat.NEW_ENTITY,
                VertexFormat.Mode.QUADS,4096,false,false,CompositeState.builder()
                        .setShaderState(RENDERTYPE_ENTITY_TRANSLUCENT_SHADER)
                        .setTextureState(new TextureStateShard(TEXTURE,true,false))
                        .setTransparencyState(TRANSLUCENT_TRANSPARENCY).setCullState(NO_CULL)
                        .setLightmapState(LIGHTMAP).setOverlayState(OVERLAY)
                        .setDepthTestState(LEQUAL_DEPTH_TEST).setWriteMaskState(COLOR_WRITE)
                        .setLayeringState(VIEW_OFFSET_Z_LAYERING).createCompositeState(false));
        private ContactLayer(){super("seele_ground_contact_definition",DefaultVertexFormat.NEW_ENTITY,
                VertexFormat.Mode.QUADS,256,false,false,()->{},()->{});}
    }
    private EvaContactShadowsR24(){}
}
