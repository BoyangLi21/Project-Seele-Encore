package com.projectseele.entity;

import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.syncher.*;
import net.minecraft.util.Mth;
import net.minecraft.world.phys.Vec3;
import org.joml.Vector3f;
import org.joml.Quaternionf;

/** World-space support for a complete planted strike, shared by skin and hit tests. */
public final class EvaCombatSupportR33
{
    private record ReactionOrigin(long start,Vec3 position){}
    private static final com.projectseele.util.WeakIdentityMap<EvaUnit01Entity,ReactionOrigin> REACTIONS=new com.projectseele.util.WeakIdentityMap<>();
    private static final com.projectseele.util.WeakIdentityMap<EvaUnit01Entity,Vec3[]> TARGETS=new com.projectseele.util.WeakIdentityMap<>();
    private static final EntityDataAccessor<CompoundTag> CONTACTS=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.COMPOUND_TAG);
    private static final EntityDataAccessor<Vector3f> DIRECTION=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.VECTOR3);
    public static boolean bootstrap(){return true;}
    public static void define(SynchedEntityData d){d.define(CONTACTS,new CompoundTag());d.define(DIRECTION,new Vector3f(0,0,1));}
    public static boolean ready(EvaUnit01Entity e)
    {
        var p=EvaGameplayMotionR32.profile(EvaGameplayMotionR32.variant(e));
        return p!=null&&p.has("combat_foundation")&&p.get("combat_foundation").getAsInt()>=33;
    }
    public static boolean strike(EvaUnit01Entity e){return e.getOrdinaryAttackStage()>=0||e.isHeavyMotionActive()||EvaBerserkMotionR34.striking(e);}
    public static float stride(EvaUnit01Entity e,double dx,double dz,float fallback)
    {
        if(!ready(e)||EvaGameplayMotionR32.guardWeight(e)<.5F||e.isPilotProne()||e.isPilotCrouching()||e.isPilotSprinting())return fallback;
        Vec3 f=e.getForward();float front=(float)(dx*f.x+dz*f.z),right=(float)(dx*f.z-dz*f.x);
        Vector3f v=new Vector3f(right,0,front);if(v.lengthSquared()<1e-6)return fallback;v.normalize();
        e.getEntityData().set(DIRECTION,new Vector3f(e.getEntityData().get(DIRECTION)).lerp(v,.25F));
        String name=Math.abs(front)>=Math.abs(right)?front>=0?"advance":"retreat":right>=0?"right":"left";
        var clip=EvaGameplayMotionR32.profile(EvaGameplayMotionR32.variant(e)).getAsJsonObject("clips").getAsJsonObject("r32_"+name);
        return clip==null?fallback:clip.get("stride_blocks").getAsFloat();
    }
    public static EvaBodyPose.Sample locomotion(EvaUnit01Entity e,EvaBodyPose.Sample guard,float partial)
    {
        if(!ready(e)||e.rifleMoveBlend(partial)<.01F)return guard;
        var dir=e.getEntityData().get(DIRECTION);float phase=e.rifleGaitPhase(partial);phase-=Mth.floor(phase);
        var fore=EvaBodyPose.gameplayClip(e,dir.z>=0?"advance":"retreat",phase);
        var side=EvaBodyPose.gameplayClip(e,dir.x>=0?"right":"left",phase);
        float w=Math.abs(dir.x)/Math.max(.001F,Math.abs(dir.x)+Math.abs(dir.z));
        return EvaBodyPose.blend(guard,EvaBodyPose.blend(fore,side,w),e.rifleMoveBlend(partial)*Math.min(1,Math.abs(dir.x)+Math.abs(dir.z)));
    }
    public static EvaBodyPose.Sample reactionStep(EvaUnit01Entity e,CombatFeelR31.Beat hit,float partial)
    {
        var start=REACTIONS.get(e);
        if(start==null||start.start!=hit.start()){start=new ReactionOrigin(hit.start(),e.position());REACTIONS.put(e,start);}
        Vec3 forward=e.getForward(),right=new Vec3(forward.z,0,-forward.x);
        double f=hit.direction().dot(forward),s=hit.direction().dot(right);
        String name=Math.abs(f)>=Math.abs(s)?f>=0?"advance":"retreat":s>=0?"right":"left";
        var clip=EvaGameplayMotionR32.profile(EvaGameplayMotionR32.variant(e)).getAsJsonObject("clips").getAsJsonObject("r32_"+name);
        double distance=(e.level().isClientSide?e.getPosition(partial):e.position()).subtract(start.position).horizontalDistance();
        return EvaBodyPose.gameplayClip(e,name,(float)Math.min(.48,distance/clip.get("stride_blocks").getAsFloat()));
    }
    public static Vector3f toe(EvaUnit01Entity e,String side)
    {
        var a=EvaGameplayMotionR32.profile(EvaGameplayMotionR32.variant(e)).getAsJsonObject("support_toes").getAsJsonArray(side);
        return new Vector3f(a.get(0).getAsFloat(),a.get(1).getAsFloat(),a.get(2).getAsFloat());
    }
    public static void capture(EvaUnit01Entity e,EvaBodyPose.Sample pose)
    {
        if(e.level().isClientSide||!ready(e)||!supported(e)||e.isPilotCrouching()||e.isPilotProne())return;
        CompoundTag t=new CompoundTag();t.putFloat("yaw",e.getYRot());t.putLong("plant",e.level().getGameTime());t.putInt("weapon",e.getWeapon());
        for(String s:new String[]{"l","r"})
        {
            String n="foot_"+s;Vector3f p=pose.matrix(n).transformPosition(new Vector3f(pose.rig.get(n).pivot()).add(toe(e,s)))
                    .mul(EvaScale.RENDER_SCALE).rotateY((180-e.getYRot())*Mth.DEG_TO_RAD);
            Vec3 w=e.position().add(p.x,p.y,p.z);
            var floor=e.level().clip(new net.minecraft.world.level.ClipContext(w.add(0,5,0),w.add(0,-8,0),
                    net.minecraft.world.level.ClipContext.Block.COLLIDER,net.minecraft.world.level.ClipContext.Fluid.NONE,e));
            if(floor.getType()!=net.minecraft.world.phys.HitResult.Type.BLOCK)
            {e.getEntityData().set(CONTACTS,new CompoundTag());return;}
            t.putDouble(s+"x",w.x);t.putDouble(s+"y",floor.getLocation().y);t.putDouble(s+"z",w.z);t.putDouble(s+"startY",Math.max(w.y,floor.getLocation().y));
            t.putBoolean(s+"active",true);t.putLong(s+"plant",e.level().getGameTime());
        }
        e.getEntityData().set(CONTACTS,t);
    }
    private static Vec3 plantTarget(EvaUnit01Entity e,CompoundTag t,String side,float partial,float soleOffset)
    {
        long since=EvaGameplayMotionR32.directed(e)?t.getLong(side+"plant"):t.getLong("plant");
        float step=Mth.clamp((e.level().getGameTime()-since+partial)/4F,0,1),u=step*step*step*(10+step*(-15+6*step));
        double ground=t.getDouble(side+"y")+soleOffset*EvaScale.RENDER_SCALE;
        double y=Mth.lerp(u,Math.max(t.getDouble(side+"startY"),ground),ground);
        return new Vec3(t.getDouble(side+"x"),y,t.getDouble(side+"z"));
    }
    public static Vec3 anchor(EvaUnit01Entity e,String side,float partial)
    {var t=e.getEntityData().get(CONTACTS);var targets=TARGETS.get(e);return t.isEmpty()||t.contains("release")||targets==null?null:targets[side.equals("l")?0:1];}
    private static boolean supported(EvaUnit01Entity e)
    {return e.onGround()&&!e.isVisuallyAirborneForRender()&&EvaGameplayMotionR32.airAge(e,0)<0;}
    public static void release(EvaUnit01Entity e)
    {if(!e.level().isClientSide)e.getEntityData().set(CONTACTS,new CompoundTag());TARGETS.remove(e);}
    public static void tick(EvaUnit01Entity e)
    {
        if(e.level().isClientSide||!ready(e))return;
        var beat=CombatFeelR31.beat(e);boolean fallen=beat!=null&&(beat.kind()==CombatFeelR31.DOWN||beat.kind()==CombatFeelR31.THROWN);
        boolean release=!supported(e)||e.isNervLogisticsLocked()||e.isFirstBattleActive()||EvaShutdownR30.disabled(e)
                ||e.getWeapon()!=EvaUnit01Entity.WEAPON_FISTS||e.isPilotCrouching()||e.isPilotProne()||fallen||!strike(e)&&e.rifleMoveBlend(1)>.18F;
        if(release&&!e.getEntityData().get(CONTACTS).isEmpty())e.getEntityData().set(CONTACTS,new CompoundTag());
        var t=e.getEntityData().get(CONTACTS);
        if(EvaGameplayMotionR32.directed(e)&&strike(e)&&!t.isEmpty())
        {
            var updated=t.copy();boolean changed=false;
            for(String side:new String[]{"l","r"})
            {
                boolean plant=EvaGameplayMotionR32.planted(e,side,0);
                if(plant==t.getBoolean(side+"active"))continue;
                updated.putBoolean(side+"active",plant);changed=true;
                if(plant)
                {
                    var pose=EvaBodyPose.sample(e,0);String n="foot_"+side;
                    var point=pose.matrix(n).transformPosition(new Vector3f(pose.rig.get(n).pivot()).add(toe(e,side))).mul(EvaScale.RENDER_SCALE).rotateY((180-e.getYRot())*Mth.DEG_TO_RAD);
                    var world=e.position().add(point.x,point.y,point.z);
                    var floor=e.level().clip(new net.minecraft.world.level.ClipContext(world.add(0,6,0),world.add(0,-10,0),net.minecraft.world.level.ClipContext.Block.COLLIDER,net.minecraft.world.level.ClipContext.Fluid.NONE,e));
                    if(floor.getType()==net.minecraft.world.phys.HitResult.Type.BLOCK)
                    {
                        updated.putDouble(side+"x",world.x);updated.putDouble(side+"y",floor.getLocation().y);updated.putDouble(side+"z",world.z);
                        updated.putDouble(side+"startY",world.y);updated.putLong(side+"plant",e.level().getGameTime());
                        CombatFoleyR36.step(e,new Vec3(world.x,floor.getLocation().y,world.z),false,1.1F);
                    }
                    else updated.putBoolean(side+"active",false);
                }
            }
            if(changed){e.getEntityData().set(CONTACTS,updated);t=updated;}
        }
        if(!t.isEmpty()&&!strike(e))
        {
            if(!t.contains("release")&&Math.abs(Mth.wrapDegrees(e.getYRot()-t.getFloat("yaw")))>35)
            {t=t.copy();t.putLong("release",e.level().getGameTime());e.getEntityData().set(CONTACTS,t);}
            if(t.contains("release")&&e.level().getGameTime()-t.getLong("release")>=8)e.getEntityData().set(CONTACTS,new CompoundTag());
        }
    }
    public static void apply(EvaUnit01Entity e,EvaBodyPose.Sample p,float partial)
    {
        TARGETS.remove(e);
        if(CombatReactionsR36.active(e))return;
        if(!ready(e)||!supported(e)||!EvaGameplayMotionR32.owns(e,partial)||e.isNervLogisticsLocked()||EvaShutdownR30.disabled(e))return;
        var beat=CombatFeelR31.beat(e);if(beat!=null&&(beat.kind()==CombatFeelR31.DOWN||beat.kind()==CombatFeelR31.THROWN))return;
        var t=e.getEntityData().get(CONTACTS);if(t.isEmpty()||t.getInt("weapon")!=EvaUnit01Entity.WEAPON_FISTS)return;
        var origin=e.level().isClientSide?e.getPosition(partial):e.position();
        String[] sides={"l","r"};Vector3f[] targets=new Vector3f[2];Quaternionf[] orientations=new Quaternionf[2];Vec3[] worldTargets=new Vec3[2];
        for(int i=0;i<2;i++)
        {
            String s=sides[i];
            String foot="foot_"+s;var orientation=p.matrix(foot).getUnnormalizedRotation(new Quaternionf());
            if(EvaGameplayMotionR32.directed(e)&&!t.getBoolean(s+"active"))
            {
                targets[i]=point(p,foot);orientations[i]=orientation;continue;
            }
            // A boot rolls on its real sole, not on an abstract marker floating
            // inside the mesh. Keep X/Z planted while its support patch changes.
            var planted=plantTarget(e,t,s,partial,EvaBodyPose.soleBelowToeR33(e,s,orientation,toe(e,s)));worldTargets[i]=planted;
            var target=new Vector3f((float)(planted.x-origin.x),(float)(planted.y-origin.y),(float)(planted.z-origin.z))
                    .rotateY(-(180-EvaAirTransportR31.frameYaw(e,partial))*Mth.DEG_TO_RAD).div(EvaScale.RENDER_SCALE);
            if(t.contains("release"))
            {
                float step=Mth.clamp((e.level().getGameTime()-t.getLong("release")+partial-i*4)/4F,0,1);
                float u=step*step*step*(10+step*(-15+6*step));
                var free=p.matrix(foot).transformPosition(new Vector3f(p.rig.get(foot).pivot()).add(toe(e,s)));
                target.lerp(free,u).add(0,(float)Math.sin(step*Math.PI)*.25F,0);
            }
            target.sub(orientation.transform(toe(e,s)));
            targets[i]=target;orientations[i]=orientation;
        }
        // A moving entry stance or an actual hit can differ from the authored
        // stance. Put the pelvis inside BOTH legs' reachable volumes before
        // solving either knee; otherwise the second foot can never reach its
        // support point and the visible sole silently slides several metres.
        for(int pass=0;pass<12;pass++)for(int i=0;i<2;i++)
        {
            if(EvaGameplayMotionR32.directed(e)&&!t.getBoolean(sides[i]+"active"))continue;
            String s=sides[i],a="leg_"+s,c="foot_"+s;Vector3f joint=knee(p,s);
            float reach=(joint.distance(p.rig.get(a).pivot())+joint.distance(p.rig.get(c).pivot()))*.997F;
            Vector3f delta=point(p,a).sub(targets[i]);float distance=delta.length();
            if(distance>reach){p.positions.get("root").sub(delta.mul(1-reach/distance));p.dirty();}
        }
        var profile=com.projectseele.physics.CombatBodyProfiles.get(e);
        for(int i=0;i<2;i++)if(!EvaGameplayMotionR32.directed(e)||t.getBoolean(sides[i]+"active"))
            com.projectseele.physics.AnatomicalLimbConstraints.reachFoot(p,profile,sides[i],targets[i],orientations[i]);
        TARGETS.put(e,worldTargets);
    }
    private static Vector3f point(EvaBodyPose.Sample p,String n){return p.matrix(n).transformPosition(new Vector3f(p.rig.get(n).pivot()));}
    private static Vector3f knee(EvaBodyPose.Sample p,String side)
    {String marker="r30_knee_socket_"+side;return p.rig.containsKey(marker)?new Vector3f(p.rig.get(marker).pivot()):new Vector3f(p.rig.get("shin_"+side).pivot()).add(0,11.4F/16,0);}
    private EvaCombatSupportR33(){}
}
