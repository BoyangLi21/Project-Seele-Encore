package com.projectseele.world;

import com.google.gson.*;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import net.minecraft.world.phys.*;

/** Complete old carrier pieces against retained actual floor shapes. A subset
 * can disprove this proposed repair; no result admits a native migration. */
public final class AuditCarrierFloorEgressR53
{
    private static JsonObject read(String file)throws Exception{return JsonParser.parseString(Files.readString(Path.of(file))).getAsJsonObject();}
    private static String sha(String file)throws Exception{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(Path.of(file))));}
    public static void main(String[] args)throws Exception
    {
        if(args.length!=3)throw new IllegalArgumentException("source mesh export, exact actual floor subset, output required");
        var mesh=read(args[0]);var floor=read(args[1]);
        if(!floor.get("stable_regions").getAsBoolean()||!mesh.get("source_mesh_sha256").equals(floor.get("source_mesh_sha256"))||!mesh.get("selected_profile_fingerprint").equals(floor.get("selected_profile_fingerprint")))throw new IllegalStateException("Actual source identity mismatch");
        var origin=floor.getAsJsonObject("root");var xyz=Arrays.stream(origin.get("translation").getAsString().replace("(","").replace(")","").split(",")).map(String::trim).mapToDouble(Double::parseDouble).toArray();
        var root=new RigidTransform(new Vec3(xyz[0],xyz[1],xyz[2]),origin.get("qx").getAsFloat(),origin.get("qy").getAsFloat(),origin.get("qz").getAsFloat(),origin.get("qw").getAsFloat());
        var parts=new ArrayList<RescueTranslationEgressR53.Part>();var originalParts=new LinkedHashMap<String,NervOriginalCarrierR52.Part>();
        for(var value:mesh.getAsJsonArray("parts"))
        {
            var source=value.getAsJsonObject();var rgb=source.getAsJsonArray("triangles_rgb");double[] points=new double[rgb.size()/2],local=new double[points.length];
            for(int v=0;v<rgb.size()/6;v++){for(int axis=0;axis<3;axis++)local[v*3+axis]=rgb.get(v*6+axis).getAsDouble();var p=root.transformPoint(new Vec3(local[v*3],local[v*3+1],local[v*3+2]));points[v*3]=p.x;points[v*3+1]=p.y;points[v*3+2]=p.z;}
            String name="carrier/"+source.get("name").getAsString();parts.add(new RescueTranslationEgressR53.Part(name,points));originalParts.put(name,new NervOriginalCarrierR52.Part(name,NervOriginalCarrierR52.Role.STRUCTURE,new NervRigidMeshSweepR52(local),root));
        }
        var boxes=new ArrayList<AABB>();for(var value:floor.getAsJsonArray("boxes")){var b=value.getAsJsonArray();boxes.add(new AABB(b.get(0).getAsDouble(),b.get(1).getAsDouble(),b.get(2).getAsDouble(),b.get(3).getAsDouble(),b.get(4).getAsDouble(),b.get(5).getAsDouble()));}
        var delta=new Vec3(0,4.25,0);var rows=new ArrayList<Object>();
        for(var part:parts)
        {
            var result=RescueTranslationEgressR53.prove(List.of(part),boxes,delta,4.25);var row=new LinkedHashMap<String,Object>();row.put("part",part.name());row.put("triangles",part.worldTriangles().length/9);row.put("proof",result);
            var actual=originalParts.get(part.name());
            row.put("strict_initial_block_rejection",NervOriginalCarrierR52.nativeBlockRejectionR53(List.of(actual),List.of(actual),0,b->true,b->boxes));
            if(result.obstacle()>=0){row.put("obstacle",boxes.get(result.obstacle()));row.put("state",floor.getAsJsonArray("states").get(result.obstacle()).getAsString());row.put("source_world_triangle",Arrays.copyOfRange(part.worldTriangles(),result.triangle()*9,result.triangle()*9+9));}
            rows.add(row);
        }
        var report=new LinkedHashMap<String,Object>();report.put("scope","Complete old 18 carrier body/deck/clamp/retract pieces at retained V17 root/rise=1, fixed +4.25m vertical translation against exact saved known full cubes. No rear heads, rods, EVA, plug, pilot, cables or actors admission; unknown block shapes retained separately. Negative result proves this migration path is not certified.");
        report.put("world_written",false);report.put("native_accepted",false);report.put("source_export_sha256",sha(args[0]));report.put("floor_subset_sha256",sha(args[1]));report.put("root",root);report.put("delta",delta);report.put("unknown_block_shapes",floor.getAsJsonArray("unknown").size());report.put("whole_candidate",RescueTranslationEgressR53.prove(parts,boxes,delta,4.25));report.put("parts",rows);
        Files.writeString(Path.of(args[2]),new GsonBuilder().setPrettyPrinting().create().toJson(report));System.out.println("Carrier actual-floor egress: parts="+parts.size()+" boxes="+boxes.size()+"; "+report.get("whole_candidate"));
    }
    private AuditCarrierFloorEgressR53(){}
}
