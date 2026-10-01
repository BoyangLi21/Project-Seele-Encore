package com.projectseele.client.render;

import com.google.gson.*;
import com.mojang.blaze3d.vertex.PoseStack;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.EvaDorsalMechanism;
import net.minecraft.client.Minecraft;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.phys.Vec3;
import org.joml.Quaternionf;
import org.joml.Vector3f;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.*;

/** A facet-matched pad lifts away before its hydraulic assembly retracts. */
final class TvShoulderRestraintsR44
{
    private record Pad(int variant,int side,String part,Vec3 normal,List<Vec3> anchors,List<Vec3> links) {}
    private static final Map<String,RigidMachineryPartR44> PARTS=new HashMap<>();
    private static final List<Pad> PADS=new ArrayList<>();
    private static boolean attempted;

    static void clearCache(){PARTS.clear();PADS.clear();attempted=false;}
    private static Vec3 point(JsonArray a)
    {
        var p=new Vec3(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble());
        if(!Double.isFinite(p.x)||!Double.isFinite(p.y)||!Double.isFinite(p.z))throw new IllegalArgumentException("Invalid shoulder frame");
        return p;
    }
    private static List<Vec3> points(JsonArray array)
    {var result=new ArrayList<Vec3>();for(var element:array)result.add(point(element.getAsJsonArray()));return List.copyOf(result);}
    private static void load()
    {
        if(attempted)return;attempted=true;
        var path=new ResourceLocation(ProjectSeele.MODID,"mesh/hangar_shoulder_contacts_r44.json");
        try(var stream=Minecraft.getInstance().getResourceManager().open(path);var reader=new InputStreamReader(stream,StandardCharsets.UTF_8))
        {
            var resource=JsonParser.parseReader(reader).getAsJsonObject();
            for(var entry:resource.getAsJsonObject("parts").entrySet())PARTS.put(entry.getKey(),RigidMachineryPartR44.triangles(entry.getValue().getAsJsonArray()));
            var keys=new HashSet<String>();
            for(var element:resource.getAsJsonArray("contacts"))
            {
                var row=element.getAsJsonObject();int variant=row.get("variant").getAsInt(),side=row.get("side").getAsInt();
                String part=row.get("part").getAsString();Vec3 normal=point(row.getAsJsonArray("normal"));
                var anchors=points(row.getAsJsonArray("anchors"));var links=points(row.getAsJsonArray("links"));
                if(variant<0||variant>2||Math.abs(side)!=1||anchors.size()!=2||links.size()!=2||Math.abs(normal.length()-1)>.0001
                        ||!PARTS.containsKey(part)||!keys.add(variant+"/"+side))throw new IllegalArgumentException("Incomplete original shoulder contact set");
                PADS.add(new Pad(variant,side,part,normal,anchors,links));
            }
            if(PADS.size()!=6)throw new IllegalArgumentException("All six shoulder pads are required");
        }
        catch(Exception error){PADS.clear();PARTS.clear();ProjectSeele.LOGGER.error("R44 measured shoulder machinery rejected",error);}
    }
    private static float ramp(float value,float a,float b){return EvaDorsalMechanism.smooth((value-a)/(b-a));}
    private static void draw(String name,PoseStack poses,int light)
    {PARTS.get(name).draw(poses,TvFacilityMeshes.currentBuffers(),light);}

    static boolean render(int variant,float opening,PoseStack poses,int light)
    {return render(variant,opening,poses,light,true);}
    static boolean render(int variant,float opening,PoseStack poses,int light,boolean fixedMounts)
    {
        load();if(variant<0||variant>2||PADS.size()!=6)return false;
        if(fixedMounts)draw("shoulder_fixed_mounts",poses,light);
        for(var pad:PADS)
        {
            if(pad.variant!=variant)continue;
            Vec3 move=pad.normal.scale(2.1*ramp(opening,0,.25F)).add(pad.side*5.35*ramp(opening,.23F,.88F),0,0);
            poses.pushPose();poses.translate(move.x,move.y,move.z);draw(pad.part,poses,light);poses.popPose();
            for(int i=0;i<2;i++)
            {
                Vec3 anchor=pad.anchors.get(i),end=pad.links.get(i).add(move),delta=end.subtract(anchor);
                double length=delta.length();if(length<=2.22)throw new IllegalStateException("Shoulder actuator exhausted its real stroke");
                var direction=new Vector3f((float)(delta.x/length),(float)(delta.y/length),(float)(delta.z/length));
                poses.pushPose();poses.translate(anchor.x,anchor.y,anchor.z);
                poses.mulPose(new Quaternionf().rotationTo(new Vector3f(0,0,1),direction));
                draw("shoulder_joint",poses,light);draw("shoulder_barrel",poses,light);
                poses.pushPose();poses.translate(0,0,2.18);poses.scale(1,1,(float)(length-2.18));draw("shoulder_piston_unit",poses,light);poses.popPose();
                poses.translate(0,0,length);draw("shoulder_joint",poses,light);poses.popPose();
            }
        }
        return true;
    }
    private TvShoulderRestraintsR44(){}
}
