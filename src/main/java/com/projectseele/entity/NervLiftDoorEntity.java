package com.projectseele.entity;

import com.projectseele.registry.ModEntities;
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

/** Smooth silver leaves for an S20 physical elevator landing. */
public final class NervLiftDoorEntity extends Entity
{
    private static final EntityDataAccessor<Integer> DATA_DOOR_ID =
            SynchedEntityData.defineId(NervLiftDoorEntity.class,
                    EntityDataSerializers.INT);
    private static final EntityDataAccessor<Boolean> DATA_AXIS_X =
            SynchedEntityData.defineId(NervLiftDoorEntity.class,
                    EntityDataSerializers.BOOLEAN);
    private static final EntityDataAccessor<Integer> DATA_WIDTH =
            SynchedEntityData.defineId(NervLiftDoorEntity.class,
                    EntityDataSerializers.INT);
    private static final EntityDataAccessor<Integer> DATA_HEIGHT =
            SynchedEntityData.defineId(NervLiftDoorEntity.class,
                    EntityDataSerializers.INT);
    private static final EntityDataAccessor<Float> DATA_OPEN =
            SynchedEntityData.defineId(NervLiftDoorEntity.class,
                    EntityDataSerializers.FLOAT);
    private static final EntityDataAccessor<Float> DATA_TARGET =
            SynchedEntityData.defineId(NervLiftDoorEntity.class,
                    EntityDataSerializers.FLOAT);
    private static final EntityDataAccessor<Integer> DATA_STYLE =
            SynchedEntityData.defineId(NervLiftDoorEntity.class,
                    EntityDataSerializers.INT);
    public static final int STYLE_SILVER = 0;
    public static final int STYLE_NERV_BLACK = 1;
    private float clientOpen;
    private float clientOpenO;

    public NervLiftDoorEntity(EntityType<? extends NervLiftDoorEntity> type,
                              Level level)
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
        this.entityData.define(DATA_DOOR_ID, 0);
        this.entityData.define(DATA_AXIS_X, true);
        this.entityData.define(DATA_WIDTH, 5);
        this.entityData.define(DATA_HEIGHT, 3);
        this.entityData.define(DATA_OPEN, 0.0F);
        this.entityData.define(DATA_TARGET, 0.0F);
        this.entityData.define(DATA_STYLE, STYLE_SILVER);
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
        float next = Mth.approach(current,
                this.entityData.get(DATA_TARGET), 0.075F);
        if (Math.abs(next - current) > 1.0E-5F)
        {
            this.entityData.set(DATA_OPEN, next);
        }
    }

    public int getDoorId() { return this.entityData.get(DATA_DOOR_ID); }
    public boolean isAxisX() { return this.entityData.get(DATA_AXIS_X); }
    public int getDoorWidth() { return this.entityData.get(DATA_WIDTH); }
    public int getDoorHeight() { return this.entityData.get(DATA_HEIGHT); }
    public int getDoorStyle() { return this.entityData.get(DATA_STYLE); }

    public float getOpenProgress(float partialTick)
    {
        if (!this.level().isClientSide) return this.entityData.get(DATA_OPEN);
        return Mth.lerp(partialTick, this.clientOpenO, this.clientOpen);
    }

    public void setOpen(boolean open)
    {
        this.entityData.set(DATA_TARGET, open ? 1.0F : 0.0F);
    }

    public static NervLiftDoorEntity reconcile(ServerLevel level, int doorId,
            boolean axisX, int width, int height, Vec3 centre)
    {
        return reconcile(level, doorId, axisX, width, height,
                STYLE_SILVER, centre);
    }

    public static NervLiftDoorEntity reconcile(ServerLevel level, int doorId,
            boolean axisX, int width, int height, int style, Vec3 centre)
    {
        AABB search = new AABB(centre, centre).inflate(4.0D);
        List<NervLiftDoorEntity> matches = level.getEntitiesOfClass(
                NervLiftDoorEntity.class, search,
                door -> door.getDoorId() == doorId);
        matches.sort(Comparator.comparingInt(Entity::getId));
        NervLiftDoorEntity door;
        if (matches.isEmpty())
        {
            door = ModEntities.NERV_LIFT_DOOR.get().create(level);
            if (door == null)
            {
                return null;
            }
            door.entityData.set(DATA_DOOR_ID, doorId);
            door.entityData.set(DATA_AXIS_X, axisX);
            door.entityData.set(DATA_WIDTH, width);
            door.entityData.set(DATA_HEIGHT, height);
            door.entityData.set(DATA_STYLE, style);
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
            door.entityData.set(DATA_WIDTH, width);
            door.entityData.set(DATA_HEIGHT, height);
            door.entityData.set(DATA_STYLE, style);
            if (door.position().distanceToSqr(centre) > 1.0E-8D)
            {
                door.setPos(centre.x, centre.y, centre.z);
            }
            for (int index = 1; index < matches.size(); index++)
            {
                matches.get(index).discard();
            }
        }
        return door;
    }

    @Override public boolean isPickable() { return false; }
    @Override public boolean isPushable() { return false; }
    @Override public boolean hurt(DamageSource source, float amount) { return false; }
    @Override public PushReaction getPistonPushReaction() { return PushReaction.IGNORE; }
}
