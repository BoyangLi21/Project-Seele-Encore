package com.projectseele.world;

import com.google.gson.*;
import com.projectseele.entity.*;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.zip.GZIPOutputStream;
import net.minecraft.world.phys.Vec3;
import org.joml.Quaternionf;

/** Actual source-local full assembly, separately labelled for every variant. */
public final class ExportLaunchCloudR52 {
    private record Part(String name,String source,double[] triangles){}
    private static Vec3 point(JsonArray a){return new Vec3(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble());}
    private static Map<String,String> hashes(String path)throws Exception{
        var out=new LinkedHashMap<String,String>();
        JsonParser.parseString(Files.readString(Path.of(path))).getAsJsonObject().getAsJsonArray("files").forEach(v->{var r=v.getAsJsonObject();out.put(r.get("resource").getAsString(),r.get("sha256").getAsString());});return out;
    }
    public static void main(String[] args)throws Exception{
        var fullHashes=hashes(args[0]);var evaHashes=hashes(args[1]);
        var machine=FullAssemblyGeometryR52.load(EvaOriginalMeshGeometryR52::classpathBytes,fullHashes);
        var provider=EvaOriginalMeshGeometryR52.load(EvaOriginalMeshGeometryR52::classpathBytes,evaHashes);
        var body=JsonParser.parseString(Files.readString(Path.of(args[2]))).getAsJsonObject();
        var dorsals=JsonParser.parseString(Files.readString(Path.of(args[3]))).getAsJsonObject().getAsJsonObject("profiles");
        var make=EvaOriginalMeshGeometryR52Test.class.getDeclaredMethod("body",JsonObject.class,int.class);make.setAccessible(true);
        var controls=EvaAnatomicalHandsR45.class.getDeclaredMethod("controls",EvaAnatomicalHandsR45.Rig.class,String.class,String.class);controls.setAccessible(true);
        var rotation=EvaAnatomicalHandsR45.class.getDeclaredMethod("rotation",EvaAnatomicalHandsR45.Joint.class,float.class,float.class,float.class);rotation.setAccessible(true);
        Path out=Path.of(args[4]);Files.createDirectories(out);var report=new JsonObject();var units=new JsonArray();
        for(int variant=0;variant<3;variant++){
            var pose=(EvaBodyPose.Sample)make.invoke(null,body,variant);var rig=EvaAnatomicalHandsR45.rig(variant);
            @SuppressWarnings("unchecked") var control=(Map<String,float[]>)controls.invoke(null,rig,"relaxed","relaxed");
            var hands=new LinkedHashMap<String,Quaternionf>();for(var j:rig.joints()){var c=control.get(j.name());hands.put(j.name(),(Quaternionf)rotation.invoke(null,j,c[0],c[1],c[2]));}
            var eva=provider.evaluate(variant,pose,new EvaAnatomicalHandsR45.Pose("relaxed","relaxed",Map.copyOf(hands)));
            var parts=new ArrayList<Part>();for(var part:eva.parts())parts.add(new Part("eva/"+part.bone(),part.sourceSHA256(),part.triangles()));
            for(var part:machine.carrierParts(1,false,0).entrySet())parts.add(new Part("carrier/"+part.getKey(),"carrier-manifest",part.getValue()));
            var d=dorsals.getAsJsonObject("eva_unit0"+variant);
            var profile=new EvaDorsalProfile.Profile(point(d.getAsJsonArray("centre")),point(d.getAsJsonArray("outward")),point(d.getAsJsonArray("hinge")),point(d.getAsJsonArray("hinge_axis")),d.get("open_angle_degrees").getAsFloat());
            var socket=EvaMechanicalFrameMathR52.emptySocket(pose,EvaRifleKinematics.frameWorldR52(Vec3.ZERO,180),profile);
            for(var part:machine.closedPlugParts(variant).entrySet()){
                var xyz=part.getValue().clone();for(int i=0;i<xyz.length;i+=3){var v=socket.transformPoint(new Vec3(xyz[i],xyz[i+1],xyz[i+2]));xyz[i]=v.x;xyz[i+1]=v.y;xyz[i+2]=v.z;}
                parts.add(new Part("capsule/"+part.getKey(),"carrier-manifest",xyz));
            }
            Path file=out.resolve("unit"+variant+"_full_parts.bin.gz");long vertices=0;double error=0;
            try(var stream=new DataOutputStream(new GZIPOutputStream(Files.newOutputStream(file)))){
                stream.writeInt(0x52353243);stream.writeInt(variant);stream.writeInt(parts.size());
                for(var p:parts){stream.writeUTF(p.name());stream.writeUTF(p.source());stream.writeInt(p.triangles().length/3);vertices+=p.triangles().length/3;
                    for(double x:p.triangles()){if(!Double.isFinite(x))throw new IllegalStateException("Nonfinite source vertex");float f=(float)x;error=Math.max(error,Math.abs(x-f));stream.writeFloat(f);}}
            }
            var r=new JsonObject();r.addProperty("variant",variant);r.addProperty("parts",parts.size());r.addProperty("triangle_vertices",vertices);r.addProperty("max_float32_cast_error_metres",error);r.addProperty("file",file.toString());r.addProperty("sha256",HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(file))));units.add(r);
        }
        report.addProperty("schema","projectseele.r52.actual-full-assembly-cloud.v1");report.addProperty("world_written",false);report.addProperty("basis","Source-local metres, no world rotation; actual body, 34 hand joints, source carrier and each variant's own seated capsule. Geometry-only readback; not native route acceptance.");
        report.add("eva_sources",new Gson().toJsonTree(evaHashes));report.add("machine_sources",new Gson().toJsonTree(fullHashes));report.add("units",units);
        Files.writeString(out.resolve("RECEIPT.json"),new GsonBuilder().setPrettyPrinting().create().toJson(report));System.out.println(units);
    }
}
