package com.projectseele.world;

import com.google.gson.*;
import java.nio.file.*;
import java.util.*;
import net.minecraft.world.phys.Vec3;

/** Full-source finite pad predicate and source-pair delta; no whole-actor collision waivers. */
public final class AuditAboveFloorGantryContactsR53
{
    private static boolean hit(NervLegacyCarrierRideR52.Piece a,NervLegacyCarrierRideR52.Piece b)
    {return a.mesh().envelope(a.frame(),a.frame()).intersects(b.mesh().envelope(b.frame(),b.frame()))&&a.mesh().intersects(a.frame(),a.frame(),b.mesh(),b.frame(),b.frame(),.003,Vec3.ZERO);}
    private static Set<String> pairs(List<NervLegacyCarrierRideR52.Piece> pieces)
    {
        var pairs=new TreeSet<String>();for(int i=0;i<pieces.size();i++)for(int j=i+1;j<pieces.size();j++)
        {var a=pieces.get(i);var b=pieces.get(j);if(!(a.name().startsWith("shoulder_bearing/")||b.name().startsWith("shoulder_bearing/")||a.name().startsWith("shell_")||b.name().startsWith("shell_")))continue;if(hit(a,b))pairs.add(a.name()+" | "+b.name());}return pairs;
    }
    public static void main(String[] args)throws Exception
    {
        NervPlantMotionR52.install("3b2ea3f2ee5742a56e5ad9c6c5a83d0262b0148dd6e23bc438c72407ad44e1d9");var results=new ArrayList<Object>();
        for(int v=0;v<3;v++)
        {
            byte[] bytes=Files.readAllBytes(Path.of(args[0]).resolve("unit0"+v+".json"));String sha=HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(bytes));var json=JsonParser.parseString(new String(bytes,java.nio.charset.StandardCharsets.UTF_8)).getAsJsonObject();var parts=new ArrayList<EvaOriginalMeshGeometryR52.Part>();
            for(var e:json.getAsJsonObject("parts").entrySet()){var a=e.getValue().getAsJsonArray();double[] xyz=new double[a.size()];for(int i=0;i<xyz.length;i++)xyz[i]=a.get(i).getAsDouble();var mesh=new NervRigidMeshSweepR52(xyz);parts.add(new EvaOriginalMeshGeometryR52.Part(e.getKey(),"actual_body_export",sha,xyz,mesh.bounds()));}
            var body=new EvaOriginalMeshGeometryR52.Geometry(v,sha,parts);var load=new RigidTransform(new Vec3(0,4.25,0),0,0,0,1);var calibratedGantry=new RigidTransform(new Vec3(0,4.25-.96,0),0,0,0,1);var closed=AuditAboveFloorAgainstGantryR53.gantry(v,1,0,4.25);var permits=new TreeMap<String,Boolean>();
            for(String name:List.of("shoulder_bearing/0","shoulder_bearing/9")){var p=closed.stream().filter(x->x.name().equals(name)).findFirst().orElseThrow();permits.put(name,NervShoulderBearingR52.permitsPadContactR52(body,load,calibratedGantry,v,name.endsWith("/0")?"arm_l":"arm_r",new NervFlightProofR52.ObstacleMesh(p.mesh(),p.frame())));}
            var samples=new ArrayList<Object>();for(float c:new float[]{0,.25F,.5F,.75F,1})
            {
                var original=pairs(AuditAboveFloorAgainstGantryR53.gantry(v,c,0,0));var candidate=pairs(AuditAboveFloorAgainstGantryR53.gantry(v,c,0,4.25));var added=new TreeSet<>(candidate);added.removeAll(original);var removed=new TreeSet<>(original);removed.removeAll(candidate);
                samples.add(Map.of("closed",c,"baseline_pairs",original,"candidate_pairs",candidate,"added_pairs",added,"removed_pairs",removed));
            }
            results.add(Map.of("variant",v,"body_export_sha256",sha,"complete_body_triangles",body.triangleCount(),"production_bears",NervShoulderBearingR52.bears(body,load,calibratedGantry,v),"production_finite_pad_permits",permits,"gantry_pair_samples",samples));System.out.println("variant="+v+" permits="+permits);
        }
        Files.writeString(Path.of(args[1]),new GsonBuilder().setPrettyPrinting().create().toJson(Map.of("installed",false,"world_written",false,"continuous_proof",false,"variants",results)));
    }
}
