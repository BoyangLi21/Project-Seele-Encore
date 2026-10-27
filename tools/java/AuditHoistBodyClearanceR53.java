package com.projectseele.world;

import com.google.gson.*;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import net.minecraft.world.phys.Vec3;

/** Full frozen standing-body source against every actual hoist part.
 * This does not substitute for dynamic neck/hatch poses or native playback. */
public final class AuditHoistBodyClearanceR53
{
    private static RigidTransform frame(JsonArray a)
    {return new RigidTransform(new Vec3(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble()),a.get(3).getAsFloat(),a.get(4).getAsFloat(),a.get(5).getAsFloat(),a.get(6).getAsFloat());}
    public static void main(String[] args)throws Exception
    {
        byte[] bodyBytes=Files.readAllBytes(Path.of(args[0]));var body=JsonParser.parseString(new String(bodyBytes,java.nio.charset.StandardCharsets.UTF_8)).getAsJsonObject();
        var geometry=JsonParser.parseString(Files.readString(Path.of(args[1]))).getAsJsonObject();var poses=JsonParser.parseString(Files.readString(Path.of(args[2]))).getAsJsonObject();
        var bodies=new LinkedHashMap<String,NervRigidMeshSweepR52>();for(var part:body.getAsJsonObject("parts").entrySet())
        {var values=part.getValue().getAsJsonArray();double[] xyz=new double[values.size()];for(int i=0;i<xyz.length;i++)xyz[i]=values.get(i).getAsDouble();bodies.put(part.getKey(),new NervRigidMeshSweepR52(xyz));}
        var names=new ArrayList<String>();var meshes=new ArrayList<NervRigidMeshSweepR52>();
        for(var raw:geometry.getAsJsonArray("parts"))
        {var p=raw.getAsJsonObject();names.add(p.get("name").getAsString());var a=p.getAsJsonArray("triangles_rgb");double[] xyz=new double[a.size()/2];for(int i=0;i<xyz.length/3;i++)for(int k=0;k<3;k++)xyz[i*3+k]=a.get(i*6+k).getAsDouble();meshes.add(new NervRigidMeshSweepR52(xyz));}
        var hits=new ArrayList<Object>();int tests=0;double load=Double.parseDouble(args[4]);
        for(var raw:poses.getAsJsonArray("poses"))
        {
            var row=raw.getAsJsonObject();var root=frame(row.getAsJsonArray("root")).compose(new RigidTransform(new Vec3(0,load,0),0,0,0,1));
            var transforms=row.getAsJsonArray("frames");var scales=row.getAsJsonArray("scales");
            for(int i=0;i<names.size();i++)if(names.get(i).startsWith("hoist/"))
            {
                var moving=frame(transforms.get(i).getAsJsonArray());var mesh=meshes.get(i);var scale=scales.get(i).getAsJsonArray();
                double sx=scale.get(0).getAsDouble(),sy=scale.get(1).getAsDouble(),sz=scale.get(2).getAsDouble();
                if(sx!=1||sy!=1||sz!=1)
                {var p=geometry.getAsJsonArray("parts").get(i).getAsJsonObject().getAsJsonArray("triangles_rgb");double[] xyz=new double[p.size()/2];for(int n=0;n<xyz.length/3;n++){xyz[n*3]=p.get(n*6).getAsDouble()*sx;xyz[n*3+1]=p.get(n*6+1).getAsDouble()*sy;xyz[n*3+2]=p.get(n*6+2).getAsDouble()*sz;}mesh=new NervRigidMeshSweepR52(xyz);}
                var envelope=mesh.envelope(moving,moving);
                for(var part:bodies.entrySet())
                {
                    tests++;var obstacle=part.getValue();
                    if(envelope.intersects(obstacle.envelope(root,root))&&mesh.intersects(moving,moving,obstacle,root,root,.003,Vec3.ZERO))
                        hits.add(Map.of("leg",row.get("leg").getAsString(),"progress",row.get("metres").getAsDouble(),"hoist",names.get(i),"body",part.getKey()));
                }
            }
        }
        Files.writeString(Path.of(args[3]),new GsonBuilder().setPrettyPrinting().create().toJson(Map.of("world_written",false,"installed",false,"continuous_proof",false,"tests",tests,"hits",hits,"scope","Frozen full standing body only; dynamic dorsal mechanism and native playback remain separate")));
        System.out.println("hoist/body pairs="+tests+" hits="+hits.size());
    }
}
