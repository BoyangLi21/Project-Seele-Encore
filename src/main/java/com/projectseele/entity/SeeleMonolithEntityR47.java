package com.projectseele.entity;

import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.protocol.Packet;
import net.minecraft.network.protocol.game.ClientGamePacketListener;
import net.minecraft.network.syncher.EntityDataAccessor;
import net.minecraft.network.syncher.EntityDataSerializers;
import net.minecraft.network.syncher.SynchedEntityData;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.network.NetworkHooks;

/** A world-owned communication monolith, with a persistent council number. */
public final class SeeleMonolithEntityR47 extends Entity
{
    private static final EntityDataAccessor<Integer> NUMBER=SynchedEntityData.defineId(SeeleMonolithEntityR47.class,EntityDataSerializers.INT);
    private static final EntityDataAccessor<Boolean> MEETING=SynchedEntityData.defineId(SeeleMonolithEntityR47.class,EntityDataSerializers.BOOLEAN);
    public SeeleMonolithEntityR47(EntityType<? extends SeeleMonolithEntityR47> type,Level level)
    {super(type,level);this.noPhysics=true;this.setNoGravity(true);this.setInvulnerable(true);}
    @Override protected void defineSynchedData(){entityData.define(NUMBER,1);entityData.define(MEETING,false);}
    public boolean meetingLightsR48(){return entityData.get(MEETING);}
    public int number(){return entityData.get(NUMBER);}
    public void setNumber(int value){if(value<0||value>12)throw new IllegalArgumentException("SEELE prop index");entityData.set(NUMBER,value);}
    @Override protected void readAdditionalSaveData(CompoundTag tag){setNumber(Math.max(0,Math.min(12,tag.getInt("CouncilNumber"))));}
    @Override protected void addAdditionalSaveData(CompoundTag tag){tag.putInt("CouncilNumber",number());}
    @Override public Packet<ClientGamePacketListener> getAddEntityPacket(){return NetworkHooks.getEntitySpawningPacket(this);}
    @Override public void tick()
    {
        super.tick();setDeltaMovement(Vec3.ZERO);
        if(level() instanceof net.minecraft.server.level.ServerLevel server)
            entityData.set(MEETING,com.projectseele.world.SeeleLightingR48.meetingModeR48(server));
        boolean desk=number()==0;double halfX=desk?2.25:1.1,halfZ=desk?.8:.175;
        double angle=Math.toRadians(getYRot()),x=Math.abs(Math.cos(angle))*halfX+Math.abs(Math.sin(angle))*halfZ,
                z=Math.abs(Math.sin(angle))*halfX+Math.abs(Math.cos(angle))*halfZ;
        setBoundingBox(new net.minecraft.world.phys.AABB(getX()-x,getY()+(desk?0:.18),getZ()-z,getX()+x,getY()+(desk?1.04:4.68),getZ()+z));
    }
    @Override public boolean canBeCollidedWith(){return true;}
    @Override public net.minecraft.world.phys.AABB getBoundingBoxForCulling()
    {
        return number()==0?new net.minecraft.world.phys.AABB(getX()-17.5,getY(),getZ()-7,getX()+17.5,getY()+1.1,getZ()+7):getBoundingBox();
    }
    @Override public boolean isPickable(){return false;}
    @Override public boolean isPushable(){return false;}
}
