package com.projectseele.world;

import com.google.gson.*;
import java.nio.file.*;
import java.util.*;
import java.util.regex.Pattern;
import net.minecraft.world.phys.*;

/** Original side receiver avoids the personnel edge while its mast telescopes. */
public final class CarrierBayReceiverStowR54Test
{
    static int checks;
    static void check(boolean v,String why){checks++;if(!v)throw new AssertionError(why);}
    public static void main(String[] args)throws Exception
    {
        var source=CarrierRearGuideR53.readHardware(EvaOriginalMeshGeometryR52.classpathBytes(CarrierRearGuideR53.HARDWARE),"source-receiver-stow-fixture");
        var root=new RigidTransform(new Vec3(-11.5,-1062,328.5),0,1,0,0);
        var mount=new CarrierMountProfileR53.State(false,0,1,true);
        var templates=CarrierMountProfileR53.rearTemplates(source,mount);
        for(var sleeve:templates)if(sleeve.name().contains("/lift_sleeve/"))
        {
            String prefix=sleeve.name().substring(0,sleeve.name().indexOf("/lift_sleeve/"));
            var rod=templates.stream().filter(p->p.name().equals(prefix+"/lift_rod")).findFirst().orElseThrow();
            int side=Integer.parseInt(sleeve.name().substring(sleeve.name().indexOf("/lift_sleeve/")+13).split("/")[0]);
            check(CarrierRearLateralR53.rectangular(sleeve.mesh()),"Closed complete sleeve faces");
            for(float rise:new float[]{0,.5F,1})
            {
                var r=rod.mesh().bounds().move(0,7-mount.bodyDrop(rise),0);
                check(CarrierRearLateralR53.faceArea(r,sleeve.mesh().bounds(),side<2?0:2)>.01,"Finite sliding bearing throughout relative mast travel");
            }
        }
        var a=source.partsAt(root,0,new Vec3(0,0,-1),0,7,mount);
        var b=source.partsAt(root,1,new Vec3(0,0,-1),0,7,mount);
        check(CarrierRearLateralR53.selfRejection(a,b)==null,"Complete rear assembly has no new self-intersection: "+CarrierRearLateralR53.selfRejection(a,b));
        for(int i=0;i<a.size();i++)
        {
            var p=a.get(i);var q=b.get(i);
            if(p.name().contains("/ball")||p.name().contains("/lateral/"))check(Math.abs(p.frame().translation().y-q.frame().translation().y)<1e-8
                    &&Math.abs(p.frame().translation().z-q.frame().translation().z+7.5)<1e-8,"Side receiver keeps its independent upper height and follows the rear guide withdrawal");
            if(p.role().equals("source_weld"))check(Math.abs(q.frame().translation().y-p.frame().translation().y-54)<1e-8,"Original mast attachment completes its 54 metre stroke");
        }
        if(args.length>0)
        {
            var doc=JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject();var boxes=new HashSet<AABB>();
            for(var raw:doc.getAsJsonArray("wholeStrokeBlockHits"))
            {
                var m=Pattern.compile("-?\\d+\\.\\d+").matcher(raw.getAsJsonObject().get("box").getAsString());double[] v=new double[6];int n=0;while(m.find())v[n++]=Double.parseDouble(m.group());
                boxes.add(new AABB(v[0],v[1],v[2],v[3],v[4],v[5]));
            }
            for(int i=0;i<a.size();i++)for(var box:boxes)check(!a.get(i).mesh().intersects(a.get(i).frame(),b.get(i).frame(),box,.003),"Actual native personnel/tray shape still obstructs "+a.get(i).name()+" "+box);
        }
        System.out.println("PASS R54 independent receiver stow, full mast stroke, finite sleeves and native side obstacles: "+checks);
    }
}
