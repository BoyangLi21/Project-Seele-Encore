package com.projectseele.world;

import com.google.gson.*;
import java.nio.file.*;
import java.util.*;
import net.minecraft.world.phys.Vec3;

/** Independent candidate fixtures; no native entity/world writes or contact exemptions. */
public final class AuditAboveFloorGantryStrokeR53
{
    private static boolean hit(NervLegacyCarrierRideR52.Piece a,NervLegacyCarrierRideR52.Piece b)
    {return a.mesh().envelope(a.frame(),a.frame()).intersects(b.mesh().envelope(b.frame(),b.frame()))&&a.mesh().intersects(a.frame(),a.frame(),b.mesh(),b.frame(),b.frame(),.003,Vec3.ZERO);}
    private static boolean piston(String name){return name.equals("shoulder_bearing/3")||name.equals("shoulder_bearing/7")||name.equals("shoulder_bearing/12")||name.equals("shoulder_bearing/16");}
    private static double[] values(RigidTransform f){var p=f.translation();return new double[]{p.x,p.y,p.z,f.qx(),f.qy(),f.qz(),f.qw()};}
    private static Vec3 point(JsonArray a){return new Vec3(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble());}
    private static RigidTransform root(JsonObject o){var q=o.getAsJsonArray("quaternion");return new RigidTransform(point(o.getAsJsonArray("position")),q.get(0).getAsFloat(),q.get(1).getAsFloat(),q.get(2).getAsFloat(),q.get(3).getAsFloat());}
    private static String sha(byte[] b)throws Exception{return HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(b));}
    public static void main(String[] args)throws Exception
    {
        var candidate=new CandidateRearLateralProfileR53(CarrierRearGuideR53.readHardware(Files.readAllBytes(Path.of(args[0])),"uninstalled-lateral"));
        NervPlantMotionR52.install("3b2ea3f2ee5742a56e5ad9c6c5a83d0262b0148dd6e23bc438c72407ad44e1d9");
        var owner=JsonParser.parseString(Files.readString(Path.of(args[2]))).getAsJsonObject();Path out=Path.of(args[3]);Files.createDirectories(out);var reports=new ArrayList<Object>();
        for(int v=0;v<3;v++)
        {
            var json=JsonParser.parseString(Files.readString(Path.of(args[1]).resolve("unit0"+v+".json"))).getAsJsonObject();var eva=new LinkedHashMap<String,NervRigidMeshSweepR52>();
            for(var entry:json.getAsJsonObject("parts").entrySet()){var a=entry.getValue().getAsJsonArray();double[] xyz=new double[a.size()];for(int i=0;i<xyz.length;i++)xyz[i]=a.get(i).getAsDouble();eva.put(entry.getKey(),new NervRigidMeshSweepR52(xyz));}
            JsonObject unit=null;for(var u:owner.getAsJsonArray("units"))if(u.getAsJsonObject().get("variant").getAsInt()==v)unit=u.getAsJsonObject();var bay=root(unit.getAsJsonObject("bay_frame"));
            var rows=new ArrayList<Object>();var poses=new ArrayList<Object>();var names=new ArrayList<Object>();var source=new ArrayList<Object>();
            for(int tick=0;tick<=120;tick++)
            {
                float closed=1-tick/120F,rise=.9F+.1F*(1-closed);var actors=AuditAboveFloorAgainstGantryR53.gantry(v,closed,0,4.25);var assembly=new ArrayList<NervLegacyCarrierRideR52.Piece>();var load=CandidateAboveFloorCarrierProfileR53.loadFrame(RigidTransform.identity());
                eva.forEach((name,m)->assembly.add(new NervLegacyCarrierRideR52.Piece("eva/"+name,m,new double[0],load,"eva")));var bodyFrames=candidate.aboveFloor().carrierFrames(RigidTransform.identity(),rise,0);
                CarrierAssemblyR53.selected().parts().forEach((name,s)->assembly.add(new NervLegacyCarrierRideR52.Piece("carrier/"+name,new NervRigidMeshSweepR52(s.positions()),new double[0],bodyFrames.get(name),"carrier")));
                assembly.addAll(candidate.partsAt(RigidTransform.identity(),rise,new Vec3(0,0,1),0,7,1));
                var hits=new ArrayList<Object>();for(var a:assembly)for(var b:actors)if(hit(a,b))hits.add(Map.of("moving",a.name(),"gantry",b.name()));
                var index=new HashMap<String,NervLegacyCarrierRideR52.Piece>();for(var a:actors)index.put(a.name(),a);var contacts=new ArrayList<Object>();
                for(int side:new int[]{0,9})for(int actuator:new int[]{0,1})
                {
                    int a=side+1+actuator*4;var pad=index.get("shoulder_bearing/"+side);var joint=index.get("shoulder_bearing/"+(a+3));var rod=index.get("shoulder_bearing/"+(a+2));var barrel=index.get("shoulder_bearing/"+(a+1));
                    contacts.add(Map.of("side",side==0?-1:1,"actuator",actuator,"pad_joint",hit(pad,joint),"piston_joint",hit(rod,joint),"barrel_piston",hit(barrel,rod)));
                }
                var frames=new ArrayList<double[]>();var scales=new ArrayList<double[]>();
                for(var a:actors)
                {
                    double stretch=piston(a.name())?a.mesh().bounds().maxZ:1;
                    if(tick==0){double[] xyz=a.mesh().triangles(),rgb=new double[xyz.length*2];for(int i=0;i<xyz.length/3;i++){rgb[6*i]=xyz[3*i];rgb[6*i+1]=xyz[3*i+1];rgb[6*i+2]=xyz[3*i+2]/stretch;Arrays.fill(rgb,6*i+3,6*i+6,.5);}source.add(Map.of("name",a.name(),"frame",a.name(),"role","full_original_gantry_source","triangles_rgb",rgb));names.add(Map.of("name",a.name(),"frame",a.name(),"role","full_original_gantry_source"));}
                    frames.add(values(bay.compose(a.frame())));scales.add(new double[]{1,1,stretch});
                }
                if(tick%6==0||tick==120)poses.add(Map.of("leg","unit"+v+"/gantry_opening","metres",tick/120D,"root",values(bay),"frames",frames,"scales",scales));
                rows.add(Map.of("tick",tick,"closed",closed,"carrier_rise",rise,"hits",hits,"actuator_contacts",contacts));
            }
            byte[] geometry=new Gson().toJson(Map.of("source_name_prefix","","parts",source)).getBytes(java.nio.charset.StandardCharsets.UTF_8);Files.write(out.resolve("unit"+v+".mesh.json"),geometry);Files.writeString(out.resolve("unit"+v+".frames.json"),new Gson().toJson(Map.of("hardware_sha256",sha(geometry),"parts",names,"poses",poses)));
            reports.add(Map.of("variant",v,"samples",121,"rows",rows));System.out.println("variant="+v+" complete");
        }
        Files.writeString(out.resolve("gantry-stroke.json"),new GsonBuilder().setPrettyPrinting().create().toJson(Map.of("installed",false,"world_written",false,"continuous_proof",false,"samples",363,"notes","Full source at 121 opening samples per variant, original anchors/fixed members unchanged, pad-side lugs rigid with pad; all collisions and finite source overlaps reported without exemption.","variants",reports)));
    }
}
