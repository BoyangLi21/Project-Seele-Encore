package com.projectseele.entity;

import com.google.gson.GsonBuilder;
import com.projectseele.physics.CombatBodyContacts;
import com.projectseele.physics.CombatBodyDynamics;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.*;
import net.minecraft.network.syncher.SynchedEntityData;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import sun.misc.Unsafe;

/** Calls the production FK/IK/whip functions with the selected real profiles.
 * This is a favourable free-space reach measurement, never native world LOS,
 * route/collider clearance or a replacement game. No source/world mutation. */
public final class SurfaceArmorReachR52
{
    private static final class Foot extends SachielEntity
    {
        Level clock; SynchedEntityData data; Vec3 origin,aim; float yaw; int mode;
        private Foot(){super((EntityType<? extends SachielEntity>)null,null);}
        @Override public Level level(){return clock;}
        @Override public SynchedEntityData getEntityData(){return data;}
        @Override public Vec3 position(){return origin;}
        @Override public float getYRot(){return yaw;} @Override public float getXRot(){return 0;}
        @Override public boolean isStrikeActive(){return true;} @Override public int strikeMode(){return mode;}
        @Override public Vec3 strikeAim(){return aim;}
        @Override public net.minecraft.nbt.CompoundTag strikeEntryR36(){return new net.minecraft.nbt.CompoundTag();}
        @Override public boolean isFirstBattleActive(){return false;}
    }
    private static final class Whip extends ShamshelEntity
    {
        Level clock; Vec3 origin;float yaw;int side,mode;
        private Whip(){super((EntityType<? extends ShamshelEntity>)null,null);}
        @Override public Level level(){return clock;}
        @Override public Vec3 position(){return origin;}
        @Override public boolean isSweeping(){return true;} @Override public float sweepYaw(){return yaw;}
        @Override public int sweepSide(){return side;} @Override public int sweepMode(){return mode;}
    }
    private static Field field(Class<?> type,String name)throws Exception {var f=type.getDeclaredField(name);f.setAccessible(true);return f;}
    private static double[] xyz(Vec3 p){return new double[]{p.x,p.y,p.z};}
    private static boolean intersects(AABB plate,Vec3 a,Vec3 b){return plate.contains(a)||plate.contains(b)||plate.clip(a,b).isPresent();}
    private static double distance(AABB box,Vec3 p){double x=Math.max(box.minX-p.x,Math.max(0,p.x-box.maxX)),y=Math.max(box.minY-p.y,Math.max(0,p.y-box.maxY)),z=Math.max(box.minZ-p.z,Math.max(0,p.z-box.maxZ));return Math.sqrt(x*x+y*y+z*z);}
    private static Vec3 contact(Foot actor,float age)
    {
        var pose=SachielGameplayMotionR32.pose(actor,age);
        CombatBodyDynamics.normalize(actor,pose);
        SachielGameplayMotionR32.adaptContact(actor,pose,age,0);
        String side=SachielStrike.strikingLeft(actor.mode)?"l":"r";
        var point=actor.mode==SachielStrike.STOMP?CombatBodyContacts.soleLocal(actor,pose,side)
                :pose.matrix("hand_"+side).transformPosition(new org.joml.Vector3f(pose.rig.get("hand_"+side).pivot()));
        var matrix=SachielStrike.root(actor,0);Vec3 hand=new Vec3(matrix.transformPosition(point));
        if(actor.mode!=SachielStrike.PILE)return hand;
        String bone="forearm_"+side;
        var joint=com.projectseele.physics.AnatomicalLimbConstraints.elbowJoint(com.projectseele.physics.CombatBodyProfiles.get(actor),side,pose.rig.get(bone).pivot());
        Vec3 elbow=new Vec3(matrix.transformPosition(pose.matrix(bone).transformPosition(joint)));
        float extension=EvaDorsalMechanism.smooth((age-21)/5)*(1-EvaDorsalMechanism.smooth((age-30)/7));
        return hand.add(hand.subtract(elbow).normalize().scale(extension*25));
    }
    public static void main(String[] args)throws Exception
    {
        Path bundle=Path.of(args[0]).toAbsolutePath(),out=Path.of(args[1]).toAbsolutePath();Files.createDirectories(out);
        System.setProperty("projectseele.gameplayReviewDirectory",bundle.toString());
        System.setProperty("projectseele.bodyPhysicsProfiles",bundle.resolve("articulated_bodies_r35.json").toString());
        EvaKnifeRecoveryR52Test.main(new String[0]); // Existing data-only native API harness; no game/world.
        Unsafe unsafe=(Unsafe)field(EvaKnifeRecoveryR52Test.class,"unsafe").get(null);
        Method context=EvaKnifeRecoveryR52Test.class.getDeclaredMethod("context",int.class,int.class,int.class);context.setAccessible(true);
        Object clockContext=context.invoke(null,0,0,0);Level clock=(Level)field(clockContext.getClass(),"clock").get(clockContext);
        if(!SachielGameplayMotionR32.ready())throw new IllegalStateException("Actual selected Sachiel motion absent");
        AABB plate=new AABB(27,78,352,34,81,359);Vec3 aim=new Vec3(30.5,80.5,355.5);
        var report=new LinkedHashMap<String,Object>();report.put("world_written",false);report.put("native_world_acceptance",false);
        report.put("plate",new double[]{27,78,352,34,81,359});report.put("production_strike_aim",xyz(aim));report.put("terrain_stage","Omitted only floor-lift/world-ray corrections: favourable free space; no reactions or grapple");
        var hashes=new LinkedHashMap<String,String>();for(String name:List.of("sachiel_gameplay_r32.json","articulated_bodies_r35.json"))hashes.put(name,HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(bundle.resolve(name)))));report.put("selected_resource_sha256",hashes);
        var results=new ArrayList<Map<String,Object>>();var rows=new ArrayList<Map<String,Object>>();
        for(double x:new double[]{10.5,50.5})
        {
            float yaw=x<30.5?-90:90;
            for(int mode:new int[]{SachielStrike.STOMP,SachielStrike.PILE})
            {
                Foot actor=(Foot)unsafe.allocateInstance(Foot.class);actor.clock=clock;actor.origin=new Vec3(x,81,355.5);actor.aim=aim;actor.yaw=yaw;actor.yBodyRot=yaw;actor.mode=mode;
                field(net.minecraft.world.entity.Entity.class,"position").set(actor,actor.origin);
                actor.data=new SynchedEntityData(actor);actor.firstBattleSignals().define(actor.data);SachielTacticsR34.define(actor.data);
                double best=Double.POSITIVE_INFINITY,minY=Double.POSITIVE_INFINITY;Vec3 nearest=null;int actualHits=0;
                for(int age=SachielStrike.contactStart(mode);age<=SachielStrike.contactEnd(mode);age++)for(int i=0;i<=4;i++)
                {
                    float t=age-1+i/4F;Vec3 a=contact(actor,t-.25F),b=contact(actor,t);
                    if(intersects(plate,a,b))actualHits++;if(distance(plate,b)<best){best=distance(plate,b);nearest=b;}minY=Math.min(minY,b.y);
                    rows.add(Map.of("actor","sachiel","x",x,"mode",mode,"age",t,"from",xyz(a),"to",xyz(b)));
                }
                results.add(Map.of("actor","sachiel","x",x,"mode",mode,"exact_production_segment_plate_hits",actualHits,"minimum_point_distance",best,"lowest_contact_y",minY,"nearest_contact",xyz(nearest)));
            }
            for(int mode:new int[]{0,1,2})for(int side:new int[]{-1,1})
            {
                Whip actor=(Whip)unsafe.allocateInstance(Whip.class);actor.clock=clock;actor.origin=new Vec3(x,81,355.5);actor.yaw=yaw;actor.mode=mode;actor.side=side;
                double best=Double.POSITIVE_INFINITY,minY=Double.POSITIVE_INFINITY;Vec3 nearest=null;int hits=0;
                for(int age=ShamshelWhipMotion.contactStart(mode);age<=ShamshelWhipMotion.contactEnd(mode);age++)for(int i=0;i<=4;i++)
                {
                    float t=age-1+i/4F;var now=ShamshelWhipMotion.points(actor,t,0);var before=ShamshelWhipMotion.points(actor,t-.25F,0);
                    for(int j=1;j<now.size();j++)
                    {
                        if(intersects(plate,now.get(j-1),now.get(j))||intersects(plate,before.get(j),now.get(j)))hits++;
                        for(Vec3 p:List.of(now.get(j-1),now.get(j))){if(distance(plate,p)<best){best=distance(plate,p);nearest=p;}minY=Math.min(minY,p.y);}
                    }
                    rows.add(Map.of("actor","shamshel","x",x,"mode",mode,"side",side,"age",t,"points",now.stream().map(SurfaceArmorReachR52::xyz).toList()));
                }
                results.add(Map.of("actor","shamshel","x",x,"mode",mode,"side",side,"exact_production_segment_plate_hits",hits,"minimum_vertex_distance",best,"lowest_vertex_y",minY,"nearest_vertex",xyz(nearest)));
            }
        }
        report.put("results",results);var gson=new GsonBuilder().setPrettyPrinting().create();Files.writeString(out.resolve("REACH_REPORT.json"),gson.toJson(report));Files.writeString(out.resolve("CONTACT_ROWS.json"),gson.toJson(rows));System.out.println(gson.toJson(results));
    }
    private SurfaceArmorReachR52(){}
}
