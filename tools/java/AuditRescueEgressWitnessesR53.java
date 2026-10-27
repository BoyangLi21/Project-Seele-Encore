package com.projectseele.world;

import com.google.gson.*;
import com.projectseele.entity.*;
import java.io.*;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import java.util.zip.ZipFile;
import net.minecraft.nbt.*;
import net.minecraft.world.phys.*;
import org.joml.Vector3f;
import org.joml.Quaternionf;

/** Replays retained pose on explicitly supplied selected assets. The historical
 * obstacle subset can disprove routes, never certify a complete current world. */
public final class AuditRescueEgressWitnessesR53
{
    private static String sha(byte[] bytes)throws Exception{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));}
    private static Vector3f vector(JsonArray a){return new Vector3f(a.get(0).getAsFloat(),a.get(1).getAsFloat(),a.get(2).getAsFloat());}
    private static EvaBodyPose.Sample rig(JsonObject data,int variant)
    {
        var bones=new LinkedHashMap<String,EvaBodyPose.Bone>();
        for(var value:data.getAsJsonObject("rigs").getAsJsonArray(Integer.toString(variant)))
        {
            var b=value.getAsJsonObject();var e=b.has("rotation")?vector(b.getAsJsonArray("rotation")):b.has("bindRotationDegrees")?vector(b.getAsJsonArray("bindRotationDegrees")):new Vector3f();e.mul((float)Math.PI/180);
            String name=b.get("name").getAsString();bones.put(name,new EvaBodyPose.Bone(name,b.has("parent")?b.get("parent").getAsString():null,vector(b.getAsJsonArray("pivot")).mul(-1,1,1).div(16),new Quaternionf().rotationZYX(e.z,-e.y,-e.x)));
        }
        return new EvaBodyPose.Sample(Map.copyOf(bones));
    }
    private static AABB box(String text)
    {
        String[] a=text.replace("AABB","").replace("[","").replace("]","").replace("->",",").split(",");
        if(a.length!=6)throw new IllegalArgumentException("Actual native obstacle format changed");var v=Arrays.stream(a).map(String::trim).mapToDouble(Double::parseDouble).toArray();return new AABB(v[0],v[1],v[2],v[3],v[4],v[5]);
    }
    private static void obstacles(JsonElement e,Set<AABB> result)
    {
        if(e.isJsonObject()){var o=e.getAsJsonObject();if(o.has("obstacle"))result.add(box(o.get("obstacle").getAsString()));for(var v:o.entrySet())if(!v.getKey().equals("obstacle"))obstacles(v.getValue(),result);}
        else if(e.isJsonArray())for(var v:e.getAsJsonArray())obstacles(v,result);
    }
    public static void main(String[] args)throws Exception
    {
        if(args.length<5||args.length>7)throw new IllegalArgumentException("actual-jar actual-air-state body-rig historical-body-evidence output [local-block-boxes] [--bounded-grid]");
        byte[] stateBytes=Files.readAllBytes(Path.of(args[1])),rigBytes=Files.readAllBytes(Path.of(args[2])),witnessBytes=Files.readAllBytes(Path.of(args[3]));
        var saved=NbtIo.readCompressed(new ByteArrayInputStream(stateBytes)).getCompound("data");CompoundTag job=null;
        UUID expected=UUID.fromString("7d09aefc-5fb7-45b2-833e-a7f26be41ca9");for(var value:saved.getList("Jobs",10)){var j=(CompoundTag)value;if(j.getUUID("Task").equals(expected))job=j;}
        if(job==null||!job.getString("Phase").equals("COMPLETE"))throw new IllegalStateException("Explicit retained completed original rescue absent");
        var data=job.getCompound("OwnerData");if(!data.contains("RescueBodyR53")||!data.contains("RescueHandsR53"))throw new IllegalStateException("Frozen original pose absent");
        try(var jar=new ZipFile(args[0]))
        {
            EvaOriginalMeshGeometryR52.ByteSource source=path->{var entry=jar.getEntry("assets/projectseele/"+path);if(entry==null)throw new IOException(path);try(var in=jar.getInputStream(entry)){return in.readAllBytes();}};
            var receipt=JsonParser.parseString(new String(source.read("eva/eva_original_mesh_geometry_r52_sources.json"),java.nio.charset.StandardCharsets.UTF_8)).getAsJsonObject();var hashes=new HashMap<String,String>();receipt.getAsJsonObject("resources").entrySet().forEach(e->hashes.put(e.getKey(),e.getValue().getAsString()));
            var provider=EvaOriginalMeshGeometryR52.load(source,hashes);if(!provider.sourceFingerprint().equals(data.getString("FlightSourceR52")))throw new IllegalStateException("Selected source differs from retained actual rescue fingerprint");int variant=job.getCompound("Original").getInt("Variant");var body=rig(JsonParser.parseString(new String(rigBytes,java.nio.charset.StandardCharsets.UTF_8)).getAsJsonObject(),variant);EvaPoseSnapshotR50.decode(data.getCompound("RescueBodyR53"),body);
            var hands=EvaFrozenHandsR52.decode(variant,provider.handContractFingerprint(variant),provider.handJoints(variant),data.getCompound("RescueHandsR53"));var geometry=provider.evaluate(variant,body,hands);
            var previous=data.getCompound("PickupRoot");var root=new RigidTransform(new Vec3(-40.70642275783638,-466,167.17349525501666),previous.getFloat("QX"),previous.getFloat("QY"),previous.getFloat("QZ"),previous.getFloat("QW"));
            var parts=new ArrayList<RescueTranslationEgressR53.Part>();
            for(var part:geometry.parts())
            {
                var xyz=part.triangles();for(int n=0;n<xyz.length;n+=3){var p=root.transformPoint(new Vec3(xyz[n],xyz[n+1],xyz[n+2]));xyz[n]=p.x;xyz[n+1]=p.y;xyz[n+2]=p.z;}
                parts.add(new RescueTranslationEgressR53.Part(part.bone(),xyz));
            }
            var recorded=new LinkedHashSet<AABB>();obstacles(JsonParser.parseString(new String(witnessBytes,java.nio.charset.StandardCharsets.UTF_8)),recorded);
            if(args.length>=6)
            {
                var document=JsonParser.parseString(Files.readString(Path.of(args[5]))).getAsJsonObject();if(!document.get("stable_regions").getAsBoolean())throw new IllegalStateException("Local source regions changed while reading");
                for(var b:document.getAsJsonArray("boxes")){var a=b.getAsJsonArray();recorded.add(new AABB(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble(),a.get(3).getAsDouble(),a.get(4).getAsDouble(),a.get(5).getAsDouble()));}
            }
            var blocks=List.copyOf(recorded);var rows=new ArrayList<Object>();
            var deltas=new ArrayList<>(List.of(new Vec3(6.3,0,0),new Vec3(-6.3,0,0),new Vec3(0,6.3,0),new Vec3(0,-6.3,0),new Vec3(0,0,6.3),new Vec3(0,0,-6.3)));
            if(args.length==7)
            {
                if(!args[6].equals("--bounded-grid"))throw new IllegalArgumentException("Explicit bounded local grid only");deltas.clear();
                for(int x=-1;x<=1;x++)for(int y=-1;y<=1;y++)for(int z=-1;z<=1;z++)if(x!=0||y!=0||z!=0)
                    for(double length:new double[]{.25,.5,1,2,3,4,6.3})deltas.add(new Vec3(x,y,z).normalize().scale(length));
            }
            for(var delta:deltas)
            {
                var result=RescueTranslationEgressR53.prove(parts,blocks,delta,8);var row=new LinkedHashMap<String,Object>();row.put("delta",delta);row.put("proof",result);if(result.obstacle()>=0)row.put("obstacle",blocks.get(result.obstacle()));rows.add(row);
            }
            var report=new LinkedHashMap<String,Object>();report.put("scope","Historical corrected body/hands at former blocked root, evaluated against a subset of recorded native obstacle boxes. Rejection is a body-only negative witness; success cannot certify missing capsule/pilot/aircraft/clamps/current world.");
            report.put("world_written",false);report.put("native_accepted",false);report.put("task",expected.toString());report.put("state_sha",sha(stateBytes));report.put("rig_sha",sha(rigBytes));report.put("evidence_sha",sha(witnessBytes));if(args.length>=6)report.put("local_block_subset_sha",sha(Files.readAllBytes(Path.of(args[5]))));report.put("selected_provider_fingerprint",provider.sourceFingerprint());report.put("saved_flight_source",data.getString("FlightSourceR52"));report.put("root",root);report.put("parts",parts.size());report.put("triangles",geometry.triangleCount());report.put("obstacle_boxes",blocks.size());report.put("directions",rows);
            Files.writeString(Path.of(args[4]),new GsonBuilder().setPrettyPrinting().create().toJson(report));System.out.println("Rescue actual selected body witnesses: parts="+parts.size()+" triangles="+geometry.triangleCount()+" boxes="+blocks.size()+" bounded_candidates="+rows.size());
        }
    }
}
