package com.projectseele.world;

import com.google.gson.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import net.minecraft.core.BlockPos;
import net.minecraft.world.phys.*;

public final class CarrierBayLiftRailsR54Test
{
    static int checks;
    static void check(boolean good,String why){checks++;if(!good)throw new AssertionError(why);}
    static double volume(AABB b){return b.getXsize()*b.getYsize()*b.getZsize();}
    public static void main(String[] args)throws Exception
    {
        var root=RigidTransform.identity();var retired=new HashSet<BlockPos>();
        var doc=JsonParser.parseString(new String(EvaOriginalMeshGeometryR52.classpathBytes(CarrierBayTrayR53.RESOURCE),StandardCharsets.UTF_8)).getAsJsonObject();
        for(var raw:doc.getAsJsonArray("bays"))
        {
            var row=raw.getAsJsonObject();var at=row.getAsJsonArray("root");var frame=new RigidTransform(new Vec3(at.get(0).getAsDouble(),at.get(1).getAsDouble(),at.get(2).getAsDouble()),0,1,0,0);
            var parts=new ArrayList<NervLegacyCarrierRideR52.Piece>();
            for(var value:row.getAsJsonArray("rails"))
            {
                var rail=value.getAsJsonObject();var values=rail.getAsJsonArray("triangles_rgb");double[] rgb=new double[values.size()],xyz=new double[values.size()/2];
                for(int i=0,n=0;i<rgb.length;i+=6){for(int k=0;k<6;k++)rgb[i+k]=values.get(i+k).getAsDouble();for(int k=0;k<3;k++)xyz[n++]=rgb[i+k];}
                parts.add(new NervLegacyCarrierRideR52.Piece("tray/"+row.get("variant").getAsInt()+"/"+rail.get("name").getAsString(),new NervRigidMeshSweepR52(xyz),rgb,frame,"tray_rail"));
            }
            var bay=new CarrierBayTrayR53.Bay(row.get("variant").getAsInt(),UUID.fromString(row.get("eva").getAsString()),frame,BlockPos.ZERO,BlockPos.ZERO,List.of(),parts);
            var down=CarrierBayLiftRailsR54.at(bay,0);var up=CarrierBayLiftRailsR54.at(bay,1);
            check(up.size()==10,"Two split rails plus four unchanged bank seats");
            check(CarrierBayLiftRailsR54.retiredSupports(bay).size()==36,"Only 36 bridge support cells per bay");retired.addAll(CarrierBayLiftRailsR54.retiredSupports(bay));
            check(CarrierBayTrayR53.bears(bay,frame,0)&&CarrierBayTrayR53.bears(bay,frame,.95F)&&CarrierBayTrayR53.bears(bay,frame,1),"Deck retains four finite supports while bridges are lowered, moving and raised");
            for(var original:parts)
            {
                if(!CarrierBayLiftRailsR54.mainRail(original)){check(up.contains(original)&&down.contains(original),"Bank seat unchanged");continue;}
                var split=up.stream().filter(p->p.name().startsWith(original.name()+"/")).toList();
                check(split.size()==3,"Front, moving bridge, rear");
                check(Math.abs(split.stream().mapToDouble(p->volume(p.mesh().bounds())).sum()-volume(original.mesh().bounds()))<1e-8,"Raised outer box and volume retained");
                for(var p:split)check(CarrierRearLateralR53.rectangular(p.mesh()),"Closed twelve-triangle rail piece");
            }
            for(int i=0;i<up.size();i++)if(CarrierBayLiftRailsR54.bridge(up.get(i)))
            {
                var p=up.get(i);var d=down.get(i);check(Math.abs(p.frame().translation().y-d.frame().translation().y-54)<1e-8,"Real full 54 metre stroke");
                var obstruction=p.mesh().envelope(p.frame(),d.frame()).getCenter();
                check(p.mesh().intersects(d.frame(),p.frame(),new AABB(obstruction,obstruction).inflate(.1),.003),"External obstacle in rail stroke remains a collision");
            }
        }
        check(retired.size()==108,"Exact three-bay retirement");
        check(CarrierBayLiftRailsR54.drop(0)==-54&&CarrierBayLiftRailsR54.drop(.9F)==-54&&CarrierBayLiftRailsR54.drop(1)==0,"Mast first; bridge then; reverse uses identical clock");
        check(Math.abs(CarrierBayLiftRailsR54.drop(.95F)+27)<1e-4,"Continuous half stroke");
        var source=CarrierAssemblyR53.selected();var mounting=new CarrierMountProfileR53.State(false,0,0,true);
        for(String fixed:List.of("deck","toe_l","toe_r"))
        {
            var support=new NervRigidMeshSweepR52(source.parts().get(fixed).positions());
            for(String moving:List.of("body","retract_body","retract_spine","clamp_lower_l","clamp_lower_r","jaw_fixed_lower_l","jaw_fixed_lower_r"))
            {
                var mesh=new NervRigidMeshSweepR52(source.parts().get(moving).positions());
                for(int step=0;step<90;step++)
                {
                    var a=mounting.carrierLocalFrame(source,moving,step/100F,0,0);
                    var b=mounting.carrierLocalFrame(source,moving,(step+1)/100F,0,0);
                    check(!mesh.intersects(a,b,support,root,root,.003,Vec3.ZERO),"Actual capped slot must clear "+moving+" / "+fixed+" at "+step);
                }
            }
        }
        for(var pad:CarrierFootBearingR53.selected().pads())check(pad.mesh().bounds().maxZ<6.4,"All six original sole-bearing areas ahead of cut");
        System.out.println("PASS R54 bridge rails, finite supports, external collision, actual capped mast slot and unchanged six soles: "+checks);
    }
}
