package com.projectseele.client.fx;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.SachielEntity;
import com.projectseele.entity.SachielArmorBeamR52;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.RenderLevelStageEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Synced windup at the actual posed skull precedes the existing visible energy-beam FX. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID,value=Dist.CLIENT)
public final class SachielArmorChargeR52
{
    @SubscribeEvent public static void render(RenderLevelStageEvent event)
    {
        if(event.getStage()!=RenderLevelStageEvent.Stage.AFTER_ENTITIES)return;
        var mc=Minecraft.getInstance();if(mc.level==null)return;
        var buffers=mc.renderBuffers().bufferSource();var buffer=buffers.getBuffer(RenderType.lightning());var matrix=event.getPoseStack().last().pose();
        Vec3 camera=event.getCamera().getPosition();
        for(var entity:mc.level.entitiesForRendering())if(entity instanceof SachielEntity actor&&actor.isArmorBeamR52())
        {
            float age=actor.armorBeamAgeR52(event.getPartialTick());if(age>=SachielArmorBeamR52.CHARGE)continue;
            float weight=Math.min(1,age/SachielArmorBeamR52.CHARGE);Vec3 centre=SachielArmorBeamR52.origin(actor,event.getPartialTick()).subtract(camera);
            double radius=.12+1.25*weight;float alpha=.2F+.6F*weight;
            for(int axis=0;axis<3;axis++)for(int i=0;i<16;i++)
            {
                double a=i*Math.PI/8,b=(i+1)*Math.PI/8;
                for(double[] p:new double[][]{{a,radius*.75},{a,radius},{b,radius},{b,radius*.75}})
                {
                    double x=Math.cos(p[0])*p[1],y=Math.sin(p[0])*p[1];
                    Vec3 v=centre.add(axis==0?new Vec3(x,y,0):axis==1?new Vec3(0,x,y):new Vec3(y,0,x));
                    buffer.vertex(matrix,(float)v.x,(float)v.y,(float)v.z).color(1F,.74F,.83F,alpha).endVertex();
                }
            }
        }
        buffers.endBatch(RenderType.lightning());
    }
    private SachielArmorChargeR52(){}
}
