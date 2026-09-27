package com.projectseele.entity;

import net.minecraft.core.BlockPos;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.syncher.EntityDataAccessor;
import net.minecraft.network.syncher.EntityDataSerializers;
import net.minecraft.network.syncher.SynchedEntityData;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.phys.Vec3;
import org.joml.Vector3f;

/** Shared actor clock and precise local origin for the directed first battle. */
public final class FirstBattleSignals
{
    private static long clientFrameNanos;
    private static boolean clientPaused;
    private static final java.util.Map<Entity,FirstBattleClock> CLIENT_CLOCKS=new java.util.WeakHashMap<>();
    public static void beginClientFrame(long now,boolean paused){clientFrameNanos=now;clientPaused=paused;}
    public static long clientFrameTime(){return clientFrameNanos==0?System.nanoTime():clientFrameNanos;}
    private static float clientTime(Entity entity,int age)
    {
        long now=clientFrameNanos==0?System.nanoTime():clientFrameNanos;FirstBattleClock clock=CLIENT_CLOCKS.get(entity);
        if(clock==null){clock=new FirstBattleClock(age,now);CLIENT_CLOCKS.put(entity,clock);}
        return (float)(clock.sample(age,now,clientPaused)/20D);
    }
    public interface Actor
    {
        SignalSet firstBattleSignals();
        boolean isFirstBattleEva();
    }
    public record Spec(Vec3 origin,float yaw,float evaYaw,float angelYaw,float initialDistance,float initialHeight) {}
    public static final class SignalSet
    {
        private final java.util.Map<Mob,Boolean> clientActive=new java.util.WeakHashMap<>();
        private final EntityDataAccessor<Boolean> active;
        private final EntityDataAccessor<Integer> age,partner,flags,weapon;
        private final EntityDataAccessor<BlockPos> origin;
        private final EntityDataAccessor<Vector3f> fraction;
        private final EntityDataAccessor<Float> yaw,evaYaw,angelYaw,distance,height;
        public SignalSet(Class<? extends Entity> type)
        {
            active=SynchedEntityData.defineId(type,EntityDataSerializers.BOOLEAN);
            age=SynchedEntityData.defineId(type,EntityDataSerializers.INT);partner=SynchedEntityData.defineId(type,EntityDataSerializers.INT);
            origin=SynchedEntityData.defineId(type,EntityDataSerializers.BLOCK_POS);fraction=SynchedEntityData.defineId(type,EntityDataSerializers.VECTOR3);
            yaw=SynchedEntityData.defineId(type,EntityDataSerializers.FLOAT);evaYaw=SynchedEntityData.defineId(type,EntityDataSerializers.FLOAT);angelYaw=SynchedEntityData.defineId(type,EntityDataSerializers.FLOAT);
            distance=SynchedEntityData.defineId(type,EntityDataSerializers.FLOAT);height=SynchedEntityData.defineId(type,EntityDataSerializers.FLOAT);
            flags=SynchedEntityData.defineId(type,EntityDataSerializers.INT);weapon=SynchedEntityData.defineId(type,EntityDataSerializers.INT);
        }
        public void define(SynchedEntityData data)
        {
            data.define(active,false);data.define(age,0);data.define(partner,-1);data.define(origin,BlockPos.ZERO);data.define(fraction,new Vector3f());
            data.define(yaw,0F);data.define(evaYaw,0F);data.define(angelYaw,180F);data.define(distance,34F);data.define(height,0F);data.define(flags,0);data.define(weapon,-1);
        }
        public boolean active(Entity entity){return entity.getEntityData().get(active);}
        public int age(Entity entity){return entity.getEntityData().get(age);}
        public int partner(Entity entity){return entity.getEntityData().get(partner);}
        public void clientPhysics(Mob entity)
        {
            if(!entity.level().isClientSide)return;
            if(active(entity)){clientActive.put(entity,true);entity.noPhysics=true;}
            else if(clientActive.remove(entity)!=null)entity.noPhysics=(entity.getEntityData().get(flags)&1)!=0;
        }
        public void advance(Entity entity,int tick,int other){entity.getEntityData().set(age,tick);entity.getEntityData().set(partner,other);}
        public float time(Entity entity,float partial)
        {
            int tick=age(entity);Entity clockOwner=entity;
            if(!active(entity))
            {
                if(entity.level().isClientSide)CLIENT_CLOCKS.remove(entity);
                return Math.max(0,tick/20F);
            }
            if("r10-choreography".equals(System.getProperty("projectseele.regionalBuild","")))return tick/20F;
            if(entity instanceof Actor actor&&!actor.isFirstBattleEva())
            {
                Entity hero=entity.level().getEntity(partner(entity));
                if(hero instanceof Actor other&&other.isFirstBattleEva()&&other.firstBattleSignals().active(hero)){tick=other.firstBattleSignals().age(hero);clockOwner=hero;}
            }
            return entity.level().isClientSide?clientTime(clockOwner,tick):Math.max(0,tick/20F);
        }
        public Spec spec(Entity entity)
        {
            var d=entity.getEntityData();var p=d.get(origin);var f=d.get(fraction);
            return new Spec(new Vec3(p.getX()+f.x,p.getY()+f.y,p.getZ()+f.z),d.get(yaw),d.get(evaYaw),d.get(angelYaw),d.get(distance),d.get(height));
        }
        private void setSpec(Entity entity,Spec spec)
        {
            var d=entity.getEntityData();BlockPos p=BlockPos.containing(spec.origin());
            d.set(origin,p);d.set(fraction,new Vector3f((float)(spec.origin.x-p.getX()),(float)(spec.origin.y-p.getY()),(float)(spec.origin.z-p.getZ())));
            d.set(yaw,spec.yaw);d.set(evaYaw,spec.evaYaw);d.set(angelYaw,spec.angelYaw);d.set(distance,spec.initialDistance);d.set(height,spec.initialHeight);
        }
        public void resume(Entity entity,Spec spec,int tick,int other)
        {
            if(entity instanceof net.minecraft.world.entity.LivingEntity body)
            {CombatFeelR31.clear(body);com.projectseele.physics.CombatBodyDynamics.acknowledgeHandoff(body);}
            setSpec(entity,spec);advance(entity,tick,other);entity.getEntityData().set(active,true);
        }
        public void begin(Mob entity,Spec spec,int other,int oldWeapon)
        {
            CombatFeelR31.clear(entity);
            com.projectseele.physics.CombatBodyDynamics.acknowledgeHandoff(entity);
            var d=entity.getEntityData();d.set(flags,(entity.noPhysics?1:0)|(entity.isNoGravity()?2:0)|(entity.isNoAi()?4:0));d.set(weapon,oldWeapon);
            setSpec(entity,spec);advance(entity,0,other);d.set(active,true);entity.noPhysics=true;entity.setNoGravity(true);entity.setNoAi(true);entity.setDeltaMovement(Vec3.ZERO);entity.fallDistance=0;
        }
        public int end(Mob entity)
        {
            var d=entity.getEntityData();int saved=d.get(flags),oldWeapon=d.get(weapon);
            d.set(active,false);d.set(partner,-1);entity.noPhysics=(saved&1)!=0;entity.setNoGravity((saved&2)!=0);entity.setNoAi((saved&4)!=0);entity.setDeltaMovement(Vec3.ZERO);entity.fallDistance=0;
            return oldWeapon;
        }
        public void save(Entity entity,CompoundTag tag)
        {
            if(!active(entity))return;Spec s=spec(entity);CompoundTag t=new CompoundTag();
            t.putDouble("X",s.origin.x);t.putDouble("Y",s.origin.y);t.putDouble("Z",s.origin.z);t.putFloat("Yaw",s.yaw);t.putFloat("EvaYaw",s.evaYaw);t.putFloat("AngelYaw",s.angelYaw);
            t.putFloat("Distance",s.initialDistance);t.putFloat("Height",s.initialHeight);t.putInt("Age",age(entity));t.putInt("Flags",entity.getEntityData().get(flags));t.putInt("Weapon",entity.getEntityData().get(weapon));tag.put("FirstBattleSceneR10",t);
        }
        public void restore(Mob entity,CompoundTag tag)
        {
            if(!tag.contains("FirstBattleSceneR10"))return;var t=tag.getCompound("FirstBattleSceneR10");
            CombatFeelR31.clear(entity);com.projectseele.physics.CombatBodyDynamics.acknowledgeHandoff(entity);
            Spec s=new Spec(new Vec3(t.getDouble("X"),t.getDouble("Y"),t.getDouble("Z")),t.getFloat("Yaw"),t.getFloat("EvaYaw"),t.getFloat("AngelYaw"),t.getFloat("Distance"),t.getFloat("Height"));
            setSpec(entity,s);var d=entity.getEntityData();d.set(age,t.getInt("Age"));d.set(flags,t.getInt("Flags"));d.set(weapon,t.getInt("Weapon"));d.set(active,true);
            entity.noPhysics=true;entity.setNoGravity(true);entity.setNoAi(true);
        }
    }
    private FirstBattleSignals() {}
}
