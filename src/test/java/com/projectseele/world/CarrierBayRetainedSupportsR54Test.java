package com.projectseele.world;

import com.google.gson.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import net.minecraft.core.BlockPos;
import net.minecraft.world.phys.*;

/** Original bay and adjacent-route rail bearings remain outside the moving refit. */
public final class CarrierBayRetainedSupportsR54Test
{
    static int checks;
    static void check(boolean v,String why){checks++;if(!v)throw new AssertionError(why);}
    static JsonObject resource(String path)throws Exception
    {return JsonParser.parseString(new String(EvaOriginalMeshGeometryR52.classpathBytes(path),StandardCharsets.UTF_8)).getAsJsonObject();}
    public static void main(String[] args)throws Exception
    {
        var supports=resource("eva/carrier_bay_retained_supports_r54.json");
        var profile=CarrierAssemblyR53.selected();var hardware=CarrierRearGuideR53.readHardware(EvaOriginalMeshGeometryR52.classpathBytes(CarrierRearGuideR53.HARDWARE),"bearing-refit-fixture");
        var mounting=new CarrierMountProfileR53.State(false,0,1,true);var meshes=new LinkedHashMap<String,NervRigidMeshSweepR52>();
        profile.parts().forEach((name,surface)->meshes.put(name,new NervRigidMeshSweepR52(surface.positions())));
        check(supports.getAsJsonArray("anchors").size()==21&&supports.getAsJsonArray("cells").size()==26,"Complete three-bay and adjacent-route bearings with their outer-platform links");
        for(var raw:resource(CarrierBayTrayR53.RESOURCE).getAsJsonArray("bays"))
        {
            var row=raw.getAsJsonObject();int variant=row.get("variant").getAsInt();var at=row.getAsJsonArray("root");
            var root=new RigidTransform(new Vec3(at.get(0).getAsDouble(),at.get(1).getAsDouble(),at.get(2).getAsDouble()),0,1,0,0);
            var rails=new ArrayList<NervLegacyCarrierRideR52.Piece>();
            for(var value:row.getAsJsonArray("rails"))
            {
                var rail=value.getAsJsonObject();var values=rail.getAsJsonArray("triangles_rgb");double[] rgb=new double[values.size()],xyz=new double[values.size()/2];
                for(int i=0,n=0;i<rgb.length;i+=6){for(int k=0;k<6;k++)rgb[i+k]=values.get(i+k).getAsDouble();for(int k=0;k<3;k++)xyz[n++]=rgb[i+k];}
                rails.add(new NervLegacyCarrierRideR52.Piece("tray/"+variant+"/"+rail.get("name").getAsString(),new NervRigidMeshSweepR52(xyz),rgb,root,"tray_rail"));
            }
            var bay=new CarrierBayTrayR53.Bay(variant,UUID.fromString(row.get("eva").getAsString()),root,BlockPos.ZERO,BlockPos.ZERO,List.of(),rails);
            var samples=new ArrayList<List<NervOriginalCarrierR52.Part>>();
            for(float rise:new float[]{0,.9F,.915F,.96F,.98F,1})
            {
                var parts=new ArrayList<NervOriginalCarrierR52.Part>();
                for(var entry:meshes.entrySet())parts.add(new NervOriginalCarrierR52.Part(entry.getKey(),NervOriginalCarrierR52.Role.STRUCTURE,entry.getValue(),root.compose(profile.frame(entry.getKey(),rise,0,0,mounting))));
                parts.addAll(CarrierFootBearingR53.partsAt(CarrierFootBearingR53.selected(),variant,root,mounting));
                for(var part:hardware.partsAt(root,rise,new Vec3(0,0,-1),0,7,mounting))parts.add(new NervOriginalCarrierR52.Part(part.name(),NervOriginalCarrierR52.Role.GUIDE,part.mesh(),part.frame()));
                for(var part:CarrierBayTrayR53.railsAt(bay,rise))parts.add(new NervOriginalCarrierR52.Part(part.name(),NervOriginalCarrierR52.Role.STRUCTURE,part.mesh(),part.frame()));
                samples.add(parts);
            }
            for(var value:supports.getAsJsonArray("cells"))
            {
                var cell=value.getAsJsonObject();if(cell.get("variant").getAsInt()!=variant)continue;
                var p=cell.getAsJsonArray("at");var position=new BlockPos(p.get(0).getAsInt(),p.get(1).getAsInt(),p.get(2).getAsInt());var box=new AABB(position);
                check(!CarrierBayLiftSlotsR54.contains(position),"Fixed bearing shelf cannot be treated as optional slot air");
                for(int segment=0;segment+1<samples.size();segment++)for(int i=0;i<samples.get(segment).size();i++)
                {
                    var a=samples.get(segment).get(i);var b=samples.get(segment+1).get(i);
                    check(!a.mesh().intersects(a.frame(),b.frame(),box,.003),"Restored shelf conflicts with "+a.name()+" at "+position);
                }
            }
        }
        check(CarrierBayLiftSlotsR54.contains(new BlockPos(-11,-1070,316)),"Unrelated actual mast shaft remains open");
        System.out.println("PASS R54 complete restored bearing shelves versus whole refitted source stroke: "+checks);
    }
}
