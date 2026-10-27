package com.projectseele.world;

import com.google.gson.*;
import java.nio.file.*;
import java.util.*;
import net.minecraft.world.phys.Vec3;

/** Full source contact inventory; a contact is reported, never automatically waived. */
public final class AuditHoistCapsuleContactsR53
{
    private static RigidTransform frame(JsonArray a){return new RigidTransform(new Vec3(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble()),a.get(3).getAsFloat(),a.get(4).getAsFloat(),a.get(5).getAsFloat(),a.get(6).getAsFloat());}
    public static void main(String[] args)throws Exception
    {
        var geometry=JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject();var poses=JsonParser.parseString(Files.readString(Path.of(args[1]))).getAsJsonObject();
        var names=new ArrayList<String>();var meshes=new ArrayList<NervRigidMeshSweepR52>();
        for(var r:geometry.getAsJsonArray("parts")){var p=r.getAsJsonObject();names.add(p.get("name").getAsString());var a=p.getAsJsonArray("triangles_rgb");double[] xyz=new double[a.size()/2];for(int i=0;i<xyz.length/3;i++)for(int k=0;k<3;k++)xyz[i*3+k]=a.get(i*6+k).getAsDouble();meshes.add(new NervRigidMeshSweepR52(xyz));}
        var hits=new ArrayList<Object>();int tested=0;
        for(var raw:poses.getAsJsonArray("poses"))
        {
            var row=raw.getAsJsonObject();var f=row.getAsJsonArray("frames");
            for(int i=0;i<names.size();i++)for(int j=i+1;j<names.size();j++)
            {
                boolean capsule=names.get(i).startsWith("capsule/")&&(names.get(j).startsWith("hoist/gripper/")||names.get(j).startsWith("hoist/bearing/"));
                boolean mount=names.get(i).startsWith("hoist/bearing/")&&names.get(j).startsWith("hoist/gripper/");
                if(!capsule&&!mount)continue;
                var a=frame(f.get(i).getAsJsonArray());var b=frame(f.get(j).getAsJsonArray());var m=meshes.get(i);var n=meshes.get(j);tested++;
                if(m.envelope(a,a).intersects(n.envelope(b,b))&&m.intersects(a,a,n,b,b,.003,Vec3.ZERO))hits.add(Map.of("leg",row.get("leg").getAsString(),"progress",row.get("metres").getAsDouble(),"capsule",names.get(i),"gripper",names.get(j)));
            }
        }
        Files.writeString(Path.of(args[2]),new GsonBuilder().setPrettyPrinting().create().toJson(Map.of("world_written",false,"installed",false,"tests",tested,"contacts_requiring_interface_classification",hits,"geometric_clearance_claim",false)));
        System.out.println("tests="+tested+" contacts="+hits.size());
    }
}
