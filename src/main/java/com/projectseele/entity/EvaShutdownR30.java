package com.projectseele.entity;

import net.minecraft.nbt.*;
import net.minecraft.network.syncher.*;
import net.minecraft.server.level.ServerPlayer;
import org.joml.Quaternionf;
import org.joml.Vector3f;
import java.util.*;

/** Loss of power and loss of a pilot are persistent, recoverable airframe states. */
public final class EvaShutdownR30
{
    public static final int ACTIVE=0,POWER_LOCK=1,EMPTY=2,WRECK=3;
    private static final EntityDataAccessor<Integer> MODE=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.INT);
    private static final EntityDataAccessor<Long> SINCE=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.LONG);
    private static final EntityDataAccessor<CompoundTag> POSE=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.COMPOUND_TAG);
    private static final EntityDataAccessor<CompoundTag> ORIGIN=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.COMPOUND_TAG);
    private static final EntityDataAccessor<Boolean> WAITING=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.BOOLEAN);
    private static final EntityDataAccessor<CompoundTag> REST_BOUNDS=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.COMPOUND_TAG);
    private static final Map<EvaUnit01Entity,Memory> MEMORY=new WeakHashMap<>();
    private static final class Memory {boolean pilot;CompoundTag last=new CompoundTag();}
    public static boolean bootstrap(){return true;}
    public static void define(SynchedEntityData d){d.define(MODE,ACTIVE);d.define(SINCE,0L);d.define(POSE,new CompoundTag());d.define(ORIGIN,new CompoundTag());d.define(WAITING,false);d.define(REST_BOUNDS,new CompoundTag());}
    public static int mode(EvaUnit01Entity e){return e.getEntityData().get(MODE);}
    public static boolean disabled(EvaUnit01Entity e){return mode(e)!=ACTIVE;}
    public static boolean wreck(EvaUnit01Entity e){return mode(e)==WRECK;}
    public static boolean updatesBounds(EntityDataAccessor<?> accessor){return accessor==MODE||accessor==REST_BOUNDS;}
    public static long since(EvaUnit01Entity e){return e.getEntityData().get(SINCE);}
    public static CompoundTag pose(EvaUnit01Entity e){return e.getEntityData().get(POSE);}
    public static CompoundTag origin(EvaUnit01Entity e){return e.getEntityData().get(ORIGIN);}
    public static float collapse(EvaUnit01Entity e,float partial){return mode(e)==POWER_LOCK?1:EvaDorsalMechanism.smooth((float)(((e.level().getGameTime()-since(e))+(double)partial)/18D));}
    public static boolean displayed(EvaUnit01Entity e){return disabled(e)&&(!e.isNervLogisticsLocked()||e.getEntityData().get(WAITING))&&!e.hasActiveCarrierMotion()&&!e.isLaunchSequenceActive();}
    public static void waitingR31(EvaUnit01Entity e,boolean waiting){if(!e.level().isClientSide)e.getEntityData().set(WAITING,waiting);}
    public static void save(EvaUnit01Entity e,CompoundTag t){t.putInt("R30Shutdown",mode(e));t.putLong("R30ShutdownSince",since(e));t.put("R30FrozenPose",pose(e).copy());t.put("R30ShutdownOrigin",origin(e).copy());t.put("R35RestBounds",e.getEntityData().get(REST_BOUNDS).copy());}
    public static void load(EvaUnit01Entity e,CompoundTag t)
    {e.getEntityData().set(MODE,Math.max(0,Math.min(3,t.getInt("R30Shutdown"))));e.getEntityData().set(SINCE,t.getLong("R30ShutdownSince"));e.getEntityData().set(POSE,t.getCompound("R30FrozenPose").copy());e.getEntityData().set(ORIGIN,t.getCompound("R30ShutdownOrigin").copy());e.getEntityData().set(REST_BOUNDS,t.getCompound("R35RestBounds").copy());}
    public static net.minecraft.world.phys.AABB restBounds(EvaUnit01Entity e)
    {
        if(e.tickCount<=0||!displayed(e)||EvaAirTransportR31.active(e))return null;var b=e.getEntityData().get(REST_BOUNDS);if(b.isEmpty())return null;
        return new net.minecraft.world.phys.AABB(b.getDouble("x0"),b.getDouble("y0"),b.getDouble("z0"),b.getDouble("x1"),b.getDouble("y1"),b.getDouble("z1")).move(e.position());
    }
    public static void physicalRest(EvaUnit01Entity e,EvaBodyPose.Sample pose,net.minecraft.world.phys.AABB worldBounds)
    {
        var frozen=encode(pose);e.getEntityData().set(POSE,frozen);e.getEntityData().set(ORIGIN,frozen.copy());
        var b=worldBounds.move(e.position().scale(-1));CompoundTag bounds=new CompoundTag();bounds.putDouble("x0",b.minX);bounds.putDouble("y0",b.minY);bounds.putDouble("z0",b.minZ);bounds.putDouble("x1",b.maxX);bounds.putDouble("y1",b.maxY);bounds.putDouble("z1",b.maxZ);e.getEntityData().set(REST_BOUNDS,bounds);
    }
    public static void stored(EvaUnit01Entity e)
    {
        MEMORY.remove(e);
        if(e.getHealth()>0&&!EvaBayRepairR33.active(e))clear(e);
    }
    public static void clear(EvaUnit01Entity e)
    {
        if(e.level().isClientSide)return;e.getEntityData().set(MODE,ACTIVE);e.getEntityData().set(POSE,new CompoundTag());e.getEntityData().set(ORIGIN,new CompoundTag());e.getPersistentData().remove("R30FrozenPoseConfirmed");
        e.getEntityData().set(REST_BOUNDS,new CompoundTag());com.projectseele.physics.CombatBodyDynamics.cancel(e);
    }
    public static void ensureUnpilotedR31(EvaUnit01Entity e)
    {if(!e.level().isClientSide&&e.getPilotEntity()==null&&mode(e)==ACTIVE)begin(e,EMPTY);}
    public static void fail(EvaUnit01Entity e)
    {
        if(e.level().isClientSide)return;begin(e,WRECK);e.setHealth(0);e.setPersistenceRequired();
    }
    public static void restAfterFirstBattle(EvaUnit01Entity e,EvaBodyPose.Sample finalPose)
    {
        if(e.level().isClientSide)return;
        MEMORY.computeIfAbsent(e,k->new Memory()).last=encode(finalPose);
        begin(e,POWER_LOCK);
        // The authored final pose is authoritative; a delayed pre-cinematic
        // pilot snapshot must not replace it after the return packet.
        e.getPersistentData().putBoolean("R30FrozenPoseConfirmed",true);
    }
    private static void begin(EvaUnit01Entity e,int mode)
    {
        if(mode(e)==mode)return;
        if(mode!=POWER_LOCK&&!com.projectseele.physics.CombatBodyDynamics.active(e)&&!e.isNervLogisticsLocked()&&!e.hasActiveCarrierMotion())
            com.projectseele.physics.CombatBodyDynamics.start(e,e.getBoundingBox().getCenter(),e.getForward(),-1);
        var memory=MEMORY.computeIfAbsent(e,k->new Memory());
        e.getEntityData().set(ORIGIN,memory.last.isEmpty()?encode(EvaBodyPose.sample(e,1)):memory.last.copy());
        if(mode!=POWER_LOCK)e.stowHandsForShutdownR30();
        CompoundTag snapshot=mode==POWER_LOCK&&!memory.last.isEmpty()?memory.last.copy():encode(mode==POWER_LOCK?EvaBodyPose.sample(e,1):EvaBodyPose.inactivePoseR30(e,mode==WRECK));
        e.getEntityData().set(POSE,snapshot);e.getEntityData().set(SINCE,e.level().getGameTime());e.getEntityData().set(MODE,mode);
        if(mode==POWER_LOCK&&com.projectseele.physics.CombatBodyDynamics.active(e))
        {physicalRest(e,EvaBodyPose.sample(e,0),e.getBoundingBox());com.projectseele.physics.CombatBodyDynamics.cancel(e);}
        e.getPersistentData().putInt("R31ShutdownPoseVersion",31);
        e.getPersistentData().remove("R30FrozenPoseConfirmed");e.getNavigation().stop();e.setTarget(null);
        if(e instanceof EvaPrototypeEntity un)un.stopUNFlight();
        if(!e.isNervLogisticsLocked()&&!e.hasActiveCarrierMotion())e.setNoGravity(false);
        e.refreshDimensions();
        if(e.getPilotEntity() instanceof ServerPlayer pilot)pilot.sendSystemMessage(net.minecraft.network.chat.Component.literal(mode==POWER_LOCK?"主电源耗尽，机体姿态锁止。通信电源仍可呼叫运输回收。":"机体损毁，驱动系统已关闭。可通过电话请求回收，或弹出插入栓。"));
    }
    public static void tick(EvaUnit01Entity e)
    {
        if(e.level().isClientSide)return;var memory=MEMORY.computeIfAbsent(e,k->new Memory());boolean piloted=e.getPilotEntity()!=null;
        EvaDorsalMechanism.rearmAfterRepair(e);
        waitingR31(e,e.getPersistentData().getBoolean("R30AwaitingIntake")||e.getPersistentData().getBoolean("R30AwaitingNervRecovery"));
        if(e.tickCount>5&&(mode(e)==WRECK||mode(e)==EMPTY)&&e.getPersistentData().getInt("R31ShutdownPoseVersion")<31)
        {e.getEntityData().set(POSE,encode(EvaBodyPose.inactivePoseR30(e,mode(e)==WRECK)));e.getPersistentData().putInt("R31ShutdownPoseVersion",31);}
        if(mode(e)==WRECK&&e.getHealth()>0&&!EvaBayRepairR33.active(e))clear(e);
        if(mode(e)==POWER_LOCK&&!e.isPowerDepleted())clear(e);
        if(mode(e)==ACTIVE&&!e.isFirstBattleActive()&&!e.isBerserk())
        {
            if(!e.isExperimentalUnit()&&piloted&&e.isEntryPlugInserted()&&e.isPowerDepleted()&&e.getActivationTicks()==0&&!e.isNervLogisticsLocked())begin(e,POWER_LOCK);
            else if(memory.pilot&&!piloted&&!e.isNervLogisticsLocked()&&!e.isLaunchSequenceActive()&&!e.hasActiveCarrierMotion())begin(e,EMPTY);
            else if(e.isPoweredOn())memory.last=encode(EvaBodyPose.sample(e,1));
        }
        memory.pilot=piloted;
    }
    public static void acceptPilotPose(ServerPlayer player,int entityId,CompoundTag tag)
    {
        if(!(player.serverLevel().getEntity(entityId) instanceof EvaUnit01Entity e)||mode(e)!=POWER_LOCK||e.getPilotEntity()!=player
                ||e.getPersistentData().getBoolean("R30FrozenPoseConfirmed")||e.level().getGameTime()-since(e)>200||!valid(tag))return;
        e.getEntityData().set(POSE,tag.copy());e.getPersistentData().putBoolean("R30FrozenPoseConfirmed",true);
    }
    public static boolean valid(CompoundTag tag)
    {
        if(tag.isEmpty()||tag.size()>128)return false;
        for(String name:tag.getAllKeys())
        {
            if(!name.matches("[a-zA-Z0-9_]{1,64}"))return false;var a=tag.getList(name,Tag.TAG_FLOAT);if(a.size()!=9)return false;
            for(int i=0;i<9;i++){float v=a.getFloat(i);if(!Float.isFinite(v)||Math.abs(v)>(i<3?32:i<6?256:4)||i>=6&&v<0)return false;}
        }
        return true;
    }
    public static Vector3f euler(Quaternionf q)
    {
        return new Vector3f((float)Math.atan2(2*(q.w*q.x+q.y*q.z),1-2*(q.x*q.x+q.y*q.y)),
                (float)Math.asin(Math.max(-1,Math.min(1,2*(q.w*q.y-q.z*q.x)))),(float)Math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z)));
    }
    public static CompoundTag encode(EvaBodyPose.Sample sample)
    {
        CompoundTag out=new CompoundTag();for(String name:sample.rotations.keySet())
        {
            var r=euler(sample.rotations.get(name));var p=sample.positions.get(name);ListTag values=new ListTag();
            for(float v:new float[]{r.x,r.y,r.z,-p.x*16,p.y*16,p.z*16,1,1,1})values.add(FloatTag.valueOf(v));out.put(name,values);
        }return out;
    }
    public static void decode(CompoundTag tag,EvaBodyPose.Sample sample)
    {
        for(String name:tag.getAllKeys())if(sample.rotations.containsKey(name))
        {var a=tag.getList(name,Tag.TAG_FLOAT);if(a.size()!=9)continue;sample.rotations.put(name,new Quaternionf().rotationZYX(a.getFloat(2),a.getFloat(1),a.getFloat(0)));sample.positions.put(name,new Vector3f(-a.getFloat(3),a.getFloat(4),a.getFloat(5)).div(16));}
        sample.dirty();
    }
    private EvaShutdownR30() {}
}
