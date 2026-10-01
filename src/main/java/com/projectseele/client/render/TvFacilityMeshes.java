package com.projectseele.client.render;

import com.google.gson.JsonParser;
import com.mojang.blaze3d.systems.RenderSystem;
import com.mojang.blaze3d.vertex.*;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.EvaDorsalMechanism;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.SiloHatchMechanism;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.GameRenderer;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.resources.ResourceLocation;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;

/** Original TV-style rigid machinery, with each moving assembly baked only once. */
public final class TvFacilityMeshes
{
    private static final Map<String,RigidMachineryPartR44> PARTS=new HashMap<>();
    private static final Map<Integer,float[][]> CARRIER_MOUNTS=new HashMap<>();
    private static final ThreadLocal<MultiBufferSource> ACTIVE_BUFFERS=new ThreadLocal<>();
    private static boolean attempted;
    /** Preserve the caller's normal/shadow/outline pass for nested machinery. */
    public static void withBuffers(MultiBufferSource buffers,Runnable rendering)
    {
        var previous=ACTIVE_BUFFERS.get();ACTIVE_BUFFERS.set(buffers);
        try{rendering.run();}
        finally{if(previous==null)ACTIVE_BUFFERS.remove();else ACTIVE_BUFFERS.set(previous);}
    }
    static MultiBufferSource currentBuffers()
    {
        var buffers=ACTIVE_BUFFERS.get();
        return buffers!=null?buffers:Minecraft.getInstance().renderBuffers().bufferSource();
    }
    public static void clearCache()
    {
        Runnable release=()->{RigidMachineryGpuR44.clear();PARTS.clear();CARRIER_MOUNTS.clear();attempted=false;EvaBayMachineryR33.clearCache();PlugGantryRenderer.clearCache();TvShoulderRestraintsR44.clearCache();TvCageEnclosureR44.clearCache();};
        if(RenderSystem.isOnRenderThread())release.run();else RenderSystem.recordRenderCall(release::run);
    }
    private static void load()
    {
        if(attempted)return;attempted=true;
        try(var stream=Minecraft.getInstance().getResourceManager().open(new ResourceLocation(ProjectSeele.MODID,"mesh/tv_facilities_r16.json"));
            var reader=new InputStreamReader(stream,StandardCharsets.UTF_8))
        {
            var resource=JsonParser.parseReader(reader).getAsJsonObject();var parts=resource.getAsJsonObject("parts");
            if(resource.has("carrier_actuator_mounts"))for(var entry:resource.getAsJsonObject("carrier_actuator_mounts").entrySet())
            {
                var rows=entry.getValue().getAsJsonArray();float[][] mounts=new float[rows.size()][4];
                for(int i=0;i<rows.size();i++)for(int j=0;j<4;j++)mounts[i][j]=rows.get(i).getAsJsonArray().get(j).getAsFloat();
                CARRIER_MOUNTS.put(Integer.parseInt(entry.getKey()),mounts);
            }
            for(var part:parts.entrySet())
            {
                PARTS.put(part.getKey(),RigidMachineryPartR44.triangles(part.getValue().getAsJsonArray()));
            }
            ProjectSeele.LOGGER.info("TV facility machinery loaded: {} rigid assemblies",PARTS.size());
        }
        catch(Exception e){ProjectSeele.LOGGER.error("TV facility machinery resource rejected",e);}
    }
    public static void draw(String part,PoseStack poses,int light)
    {draw(part,poses,light,1);}
    private static void draw(String part,PoseStack poses,int light,float opacity)
    {
        load();RigidMachineryPartR44 mesh=PARTS.get(part);if(mesh==null)return;
        mesh.draw(poses,currentBuffers(),light);
    }
    public static float[] partBounds(String part)
    {load();var mesh=PARTS.get(part);return mesh==null?null:mesh.bounds();}
    private static float ramp(float value,float a,float b){return EvaDorsalMechanism.smooth((value-a)/(b-a));}
    public static void cage(PoseStack poses,int light,float closed)
    {cage(poses,light,closed,-1);}
    public static void cage(PoseStack poses,int light,float closed,int variant)
    {
        float opening=1-closed;
        boolean tvEnclosure=TvCageEnclosureR44.render(variant,opening,poses,light);
        if(!tvEnclosure)draw("cage_frame",poses,light);
        boolean measuredShoulders=TvShoulderRestraintsR44.render(variant,opening,poses,light,!tvEnclosure);
        for(int side:new int[]{-1,1})
        {
            poses.pushPose();poses.scale(side,1,1);
            float shoulder=5.35F*ramp(opening,.23F,.88F),arm=3.3F*ramp(opening,.12F,.83F),leg=7.4F*ramp(opening,.35F,.96F);
            if(!measuredShoulders)
            {
                poses.pushPose();poses.translate(shoulder,2.1*ramp(opening,0,.25F),0);draw("shoulder_pin",poses,light);poses.popPose();
                poses.pushPose();poses.translate(shoulder,0,0);draw("shoulder_jaw",poses,light);poses.popPose();
                rod(poses,light,"shoulder_rod",8.8F+shoulder,Math.max(.04F,5.1F-shoulder));
            }
            if(!tvEnclosure)
            {
                // The complete legacy guard/ram pair was authored outside
                // the actual arms; it is not a valid closed TV contact.
                poses.pushPose();poses.translate(arm,0,0);draw("arm_guard",poses,light);poses.popPose();
                rod(poses,light,"arm_rod",10.8F+arm,3.8F-arm);
            }
            poses.pushPose();poses.translate(leg,0,0);draw("lower_jaw",poses,light);poses.popPose();
            rod(poses,light,"lower_rod",6.8F+leg,7.6F-leg);
            poses.pushPose();poses.translate(4.0*ramp(opening,0,.60F),0,0);draw("cage_front",poses,light);poses.popPose();
            poses.popPose();
        }
    }
    private static void rod(PoseStack poses,int light,String name,float x,float length)
    {
        poses.pushPose();poses.translate(x,0,0);poses.scale(length,1,1);draw(name,poses,light);poses.popPose();
    }
    public static void carrier(PoseStack poses,int light,EvaUnit01Entity unit,float partial)
    {
        float opacity=1;
        poses.pushPose();
        if(unit.recoveryRackR39())poses.translate(0,-3*(1-unit.carrierRiseProgress(partial)),0);
        draw("carrier_deck",poses,light);
        draw("carrier_deck_guides",poses,light);
        poses.popPose();
        poses.pushPose();
        poses.translate(0,-64*(1-unit.carrierRiseProgress(partial)),0);
        draw("carrier_spine",poses,light,opacity);
        draw("carrier_support_members",poses,light);
        float release=unit.getLaunchPhase()==EvaUnit01Entity.LAUNCH_CLEAR?ramp(1-(unit.getLaunchTicks()-partial)/18F,0,1):0;
        poses.pushPose();poses.translate(0,0,-3*release);draw("carrier_clamp",poses,light,opacity);poses.popPose();
        var mounts=CARRIER_MOUNTS.get(unit.getUnitVariant());
        if(mounts!=null)
        {
            draw("carrier_actuator_housings",poses,light);
            float stroke=6*(1-ramp(unit.carrierRiseProgress(partial),.80F,1))+4*release;
            for(var mount:mounts)stroke=Math.min(stroke,mount[3]-mount[2]-.28F);
            poses.pushPose();poses.translate(0,0,stroke);draw("carrier_contact_pads_"+unit.getUnitVariant(),poses,light);poses.popPose();
            for(var mount:mounts)
            {
                poses.pushPose();poses.translate(mount[0],mount[1],mount[2]+stroke);poses.scale(1,1,mount[3]-mount[2]-stroke);
                draw("carrier_ram_unit",poses,light);poses.popPose();
            }
        }
        else
        {poses.pushPose();poses.translate(0,0,6*(1-ramp(unit.carrierRiseProgress(partial),.80F,1))+4*release);draw("carrier_contacts_"+unit.getUnitVariant(),poses,light,opacity);poses.popPose();}
        draw("carrier_power_reel",poses,light,opacity);
        poses.popPose();
    }
    public static void pressureDoors(PoseStack poses,int light,float open)
    {
        for(int side:new int[]{-1,1})
        {
            poses.pushPose();poses.scale(side,1,1);poses.translate(open*17,0,0);draw("pressure_leaf",poses,light);poses.popPose();
        }
    }
    public static void shaftHatch(PoseStack poses,int light,float open)
    {
        draw("hatch_frame",poses,light);
        for(int side:new int[]{-1,1})
        {
            poses.pushPose();poses.scale(side,1,1);
            draw("hatch_cassette",poses,light);
            for(int index=0;index<SiloHatchMechanism.PANELS;index++)
            {
                var panel=SiloHatchMechanism.panel(index,open);
                poses.pushPose();poses.translate(panel.x(),panel.y(),0);
                draw("hatch_panel",poses,light);poses.popPose();
            }
            poses.popPose();
        }
    }
    private TvFacilityMeshes() {}
}
