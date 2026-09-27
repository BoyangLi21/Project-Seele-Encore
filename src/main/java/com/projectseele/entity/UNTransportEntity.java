package com.projectseele.entity;

import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.protocol.Packet;
import net.minecraft.network.protocol.game.ClientGamePacketListener;
import net.minecraft.network.syncher.*;
import net.minecraft.world.entity.*;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.minecraft.util.Mth;
import net.minecraftforge.network.NetworkHooks;

/** One persistent service aircraft per active airlift, owned by the server job. */
public final class UNTransportEntity extends Entity
{
    private static final EntityDataAccessor<Integer> SERIAL=SynchedEntityData.defineId(UNTransportEntity.class,EntityDataSerializers.INT);
    private static final EntityDataAccessor<Boolean> CARGO=SynchedEntityData.defineId(UNTransportEntity.class,EntityDataSerializers.BOOLEAN);
    private static final EntityDataAccessor<Integer> KIND=SynchedEntityData.defineId(UNTransportEntity.class,EntityDataSerializers.INT);
    private static final EntityDataAccessor<Integer> CARGO_ID=SynchedEntityData.defineId(UNTransportEntity.class,EntityDataSerializers.INT);
    private static final EntityDataAccessor<Float> DEPLOY=SynchedEntityData.defineId(UNTransportEntity.class,EntityDataSerializers.FLOAT);
    private static final EntityDataAccessor<Boolean> NERV=SynchedEntityData.defineId(UNTransportEntity.class,EntityDataSerializers.BOOLEAN);
    private static final EntityDataAccessor<Float> HOIST=SynchedEntityData.defineId(UNTransportEntity.class,EntityDataSerializers.FLOAT);
    private float rigFrom,rigTarget,jawFrom=1,jawTarget=1;
    private long rigSince,jawSince;
    private boolean rigInitialized,jawInitialized;
    private Vec3 flightFrom,flightTo;private float flightYawFrom,flightYawTo;private long flightSince;
    public UNTransportEntity(EntityType<? extends UNTransportEntity> type,Level level)
    {super(type,level);noPhysics=true;noCulling=true;setNoGravity(true);setInvulnerable(true);}
    @Override protected void defineSynchedData(){entityData.define(SERIAL,0);entityData.define(CARGO,false);entityData.define(KIND,0);entityData.define(CARGO_ID,-1);entityData.define(DEPLOY,0F);entityData.define(NERV,false);entityData.define(HOIST,84F);}
    public float hoistDistance(){return entityData.get(HOIST);}
    public void setHoistDistance(float length){entityData.set(HOIST,Mth.clamp(length,84,144));}
    public boolean isNerv(){return entityData.get(NERV);}
    public void setNerv(){entityData.set(NERV,true);}
    public void configure(int serial,boolean cargo){entityData.set(SERIAL,serial);entityData.set(CARGO,cargo);}
    public int serial(){return entityData.get(SERIAL);}
    public boolean carrying(){return entityData.get(CARGO);}
    public boolean groundCart(){return entityData.get(KIND)==1;}
    public void setGroundCart(){entityData.set(KIND,1);}
    public int cargoEntityId(){return entityData.get(CARGO_ID);}
    /** Entity ids change on load; attachment/jaw state must survive rebinding. */
    public void rebindCargo(int id){entityData.set(CARGO_ID,id);}
    public void cargo(int id,boolean attached,float deployment){entityData.set(CARGO_ID,id);entityData.set(CARGO,attached);entityData.set(DEPLOY,Mth.clamp(deployment,0,1));}
    public float targetDeployment(){return entityData.get(DEPLOY);}
    private static float visual(float from,float target,long since,long now,float partial,float speed)
    {
        float elapsed=Math.max(0,(float)(now-since)+(levelPartial(partial)));
        return Mth.approach(from,target,elapsed*speed);
    }
    private static float levelPartial(float partial){return Mth.clamp(partial,0,1);}
    /** Aircraft can render outside the client's entity-ticking sections. A loaded
     * cradle must never disappear because its independent local tick cache froze. */
    public float rig(float partial)
    {
        long now=level().getGameTime();float target=carrying()?1:targetDeployment();
        if(carrying()||!rigInitialized){rigFrom=rigTarget=target;rigSince=now;rigInitialized=true;}
        else if(target!=rigTarget){rigFrom=visual(rigFrom,rigTarget,rigSince,now,0,.035F);rigTarget=target;rigSince=now;}
        return visual(rigFrom,rigTarget,rigSince,now,partial,.035F);
    }
    public float jaws(float partial)
    {
        long now=level().getGameTime();float target=carrying()?0:1;
        if(level().getEntity(cargoEntityId()) instanceof EvaUnit01Entity eva&&EvaAirTransportR31.active(eva))
        {
            target=EvaAirTransportR31.jawOpening(eva,partial);
            jawFrom=jawTarget=target;jawSince=now;jawInitialized=true;
            return target;
        }
        if(!jawInitialized){jawFrom=jawTarget=target;jawSince=now;jawInitialized=true;}
        else if(target!=jawTarget){jawFrom=visual(jawFrom,jawTarget,jawSince,now,0,.05F);jawTarget=target;jawSince=now;}
        return visual(jawFrom,jawTarget,jawSince,now,partial,.05F);
    }
    @Override public AABB getBoundingBoxForCulling(){return groundCart()?new AABB(getX()-65,getY()-3,getZ()-65,getX()+65,getY()+12,getZ()+65):new AABB(getX()-74,getY()-hoistDistance()-1,getZ()-60,getX()+74,getY()+22,getZ()+60);}
    @Override public boolean shouldRenderAtSqrDistance(double distance){return distance<1600*1600;}
    public Vec3 renderFlightPosition(float partial)
    {
        if(!level().isClientSide||flightTo==null)return new Vec3(Mth.lerp((double)partial,xOld,getX()),Mth.lerp((double)partial,yOld,getY()),Mth.lerp((double)partial,zOld,getZ()));
        return flightFrom.lerp(flightTo,Mth.clamp(((level().getGameTime()-flightSince)+(double)partial)/3D,0,1));
    }
    public float renderFlightYaw(float partial)
    {return flightTo==null?Mth.rotLerp(partial,yRotO,getYRot()):Mth.rotLerp((float)Mth.clamp(((level().getGameTime()-flightSince)+(double)partial)/3D,0,1),flightYawFrom,flightYawTo);}
    @Override public void lerpTo(double x,double y,double z,float yaw,float pitch,int steps,boolean teleport)
    {
        Vec3 from=flightTo==null?position():renderFlightPosition(0);float fromYaw=flightTo==null?getYRot():renderFlightYaw(0);
        flightTo=new Vec3(x,y,z);flightFrom=teleport?flightTo:from;flightYawTo=yaw;flightYawFrom=teleport?yaw:fromYaw;flightSince=level().getGameTime();
        // A service aircraft is tracked beyond loaded client chunks. Leaving
        // its spatial position at the old airport until tick() runs strands it
        // outside ticking sections forever. Relocate now; render on this clock.
        setPos(x,y,z);setYRot(yaw);setXRot(pitch);
    }
    @Override public void tick()
    {
        super.tick();
        if(!level().isClientSide&&groundCart()&&targetDeployment()>.01F&&tickCount%20==0&&level().getEntity(cargoEntityId())==null)
        {
            var level=(net.minecraft.server.level.ServerLevel)level();var id=com.projectseele.world.UNRecoveryR22.identity(level,serial());
            if(id!=null&&level.getEntity(id) instanceof EvaPrototypeEntity eva&&eva.distanceToSqr(this)<120*120)
                cargo(eva.getId(),false,targetDeployment());
        }
        if(!level().isClientSide&&!groundCart()&&getTags().contains("seele_un_airlift")&&tickCount>200
                &&!com.projectseele.world.UNAirLiftR29.ownsAircraft((net.minecraft.server.level.ServerLevel)level(),getUUID())){discard();return;}
    }
    @Override protected void addAdditionalSaveData(CompoundTag tag){tag.putInt("UNSerial",serial());tag.putBoolean("Cargo",carrying());tag.putInt("Kind",entityData.get(KIND));tag.putFloat("Deploy",entityData.get(DEPLOY));tag.putBoolean("NervAircraft",isNerv());tag.putFloat("HoistDistance",hoistDistance());}
    @Override protected void readAdditionalSaveData(CompoundTag tag){configure(tag.getInt("UNSerial"),tag.getBoolean("Cargo"));entityData.set(KIND,tag.getInt("Kind"));entityData.set(DEPLOY,tag.getFloat("Deploy"));entityData.set(NERV,tag.getBoolean("NervAircraft"));setHoistDistance(tag.contains("HoistDistance")?tag.getFloat("HoistDistance"):84);}
    @Override public Packet<ClientGamePacketListener> getAddEntityPacket(){return NetworkHooks.getEntitySpawningPacket(this);}
    @Override public boolean isPickable(){return false;}
    @Override public boolean isPushable(){return false;}
}
