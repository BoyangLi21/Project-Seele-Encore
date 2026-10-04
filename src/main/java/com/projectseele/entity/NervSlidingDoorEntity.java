package com.projectseele.entity;

import com.projectseele.registry.ModEntities;
import com.projectseele.world.CommandRoomSlidingDoorDirector;
import java.util.Comparator;
import java.util.List;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.protocol.Packet;
import net.minecraft.network.protocol.game.ClientGamePacketListener;
import net.minecraft.network.syncher.EntityDataAccessor;
import net.minecraft.network.syncher.EntityDataSerializers;
import net.minecraft.network.syncher.SynchedEntityData;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.util.Mth;
import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.material.PushReaction;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.network.NetworkHooks;

/** Smooth two-leaf silver door for one authored three-wide command-room port. */
public final class NervSlidingDoorEntity extends Entity
{
    private static final EntityDataAccessor<Integer> DATA_DOOR_ID =
            SynchedEntityData.defineId(NervSlidingDoorEntity.class,
                    EntityDataSerializers.INT);
    private static final EntityDataAccessor<Boolean> DATA_AXIS_X =
            SynchedEntityData.defineId(NervSlidingDoorEntity.class,
                    EntityDataSerializers.BOOLEAN);
    private static final EntityDataAccessor<Float> DATA_OPEN =
            SynchedEntityData.defineId(NervSlidingDoorEntity.class,
                    EntityDataSerializers.FLOAT);
    private static final EntityDataAccessor<Float> DATA_TARGET =
            SynchedEntityData.defineId(NervSlidingDoorEntity.class,
                    EntityDataSerializers.FLOAT);
    private static final int HOLD_OPEN_TICKS = 80;
    private static final float COLLISION_THRESHOLD = 0.82F;

    private float clientOpen;
    private float clientOpenO;
    private int holdTicks;

    public NervSlidingDoorEntity(
            EntityType<? extends NervSlidingDoorEntity> type, Level level)
    {
        super(type, level);
        this.noPhysics = true;
        this.noCulling = true;
        this.setNoGravity(true);
        this.setInvulnerable(true);
    }

    @Override
    protected void defineSynchedData()
    {
        this.entityData.define(DATA_DOOR_ID, -1);
        this.entityData.define(DATA_AXIS_X, true);
        this.entityData.define(DATA_OPEN, 0.0F);
        this.entityData.define(DATA_TARGET, 0.0F);
    }

    @Override protected void readAdditionalSaveData(CompoundTag tag) {}
    @Override protected void addAdditionalSaveData(CompoundTag tag) {}

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
        if (this.level().isClientSide)
        {
            this.clientOpenO = this.clientOpen;
            this.clientOpen = this.entityData.get(DATA_OPEN);
            return;
        }

        float current = this.entityData.get(DATA_OPEN);
        float target = this.entityData.get(DATA_TARGET);
        if (target > 0.5F && current >= 0.995F)
        {
            if (this.holdTicks > 0)
            {
                this.holdTicks--;
            }
            else if (this.level() instanceof ServerLevel level
                    && !CommandRoomSlidingDoorDirector.apertureOccupied(
                            level, this.getDoorId()))
            {
                this.entityData.set(DATA_TARGET, 0.0F);
                target = 0.0F;
            }
        }

        float next = Mth.approach(current, target, 0.085F);
        if (target < 0.5F && next <= COLLISION_THRESHOLD
                && this.level() instanceof ServerLevel level)
        {
            if (CommandRoomSlidingDoorDirector.apertureOccupied(
                    level, this.getDoorId()))
            {
                this.requestOpen();
                target = 1.0F;
                next = Mth.approach(current, target, 0.085F);
            }
            else
            {
                CommandRoomSlidingDoorDirector.maintainCollision(
                        level, this.getDoorId(), true);
            }
        }
        else if (target > 0.5F && next >= COLLISION_THRESHOLD
                && this.level() instanceof ServerLevel level)
        {
            CommandRoomSlidingDoorDirector.maintainCollision(
                    level, this.getDoorId(), false);
        }
        if (Math.abs(next - current) > 1.0E-5F)
        {
            this.entityData.set(DATA_OPEN, next);
        }
    }

    public int getDoorId()
    {
        return this.entityData.get(DATA_DOOR_ID);
    }

    public boolean isAxisX()
    {
        return this.entityData.get(DATA_AXIS_X);
    }

    public float getOpenProgress(float partialTick)
    {
        if(!this.level().isClientSide)return this.entityData.get(DATA_OPEN);
        return Mth.lerp(partialTick, this.clientOpenO, this.clientOpen);
    }
    public float requestedOpenProgress(){return this.entityData.get(DATA_TARGET);}
    /** Read-only actual server hold for the one-lane review witness. */
    public int reviewHoldTicksR45(){return this.holdTicks;}

    public void requestOpen()
    {
        this.holdTicks = HOLD_OPEN_TICKS;
        this.entityData.set(DATA_TARGET, 1.0F);
    }

    /** Short renewable hold used by arbitrary buttons, levers and redstone. */
    public void requestRedstoneOpen()
    {
        this.holdTicks = Math.max(this.holdTicks, 12);
        this.entityData.set(DATA_TARGET, 1.0F);
    }

    public static NervSlidingDoorEntity reconcile(
            ServerLevel level, int doorId, boolean axisX, Vec3 centre)
    {
        AABB search = new AABB(centre, centre).inflate(2.5D);
        List<NervSlidingDoorEntity> matches = level.getEntitiesOfClass(
                NervSlidingDoorEntity.class, search,
                door -> door.getDoorId() == doorId);
        matches.sort(Comparator.comparingInt(Entity::getId));
        NervSlidingDoorEntity door;
        if (matches.isEmpty())
        {
            door = ModEntities.NERV_SLIDING_DOOR.get().create(level);
            if (door == null)
            {
                return null;
            }
            door.entityData.set(DATA_DOOR_ID, doorId);
            door.entityData.set(DATA_AXIS_X, axisX);
            door.setPos(centre.x, centre.y, centre.z);
            if (!level.addFreshEntity(door))
            {
                return null;
            }
        }
        else
        {
            door = matches.get(0);
            door.entityData.set(DATA_AXIS_X, axisX);
            if (door.position().distanceToSqr(centre) > 1.0E-8D)
            {
                door.setPos(centre.x, centre.y, centre.z);
            }
            for (int index = 1; index < matches.size(); index++)
            {
                var duplicate=matches.get(index);
                if(duplicate.entityData.get(DATA_TARGET)>.5F)
                {door.entityData.set(DATA_TARGET,1F);door.holdTicks=Math.max(door.holdTicks,duplicate.holdTicks);}
                door.entityData.set(DATA_OPEN,Math.max(door.entityData.get(DATA_OPEN),duplicate.entityData.get(DATA_OPEN)));
                duplicate.discard();
            }
        }
        return door;
    }

    @Override public boolean isPickable() { return false; }
    @Override public boolean isPushable() { return false; }
    @Override public boolean hurt(DamageSource source, float amount) { return false; }
    @Override public PushReaction getPistonPushReaction() { return PushReaction.IGNORE; }
}
