package com.projectseele.world;

import com.google.gson.*;
import java.nio.file.*;
import java.util.*;
import net.minecraft.world.phys.Vec3;

/** Read-only rejection scan. Sampled poses do not certify the intervening curve. */
public final class AuditRearRouteGeometryR53
{
    private static Vec3 point(JsonArray a)
    {return new Vec3(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble());}
    public static void main(String[] args)throws Exception
    {
        var bytes=Files.readAllBytes(Path.of(args[2]));
        var hardware=CarrierRearGuideR53.readHardware(bytes,"uninstalled-diagnostic");
        var source=JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject();
        var rails=args.length>4?CarrierRearGuideR53.readExistingFixed(Files.readAllBytes(Path.of(args[3])),args[4],source.get("directory").getAsString()):
            CarrierRearGuideR53.readFixedForAudit(Files.readAllBytes(Path.of(args[3])),bytes);
        var meshes=new LinkedHashMap<String,NervRigidMeshSweepR52>();
        CarrierAssemblyR53.selected().posed(1,0,0).forEach((name,xyz)->meshes.put(name,new NervRigidMeshSweepR52(xyz)));
        var failures=new ArrayList<Object>();int poses=0,tests=0,contacts=0;
        for(var raw:source.getAsJsonArray("legs"))
        {
            var leg=raw.getAsJsonObject();String id=leg.get("leg").getAsString();
            if(!id.contains("/exit"))continue;
            double last=-100;var samples=leg.getAsJsonArray("samples");int before=failures.size();
            for(int sample=0;sample<samples.size();sample++)
            {
                var row=samples.get(sample).getAsJsonObject();double metres=row.get("metres").getAsDouble();
                if(metres-last<2&&sample!=samples.size()-1)continue;last=metres;poses++;
                var root=new RigidTransform(point(row.getAsJsonArray("root")),0,1,0,0);
                var rear=hardware.partsAt(root,1,point(row.getAsJsonArray("tangent")),0);
                var all=new ArrayList<>(rear);
                meshes.forEach((name,mesh)->all.add(new NervLegacyCarrierRideR52.Piece("body/"+name,mesh,new double[0],root,"body")));
                for(var p:all)
                {
                    var bounds=p.mesh().envelope(p.frame(),p.frame());
                    for(var fixed:rails.index().query(bounds))
                    {
                        if(!p.role().equals("body")&&CarrierRearGuideR53.namedContact(p,p,fixed,id)){contacts++;continue;}
                        var f=fixed.steel();tests++;
                        if(p.mesh().intersects(p.frame(),p.frame(),f.mesh(),f.frame(),f.frame(),.003,Vec3.ZERO))
                            failures.add(Map.of("leg",id,"metres",metres,"moving",p.name(),"fixed",fixed.name()));
                    }
                }
                if(failures.size()>500)break;
            }
            System.out.println(id+" poses="+poses+" failures="+(failures.size()-before));
            if(failures.size()>500)break;
        }
        Files.writeString(Path.of(args[1]),new Gson().toJson(Map.of("schema","projectseele.r53.rear-route-sampled-audit.v1",
            "world_written",false,"continuous_proof",false,"poses",poses,"pair_tests",tests,"contacts",contacts,"failures",failures)));
    }
}
