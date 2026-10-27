package com.projectseele.world;

import com.google.gson.*;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import net.minecraft.world.phys.Vec3;

/** Read-only original carrier surfaces and exact bay rise frames for frozen native-shape diagnostics. */
public final class ExportOriginalCarrierRiseR53
{
    private static double[] frame(RigidTransform f)
    {var p=f.translation();return new double[]{p.x,p.y,p.z,f.qx(),f.qy(),f.qz(),f.qw()};}
    private static String sha(byte[] bytes)throws Exception
    {return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));}
    public static void main(String[] args)throws Exception
    {
        var profile=Objects.requireNonNull(CarrierAssemblyR53.selected());
        var source=JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject();
        var parts=new ArrayList<Object>();var names=new ArrayList<Object>();
        for(var p:profile.parts().entrySet())
        {
            var xyz=p.getValue().positions();var rgb=new double[xyz.length*2];
            for(int i=0;i<xyz.length/3;i++)for(int axis=0;axis<3;axis++)rgb[i*6+axis]=xyz[i*3+axis];
            parts.add(Map.of("name",p.getKey(),"frame","PROFILE","role","original", "triangles_rgb",rgb));
            names.add(Map.of("name","carrier/"+p.getKey(),"frame","PROFILE","role","original"));
        }
        String hardware=new Gson().toJson(Map.of("schema","projectseele.r53.original-rise-diagnostic-mesh.v1",
            "source_name_prefix","carrier/","source_mesh_sha256",sha(EvaOriginalMeshGeometryR52.classpathBytes(CarrierAssemblyR53.MESH)),
            "selected_profile_fingerprint",profile.fingerprint(),"parts",parts));
        byte[] hardwareBytes=hardware.getBytes(java.nio.charset.StandardCharsets.UTF_8);
        Files.write(Path.of(args[1]),hardwareBytes);var poses=new ArrayList<Object>();
        for(var raw:source.getAsJsonArray("legs"))
        {
            var leg=raw.getAsJsonObject();String id=leg.get("leg").getAsString();if(!id.endsWith("/original_incline"))continue;
            var row=leg.getAsJsonArray("samples").get(0).getAsJsonObject();var v=row.getAsJsonArray("root");var q=row.getAsJsonArray("rotation");
            var root=new RigidTransform(new Vec3(v.get(0).getAsDouble(),v.get(1).getAsDouble(),v.get(2).getAsDouble()),
                q.get(0).getAsFloat(),q.get(1).getAsFloat(),q.get(2).getAsFloat(),q.get(3).getAsFloat());
            for(int n=0;n<=40;n++)
            {
                float rise=n/40F;var frames=new ArrayList<double[]>();
                for(var p:profile.parts().keySet())frames.add(frame(root.compose(profile.frame(p,rise,0,0))));
                poses.add(Map.of("leg",id.replace("original_incline","original_carrier_rise"),"metres",64*Math.min(1,rise/CarrierAssemblyR53.RISE_END),
                    "rise",rise,"root",frame(root),"frames",frames));
            }
        }
        Files.writeString(Path.of(args[2]),new Gson().toJson(Map.of("world_written",false,"continuous_proof",false,
            "kinematics","CarrierAssemblyR53.Profile.frame(rise,release=0,deckTravel=0) at frozen original bay roots",
            "parts",names,"poses",poses,"hardware_sha256",sha(hardwareBytes))));
        System.out.println("original_rise_poses="+poses.size()+" parts="+parts.size());
    }
    private ExportOriginalCarrierRiseR53(){}
}
