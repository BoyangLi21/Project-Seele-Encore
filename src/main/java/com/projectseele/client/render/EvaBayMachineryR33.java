package com.projectseele.client.render;

import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.math.Axis;
import com.projectseele.entity.*;
import net.minecraft.client.renderer.LightTexture;
import org.joml.Vector3f;
import org.joml.Quaternionf;

/** Twelve rail-mounted service arms; all links are opaque rigid geometry. */
public final class EvaBayMachineryR33
{
    private static final java.util.Map<Integer,Vector3f[]> TARGETS=new java.util.HashMap<>();
    public static void clearCache(){TARGETS.clear();}
    private static Vector3f[] targets(int variant)
    {
        if(TARGETS.isEmpty())try(var reader=net.minecraft.client.Minecraft.getInstance().getResourceManager()
                .getResource(new net.minecraft.resources.ResourceLocation("projectseele","mesh/bay_service_targets_r33.json")).orElseThrow().openAsReader())
        {
            var data=com.google.gson.JsonParser.parseReader(reader).getAsJsonObject().getAsJsonObject("targets");
            for(var entry:data.entrySet())
            {var list=entry.getValue().getAsJsonArray();Vector3f[] values=new Vector3f[list.size()];for(int i=0;i<values.length;i++){var a=list.get(i).getAsJsonArray();values[i]=new Vector3f(a.get(0).getAsFloat(),a.get(1).getAsFloat(),a.get(2).getAsFloat());}TARGETS.put(Integer.parseInt(entry.getKey()),values);}
        }
        catch(Exception failure){throw new IllegalStateException("Repair contact geometry missing",failure);}
        return TARGETS.get(variant);
    }
    public static void render(PoseStack p,EvaUnit01Entity e,float partial)
    {
        if(!(e instanceof EvaPrototypeEntity un)||!un.isInsideTestHangar()||e.position().distanceToSqr(un.homePosition())>16)return;
        p.pushPose();p.mulPose(Axis.YP.rotationDegrees(180-e.getYRot()));
        render(p,EvaBayRepairR33.active(e)?EvaBayRepairR33.progress(e,partial):-1,e.tickCount+partial,22,true,3+un.getUNSerial());p.popPose();
    }
    public static void render(PoseStack p,float phase,float time,float width,boolean wide,int variant)
    {
        float engagement=phase<0?0:EvaDorsalMechanism.smooth(Math.min(phase/.05F,(1-phase)/.05F));
        Vector3f[] contacts=targets(variant);
        p.pushPose();
        for(int side:new int[]{-1,1})
        {
            p.pushPose();p.translate(side*width,0,4.3);TvFacilityMeshes.draw("repair_rail",p,LightTexture.FULL_BRIGHT);p.popPose();
            for(int i=0;i<6;i++)
            {
                Vector3f contact=contacts[(side<0?0:6)+i];float y=contact.y;
                float oscillation=(float)Math.sin(time*.018+i*1.3+side)*.22F*engagement;
                Vector3f a=new Vector3f(side*width,y,4.3F);
                Vector3f b=new Vector3f(side*(width+(wide?.4F:.9F)+(wide?.9F:1.4F)*engagement),y+2.1F+oscillation,2-14.4F*engagement);
                Vector3f c=new Vector3f(side*(width-1),y-1,2).lerp(new Vector3f(contact).add(0,0,-.64F),engagement);
                // The wrist first clears the front of the fixed restraints;
                // its last link then approaches normal to the measured skin.
                Vector3f wrist=new Vector3f(c.x,c.y,2-12*engagement);
                at(p,"repair_base",a);link(p,a,b);at(p,"repair_joint",b);link(p,b,wrist);at(p,"repair_joint",wrist);
                if(wrist.distanceSquared(c)>.0001F)link(p,wrist,c);
                p.pushPose();p.translate(c.x,c.y,c.z);p.mulPose(new Quaternionf().rotationTo(new Vector3f(0,1,0),new Vector3f(0,0,1)));
                TvFacilityMeshes.draw("repair_tool",p,LightTexture.FULL_BRIGHT);
                if(engagement>.99F&&(int)(time+i*7)%17<5){p.translate(0,.64,0);TvFacilityMeshes.draw("repair_arc",p,LightTexture.FULL_BRIGHT);}
                p.popPose();
            }
        }
        p.popPose();
    }
    private static void at(PoseStack p,String part,Vector3f v)
    {p.pushPose();p.translate(v.x,v.y,v.z);TvFacilityMeshes.draw(part,p,LightTexture.FULL_BRIGHT);p.popPose();}
    private static void link(PoseStack p,Vector3f a,Vector3f b)
    {
        Vector3f d=new Vector3f(b).sub(a);p.pushPose();p.translate(a.x,a.y,a.z);
        p.mulPose(new Quaternionf().rotationTo(new Vector3f(0,1,0),new Vector3f(d).normalize()));p.scale(1,d.length(),1);
        TvFacilityMeshes.draw("repair_link",p,LightTexture.FULL_BRIGHT);p.popPose();
    }
    private EvaBayMachineryR33(){}
}
