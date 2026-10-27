package com.projectseele.world;

import com.google.gson.*;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import net.minecraft.world.phys.Vec3;

/** Frozen original bay roots with the exact production rise transform. */
public final class ExportRearRiseFramesR53
{
    private static double[] frame(RigidTransform f)
    {var p=f.translation();return new double[]{p.x,p.y,p.z,f.qx(),f.qy(),f.qz(),f.qw()};}
    public static void main(String[] args)throws Exception
    {
        byte[] bytes=Files.readAllBytes(Path.of(args[0]));
        var h=CarrierRearGuideR53.readHardware(bytes,"uninstalled-rise-diagnostic");
        var source=JsonParser.parseString(Files.readString(Path.of(args[1]))).getAsJsonObject();
        var poses=new ArrayList<Object>();
        for(var raw:source.getAsJsonArray("legs"))
        {
            var leg=raw.getAsJsonObject();String id=leg.get("leg").getAsString();if(!id.endsWith("/original_incline"))continue;
            var row=leg.getAsJsonArray("samples").get(0).getAsJsonObject();var v=row.getAsJsonArray("root");var q=row.getAsJsonArray("rotation");
            var root=new RigidTransform(new Vec3(v.get(0).getAsDouble(),v.get(1).getAsDouble(),v.get(2).getAsDouble()),
                q.get(0).getAsFloat(),q.get(1).getAsFloat(),q.get(2).getAsFloat(),q.get(3).getAsFloat());
            for(int n=0;n<=40;n++)
            {
                float rise=n/40F;var parts=new ArrayList<double[]>();
                for(var p:h.partsAt(root,rise,root.transformVector(new Vec3(0,0,1)),0,CarrierRearGuideR53.STOW_LIFT))parts.add(frame(p.frame()));
                poses.add(Map.of("leg",id.replace("original_incline","carrier_rise"),"metres",64*Math.min(1,rise/CarrierAssemblyR53.RISE_END),
                    "rise",rise,"root",frame(root),"frames",parts));
            }
        }
        var parts=h.parts().stream().map(p->Map.of("name",p.name(),"frame",p.frame(),"role",p.role())).toList();
        Files.writeString(Path.of(args[2]),new Gson().toJson(Map.of("world_written",false,"continuous_proof",false,
            "kinematics","CarrierRearGuideR53.Hardware.partsAt rise at frozen original bay roots", "parts",parts,"poses",poses,
            "hardware_sha256",HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes)))));
        System.out.println("rise_poses="+poses.size());
    }
    private ExportRearRiseFramesR53(){}
}
