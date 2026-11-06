package com.projectseele.entity;

import com.google.gson.*;
import com.projectseele.world.*;
import java.nio.file.*;
import java.util.*;
import java.lang.reflect.*;
import net.minecraft.world.level.Level;
import org.joml.*;
import sun.misc.Unsafe;

/** Actual selected body/hands/shoe source replay, without a game or native custody claim. */
public final class HullRecoveryPoseR52
{
    private static final class Hull extends EvaUnit01Entity
    {
        int variant;Level clock;
        private Hull(){super(null,null);}
        @Override public int getUnitVariant(){return variant;}
        @Override public boolean isExperimentalUnit(){return false;}
        @Override public Level level(){return clock;}
        @Override public Set<String> getTags(){return Set.of();}
    }
    private static Field field(Class<?> c,String n)throws Exception{var f=c.getDeclaredField(n);f.setAccessible(true);return f;}
    public static void main(String[] args)throws Exception
    {
        Path bundle=Path.of(args[0]),out=Path.of(args[1]);Files.createDirectories(out);
        System.setProperty("projectseele.bodyPoseReviewDirectory",bundle.toString());System.setProperty("projectseele.gameplayReviewDirectory",bundle.toString());System.setProperty("projectseele.bodyPhysicsProfiles",bundle.resolve("articulated_bodies_r35.json").toString());
        EvaKnifeRecoveryR52Test.main(new String[0]);var unsafe=(Unsafe)field(EvaKnifeRecoveryR52Test.class,"unsafe").get(null);
        var context=EvaKnifeRecoveryR52Test.class.getDeclaredMethod("context",int.class,int.class,int.class);context.setAccessible(true);var parent=context.invoke(null,0,0,0);Level clock=(Level)field(parent.getClass(),"clock").get(parent);
        EvaOriginalMeshGeometryR52.installClasspath();var provider=EvaOriginalMeshGeometryR52.readOnlySelectedProviderR52();
        var receipt=JsonParser.parseString(new String(EvaOriginalMeshGeometryR52.classpathBytes("eva/full_assembly_geometry_r52_sources.json"),java.nio.charset.StandardCharsets.UTF_8)).getAsJsonObject();var hashes=new HashMap<String,String>();receipt.getAsJsonObject("resources").entrySet().forEach(e->hashes.put(e.getKey(),e.getValue().getAsString()));var machinery=FullAssemblyGeometryR52.load(EvaOriginalMeshGeometryR52::classpathBytes,hashes);
        var rows=new ArrayList<Map<String,Object>>();var cavity=new ArrayList<Map<String,Object>>();
        for(int v=0;v<3;v++)
        {
            Hull e=(Hull)unsafe.allocateInstance(Hull.class);e.variant=v;e.clock=clock;
            var initial=EvaBodyPose.inactivePoseR30(e,true);var goal=NervHullGroundRecoveryR52.destinationPose(e,initial);
            var joints=new LinkedHashMap<String,Quaternionf>();int j=0;for(String name:new TreeSet<>(provider.handJoints(v)))joints.put(name,new Quaternionf().rotationXYZ((j++%4)*.025F,.01F,.02F));
            var handPose=new EvaAnatomicalHandsR45.Pose("captured-left","captured-right",joints);var encoded=EvaFrozenHandsR52.encode(v,provider.handContractFingerprint(v),handPose);
            double lowest=Double.POSITIVE_INFINITY,maximumBodyStep=0;
            EvaBodyPose.Sample before=null;
            for(int tick=0;tick<=NervHullGroundRecoveryR52.POSE_TICKS;tick+=10)
            {
                var body=NervHullGroundRecoveryR52.mix(initial,goal,EvaDorsalMechanism.smooth(tick/(float)NervHullGroundRecoveryR52.POSE_TICKS));var g=provider.evaluate(v,body,handPose);lowest=java.lang.Math.min(lowest,g.bounds().minY);
                if(!body.rig.keySet().equals(initial.rig.keySet()))throw new AssertionError("Original skeleton changed");
                if(body.rotations.values().stream().anyMatch(q->!Float.isFinite(q.lengthSquared())||java.lang.Math.abs(q.lengthSquared()-1)>.0001F))throw new AssertionError("Invalid intermediate original joint quaternion");
                before=body;
            }
            var finalGeometry=provider.evaluate(v,goal,handPose);var parts=machinery.carrierParts(v,1,false,0,64);var deck=new ArrayList<double[]>();deck.add(parts.get("deck"));parts.forEach((name,triangles)->{if(name.startsWith("sole_bearing_"))deck.add(triangles);});int length=deck.stream().mapToInt(a->a.length).sum();double[] support=new double[length];int n=0;for(var a:deck){System.arraycopy(a,0,support,n,a.length);n+=a.length;}
            var sourceParts=new ArrayList<Map<String,Object>>();for(var p:finalGeometry.parts())sourceParts.add(Map.of("bone",p.bone(),"resource",p.resource(),"source_sha256",p.sourceSHA256(),"triangles",p.triangles()));cavity.add(Map.of("variant",v,"body_pose_nbt",EvaShutdownR30.encode(goal).toString(),"hand_pose_nbt",encoded.toString(),"source",finalGeometry.sourceFingerprint(),"parts",sourceParts));
            boolean bearing=NervMappedPlugMechanicsR52.actualDeckFootBearing(finalGeometry,support);
            if(!bearing)throw new AssertionError("Actual recovered sole mesh does not fit both original steel shoes, variant "+v);
            var clashes=new ArrayList<String>();for(var steel:parts.entrySet())if(!steel.getKey().startsWith("sole_bearing_")&&!steel.getKey().equals("deck")){var frameBody=new NervRigidMeshSweepR52(steel.getValue());for(var part:finalGeometry.parts()){var mesh=new NervRigidMeshSweepR52(part.triangles());if(mesh.intersects(RigidTransform.identity(),RigidTransform.identity(),frameBody,RigidTransform.identity(),RigidTransform.identity(),.003,net.minecraft.world.phys.Vec3.ZERO))clashes.add(part.bone()+"/"+steel.getKey());}}
            System.out.println("variant="+v+" actual frame/body final clashes="+clashes);
            var feet=FootSupportFrameR52.sourceSoleBindingR52(finalGeometry,RigidTransform.identity());rows.add(Map.of("variant",v,"original_hand_joints",encoded.getCompound("Bones").getAllKeys().size(),"source",provider.sourceFingerprint(),"minimum_source_pose_y",lowest,"final_source_shoe_bearing",bearing,"left",feet.leftFoot().toString(),"right",feet.rightFoot().toString(),"actual_carrier_body_clashes",clashes));
        }
        var report=Map.of("world_written",false,"game_started",false,"native_recovery_acceptance",false,"source_pose_samples",97,"rows",rows);var gson=new GsonBuilder().setPrettyPrinting().create();Files.writeString(out.resolve("HULL_SOURCE_POSE_REPORT.json"),gson.toJson(report));System.out.println(gson.toJson(report));
        try(var stream=new java.util.zip.GZIPOutputStream(Files.newOutputStream(out.resolve("HULL_ACTUAL_GOAL_TRIANGLES.json.gz")))){stream.write(new Gson().toJson(Map.of("schema","projectseele.r52.actual-hull-standing-source-cavity.v1","world_written",false,"native_acceptance",false,"hand_inputs","representative original 34-joint source pose; not a captured native field event","variants",cavity)).getBytes(java.nio.charset.StandardCharsets.UTF_8));}
    }
}
