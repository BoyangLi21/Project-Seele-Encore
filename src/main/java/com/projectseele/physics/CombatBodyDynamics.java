package com.projectseele.physics;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.*;
import com.projectseele.network.*;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.util.Mth;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.phys.*;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.network.PacketDistributor;
import org.joml.Matrix4f;
import org.joml.Quaternionf;
import org.joml.Vector3f;
import java.util.*;

/** One owner for loss of balance, articulated fall, ground rest and recovery. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class CombatBodyDynamics
{
    private static final float SCALE=CombatBodyProfiles.BLOCK_TO_PHYSICS;
    private static final net.minecraft.server.level.TicketType<net.minecraft.world.level.ChunkPos> TERRAIN_TICKET=
            net.minecraft.server.level.TicketType.create("projectseele_articulated_terrain",Comparator.comparingLong(net.minecraft.world.level.ChunkPos::toLong),80);
    private static final Map<LivingEntity,State> SERVER=new IdentityHashMap<>();
    private static final com.projectseele.util.WeakIdentityMap<LivingEntity,ClientState> CLIENT=new com.projectseele.util.WeakIdentityMap<>();
    private record History(long tick,Vec3 position,float yaw,Map<String,Matrix4f> matrices) {}
    private static final com.projectseele.util.WeakIdentityMap<LivingEntity,History> HISTORY=new com.projectseele.util.WeakIdentityMap<>();
    private static final com.projectseele.util.WeakIdentityMap<LivingEntity,Long> HANDOFF=new com.projectseele.util.WeakIdentityMap<>();
    private static final Set<EvaUnit01Entity> ACTION_OWNERS=Collections.newSetFromMap(new IdentityHashMap<>());
    private static final ThreadLocal<Set<LivingEntity>> SAMPLING=ThreadLocal.withInitial(()->Collections.newSetFromMap(new IdentityHashMap<>()));
    private static final class State
    {
        CombatBodyProfiles.Profile profile;ArticulatedBody simulation;EvaBodyPose.Sample template,pose,resting;
        boolean groundImpact,thrown;
        double stitchedMax;String stitchedBone="";
        Vec3 origin,position;float yaw;AABB bounds,terrainCoverage;long started;int age,stable,pendingTerrain,recoveryAge=-1;float recoveryStart,recoveryYaw,groundY;Vector3f recoveryOffset,endShift;
    }
    private static final class ClientState
    {EvaBodyPose.Sample previous,current;Vec3 previousPosition,position;AABB bounds;float yaw;long at;int mode;}
    public static boolean active(LivingEntity entity)
    {return !scripted(entity)&&!SAMPLING.get().contains(entity)&&(entity.level().isClientSide?CLIENT.get(entity)!=null:SERVER.containsKey(entity));}
    private static boolean scripted(LivingEntity entity)
    {return entity instanceof FirstBattleSignals.Actor actor&&actor.firstBattleSignals().active(entity);}
    public static boolean available(LivingEntity entity)
    {var p=CombatBodyProfiles.get(entity);return p!=null&&p.recovery()!=null;}
    public static boolean ownsGroundAction(EvaUnit01Entity eva)
    {
        return (EvaGameplayMotionR32.serverMovement(eva)||(eva.isMeleeWeapon()&&eva.hasLiveActionForRender(0)||CombatReactionsR36.ownsDisplacement(eva))&&!eva.isVisuallyAirborneForRender())
                &&!eva.isNervLogisticsLocked()&&!eva.isLaunchSequenceActive()&&!eva.isFirstBattleActive()
                &&!EvaShutdownR30.disabled(eva)&&available(eva);
    }
    public static int phase(LivingEntity entity)
    {if(!active(entity))return 0;return entity.level().isClientSide?CLIENT.get(entity).mode:SERVER.get(entity).recoveryAge<0?1:2;}
    public static boolean recentHandoff(LivingEntity entity)
    {return entity.level().getGameTime()<HANDOFF.getOrDefault(entity,0L);}
    public static void acknowledgeHandoff(LivingEntity entity){HANDOFF.remove(entity);}
    public static float facing(LivingEntity entity)
    {return entity.level().isClientSide?CLIENT.get(entity).yaw:SERVER.get(entity).yaw;}
    public static AABB bounds(LivingEntity entity)
    {if(!active(entity))return null;return entity.level().isClientSide?CLIENT.get(entity).bounds:SERVER.get(entity).bounds;}
    public static EvaBodyPose.Sample raw(LivingEntity entity,float partial)
    {
        var set=SAMPLING.get();boolean added=set.add(entity);
        try
        {
            if(entity instanceof EvaUnit01Entity eva)return EvaBodyPose.sample(eva,partial);
            return SachielBodyPoseR35.sample((SachielEntity)entity,partial);
        }
        finally{if(added)set.remove(entity);}
    }
    public static boolean rawSampling(LivingEntity entity){return SAMPLING.get().contains(entity);}
    @SubscribeEvent public static void remember(net.minecraftforge.event.entity.living.LivingEvent.LivingTickEvent event)
    {
        var actor=event.getEntity();if(actor.level().isClientSide)return;
        if(actor instanceof EvaUnit01Entity e&&ownsGroundAction(e))ACTION_OWNERS.add(e);
        if(actor.tickCount%2!=0||active(actor)||scripted(actor)||!(actor instanceof EvaUnit01Entity||actor instanceof SachielEntity)||!available(actor))return;
        if(actor instanceof EvaUnit01Entity eva&&(eva.isNervLogisticsLocked()||eva.isFirstBattleActive()||EvaAirTransportR31.active(eva)))return;
        var profile=CombatBodyProfiles.get(actor);var pose=raw(actor,0);AnatomicalLimbConstraints.apply(pose,profile);
        HISTORY.put(actor,new History(actor.level().getGameTime(),actor.position(),actor.getYRot(),CombatBodyProfiles.physicalMatrices(pose,profile)));
    }
    public static EvaBodyPose.Sample sample(LivingEntity entity,float partial)
    {
        if(!entity.level().isClientSide)return CombatBodyProfiles.copy(SERVER.get(entity).pose);
        var state=CLIENT.get(entity);float alpha=Mth.clamp((entity.level().getGameTime()-state.at+partial)/2F,0,1);
        var pose=CombatBodyProfiles.copy(state.previous);
        for(String n:pose.rig.keySet()){pose.rotations.get(n).slerp(state.current.rotations.get(n),alpha);pose.positions.get(n).lerp(state.current.positions.get(n),alpha);}
        Vec3 target=state.previousPosition.lerp(state.position,alpha),actual=entity.getPosition(partial);
        var offset=target.subtract(actual).toVector3f().rotateY(-(180-state.yaw)*Mth.DEG_TO_RAD).div(EvaScale.RENDER_SCALE);
        pose.positions.get("root").add(offset);pose.dirty();stitch(pose,CombatBodyProfiles.get(entity));return pose;
    }
    private static void stitch(EvaBodyPose.Sample pose,CombatBodyProfiles.Profile profile)
    {
        for(var element:profile.definition().getAsJsonArray("bodies"))
        {
            var row=element.getAsJsonObject();if(row.get("parent").isJsonNull())continue;String n=row.get("name").getAsString(),parent=row.get("parent").getAsString();var a=row.getAsJsonArray("joint");
            var joint=new Vector3f(a.get(3).getAsFloat(),a.get(7).getAsFloat(),a.get(11).getAsFloat()).div(CombatBodyProfiles.MODEL_TO_PHYSICS);
            var wanted=pose.matrix(parent).transformPosition(new Vector3f(joint));
            var current=pose.matrix(n).transformPosition(new Vector3f(joint));var correction=wanted.sub(current);
            String rigParent=pose.rig.get(n).parent();if(rigParent!=null)pose.matrix(rigParent).invert().transformDirection(correction);
            pose.positions.get(n).add(correction);pose.dirty();
        }
        pose.dirty();
    }
    public static void normalize(LivingEntity entity,EvaBodyPose.Sample pose)
    {var p=CombatBodyProfiles.get(entity);if(p!=null)AnatomicalLimbConstraints.apply(pose,p);}
    public static void alignJoints(LivingEntity entity,EvaBodyPose.Sample pose)
    {var profile=CombatBodyProfiles.get(entity);if(profile!=null)stitch(pose,profile);}
    private static Vector3f local(State s,Vec3 point)
    {return point.subtract(s.origin).toVector3f().rotateY(-(180-s.yaw)*Mth.DEG_TO_RAD).mul(SCALE);}
    private static Vec3 world(State s,Vector3f point)
    {var p=new Vector3f(point).div(SCALE).rotateY((180-s.yaw)*Mth.DEG_TO_RAD);return s.origin.add(p.x,p.y,p.z);}
    public static boolean start(LivingEntity entity,Vec3 point,Vec3 direction,float strength)
    {return start(entity,point,direction,strength,null);}
    private static boolean start(LivingEntity entity,Vec3 point,Vec3 direction,float strength,EvaBodyPose.Sample releasePose)
    {
        if(!(entity.level() instanceof ServerLevel level)||!available(entity)||scripted(entity))return false;
        if(entity instanceof EvaUnit01Entity eva&&(eva.isNervLogisticsLocked()||eva.hasActiveCarrierMotion()||eva.isFirstBattleActive()||EvaAirTransportR31.active(eva)))return false;
        if(EvaCombatR31.holds(entity))return false;
        var previous=SERVER.get(entity);
        // A recovery is already a supported movement. Ordinary follow-up hits
        // may recoil the trunk, but must not restart it forever from frame zero.
        if(previous!=null&&previous.recoveryAge>=0)return true;
        if(previous!=null&&previous.recoveryAge<0)
        {impulse(previous,point,direction,strength*.65F);return true;}
        EvaBodyPose.Sample snapshot=releasePose!=null?releasePose:previous==null?raw(entity,0):CombatBodyProfiles.copy(previous.pose);
        if(previous==null&&entity instanceof EvaUnit01Entity eva&&eva.getWeapon()==EvaUnit01Entity.WEAPON_FISTS)
        {snapshot.rotations.get("head").rotateY(-eva.pilotHeadYawForRender(0)*Mth.DEG_TO_RAD).rotateX(-eva.pilotHeadPitchForRender(0)*Mth.DEG_TO_RAD);snapshot.dirty();}
        if(previous!=null){previous.simulation.close();SERVER.remove(entity);}
        State s=new State();s.profile=CombatBodyProfiles.get(entity);snapshot=CombatBodyProfiles.canonical(snapshot,s.profile);AnatomicalLimbConstraints.apply(snapshot,s.profile);stitch(snapshot,s.profile);s.template=CombatBodyProfiles.copy(snapshot);s.pose=CombatBodyProfiles.copy(snapshot);
        s.origin=entity.position();s.position=entity.position();s.yaw=entity.getYRot();s.bounds=entity.getBoundingBox();s.started=level.getGameTime();
        s.simulation=new ArticulatedBody(s.profile.definition(),CombatBodyProfiles.physicalMatrices(snapshot,s.profile));
        addTerrain(level,entity,s);Vec3 motion=entity.getDeltaMovement();s.simulation.velocity(motion.toVector3f().rotateY(-(180-s.yaw)*Mth.DEG_TO_RAD).mul(20*SCALE));
        var history=HISTORY.get(entity);long since=history==null?0:level.getGameTime()-history.tick;
        if(since>0&&since<=4&&history.position.distanceTo(s.origin)<12)
        {
            var transform=new Matrix4f().translation(local(s,history.position)).rotateY((s.yaw-history.yaw)*Mth.DEG_TO_RAD);
            Map<String,Matrix4f> previousFrames=new HashMap<>();history.matrices.forEach((n,m)->previousFrames.put(n,new Matrix4f(transform).mul(m)));
            s.simulation.motionFromPose(previousFrames,since/20F);
        }
        if(strength>=0)impulse(s,point,direction,strength);SERVER.put(entity,s);
        if(entity instanceof EvaUnit01Entity eva){eva.beginPhysicalControlR35();EvaCombatR31.clear(eva);if(eva instanceof EvaPrototypeEntity un)un.stopUNFlight();}
        if(entity instanceof SachielEntity angel)angel.cancelStrikeR31();
        send(entity,s,1);ProjectSeele.LOGGER.info("Articulated impact started actor={} rig={} point={}",entity.getUUID(),s.profile.key(),point);return true;
    }
    private static void impulse(State s,Vec3 point,Vec3 direction,float strength)
    {
        Vector3f p=local(s,point),force=direction.toVector3f().rotateY(-(180-s.yaw)*Mth.DEG_TO_RAD).normalize().mul(45+30*strength);
        var frame=s.simulation.frame();String nearest="torso_upper";double distance=Double.MAX_VALUE;
        for(var entry:frame.deformation().entrySet())
        {
            var pivot=new Vector3f(s.profile.rig().get(entry.getKey()).pivot()).mul(CombatBodyProfiles.MODEL_TO_PHYSICS);
            float d=entry.getValue().transformPosition(pivot).distanceSquared(p);if(d<distance){distance=d;nearest=entry.getKey();}
        }
        s.simulation.impulse(nearest,p,force);
    }
    public static boolean thrown(LivingEntity entity,Vec3 velocity)
    {
        EvaBodyPose.Sample release=null;var profile=CombatBodyProfiles.get(entity);var history=HISTORY.get(entity);
        if(profile!=null&&history!=null&&entity.level().getGameTime()-history.tick<=3)
        {
            float yaw=entity.getYRot();var translation=history.position.subtract(entity.position()).toVector3f().rotateY(-(180-yaw)*Mth.DEG_TO_RAD).mul(SCALE);
            var transform=new Matrix4f().translation(translation).rotateY((yaw-history.yaw)*Mth.DEG_TO_RAD);Map<String,Matrix4f> matrices=new HashMap<>();history.matrices.forEach((n,m)->matrices.put(n,new Matrix4f(transform).mul(m)));
            release=CombatBodyProfiles.render(raw(entity,0),matrices,new Vector3f());
        }
        if(!start(entity,entity.getBoundingBox().getCenter(),velocity.normalize(),0,release))return false;
        State state=SERVER.get(entity);if(state==null)return false;state.thrown=true;
        state.simulation.velocity(velocity.toVector3f().rotateY(-(180-state.yaw)*Mth.DEG_TO_RAD).mul(20*SCALE));return true;
    }
    private static boolean retainTerrain(ServerLevel level,AABB coverage)
    {
        boolean ready=true;
        for(int x=Mth.floor(coverage.minX)>>4;x<=Mth.floor(coverage.maxX)>>4;x++)
            for(int z=Mth.floor(coverage.minZ)>>4;z<=Mth.floor(coverage.maxZ)>>4;z++)
            {
                var chunk=new net.minecraft.world.level.ChunkPos(x,z);level.getChunkSource().addRegionTicket(TERRAIN_TICKET,chunk,2,chunk);
                if(!level.getChunkSource().hasChunk(x,z))ready=false;
            }
        return ready;
    }
    private static boolean addTerrain(ServerLevel level,LivingEntity entity,State s)
    {
        var coverage=s.bounds.inflate(40,16,40);
        if(!retainTerrain(level,coverage))
        {
            s.terrainCoverage=null;
            if(++s.pendingTerrain==1&&"r40-airlift".equals(System.getProperty("projectseele.regionalBuild","")))
                ProjectSeele.LOGGER.info("R40 articulated terrain waiting: actor={} coverage={}",entity.getUUID(),coverage);
            return false;
        }
        if(s.pendingTerrain>0&&"r40-airlift".equals(System.getProperty("projectseele.regionalBuild","")))
            ProjectSeele.LOGGER.info("R40 articulated terrain ready: actor={} waitedTicks={}",entity.getUUID(),s.pendingTerrain);
        s.pendingTerrain=0;s.simulation.clearTerrain();s.terrainCoverage=coverage;
        List<AABB> boxes=new ArrayList<>();for(var shape:level.getBlockCollisions(entity,s.terrainCoverage))boxes.addAll(shape.toAabbs());
        boxes=merge(boxes,true);boxes=merge(boxes,false);Quaternionf orientation=new Quaternionf().rotationY(-(180-s.yaw)*Mth.DEG_TO_RAD);
        for(var b:boxes)s.simulation.addStaticBox(local(s,b.getCenter()),new Vector3f((float)b.getXsize(),(float)b.getYsize(),(float)b.getZsize()).mul(SCALE*.5F),orientation);
        return true;
    }
    private static List<AABB> merge(List<AABB> boxes,boolean x)
    {
        boxes.sort(Comparator.comparingDouble((AABB b)->b.minY).thenComparingDouble(b->b.maxY).thenComparingDouble(b->x?b.minZ:b.minX).thenComparingDouble(b->x?b.maxZ:b.maxX).thenComparingDouble(b->x?b.minX:b.minZ));
        List<AABB> out=new ArrayList<>();for(var b:boxes)
        {
            if(!out.isEmpty())
            {
                var a=out.get(out.size()-1);boolean same=a.minY==b.minY&&a.maxY==b.maxY&&(x?a.minZ==b.minZ&&a.maxZ==b.maxZ:a.minX==b.minX&&a.maxX==b.maxX);
                if(same&&(x?b.minX<=a.maxX+.000001:b.minZ<=a.maxZ+.000001)){out.set(out.size()-1,a.minmax(b));continue;}
            }
            out.add(b);
        }return out;
    }
    private static AABB worldBounds(State s,Vector3f min,Vector3f max)
    {
        AABB result=null;for(float x:new float[]{min.x,max.x})for(float y:new float[]{min.y,max.y})for(float z:new float[]{min.z,max.z})
        {Vec3 p=world(s,new Vector3f(x,y,z));AABB point=new AABB(p,p);result=result==null?point:result.minmax(point);}return result;
    }
    private static void updateStandingActors(LivingEntity entity,State s)
    {
        if(!CombatReactionsR36.enabled(entity))return;s.simulation.beginActorFrame();
        for(var other:entity.level().getEntitiesOfClass(LivingEntity.class,s.bounds.inflate(45),e->e!=entity&&(e instanceof EvaUnit01Entity||e instanceof SachielEntity)&&e.isAlive()&&!active(e)))
        {
            if(other instanceof EvaUnit01Entity eva&&(eva.isNervLogisticsLocked()||eva.isFirstBattleActive()||EvaAirTransportR31.active(eva)))continue;
            // The throwing pair deliberately overlaps at the shoulder grip.
            // Enable body contact after release, not inside the paired hold.
            if(other instanceof EvaUnit01Entity eva&&EvaCombatR31.target(eva)==entity&&EvaCombatR31.action(eva)==EvaCombatR31.THROW)continue;
            var profile=CombatBodyProfiles.get(other);if(profile==null)continue;
            var pose=raw(other,0);AnatomicalLimbConstraints.apply(pose,profile);
            var frame=new Matrix4f().translation(local(s,other.position())).rotateY((s.yaw-other.getYRot())*Mth.DEG_TO_RAD);
            s.simulation.actor(other.getStringUUID(),profile.definition(),CombatBodyProfiles.physicalMatrices(pose,profile),frame);
        }
        s.simulation.endActorFrame();
    }
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(event.phase!=TickEvent.Phase.END)return;
        for(var actor:new ArrayList<>(ACTION_OWNERS))if(!ownsGroundAction(actor)||actor.isRemoved())
        {
            ACTION_OWNERS.remove(actor);
            if(!actor.isRemoved()&&!active(actor)&&!actor.isNervLogisticsLocked()&&!actor.isFirstBattleActive())
            {
                HANDOFF.put(actor,actor.level().getGameTime()+4);
                if(actor.onGround()&&!actor.isVisuallyAirborneForRender())SeeleNetwork.CHANNEL.send(PacketDistributor.TRACKING_ENTITY_AND_SELF.with(()->actor),new ClientboundCombatBodyPose(actor.getId(),actor.getUUID(),0,actor.position(),actor.getYRot(),actor.getBoundingBox(),new CompoundTag()));
            }
        }
        for(var entry:new ArrayList<>(SERVER.entrySet()))
        {
            LivingEntity entity=entry.getKey();State s=entry.getValue();
            if(entity.isRemoved()||scripted(entity)||entity instanceof EvaUnit01Entity e&&(e.isNervLogisticsLocked()||EvaAirTransportR31.active(e))){cancel(entity);acknowledgeHandoff(entity);continue;}
            try
            {
                s.age++;
                if(s.recoveryAge<0)
                {
                    updateStandingActors(entity,s);
                    var needed=s.bounds.inflate(12,8,12);
                    if(s.terrainCoverage==null||!s.terrainCoverage.contains(new Vec3(needed.minX,needed.minY,needed.minZ))
                            ||!s.terrainCoverage.contains(new Vec3(needed.maxX,needed.maxY,needed.maxZ)))
                    {if(!addTerrain((ServerLevel)entity.level(),entity,s)){entity.setDeltaMovement(Vec3.ZERO);continue;}}
                    else if(s.age%20==0&&!retainTerrain((ServerLevel)entity.level(),s.terrainCoverage))
                    {s.terrainCoverage=null;entity.setDeltaMovement(Vec3.ZERO);continue;}
                    if(s.age>2)s.simulation.step(.05F);var frame=s.simulation.frame();s.bounds=worldBounds(s,frame.min(),frame.max());
                    if(!s.groundImpact&&s.age>5&&frame.groundImpulse()>4)
                    {s.groundImpact=true;groundImpact((ServerLevel)entity.level(),world(s,frame.impactPoint()));}
                    var hip=new Vector3f(s.profile.rig().get("leg_l").pivot()).add(s.profile.rig().get("leg_r").pivot()).mul(.5F*CombatBodyProfiles.MODEL_TO_PHYSICS);
                    Vector3f moved=frame.deformation().get("torso_lower").transformPosition(new Vector3f(hip));
                    Vector3f offset=new Vector3f(moved.x-hip.x,frame.min().y,moved.z-hip.z);s.position=world(s,offset);
                    s.pose=CombatBodyProfiles.render(s.template,frame.deformation(),offset);
                    Map<String,Vector3f> beforeStitch=null;
                    if("r40-airlift".equals(System.getProperty("projectseele.regionalBuild","")))
                    {
                        beforeStitch=new HashMap<>();
                        for(var row:s.profile.definition().getAsJsonArray("bodies"))
                        {String n=row.getAsJsonObject().get("name").getAsString();beforeStitch.put(n,s.pose.matrix(n).transformPosition(new Vector3f(s.pose.rig.get(n).pivot())));}
                    }
                    stitch(s.pose,s.profile);
                    if(beforeStitch!=null)for(var before:beforeStitch.entrySet())
                    {
                        var n=before.getKey();double change=s.pose.matrix(n).transformPosition(new Vector3f(s.pose.rig.get(n).pivot())).distance(before.getValue())*EvaScale.RENDER_SCALE;
                        if(change>s.stitchedMax){s.stitchedMax=change;s.stitchedBone=n;}
                    }
                    s.stable=frame.supportContacts()>1&&frame.speed()<.40F?s.stable+1:0;
                    var beat=CombatFeelR31.beat(entity);
                    if(s.stable>0&&s.age>10&&s.thrown)
                    {s.thrown=false;CombatFeelR31.send(entity,CombatFeelR31.DOWN,beat==null?Vec3.ZERO:beat.direction(),beat==null?1:beat.strength(),64,0);}
                    if(s.age>18&&s.stable>=5&&entity.isAlive()&&!(entity instanceof EvaUnit01Entity eva&&EvaShutdownR30.disabled(eva)))beginRecovery(entity,s);
                }
                else recover(entity,s);
                if(!SERVER.containsKey(entity))continue;
                entity.setPos(s.position.x,s.position.y,s.position.z);entity.setYRot(s.yaw);entity.yBodyRot=entity.yHeadRot=s.yaw;entity.setBoundingBox(s.bounds);entity.setDeltaMovement(Vec3.ZERO);entity.resetFallDistance();entity.setOnGround(s.recoveryAge>=0||s.stable>0);
                if(s.stable>=12&&entity instanceof EvaUnit01Entity eva&&EvaShutdownR30.disabled(eva))
                {
                    if("r40-airlift".equals(System.getProperty("projectseele.regionalBuild","")))
                        ProjectSeele.LOGGER.info("R40 articulated rest: actor={} ticks={} root={} maxStitchBlocks={} bone={}",entity.getUUID(),s.age,s.position,s.stitchedMax,s.stitchedBone);
                    AABB sole=new AABB(s.bounds.minX,s.bounds.minY-.4,s.bounds.minZ,s.bounds.maxX,s.bounds.minY+.35,s.bounds.maxZ);double ground=Double.NEGATIVE_INFINITY;
                    for(var shape:entity.level().getBlockCollisions(entity,sole))for(var box:shape.toAabbs())if(box.maxY<=s.bounds.minY+.35)ground=Math.max(ground,box.maxY);
                    if(Double.isFinite(ground)){double lift=ground+.025-s.bounds.minY;s.position=s.position.add(0,lift,0);s.bounds=s.bounds.move(0,lift,0);entity.setPos(s.position.x,s.position.y,s.position.z);entity.setBoundingBox(s.bounds);}
                    EvaShutdownR30.physicalRest(eva,s.pose,s.bounds);cancel(entity);continue;
                }
                if(s.age%2==0)send(entity,s,s.recoveryAge<0?1:2);
            }
            catch(Exception error){ProjectSeele.LOGGER.error("Articulated body update failed: {}",entity.getUUID(),error);cancel(entity);}
        }
    }
    private static Vector3f hip(EvaBodyPose.Sample pose)
    {Vector3f p=new Vector3f(pose.rig.get("leg_l").pivot()).add(pose.rig.get("leg_r").pivot()).mul(.5F);return pose.matrix("torso_lower").transformPosition(p);}
    private static void groundImpact(ServerLevel level,Vec3 point)
    {
        var material=level.getBlockState(net.minecraft.core.BlockPos.containing(point).below());
        com.projectseele.world.GiantParticles.send(level,new net.minecraft.core.particles.BlockParticleOption(net.minecraft.core.particles.ParticleTypes.BLOCK,material),point.x,point.y+.5,point.z,58,6,.6,6,.16);
        com.projectseele.world.GiantParticles.send(level,net.minecraft.core.particles.ParticleTypes.POOF,point.x,point.y+.7,point.z,26,5,.5,5,.09);
        level.playSound(null,point.x,point.y,point.z,com.projectseele.registry.ModSounds.EVA_LAND.get(),net.minecraft.sounds.SoundSource.HOSTILE,6,.78F);
    }
    private static void rotate(EvaBodyPose.Sample pose,float angle)
    {
        Quaternionf rotation=new Quaternionf().rotationY(angle);Vector3f pivot=pose.rig.get("root").pivot();
        pose.rotations.put("root",rotation.mul(pose.rotations.get("root"),new Quaternionf()));pose.positions.put("root",rotation.transform(new Vector3f(pose.positions.get("root")).add(pivot)).sub(pivot));pose.dirty();
    }
    private static void beginRecovery(LivingEntity entity,State s)
    {
        s.resting=CombatBodyProfiles.copy(s.pose);s.recoveryAge=0;
        Vector3f front=s.pose.matrix("torso_upper").transformDirection(new Vector3f(0,0,-1));
        float[] fronts=s.profile.recovery().frontY();int chosen=0;float best=Float.POSITIVE_INFINITY;
        for(int i=0;i<fronts.length*.48F;i++){float error=Math.abs(fronts[i]-front.y)+i*.002F;if(error<best){best=error;chosen=i;}}
        s.recoveryStart=chosen/(float)Math.max(1,fronts.length-1);
        var start=CombatBodyProfiles.recovery(s.profile,s.recoveryStart);
        Vector3f from=start.matrix("head").transformPosition(new Vector3f(start.rig.get("head").pivot())).sub(hip(start));Vector3f to=s.pose.matrix("head").transformPosition(new Vector3f(s.pose.rig.get("head").pivot())).sub(hip(s.pose));
        s.recoveryYaw=(float)(Math.atan2(to.x,to.z)-Math.atan2(from.x,from.z));rotate(start,s.recoveryYaw);s.recoveryOffset=hip(s.pose).sub(hip(start));
        var end=CombatBodyProfiles.recovery(s.profile,1);rotate(end,s.recoveryYaw);end.positions.get("root").add(s.recoveryOffset);end.dirty();var live=raw(entity,0);rotate(live,s.recoveryYaw);
        s.endShift=hip(end).sub(hip(live));s.endShift.y=0;s.groundY=(float)((s.bounds.minY-s.origin.y)*SCALE);
    }
    private static EvaBodyPose.Sample mix(EvaBodyPose.Sample a,EvaBodyPose.Sample b,float weight)
    {var p=CombatBodyProfiles.copy(a);for(String n:p.rig.keySet()){p.rotations.get(n).slerp(b.rotations.get(n),weight);p.positions.get(n).lerp(b.positions.get(n),weight);}p.dirty();return p;}
    private static void recover(LivingEntity entity,State s)
    {
        s.recoveryAge++;float duration=s.profile.recovery().duration()*20*(1-s.recoveryStart)/1.55F;
        float t=Math.min(1,s.recoveryAge/duration);var target=CombatBodyProfiles.recovery(s.profile,Mth.lerp(t,s.recoveryStart,1));rotate(target,s.recoveryYaw);target.positions.get("root").add(s.recoveryOffset);target.dirty();
        var posed=mix(s.resting,target,EvaDorsalMechanism.smooth(Math.min(1,s.recoveryAge/9F)));
        if(t>.82F)
        {var live=raw(entity,0);rotate(live,s.recoveryYaw);live.positions.get("root").add(s.endShift);live.dirty();posed=mix(posed,live,EvaDorsalMechanism.smooth((t-.82F)/.18F));}
        AnatomicalLimbConstraints.apply(posed,s.profile);s.pose=posed;
        var reaction=EvaImpactResponse.sample(entity,0);
        s.pose.rotations.get("torso_upper").rotateX(reaction.pitch()*.45F).rotateZ(reaction.roll()*.45F);s.pose.dirty();
        var offset=local(s,s.position);var matrices=CombatBodyProfiles.physicalMatrices(s.pose,s.profile);
        for(var m:matrices.values())m.m30(m.m30()+offset.x).m31(m.m31()+offset.y).m32(m.m32()+offset.z);
        s.simulation.controlledPose(matrices);var geometry=s.simulation.frame();
        float lift=s.groundY-geometry.min().y;s.pose.positions.get("root").y+=lift/CombatBodyProfiles.MODEL_TO_PHYSICS;s.pose.dirty();
        for(var m:matrices.values())m.m31(m.m31()+lift);s.simulation.controlledPose(matrices);geometry=s.simulation.frame();s.bounds=worldBounds(s,geometry.min(),geometry.max());
        // Recovery is gated by completion of the supported body motion, not
        // by the old 64-tick timer which stood up a still-falling model.
        if(t>=1)
        {
            var shift=new Vector3f(s.endShift).mul(EvaScale.RENDER_SCALE).rotateY((180-s.yaw)*Mth.DEG_TO_RAD);s.position=s.position.add(shift.x,0,shift.z);
            // Bullet permits a small contact penetration. Vanilla's swept
            // movement does not depenetrate a vehicle already inside a floor.
            // Transfer control from the actual supporting block surface.
            double radius=entity.getBbWidth()*.35,ground=Double.NEGATIVE_INFINITY;
            AABB support=new AABB(s.position.x-radius,s.position.y-1.5,s.position.z-radius,s.position.x+radius,s.position.y+1.5,s.position.z+radius);
            for(var shape:entity.level().getBlockCollisions(entity,support))for(var box:shape.toAabbs())if(box.maxY<=s.position.y+1.5)ground=Math.max(ground,box.maxY);
            if(Double.isFinite(ground))s.position=new Vec3(s.position.x,ground+.025,s.position.z);
            s.yaw=Mth.wrapDegrees(s.yaw-s.recoveryYaw*Mth.RAD_TO_DEG);entity.setPos(s.position.x,s.position.y,s.position.z);entity.setYRot(s.yaw);entity.yBodyRot=entity.yHeadRot=s.yaw;
            entity.setDeltaMovement(Vec3.ZERO);entity.resetFallDistance();
            ProjectSeele.LOGGER.info("Articulated recovery handed off actor={} position={} yaw={}",entity.getUUID(),s.position,s.yaw);
            cancel(entity);CombatFeelR31.clear(entity);entity.refreshDimensions();entity.setOnGround(true);
        }
    }
    private static void send(LivingEntity entity,State s,int mode)
    {SeeleNetwork.CHANNEL.send(PacketDistributor.TRACKING_ENTITY_AND_SELF.with(()->entity),new ClientboundCombatBodyPose(entity.getId(),entity.getUUID(),mode,s.position,s.yaw,s.bounds,EvaShutdownR30.encode(s.pose)));}
    @SubscribeEvent public static void stopped(net.minecraftforge.event.server.ServerStoppedEvent event)
    {for(var state:SERVER.values())state.simulation.close();SERVER.clear();ACTION_OWNERS.clear();}
    public static void cancel(LivingEntity entity)
    {
        if(entity.level().isClientSide){CLIENT.remove(entity);return;}
        State state=SERVER.remove(entity);if(state==null)return;state.simulation.close();HANDOFF.put(entity,entity.level().getGameTime()+4);send(entity,state,0);
        if(entity instanceof EvaUnit01Entity eva&&eva.getPilotEntity() instanceof net.minecraft.server.level.ServerPlayer pilot)
            pilot.connection.send(new net.minecraft.network.protocol.game.ClientboundMoveVehiclePacket(entity));
    }
    public static void receive(LivingEntity entity,ClientboundCombatBodyPose packet)
    {
        if(entity instanceof FirstBattleSignals.Actor actor&&actor.firstBattleSignals().active(entity))
        {CLIENT.remove(entity);return;}
        if(packet.mode()==0){CLIENT.remove(entity);entity.setPos(packet.position().x,packet.position().y,packet.position().z);entity.setYRot(packet.yaw());entity.yBodyRot=entity.yHeadRot=packet.yaw();entity.setDeltaMovement(Vec3.ZERO);entity.resetFallDistance();entity.refreshDimensions();entity.setOnGround(true);return;}
        var profile=CombatBodyProfiles.get(entity);if(profile==null)return;var pose=new EvaBodyPose.Sample(profile.rig());EvaShutdownR30.decode(packet.pose(),pose);
        ClientState s=CLIENT.get(entity);if(s==null){s=new ClientState();s.current=pose;s.position=packet.position();CLIENT.put(entity,s);if(entity instanceof EvaUnit01Entity eva)eva.beginPhysicalControlR35();}
        s.previous=s.current;s.previousPosition=s.position;s.current=pose;s.position=packet.position();s.bounds=packet.bounds();s.yaw=packet.yaw();s.mode=packet.mode();s.at=entity.level().getGameTime();
        entity.setYRot(s.yaw);entity.yBodyRot=entity.yHeadRot=s.yaw;
    }
    private CombatBodyDynamics(){}
}
