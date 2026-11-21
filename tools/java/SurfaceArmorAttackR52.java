package com.projectseele.entity;

import com.google.gson.GsonBuilder;
import com.projectseele.physics.ShamshelPosedContactsR48;
import com.projectseele.physics.ShamshelContactPoseR48;
import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;
import net.minecraft.network.syncher.SynchedEntityData;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.*;
import org.joml.Vector3f;
import org.joml.Quaternionf;
import sun.misc.Unsafe;
import net.minecraft.server.level.ServerLevel;

/** Selected-resource, production FK and actual weighted-mesh replay. Never starts a game or writes a world. */
public final class SurfaceArmorAttackR52
{
    private static int checks;
    private static Field field(Class<?> c,String n)throws Exception{var f=c.getDeclaredField(n);f.setAccessible(true);return f;}
    private static Object call(Object o,String n)throws Exception{var m=o.getClass().getDeclaredMethod(n);m.setAccessible(true);return m.invoke(o);}
    private static void check(boolean value,String why){checks++;if(!value)throw new AssertionError(why);}
    private static double[] xyz(Vec3 p){return new double[]{p.x,p.y,p.z};}
    private static final class EmptyClock extends ServerLevel
    {
        private EmptyClock(){super(null,null,null,null,null,null,null,false,0,List.of(),false,null);}
        @Override public long getGameTime(){return 51801;}
        @Override public <T extends Entity> List<T> getEntitiesOfClass(Class<T> type,AABB box,java.util.function.Predicate<? super T> predicate){return List.of();}
        @Override public Iterable<net.minecraft.world.phys.shapes.VoxelShape> getBlockCollisions(Entity actor,AABB box){return List.of();}
    }
    private static final class Whip extends ShamshelEntity
    {
        Level clock;Vec3 origin,aim;float yaw,age;int side;
        private Whip(){super((EntityType<? extends ShamshelEntity>)null,null);}
        @Override public Level level(){return clock;}
        @Override public Vec3 position(){return origin;}
        @Override public boolean isSweeping(){return true;}
        @Override public int sweepMode(){return ShamshelWhipMotion.GROUND;}
        @Override public int sweepSide(){return side;}
        @Override public float sweepYaw(){return yaw;}
        @Override public float sweepAge(float partial){return age;}
        @Override public Vec3 armorAimR52(){return aim;}
        @Override public Set<String> getTags(){return Set.of();}
    }
    private static final class Beam extends SachielEntity
    {
        Level clock;Vec3 origin;SynchedEntityData data;float age,yaw;
        private Beam(){super((EntityType<? extends SachielEntity>)null,null);}
        @Override public Level level(){return clock;}
        @Override public Vec3 position(){return origin;}
        @Override public SynchedEntityData getEntityData(){return data;}
        @Override public boolean isStrikeActive(){return false;}
        @Override public float strikeAge(float partial){return -1;}
        @Override public boolean isArmorBeamR52(){return true;}
        @Override public float armorBeamAgeR52(float partial){return age;}
        @Override public boolean isFirstBattleActive(){return false;}
        @Override public net.minecraft.nbt.CompoundTag strikeEntryR36(){return new net.minecraft.nbt.CompoundTag();}
        @Override public float getYRot(){return yaw;}
    }
    public static void main(String[] args)throws Exception
    {
        Path bundle=Path.of(args[0]),out=Path.of(args[1]);Files.createDirectories(out);
        System.setProperty("projectseele.gameplayReviewDirectory",bundle.toString());
        System.setProperty("projectseele.bodyPhysicsProfiles",bundle.resolve("articulated_bodies_r35.json").toString());
        EvaKnifeRecoveryR52Test.main(new String[0]);
        var unsafe=(Unsafe)field(EvaKnifeRecoveryR52Test.class,"unsafe").get(null);
        Level clock=(EmptyClock)unsafe.allocateInstance(EmptyClock.class);
        AABB plate=new AABB(27,78,352,34,81,359);Vec3 aim=new Vec3(30.5,80.5,355.5);
        var frame=ShamshelPosedContactsR48.class.getDeclaredMethod("frame",ShamshelEntity.class);frame.setAccessible(true);
        var load=ShamshelPosedContactsR48.class.getDeclaredMethod("model");load.setAccessible(true);Object mesh=load.invoke(null);
        check(mesh!=null,"Selected actual Shamshel mesh required");
        Object[] vertices=(Object[])call(mesh,"vertices"),bones=(Object[])call(mesh,"bones");int[] skinBones=(int[])call(mesh,"skinBones");
        boolean[] body=new boolean[vertices.length];
        for(int i=0;i<body.length;i++)
        {
            body[i]=true;int[] joints=(int[])call(vertices[i],"joints");float[] weights=(float[])call(vertices[i],"weights");
            for(int k=0;k<4;k++)if(weights[k]>0&&((String)call(bones[skinBones[joints[k]]],"name")).startsWith("whip_"))body[i]=false;
        }
        var results=new ArrayList<Map<String,Object>>();var rows=new ArrayList<Map<String,Object>>();
        for(int side:new int[]{-1,1})
        {
            Whip a=(Whip)unsafe.allocateInstance(Whip.class);a.clock=clock;a.origin=new Vec3(10.5,81.35,355.5);a.aim=aim;a.yaw=-90;a.yBodyRot=-90;a.side=side;
            field(Entity.class,"position").set(a,a.origin);field(Entity.class,"uuid").set(a,UUID.randomUUID());
            field(Entity.class,"bb").set(a,new AABB(.5,81,345.5,20.5,141,365.5));
            double minBody=Double.POSITIVE_INFINITY,minMesh=Double.POSITIVE_INFINITY,lengthError=0,rigError=0,bestTip=Double.POSITIVE_INFINITY;int hits=0,undergroundOutsidePlate=0;var lowest=new LinkedHashMap<String,Object>();
            double[] rest=null;Vec3 nearest=null;
            for(float age=0;age<=64;age+=.25F)
            {
                a.age=age;var points=ShamshelWhipMotion.points(a,age,0);var previous=ShamshelWhipMotion.points(a,age-.25F,0);
                if(age==28)
                {
                    var solve=ShamshelWhipMotion.class.getDeclaredMethod("groundRotations",ShamshelEntity.class,float.class,float.class);solve.setAccessible(true);var qs=(Quaternionf[])solve.invoke(null,a,age,0);
                    for(int i=0;i<4;i++){var euler=ShamshelWhipMotion.rotation(a,side,i,age,0);check(Math.abs(qs[i].dot(new Quaternionf().rotationZYX(euler.z,euler.y,euler.x)))>.999999F,"Production ZYX channels match solved joint quaternion");}
                    System.out.println("contact tip="+points.get(4)+" aim="+aim);
                }
                double[] lengths=new double[4];for(int i=0;i<4;i++)lengths[i]=points.get(i).distanceTo(points.get(i+1));
                if(rest==null)rest=lengths;else for(int i=0;i<4;i++)lengthError=Math.max(lengthError,Math.abs(lengths[i]-rest[i]));
                var rendered=ShamshelWhipMotion.bodyMatrix(a,age,0);
                for(int i=0;i<4;i++)
                {
                    String name="whip_"+(side>0?"l":"r")+"_"+i;Object bone=null;for(Object b:bones)if(call(b,"name").equals(name))bone=b;
                    Vector3f pivot=(Vector3f)call(bone,"pivot");Vec3 anchor=new Vec3(rendered.transformPosition(new Vector3f(pivot)));
                    rigError=Math.max(rigError,anchor.distanceTo(points.get(i)));
                    var rotation=ShamshelContactPoseR48.base(a,name,new Vector3f(),0);
                    rendered.translate(pivot).rotateZYX(rotation.z,rotation.y,rotation.x).translate(new Vector3f(pivot).negate());
                }
                if(age>=28&&age<=37)
                {
                    for(int i=1;i<5;i++)if(plate.contains(points.get(i))||plate.clip(points.get(i-1),points.get(i)).isPresent()||plate.clip(previous.get(i),points.get(i)).isPresent())hits++;
                    double distance=aim.distanceTo(points.get(4));if(distance<bestTip){bestTip=distance;nearest=points.get(4);}
                }
                if(true)
                {
                    Vec3[] posed=(Vec3[])call(frame.invoke(null,a),"points");
                    for(int i=0;i<posed.length;i++){if(posed[i].y<minMesh){minMesh=posed[i].y;lowest.put("age",age);lowest.put("point",xyz(posed[i]));lowest.put("bind",call(vertices[i],"point").toString());lowest.put("joints",call(vertices[i],"joints"));lowest.put("weights",call(vertices[i],"weights"));}if(body[i])minBody=Math.min(minBody,posed[i].y);if(posed[i].y<81&&!plate.contains(posed[i]))undergroundOutsidePlate++;}
                }
                rows.add(Map.of("actor","shamshel","side",side,"age",age,"body_pitch",ShamshelWhipMotion.bodyPitch(3,age),"points",points.stream().map(SurfaceArmorAttackR52::xyz).toList()));
            }
            check(hits>0,"Actual original-length ground whip must meet plate for side "+side);
            System.out.println("measured side="+side+" hits="+hits+" minBody="+minBody+" minFull="+minMesh+" tipError="+bestTip+" chainError="+rigError+" lengths="+lengthError);
            System.out.println(new GsonBuilder().create().toJson(lowest));
            System.out.println("under ground outside plate="+undergroundOutsidePlate);
            check(undergroundOutsidePlate==0,"Visible whip cannot enter the street outside its actual plate contact");check(bestTip<.001,"Original-length solver tip reaches actual plate aim without stretching");
            check(lengthError<.0001,"Original segment lengths preserved");check(rigError<.0001,"Rendered original-bone anchors equal contact chain");check(minBody>=81,"Actual body/head/tail mesh remains above ground");
            check(Math.abs(ShamshelWhipMotion.bodyPitch(3,0))<1e-7&&Math.abs(ShamshelWhipMotion.bodyPitch(3,64))<1e-7,"Continuous windup and return");
            results.add(Map.of("actor","shamshel","side",side,"plate_hits",hits,"maximum_length_error",lengthError,"maximum_renderer_chain_error",rigError,"minimum_body_mesh_y",minBody,"minimum_full_mesh_y",minMesh,"nearest_tip_distance",bestTip,"nearest_tip",xyz(nearest),"underground_vertices_outside_plate",undergroundOutsidePlate));
        }
        Beam s=(Beam)unsafe.allocateInstance(Beam.class);s.clock=clock;s.origin=new Vec3(10.5,81,355.5);s.yaw=-90;s.yBodyRot=-90;
        field(Entity.class,"position").set(s,s.origin);s.data=new SynchedEntityData(s);s.firstBattleSignals().define(s.data);SachielTacticsR34.define(s.data);
        field(Entity.class,"entityData").set(s,s.data);
        field(Entity.class,"bb").set(s,new AABB(1.5,81,346.5,19.5,141,364.5));
        for(int age:new int[]{0,16,32,40,52})
        {
            s.age=age;var pose=SachielBodyPoseR35.sample(s,0);
            Vec3 origin=SachielArmorBeamR52.origin(s,pose,0);boolean hit=plate.clip(origin,aim).isPresent();check(hit,"Actual posed skull ray geometrically intersects plate");
            rows.add(Map.of("actor","sachiel","age",age,"actual_skull_origin",xyz(origin),"aim",xyz(aim),"geometric_hit",hit));
        }
        var report=new LinkedHashMap<String,Object>();report.put("checks",checks);report.put("world_written",false);report.put("native_world_acceptance",false);report.put("block_los_claim",false);report.put("plate",new double[]{27,78,352,34,81,359});report.put("root",new double[]{10.5,81.35,355.5});report.put("maximum_pitch_radians",.60);report.put("sample_tick_interval",.25);report.put("results",results);
        var hashes=new TreeMap<String,String>();for(String name:List.of("mesh/shamshel.mesh.json","geo/shamshel.geo.json","mesh/sachiel.mesh.json","geo/sachiel.geo.json")){byte[] bytes=SurfaceArmorAttackR52.class.getResourceAsStream("/assets/projectseele/"+name).readAllBytes();hashes.put(name,HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(bytes)));}report.put("actual_classpath_geometry_sha256",hashes);
        var gson=new GsonBuilder().setPrettyPrinting().create();Files.writeString(out.resolve("ATTACK_REPORT.json"),gson.toJson(report));Files.writeString(out.resolve("ATTACK_ROWS.json"),gson.toJson(rows));System.out.println(gson.toJson(report));
    }
}
