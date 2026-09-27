package com.projectseele.client.fx;

import com.projectseele.network.*;
import com.mojang.blaze3d.vertex.VertexConsumer;
import net.minecraft.client.Minecraft;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.sounds.SoundEvent;
import net.minecraft.sounds.SoundSource;
import net.minecraft.util.Mth;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.RenderLevelStageEvent;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import org.joml.Matrix4f;
import org.joml.Vector3f;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.client.renderer.LightTexture;
import net.minecraft.client.renderer.texture.OverlayTexture;
import java.util.ArrayList;
import java.util.List;

/** A finite visual cloud: no blocks, damage, light updates or unbounded particles. */
@Mod.EventBusSubscriber(modid="projectseele",value=Dist.CLIENT)
public final class BattleFinaleClientR29
{
    private record Blast(Vec3 point,long started) {}
    private static final List<Blast> BLASTS=new ArrayList<>();
    private static ClientLevel world;
    public static int received;
    public static void accept(ClientboundBattleFinalePacket p)
    {
        var mc=Minecraft.getInstance();if(mc.level==null)return;
        if(world!=mc.level){BLASTS.clear();world=mc.level;}
        Vec3 point=new Vec3(p.x(),p.y(),p.z());received++;
        if(com.projectseele.visual.TvCampaignR24Review.R29)com.projectseele.visual.TvCampaignR24Review.finalePackets++;
        if(BLASTS.size()>=4)BLASTS.remove(0);
        BLASTS.add(new Blast(point,mc.level.getGameTime()));
        ClientFxManager.addNukeFx(new ClientboundNukeFxPacket(p.x(),p.y()+12,p.z(),4.8F,false),false);
        ClientFxManager.addCrossExplosion(new ClientboundCrossExplosionPacket(p.x(),p.y(),p.z(),2.2F));
        mc.level.playLocalSound(p.x(),p.y()+25,p.z(),SoundEvent.createVariableRangeEvent(new ResourceLocation("projectseele","angel_nuclear_finale")),SoundSource.HOSTILE,5F,1F,false);
    }
    @SubscribeEvent public static void tick(TickEvent.ClientTickEvent event)
    {
        if(event.phase!=TickEvent.Phase.END)return;
        var level=Minecraft.getInstance().level;
        if(level!=world){BLASTS.clear();world=level;return;}
        if(level!=null)BLASTS.removeIf(b->level.getGameTime()-b.started>240);
    }
    @SubscribeEvent public static void render(RenderLevelStageEvent event)
    {
        if(event.getStage()!=RenderLevelStageEvent.Stage.AFTER_PARTICLES||world==null||BLASTS.isEmpty())return;
        float strength=com.projectseele.config.SeeleConfig.FX_INTENSITY.get().floatValue();if(strength<=0)return;
        var mc=Minecraft.getInstance();var buffers=mc.renderBuffers().bufferSource();var type=FinaleSmokeTextureR42.layer();var consumer=buffers.getBuffer(type);var poses=event.getPoseStack();var camera=event.getCamera().getPosition();
        for(var blast:BLASTS)
        {
            float age=world.getGameTime()-blast.started+event.getPartialTick();
            float growth=Mth.clamp((age-5)/75,0,1),fade=Mth.clamp((240-age)/90,0,1);
            if(growth<=0)continue;
            float alpha=.87F*fade*Math.min(strength,1),rise=22+93*growth;
            poses.pushPose();poses.translate(blast.point.x-camera.x,blast.point.y-camera.y,blast.point.z-camera.z);
            var matrix=poses.last().pose();
            for(int i=0;i<8;i++)
            {
                float y=rise*i/8F,swirl=age*.012F+i*1.7F;
                puff(matrix,consumer,Mth.sin(swirl)*5,y,Mth.cos(swirl)*5,8+growth*10,15,8+growth*10,alpha,.29F+i*.015F);
            }
            for(int ring=0;ring<2;ring++)for(int i=0;i<14;i++)
            {
                float angle=(float)(i*Math.PI*2/14)+ring*.18F,reach=(22+48*growth)*(ring==0?.58F:1);
                float size=13+18*growth+(i%3)*2;
                float heat=(float)Math.exp(-Math.max(0,age-18)/32F);
                puff(matrix,consumer,Mth.cos(angle)*reach,rise+ring*12+(i%2)*5,Mth.sin(angle)*reach,size,size*.62F,size,alpha,(ring==0?.20F:.14F)+.32F*heat);
            }
            // Low rolling dust bank carries the shock front across the square.
            float spread=Math.min(1,age/70F);
            for(int i=0;i<18;i++)
            {
                float angle=(float)(i*Math.PI*2/18),radius=25+100*spread;
                puff(matrix,consumer,Mth.cos(angle)*radius,5+3*growth,Mth.sin(angle)*radius,14,6,14,alpha*.56F,.43F);
            }
            poses.popPose();
        }
        buffers.endBatch(type);
    }
    private static void puff(Matrix4f m,VertexConsumer out,float x,float y,float z,float rx,float ry,float rz,float alpha,float tone)
    {
        // A density cloud has soft, irregular edges; a stack of translucent
        // latitude/longitude meshes looked like inflated plastic spheres.
        // Billboards also remove tens of thousands of redundant vertices.
        var rotation=Minecraft.getInstance().gameRenderer.getMainCamera().rotation();
        Vector3f right=rotation.transform(new Vector3f(rx,0,0));
        Vector3f up=rotation.transform(new Vector3f(0,ry,0));
        Vector3f normal=m.transformDirection(rotation.transform(new Vector3f(0,0,1))).normalize();
        float value=Mth.clamp(tone+.24F,.28F,.92F);
        for(float[] corner:new float[][]{{-1,-1,0,1},{1,-1,1,1},{1,1,1,0},{-1,1,0,0}})
        {
            Vector3f point=new Vector3f(x,y,z).fma(corner[0]*1.3F,right).fma(corner[1]*1.3F,up);
            out.vertex(m,point.x,point.y,point.z).color(value,value*.97F,value*.92F,alpha*.62F)
                    .uv(corner[2],corner[3]).overlayCoords(OverlayTexture.NO_OVERLAY).uv2(LightTexture.FULL_BRIGHT)
                    .normal(normal.x,normal.y,normal.z).endVertex();
        }
    }
    private BattleFinaleClientR29() {}
}
