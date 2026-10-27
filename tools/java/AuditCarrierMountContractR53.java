package com.projectseele.world;

import com.google.gson.*;
import java.nio.file.*;
import java.util.*;
import net.minecraft.world.phys.Vec3;

/** Compare the production geometry evaluator with independently retained spatial candidates. */
public final class AuditCarrierMountContractR53
{
    private static void require(boolean ok,String message){if(!ok)throw new IllegalStateException(message);}
    private static boolean same(RigidTransform a,RigidTransform b){return a.translation().distanceTo(b.translation())<1e-8&&a.rotationErrorDegrees(b)<.0001;}
    private static boolean hit(NervRigidMeshSweepR52 a,RigidTransform af,NervRigidMeshSweepR52 b,RigidTransform bf)
    {return a.envelope(af,af).intersects(b.envelope(bf,bf))&&a.intersects(af,af,b,bf,bf,.003,Vec3.ZERO);}
    public static void main(String[] args)throws Exception
    {
        var hardware=CarrierRearGuideR53.readHardware(Files.readAllBytes(Path.of(args[0])),"contract-candidate");var candidate=new CandidateRearLateralProfileR53(hardware);var source=CarrierAssemblyR53.selected();var foot=CarrierFootBearingR53.read(Files.readAllBytes(Path.of(args[1])));var identity=RigidTransform.identity();int rearChecks=0,bodyChecks=0,gantryChecks=0;var footRows=new ArrayList<Object>();
        for(int tick=0;tick<=40;tick++)for(double retract:new double[]{0,.25,.5,.75,1})for(Vec3 direction:List.of(new Vec3(0,0,1),new Vec3(0,.155,1),new Vec3(0,1,0)))
        {
            float rise=tick/40F;var mounting=new CarrierMountProfileR53.State(true,4.25,retract);var a=candidate.partsAt(identity,rise,direction,0,7,retract);var b=hardware.partsAt(identity,rise,direction,0,7,mounting);
            require(a.size()==b.size(),"Complete rear source required");for(int i=0;i<a.size();i++){require(a.get(i).name().equals(b.get(i).name())&&Arrays.equals(a.get(i).mesh().triangles(),b.get(i).mesh().triangles())&&same(a.get(i).frame(),b.get(i).frame()),"Candidate/production rear mismatch: "+a.get(i).name());rearChecks++;}
            var old=candidate.aboveFloor().carrierFrames(identity,rise,0);for(String n:source.parts().keySet()){require(same(old.get(n),source.frame(n,rise,0,0,mounting)),"Candidate/production body mismatch: "+n);bodyChecks++;}
        }
        NervPlantMotionR52.install("3b2ea3f2ee5742a56e5ad9c6c5a83d0262b0148dd6e23bc438c72407ad44e1d9");
        for(int v=0;v<3;v++)
        {
            var mounting=new CarrierMountProfileR53.State(true,4.25,1);var load=mounting.payloadFrame(identity);var parts=new ArrayList<EvaOriginalMeshGeometryR52.Part>();var json=JsonParser.parseString(Files.readString(Path.of(args[2]).resolve("unit0"+v+".json"))).getAsJsonObject();
            for(var e:json.getAsJsonObject("parts").entrySet()){var arr=e.getValue().getAsJsonArray();double[] xyz=new double[arr.size()];for(int i=0;i<xyz.length;i++)xyz[i]=arr.get(i).getAsDouble();parts.add(new EvaOriginalMeshGeometryR52.Part(e.getKey(),"retained_actual_export","fixture",xyz,new NervRigidMeshSweepR52(xyz).bounds()));}
            var body=new EvaOriginalMeshGeometryR52.Geometry(v,"actual_fixture",parts);boolean bears=CarrierFootBearingR53.bears(foot,body,load,identity,mounting,source);var bad=new RigidTransform(load.translation().add(0,.02,0),0,0,0,1);boolean badBears=CarrierFootBearingR53.bears(foot,body,bad,identity,mounting,source);var contacts=new ArrayList<Object>();
            for(var pad:foot.variant(v))
            {
                boolean permits=CarrierFootBearingR53.permitsContact(foot,body,load,identity,mounting,source,pad.bone(),new NervFlightProofR52.ObstacleMesh(pad.mesh(),load));var hits=new ArrayList<String>();
                for(var p:body.parts())if(hit(pad.mesh(),load,new NervRigidMeshSweepR52(p.triangles()),load))hits.add(p.bone());
                var carrierHits=new ArrayList<String>();for(var e:source.parts().entrySet())if(hit(pad.mesh(),load,new NervRigidMeshSweepR52(e.getValue().positions()),mounting.payloadFrame(identity).compose(source.frame(e.getKey(),1,0,0))))carrierHits.add(e.getKey());
                contacts.add(Map.of("pad",pad.name(),"permits_exact_pad",permits,"body_intersections",hits,"carrier_intersections",carrierHits,"triangles",pad.mesh().triangleCount()));require(permits&&hits.equals(List.of(pad.bone())),"Exact source foot contact only");
            }
            footRows.add(Map.of("variant",v,"bears",bears,"raised_20mm_negative_bears",badBears,"contacts",contacts));require(bears&&!badBears,"Positive/negative finite sole test");
            for(int tick=0;tick<=120;tick++)
            {
                float closed=1-tick/120F;var old=AuditAboveFloorAgainstGantryR53.gantry(v,closed,0,4.25);var current=NervPlantMotionR52.structuralMeshesAtR53(v,new RigidTransform(new Vec3(0,-.96,0),0,0,0,1),closed,0,mounting);
                require(old.size()==current.size(),"Complete gantry required");for(int i=0;i<old.size();i++){require(Arrays.equals(old.get(i).mesh().triangles(),current.get(i).mesh().triangles())&&same(old.get(i).frame(),current.get(i).frame()),"Candidate/production gantry mismatch "+old.get(i).name());gantryChecks++;}
            }
        }
        Files.writeString(Path.of(args[3]),new GsonBuilder().setPrettyPrinting().create().toJson(Map.of("installed",false,"world_written",false,"rear_piece_comparisons",rearChecks,"carrier_piece_comparisons",bodyChecks,"gantry_piece_comparisons",gantryChecks,"feet",footRows)));
        if(args.length>4)
        {
            var routes=JsonParser.parseString(Files.readString(Path.of(args[4]))).getAsJsonObject();Path folder=Path.of(args[3]).getParent().resolve("sole-native");Files.createDirectories(folder);
            for(int v=0;v<3;v++)
            {
                var sourceParts=new ArrayList<Object>();var names=new ArrayList<Object>();for(var p:foot.variant(v)){sourceParts.add(Map.of("name",p.name(),"frame",p.name(),"role","finite_sole_support","triangles_rgb",p.rgb()));names.add(Map.of("name",p.name(),"frame",p.name(),"role","finite_sole_support"));}
                byte[] geometry=new Gson().toJson(Map.of("source_name_prefix","","parts",sourceParts)).getBytes(java.nio.charset.StandardCharsets.UTF_8);String sha=HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(geometry));var poses=new ArrayList<Object>();
                for(var raw:routes.getAsJsonArray("poses"))
                {
                    var row=raw.getAsJsonObject();if(!row.get("leg").getAsString().startsWith("unit"+v+"/"))continue;var a=row.getAsJsonArray("root");var root=new RigidTransform(new Vec3(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble()),a.get(3).getAsFloat(),a.get(4).getAsFloat(),a.get(5).getAsFloat(),a.get(6).getAsFloat());var f=new CarrierMountProfileR53.State(true,4.25,1).payloadFrame(root);var p=f.translation();double[] frame={p.x,p.y,p.z,f.qx(),f.qy(),f.qz(),f.qw()};poses.add(Map.of("leg",row.get("leg").getAsString(),"metres",row.get("metres").getAsDouble(),"root",a,"frames",List.of(frame,frame)));
                }
                Files.write(folder.resolve("unit"+v+".mesh.json"),geometry);Files.writeString(folder.resolve("unit"+v+".frames.json"),new Gson().toJson(Map.of("hardware_sha256",sha,"parts",names,"poses",poses)));
            }
        }
        System.out.println("contract rear="+rearChecks+" body="+bodyChecks+" gantry="+gantryChecks+" finiteFeet="+footRows.size());
    }
}
