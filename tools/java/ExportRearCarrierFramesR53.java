package com.projectseele.world;

import com.google.gson.*;
import java.nio.file.*;
import java.util.*;
import net.minecraft.world.phys.Vec3;

/** Pure production kinematics export. Does not create an entity or edit a world. */
public final class ExportRearCarrierFramesR53
{
    private static double[] encode(RigidTransform f)
    {var p=f.translation();return new double[]{p.x,p.y,p.z,f.qx(),f.qy(),f.qz(),f.qw()};}

    public static void main(String[] args)throws Exception
    {
        var bytes=Files.readAllBytes(Path.of(args[0]));
        var hardware=CarrierRearGuideR53.readHardware(bytes,"uninstalled-diagnostic");
        var root=new RigidTransform(new Vec3(30.5,-1030,124.5),0,1,0,0);
        var frames=new ArrayList<Object>();
        for(int index=0;index<=240;index++)
        {
            double clock=index*.5;var pose=NervBankHeadTransferR53.sample(new Vec3(0,0,-1),new Vec3(0,1,0),clock);
            var parts=new LinkedHashMap<String,double[]>();
            for(var p:hardware.partsAt(root,1,pose.direction(),pose.slide()))parts.put(p.name(),encode(p.frame()));
            frames.add(Map.of("clock",clock,"slide",pose.slide(),"parts",parts));
        }
        var result=Map.of("schema","projectseele.r53.rear-guide-native-frames.v1","world_written",false,
            "body_root",encode(root),"frames",frames,"kinematics","CarrierRearGuideR53 + NervBankHeadTransferR53");
        Files.writeString(Path.of(args[1]),new Gson().toJson(result));
        System.out.println("BANK_FRAMES="+frames.size()+" PARTS="+hardware.parts().size());
    }
}
