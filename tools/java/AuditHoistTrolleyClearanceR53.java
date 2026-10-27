package com.projectseele.world;
import com.google.gson.*;
import java.nio.file.*;
import java.util.*;
import net.minecraft.world.phys.Vec3;

/** Real suspended assembly versus trolley, no contact exclusions. */
public final class AuditHoistTrolleyClearanceR53
{
    private static RigidTransform frame(JsonArray a){return new RigidTransform(new Vec3(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble()),a.get(3).getAsFloat(),a.get(4).getAsFloat(),a.get(5).getAsFloat(),a.get(6).getAsFloat());}
    public static void main(String[] args)throws Exception
    {
        var d=JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject();var frames=JsonParser.parseString(Files.readString(Path.of(args[1]))).getAsJsonObject();
        var names=new ArrayList<String>();var meshes=new ArrayList<NervRigidMeshSweepR52>();
        for(var raw:d.getAsJsonArray("parts")){var r=raw.getAsJsonObject();names.add(r.get("name").getAsString());var values=r.getAsJsonArray("triangles_rgb");double[] a=new double[values.size()/2];for(int i=0;i<a.length/3;i++)for(int k=0;k<3;k++)a[i*3+k]=values.get(i*6+k).getAsDouble();meshes.add(new NervRigidMeshSweepR52(a));}
        int top=names.indexOf("hoist/top"),tests=0;var hits=new ArrayList<Object>();
        for(var raw:frames.getAsJsonArray("poses"))
        {
            var r=raw.getAsJsonObject();var ff=r.getAsJsonArray("frames");var fixed=frame(ff.get(top).getAsJsonArray());
            for(int i=0;i<names.size();i++)if(names.get(i).startsWith("hoist/gripper/")||names.get(i).startsWith("hoist/bearing/")||names.get(i).equals("hoist/yoke"))
            {
                var f=frame(ff.get(i).getAsJsonArray());var a=meshes.get(i);var b=meshes.get(top);tests++;
                if(a.envelope(f,f).intersects(b.envelope(fixed,fixed))&&a.intersects(f,f,b,fixed,fixed,.003,Vec3.ZERO))hits.add(Map.of("leg",r.get("leg").getAsString(),"progress",r.get("metres").getAsDouble(),"part",names.get(i)));
            }
        }
        Files.writeString(Path.of(args[2]),new GsonBuilder().setPrettyPrinting().create().toJson(Map.of("tests",tests,"hits",hits,"world_written",false,"installed",false,"continuous_proof",false)));
        System.out.println("trolley pairs="+tests+" hits="+hits.size());
    }
}
