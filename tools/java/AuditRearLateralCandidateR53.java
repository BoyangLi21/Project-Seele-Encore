package com.projectseele.world;

import com.google.gson.*;
import java.nio.file.*;
import java.util.*;
import java.util.zip.GZIPInputStream;
import java.io.InputStreamReader;
import net.minecraft.world.phys.Vec3;

/** Reject-only full-source candidate checks and native-shape frame export. */
public final class AuditRearLateralCandidateR53
{
    private static Vec3 point(JsonArray a){return new Vec3(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble());}
    private static RigidTransform frame(JsonObject row){var q=row.getAsJsonArray("rotation");return new RigidTransform(point(row.getAsJsonArray("root")),q.get(0).getAsFloat(),q.get(1).getAsFloat(),q.get(2).getAsFloat(),q.get(3).getAsFloat());}
    private static double[] values(RigidTransform f){var p=f.translation();return new double[]{p.x,p.y,p.z,f.qx(),f.qy(),f.qz(),f.qw()};}
    private static boolean hit(NervLegacyCarrierRideR52.Piece a,NervLegacyCarrierRideR52.Piece b)
    {return a.mesh().envelope(a.frame(),a.frame()).intersects(b.mesh().envelope(b.frame(),b.frame()))&&a.mesh().intersects(a.frame(),a.frame(),b.mesh(),b.frame(),b.frame(),.003,Vec3.ZERO);}
    public static void main(String[] args)throws Exception
    {
        byte[] raw=Files.readAllBytes(Path.of(args[0]));var h=CarrierRearGuideR53.readHardware(raw,"uninstalled-lateral");var c=new CandidateRearLateralProfileR53(h);var routes=JsonParser.parseString(Files.readString(Path.of(args[1]))).getAsJsonObject();Path out=Path.of(args[3]);Files.createDirectories(out);
        var nativeDoc=JsonParser.parseString(Files.readString(Path.of(args[2]))).getAsJsonObject();var nativeHit=nativeDoc.getAsJsonArray("hits").get(0).getAsJsonObject();double[] vertices;
        try(var gzip=new GZIPInputStream(Files.newInputStream(Path.of(nativeHit.getAsJsonObject("actor_mesh").get("triangles_file").getAsString())));var reader=new InputStreamReader(gzip,java.nio.charset.StandardCharsets.UTF_8)){var a=JsonParser.parseReader(reader).getAsJsonArray();vertices=new double[a.size()];for(int n=0;n<vertices.length;n++)vertices[n]=a.get(n).getAsDouble();}
        var columns=new NervRigidMeshSweepR52(vertices);var body=new LinkedHashMap<String,NervRigidMeshSweepR52>();CarrierAssemblyR53.selected().parts().forEach((n,p)->body.put(n,new NervRigidMeshSweepR52(p.positions())));
        var attachment=new ArrayList<Object>();var pairs=new TreeMap<String,Integer>();
        var identity=RigidTransform.identity();var bodyFrames=c.aboveFloor().carrierFrames(identity,1,0);
        for(int tick=0;tick<=40;tick++)
        {
            double r=tick/40D;var parts=c.partsAt(identity,1,new Vec3(0,0,1),0,7,r);
            for(var p:parts){if(p.role().equals("source_weld"))continue;for(var b:body.entrySet()){var f=bodyFrames.get(b.getKey());if(hit(p,new NervLegacyCarrierRideR52.Piece(b.getKey(),b.getValue(),new double[0],f,"original")))attachment.add(Map.of("retract",r,"part",p.name(),"carrier",b.getKey()));}}
            for(int i=0;i<parts.size();i++)for(int j=i+1;j<parts.size();j++){var a=parts.get(i);var b=parts.get(j);if(!(a.name().contains("/lateral/")||b.name().contains("/lateral/")))continue;if(hit(a,b))pairs.merge(a.name()+" | "+b.name(),1,Integer::sum);}
        }
        var geometryParts=new ArrayList<Object>();var names=new ArrayList<Object>();
        for(var p:c.aboveFloor().templates()){geometryParts.add(Map.of("name",p.name(),"frame",p.frame(),"role",p.role(),"triangles_rgb",p.rgb()));names.add(Map.of("name",p.name(),"frame",p.frame(),"role",p.role()));}
        byte[] geometry=new Gson().toJson(Map.of("source_name_prefix","","parts",geometryParts)).getBytes(java.nio.charset.StandardCharsets.UTF_8);Files.write(out.resolve("geometry.json"),geometry);
        var poses=new ArrayList<Object>();var columnHits=new ArrayList<Object>();int pairTests=0;
        for(var legRaw:routes.getAsJsonArray("legs"))
        {
            var leg=legRaw.getAsJsonObject();String id=leg.get("leg").getAsString();if(id.contains("/exit"))continue;var rows=leg.getAsJsonArray("samples");var bayRow=rows.get(0).getAsJsonObject();double x=point(bayRow.getAsJsonArray("root")).x;var gantry=new RigidTransform(new Vec3(x,-1062.96,328.5),0,1,0,0);double next=-1;
            for(int i=0;i<rows.size();i++)
            {
                var row=rows.get(i).getAsJsonObject();double m=row.get("metres").getAsDouble();if(m+1e-8<next&&i!=rows.size()-1)continue;next=m+(id.endsWith("original_incline")&&m<30?.5:4);
                var root=frame(row);var parts=c.partsAt(root,1,point(row.getAsJsonArray("tangent")),0,7,1);var frames=new ArrayList<double[]>();
                for(var p:parts){frames.add(values(p.frame()));if(!p.mesh().envelope(p.frame(),p.frame()).intersects(columns.envelope(gantry,gantry)))continue;pairTests++;if(p.mesh().intersects(p.frame(),p.frame(),columns,gantry,gantry,.003,Vec3.ZERO))columnHits.add(Map.of("leg",id,"metres",m,"part",p.name()));}
                poses.add(Map.of("leg",id,"metres",m,"root",values(root),"frames",frames));
            }
        }
        String sha=HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(geometry));Files.writeString(out.resolve("frames.json"),new Gson().toJson(Map.of("hardware_sha256",sha,"parts",names,"poses",poses)));
        Files.writeString(out.resolve("candidate.json"),new GsonBuilder().setPrettyPrinting().create().toJson(Map.of("world_written",false,"installed",false,"continuous_proof",false,"poses",poses.size(),"column_pair_tests",pairTests,"column_hits",columnHits,"source_attachment_hits",attachment,"lateral_contact_or_intersection_pairs_require_classification",pairs)));
        System.out.println("poses="+poses.size()+" columnHits="+columnHits.size()+" bodyHits="+attachment.size()+" contactPairs="+pairs.size());
    }
}
