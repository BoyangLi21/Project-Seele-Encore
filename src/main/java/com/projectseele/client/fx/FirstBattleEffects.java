package com.projectseele.client.fx;

import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.VertexConsumer;
import com.mojang.math.Axis;
import com.projectseele.ProjectSeele;
import com.projectseele.client.render.RibbonRenderer;
import com.projectseele.config.SeeleConfig;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.FirstBattleClip;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.LevelRenderer;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.core.BlockPos;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.RenderLevelStageEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import org.joml.Matrix4f;
import org.joml.Vector3f;

/** World-space tear geometry and a small original rib prop follow the actor timeline. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID,value=Dist.CLIENT)
public final class FirstBattleEffects
{
    private static final RenderType FIELD=RenderType.debugQuads();
    private static final RenderType BONE=RenderType.entityCutoutNoCull(new ResourceLocation("minecraft","textures/block/bone_block_side.png"));
    private static final double[][] OCTAGON={{-7.5,-18},{7.5,-18},{18,-7.5},{18,7.5},{7.5,18},{-7.5,18},{-18,7.5},{-18,-7.5}};
    @SubscribeEvent public static void render(RenderLevelStageEvent event)
    {
        var mc=Minecraft.getInstance();if(mc.level==null||event.getStage()!=RenderLevelStageEvent.Stage.AFTER_PARTICLES)return;
        var buffers=mc.renderBuffers().bufferSource();boolean drewField=false,drewBone=false;
        for(var actor:mc.level.entitiesForRendering())
        {
            if(!(actor instanceof EvaUnit01Entity eva)||!eva.isFirstBattleActive()||!FirstBattleClip.ready())continue;
            var signals=eva.firstBattleSignals();var spec=signals.spec(eva);float seconds=signals.time(eva,event.getPartialTick()),t=FirstBattleClip.referenceSeconds(seconds);var pose=event.getPoseStack();Vec3 cam=event.getCamera().getPosition();
            pose.pushPose();pose.translate(spec.origin().x-cam.x,spec.origin().y-cam.y,spec.origin().z-cam.z);pose.mulPose(Axis.YP.rotationDegrees(-spec.yaw()));
            float intensity=SeeleConfig.FX_INTENSITY.get().floatValue();
            if(t>.5&&t<5.1&&intensity>0){field(pose.last().pose(),buffers.getBuffer(FIELD),t,intensity);drewField=true;}
            if(t>=12.75&&t<16.8&&intensity>0)
            {
                Vec3 core=FirstBattleClip.localPoint(spec,false,"core_blocks",seconds).add(0,.4,0);var out=buffers.getBuffer(FIELD);int cracks=t>14.15?7:4;
                for(int i=0;i<cracks;i++)
                {
                    double angle=i*Math.PI*2/cracks+.2;Vec3 a=core.add(Math.cos(angle)*.12,0,Math.sin(angle)*.12),b=core.add(Math.cos(angle+.18)*1.8,.035,Math.sin(angle+.18)*1.8);
                    RibbonRenderer.drawStarRibbon(pose.last().pose(),out,vec(a),vec(b),.055F,.018F,1,.40F,.08F,.85F*intensity);
                }
                drewField=true;
            }
            if(t>=15.35&&t<16.9)
            {
                Vec3 hand=FirstBattleClip.localPoint(spec,true,"hand_r_blocks",seconds),world=FirstBattleClip.world(spec,hand);int light=LevelRenderer.getLightColor(mc.level,BlockPos.containing(world));
                Vec3 tip=FirstBattleClip.hasCurve(true,"rib_tip_blocks")?FirstBattleClip.localPoint(spec,true,"rib_tip_blocks",seconds):hand.add(0,-6.05,0);
                Vec3 side=FirstBattleClip.hasCurve(true,"rib_side_blocks")?FirstBattleClip.localPoint(spec,true,"rib_side_blocks",seconds).subtract(hand):new Vec3(1,0,0);
                rib(pose,buffers.getBuffer(BONE),hand,tip,side,light);drewBone=true;
            }
            pose.popPose();
        }
        if(drewField)buffers.endBatch(FIELD);if(drewBone)buffers.endBatch(BONE);
    }
    private static Vector3f vec(Vec3 p){return new Vector3f((float)p.x,(float)p.y,(float)p.z);}
    private static float gap(double y,float tear,float t)
    {
        return Math.max(0,tear*(float)(13*Math.max(0,1-Math.abs(y)/24)+.25*Math.sin(y*2.3+t*3)));
    }
    private static double width(double y){return Math.min(18,25.5-Math.abs(y));}
    private static void field(Matrix4f pose,VertexConsumer out,float t,float intensity)
    {
        float tear=FirstBattleClip.smooth((t-3)/2),visible=FirstBattleClip.smooth((t-.5F)/.7F)*(1-FirstBattleClip.smooth((t-4.65F)/.45F));
        for(int y=-18;y<18;y++)for(int side:new int[]{-1,1})
        {
            double inner0=gap(y,tear,t),inner1=gap(y+1,tear,t),outer0=width(y),outer1=width(y+1);
            if(inner0>=outer0||inner1>=outer1)continue;
            quad(pose,out,new Vec3(side*inner0,40+y,21),new Vec3(side*outer0,40+y,21),new Vec3(side*outer1,41+y,21),new Vec3(side*inner1,41+y,21),1,.36F,.055F,.075F*visible*intensity);
            if(tear>0)
                RibbonRenderer.drawStarRibbon(pose,out,new Vector3f((float)(side*inner0),40+y,20.97F),new Vector3f((float)(side*inner1),41+y,20.97F),.055F,.055F,1,.76F,.36F,visible*intensity);
        }
        for(double scale:new double[]{1,.84,.67,.49,.30})for(int edge=0;edge<8;edge++)for(int piece=0;piece<8;piece++)
        {
            double[] a=OCTAGON[edge],b=OCTAGON[(edge+1)%8];double u=piece/8D,v=(piece+1)/8D;
            double x0=(a[0]*(1-u)+b[0]*u)*scale,y0=(a[1]*(1-u)+b[1]*u)*scale,x1=(a[0]*(1-v)+b[0]*v)*scale,y1=(a[1]*(1-v)+b[1]*v)*scale;
            if(Math.abs((x0+x1)/2)<gap((y0+y1)/2,tear,t))continue;
            RibbonRenderer.drawStarRibbon(pose,out,new Vector3f((float)x0,40+(float)y0,20.93F),new Vector3f((float)x1,40+(float)y1,20.93F),.07F,.07F,1,.58F,.14F,.58F*visible*intensity);
        }
    }
    private static void quad(Matrix4f pose,VertexConsumer out,Vec3 a,Vec3 b,Vec3 c,Vec3 d,float r,float g,float bcol,float alpha)
    {
        for(Vec3 p:new Vec3[]{a,b,c,d,d,c,b,a})out.vertex(pose,(float)p.x,(float)p.y,(float)p.z).color(r,g,bcol,alpha).endVertex();
    }
    private static Vec3 ribPoint(Vec3 hand,Vec3 tip,Vec3 side,double t){return hand.lerp(tip,t).add(side.scale(.8*Math.sin(t*Math.PI)));}
    private static void rib(PoseStack pose,VertexConsumer out,Vec3 hand,Vec3 tip,Vec3 outward,int light)
    {
        for(int i=0;i<7;i++)
        {
            double t=i/7D,u=(i+1)/7D;Vec3 a=ribPoint(hand,tip,outward,t),b=ribPoint(hand,tip,outward,u),axis=b.subtract(a).normalize();Vec3 side=outward.subtract(axis.scale(outward.dot(axis))).normalize();Vec3 other=axis.cross(side).normalize();
            double wa=.25*(1-t)+.025,wb=.25*(1-u)+.025;
            Vec3[] ring={side.add(other),side.subtract(other),side.scale(-1).subtract(other),other.subtract(side)};
            for(int face=0;face<4;face++)
            {
                Vec3 ra=ring[face],rb=ring[(face+1)%4],normal=ra.add(rb).normalize();Vec3[] points={a.add(ra.scale(wa)),a.add(rb.scale(wa)),b.add(rb.scale(wb)),b.add(ra.scale(wb))};
                for(int n=0;n<4;n++)
                {
                    Vec3 p=points[n];out.vertex(pose.last().pose(),(float)p.x,(float)p.y,(float)p.z).color(223,220,196,255).uv(n==0||n==3?0:1,n<2?0:1).overlayCoords(0).uv2(light)
                            .normal(pose.last().normal(),(float)normal.x,(float)normal.y,(float)normal.z).endVertex();
                }
            }
        }
    }
    private FirstBattleEffects() {}
}
