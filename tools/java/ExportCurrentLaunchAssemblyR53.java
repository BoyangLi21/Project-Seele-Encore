package com.projectseele.world;
import com.google.gson.*;
import java.io.*;
import java.nio.file.*;
import java.security.*;
import java.util.*;
import java.util.zip.*;
import net.minecraft.world.phys.*;
import org.joml.Quaternionf;

/** Fresh complete source geometry for conservative civil hulls; no entity, Level or World. */
public final class ExportCurrentLaunchAssemblyR53
{
    record Part(String name,String family,double[] xyz){}
    static String sha(Path p)throws Exception{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(p)));}
    static Part transform(String name,String family,double[] a,RigidTransform f){var out=new double[a.length];for(int i=0;i<a.length;i+=3){var p=f.transformPoint(new Vec3(a[i],a[i+1],a[i+2]));out[i]=p.x;out[i+1]=p.y;out[i+2]=p.z;}return new Part(name,family,out);}
    static void save(Path path,List<Part> parts)throws Exception{try(var out=new DataOutputStream(new GZIPOutputStream(Files.newOutputStream(path)))){out.writeInt(parts.size());for(var p:parts){out.writeUTF(p.name());out.writeUTF(p.family());out.writeInt(p.xyz().length);for(double x:p.xyz())out.writeDouble(x);}}}
    static NervLegacyCarrierRideR52.RidePose pose(JsonArray source){var out=new ArrayList<NervLegacyCarrierRideR52.Joint>();for(var raw:source){var p=raw.getAsJsonArray();out.add(new NervLegacyCarrierRideR52.Joint(p.get(0).getAsDouble(),p.get(1).getAsDouble(),p.get(2).getAsDouble()));}return new NervLegacyCarrierRideR52.RidePose(out);}
    public static void main(String[] args)throws Exception
    {
        Path design=Path.of(args[0]),cloud=Path.of(args[1]),windows=Path.of(args[2]),output=Path.of(args[3]);Files.createDirectories(output);var d=NervRouteDirectoryR52.parse(JsonParser.parseString(Files.readString(design)).getAsJsonObject());d.validateCompactLaunchContractR52();if(d.epoch()!=53)throw new AssertionError("Root current epoch required");var old=JsonParser.parseString(Files.readString(windows)).getAsJsonObject();var rows=new ArrayList<Object>();var sources=new LinkedHashMap<String,String>();sources.put(design.toString(),sha(design));sources.put(windows.toString(),sha(windows));
        for(int v=0;v<3;v++)
        {
            Path source=Path.of(cloud+".variant"+v+".actual_mesh.bin.gz");sources.put(source.toString(),sha(source));var parts=new ArrayList<Part>();
            try(var in=new DataInputStream(new GZIPInputStream(Files.newInputStream(source)))){int n=in.readInt();for(int i=0;i<n;i++){String name=in.readUTF(),family=in.readUTF();int length=in.readInt();var a=new double[length];for(int k=0;k<length;k++)a[k]=in.readDouble();if(!name.startsWith("carrier/"))parts.add(new Part(name,family,a));}}
            var binding=NervOriginalCarrierR52.nominalBinding(v);var orientation=RigidTransform.of(Vec3.ZERO,new Quaternionf(0,1,0,0));var root=RigidTransform.of(orientation.transformVector(binding.contactCentre()).scale(-1),orientation.rotation());var poses=new ArrayList<Object>();
            for(int bank=1;bank<=3;bank++)
            {
                String id="unit"+v+"/"+(bank==1?"original_incline":bank==2?"bank1_to_2":"bank2_to_3");JsonObject leg=null;for(var r:old.getAsJsonArray("legs"))if(r.getAsJsonObject().get("leg").getAsString().equals(id))leg=r.getAsJsonObject();if(leg==null)throw new AssertionError("Actual ready state absent");var list=leg.getAsJsonArray("windows");var last=list.get(list.size()-1).getAsJsonObject();var joints=last.getAsJsonArray("ride_to");var ride=pose(joints);
                var target=d.sample(d.leg(id),1,binding).evaRoot();var recorded=last.getAsJsonArray("root_to");if(target.translation().distanceTo(new Vec3(recorded.get(0).getAsDouble(),recorded.get(1).getAsDouble(),recorded.get(2).getAsDouble()))>1e-8||target.rotationErrorDegrees(orientation)>1e-5)throw new AssertionError("Root changed a prelaunch ready geometry; remeasure ride before launch hull");
                for(var p:NervOriginalCarrierR52.partsAtR53(v,root,1,new Vec3(0,1,0),ride,new Vec3(0,1,0),0))
                {if(p.name().startsWith("outer/"))continue;if(bank>1&&!p.name().startsWith("ride/"))continue;parts.add(transform("carrier/"+(p.name().startsWith("ride/")?"bank"+bank+"/":"")+p.name(),p.role().name(),p.mesh().triangles(),p.frame()));}
                poses.add(Map.of("bank",bank,"actual_ready_joints",joints,"actual_ready_root",target));
            }
            Path target=output.resolve("ACTUAL_FIXED_ASSEMBLY.variant"+v+".bin.gz");save(target,parts);sources.put(target.toString(),sha(target));rows.add(Map.of("variant",v,"parts",parts.size(),"triangles",parts.stream().mapToInt(p->p.xyz().length/9).sum(),"root_relative_to_actual_foot_midpoint",root,"binding",binding,"actual_three_ready_poses",poses));System.out.println("Fresh current non-head assembly variant="+v+" parts="+parts.size());
        }
        var templates=new ArrayList<Object>();var parts=new ArrayList<Part>();for(var p:NervOuterCarrierGuideR52.templates()){parts.add(new Part(p.name(),p.role(),p.mesh().triangles()));templates.add(Map.of("name",p.name(),"role",p.role(),"frame",p.frame(),"triangles",p.mesh().triangles().length/9,"local_bounds",p.mesh().bounds()));}
        Path head=output.resolve("ACTUAL_CURRENT_HEAD_TEMPLATES.bin.gz");save(head,parts);sources.put(head.toString(),sha(head));
        var report=new LinkedHashMap<String,Object>();report.put("world_written",false);report.put("game_started",false);report.put("directory_fingerprint",d.fingerprint());report.put("root_design_sha256",sha(design));report.put("head_source_sha256",NervBankHeadTransferR53.SOURCE_SHA);report.put("body_snapshot_current_exact_proof",Path.of(args[2]).getParent().resolve("CURRENT_BODY_PLUG_SNAPSHOT_EXACT.json").toString());report.put("sources_sha256",sources);report.put("variants",rows);report.put("head_templates",templates);report.put("scope","Actual current complete EVA/closed plug exact revalidated source and freshly evaluated original carrier. Three frozen bank-ready shoe states form a conservative union for the nine routes, never three physical carriers. All forty-eight head templates remain separate for continuous actual tangent-cone enclosure. Coordinate origin is actual foot midpoint, same as directory centre controls; fixed world yaw180 is already applied to non-head vertices.");Files.writeString(output.resolve("ACTUAL_CURRENT_ASSEMBLY_EXPORT.json"),new GsonBuilder().setPrettyPrinting().create().toJson(report));
    }
}
