package com.projectseele.world;
import com.google.gson.*;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.zip.GZIPInputStream;
import net.minecraft.world.phys.*;
import org.joml.Quaternionf;

/** Re-evaluate current selected providers before reusing the original exact body-only snapshot. */
public final class VerifyPreparedBodySnapshotR53
{
    record Part(String name,String family,double[] xyz){}
    static Part transformed(String name,String family,double[] xyz,RigidTransform frame){var out=new double[xyz.length];for(int i=0;i<xyz.length;i+=3){var p=frame.transformPoint(new Vec3(xyz[i],xyz[i+1],xyz[i+2]));out[i]=p.x;out[i+1]=p.y;out[i+2]=p.z;}return new Part(name,family,out);}
    public static void main(String[] args)throws Exception
    {
        EvaOriginalMeshGeometryR52.installClasspath();FullAssemblyGeometryR52.installClasspath();NervMappedPlugMechanicsR52.install();
        var body=JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject();var maker=EvaOriginalMeshGeometryR52Test.class.getDeclaredMethod("body",JsonObject.class,int.class);maker.setAccessible(true);
        var provider=EvaOriginalMeshGeometryR52.readOnlySelectedProviderR52();var field=FullAssemblyGeometryR52.class.getDeclaredField("installed");field.setAccessible(true);var full=(FullAssemblyGeometryR52.Provider)field.get(null);var rows=new ArrayList<Object>();
        for(int v=0;v<3;v++)
        {
            var pose=(com.projectseele.entity.EvaBodyPose.Sample)maker.invoke(null,body,v);var hands=com.projectseele.entity.EvaAnatomicalHandsR45.ordinaryReleaseTargetR52(v,false);var eva=provider.evaluate(v,pose,hands);var binding=FootSupportFrameR52.sourceSoleBindingR52(eva,RigidTransform.identity());var stance=RigidTransform.of(Vec3.ZERO,new Quaternionf(0,1,0,0));var root=RigidTransform.of(stance.transformVector(binding.contactCentre()).scale(-1),stance.rotation());var fresh=new ArrayList<Part>();
            for(var p:eva.parts())fresh.add(transformed("eva/"+p.bone(),"EVA",p.triangles(),root));for(var p:full.closedPlugParts(v).entrySet())fresh.add(transformed("plug/"+p.getKey(),"PLUG",p.getValue(),root.compose(binding.plugInEva())));
            var frozen=new ArrayList<Part>();try(var in=new DataInputStream(new GZIPInputStream(Files.newInputStream(Path.of(args[1]+".variant"+v+".actual_mesh.bin.gz"))))){int count=in.readInt();for(int i=0;i<count;i++){String name=in.readUTF(),family=in.readUTF();int n=in.readInt();var a=new double[n];for(int k=0;k<n;k++)a[k]=in.readDouble();if(!name.startsWith("carrier/"))frozen.add(new Part(name,family,a));}}
            if(fresh.size()!=frozen.size())throw new AssertionError("Current selected body part count changed");double error=0;long values=0;
            for(int i=0;i<fresh.size();i++){var a=fresh.get(i);var b=frozen.get(i);if(!a.name().equals(b.name())||!a.family().equals(b.family())||a.xyz().length!=b.xyz().length)throw new AssertionError("Current selected body topology changed "+a.name());for(int k=0;k<a.xyz().length;k++){error=Math.max(error,Math.abs(a.xyz()[k]-b.xyz()[k]));values++;}}
            if(error!=0)throw new AssertionError("Original prepared body snapshot no longer exact current factory: "+error);
            rows.add(Map.of("variant",v,"parts",fresh.size(),"coordinate_values_compared",values,"maximum_coordinate_difference_m",error,"actual_binding",binding,"provider_fingerprint",provider.sourceFingerprint()));System.out.println("variant="+v+" body_snapshot_current_exact values="+values);
        }
        Files.writeString(Path.of(args[2]),new GsonBuilder().setPrettyPrinting().create().toJson(Map.of("world_written",false,"game_started",false,"body_pose_source",args[0],"variants",rows,"scope","Current selected full EVA/closed plug providers re-evaluated and every transformed double exactly equals the original foot-normalized yaw180 snapshot. All frozen carrier entries are excluded; current carrier factory is independently re-evaluated per motion window.")));
    }
}
