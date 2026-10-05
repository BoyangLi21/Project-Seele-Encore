package com.projectseele.entity;

import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.protocol.Packet;
import net.minecraft.network.protocol.game.ClientGamePacketListener;
import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.material.PushReaction;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.network.NetworkHooks;

/**
 * Invisible fixed riding anchor for a physical NERV command chair.
 *
 * <p>The visible chair remains ordinary authored blocks.  Keeping the mount
 * separate means art revisions can change the chair silhouette without
 * turning the command room into a collection of movable vehicles.</p>
 */
public final class NervCommandSeatEntity extends Entity
{
    public NervCommandSeatEntity(
            EntityType<? extends NervCommandSeatEntity> type, Level level)
    {
        super(type, level);
        this.noPhysics = true;
        this.setNoGravity(true);
        this.setInvulnerable(true);
    }

    @Override
    protected void defineSynchedData()
    {
    }

    @Override
    protected void readAdditionalSaveData(CompoundTag tag)
    {
    }

    @Override
    protected void addAdditionalSaveData(CompoundTag tag)
    {
    }

    @Override
    public Packet<ClientGamePacketListener> getAddEntityPacket()
    {
        return NetworkHooks.getEntitySpawningPacket(this);
    }

    @Override
    public void tick()
    {
        super.tick();
        this.setDeltaMovement(Vec3.ZERO);
        if(!this.level().isClientSide&&this.getTags().contains("seele_office_seat")&&this.tickCount>5)
        {
            var pos=net.minecraft.core.BlockPos.of(this.getPersistentData().getLong("OfficeChair"));
            var chair=this.level().getBlockState(pos);
            boolean valid=chair.getBlock() instanceof com.projectseele.world.NervOfficeChairBlock
                    ||chair.getBlock() instanceof com.projectseele.world.PeriodFixtureBlock&&chair.getValue(com.projectseele.world.PeriodFixtureBlock.KIND)==com.projectseele.world.PeriodFixtureBlock.Kind.CAFE_STOOL;
            if(!this.isVehicle()||!valid)this.discard();
        }
    }

    @Override
    protected boolean canAddPassenger(Entity passenger)
    {
        if(this.getType()==com.projectseele.registry.ModEntities.PILOT_REST_SEAT_R47.get())
            return passenger instanceof TrainingPilotEntity pilot&&this.getPassengers().isEmpty()
                    &&(level().isClientSide||level() instanceof net.minecraft.server.level.ServerLevel server
                    &&com.projectseele.world.PilotRestroomsR47.ownsSeat(server,this,pilot));
        return passenger instanceof Player && this.getPassengers().isEmpty();
    }

    @Override
    protected void positionRider(Entity passenger, MoveFunction move)
    {
        if (!this.hasPassenger(passenger))
        {
            return;
        }
        move.accept(passenger, this.getX(), this.getY(), this.getZ());
    }

    @Override
    public Vec3 getDismountLocationForPassenger(LivingEntity passenger)
    {
        if(this.getType()==com.projectseele.registry.ModEntities.PILOT_REST_SEAT_R47.get()
                &&passenger instanceof TrainingPilotEntity pilot&&level() instanceof net.minecraft.server.level.ServerLevel server)
            return com.projectseele.world.PilotRestroomsR47.safeDismount(server,this,pilot).orElse(passenger.position());
        if(this.getTags().contains("seele_office_seat"))
        {
            var p=net.minecraft.core.BlockPos.of(this.getPersistentData().getLong("OfficeChair"));
            for(int turn:new int[]{0,90,-90,180})
            {
                Vec3 candidate=Vec3.atBottomCenterOf(p).add(Vec3.directionFromRotation(0,this.getYRot()+turn).scale(1.35));
                if(this.level().noCollision(passenger,passenger.getDimensions(net.minecraft.world.entity.Pose.STANDING).makeBoundingBox(candidate))
                        &&!this.level().getBlockState(net.minecraft.core.BlockPos.containing(candidate.add(0,-.1,0))).getCollisionShape(this.level(),net.minecraft.core.BlockPos.containing(candidate.add(0,-.1,0))).isEmpty())return candidate;
            }
            return Vec3.atBottomCenterOf(p).add(0,1.25,0);
        }
        // Every authored chair faces north. Two blocks south clears its
        // physical backrest before placing the player on the supported aisle.
        return this.position().add(0.0D, 0.08D, 2.25D);
    }

    @Override
    public boolean isPickable()
    {
        return false;
    }

    @Override
    public boolean isPushable()
    {
        return false;
    }

    @Override
    public boolean hurt(DamageSource source, float amount)
    {
        return false;
    }

    @Override
    public PushReaction getPistonPushReaction()
    {
        return PushReaction.IGNORE;
    }
}
