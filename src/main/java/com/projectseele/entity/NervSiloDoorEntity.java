package com.projectseele.entity;

import com.projectseele.registry.ModEntities;
import java.util.Comparator;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.WeakHashMap;
import net.minecraft.core.BlockPos;
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
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.material.PushReaction;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.network.NetworkHooks;

/** Synchronized visual plus physical weather seal for one EVA surface hatch. */
public final class NervSiloDoorEntity extends Entity
{
    private static final int PHYSICAL_RADIUS = 15;
    // setBlock already updates collision and heightmaps.  Cascading neighbour
    // shape work over 2,883 hatch cells only creates a first-load stall.
    private static final int UPDATE = Block.UPDATE_CLIENTS;
    private static final BlockState PHYSICAL_HATCH =
            Blocks.BARRIER.defaultBlockState();
    private static final Map<ServerLevel,Set<Long>> SEALED =
            Collections.synchronizedMap(new WeakHashMap<>());
    private static final EntityDataAccessor<Integer> DATA_STAGE =
            SynchedEntityData.defineId(NervSiloDoorEntity.class,EntityDataSerializers.INT);
    private static final EntityDataAccessor<Integer> DATA_VARIANT =
            SynchedEntityData.defineId(NervSiloDoorEntity.class,
                    EntityDataSerializers.INT);
    private static final EntityDataAccessor<Float> DATA_OPEN =
            SynchedEntityData.defineId(NervSiloDoorEntity.class,
                    EntityDataSerializers.FLOAT);
    private static final EntityDataAccessor<Float> DATA_TARGET =
            SynchedEntityData.defineId(NervSiloDoorEntity.class,
                    EntityDataSerializers.FLOAT);

    private float clientOpen;
    private float clientOpenO;
    private int openingDelay;

    public NervSiloDoorEntity(EntityType<? extends NervSiloDoorEntity> type,
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
        this.entityData.define(DATA_VARIANT, 0);
        this.entityData.define(DATA_STAGE, -1);
        this.entityData.define(DATA_OPEN, 0.0F);
        this.entityData.define(DATA_TARGET, 0.0F);
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
        if (this.level().isClientSide)
        {
            this.clientOpenO = this.clientOpen;
            this.clientOpen = this.entityData.get(DATA_OPEN);
            return;
        }
        float current = this.entityData.get(DATA_OPEN);
        float target = this.entityData.get(DATA_TARGET);
        if(target>current&&openingDelay>0){openingDelay--;return;}
        boolean tv=this.level() instanceof ServerLevel level&&com.projectseele.world.TvLaunchFacility.enabled(level);
        float next = Mth.approach(current, target, isTvBulkhead()?1.0F/18.0F:tv?1.0F/30.0F:.10F);
        if(this.level() instanceof ServerLevel serverLevel
                &&com.projectseele.world.TvLaunchFacility.enabled(serverLevel))
        {
            if(Math.abs(next-current)>1e-4F&&(current==0||current==1))
            {
                if(isTvBulkhead())this.playSound(com.projectseele.registry.ModSounds.EVA_SERVO.get(),3.5F,.60F);
                else this.playSound(com.projectseele.registry.ModSounds.SURFACE_BULKHEAD_MOTION_R48.get(),1.3F,1);
            }
            if(next!=current&&(next==0||next==1))
            {
                if(isTvBulkhead())this.playSound(com.projectseele.registry.ModSounds.EVA_ARMOR_IMPACT.get(),2.0F,.64F);
                else this.playSound(com.projectseele.registry.ModSounds.SURFACE_BULKHEAD_STOP_R48.get(),1.1F,1);
            }
        }
        if (Math.abs(next - current) > 1.0E-4F)
        {
            this.entityData.set(DATA_OPEN, next);
        }
    }

    public int getVariant()
    {
        return this.entityData.get(DATA_VARIANT);
    }

    public boolean isTvBulkhead(){return this.entityData.get(DATA_STAGE)>=0;}
    public int getBulkheadStage(){return this.entityData.get(DATA_STAGE);}

    public float getOpenProgress(float partialTick)
    {
        return EvaDorsalMechanism.smooth(Mth.lerp(partialTick, this.clientOpenO, this.clientOpen));
    }

    public void setTargetOpen(float target)
    {
        float clamped = Mth.clamp(target, 0.0F, 1.0F);
        if(clamped>0&&this.entityData.get(DATA_TARGET)<=0&&this.entityData.get(DATA_OPEN)<=1.0E-4F&&this.level() instanceof ServerLevel level
                &&com.projectseele.world.TvLaunchFacility.enabled(level))
            openingDelay=(isTvBulkhead()?getBulkheadStage():3)*6;
        if (Math.abs(this.entityData.get(DATA_TARGET) - clamped) > 1.0E-4F)
        {
            this.entityData.set(DATA_TARGET, clamped);
        }
    }

    public static void reconcile(ServerLevel level, int variant,
            BlockPos surfaceBed, float targetOpen)
    {
        reconcilePlane(level,variant,surfaceBed,targetOpen,-1);
        if(com.projectseele.world.TvLaunchFacility.enabled(level))
        {
            int[] offsets=com.projectseele.world.TvLaunchFacility.BULKHEAD_BELOW_SURFACE;
            for(int stage=0;stage<offsets.length;stage++)
                reconcilePlane(level,variant,surfaceBed.below(offsets[stage]),targetOpen>0?1:0,stage);
        }
    }

    public static boolean hasOpenRecoveryRoute(ServerLevel level,int variant,BlockPos surface)
    {
        int[] offsets=com.projectseele.world.TvLaunchFacility.enabled(level)
                ? com.projectseele.world.TvLaunchFacility.BULKHEAD_BELOW_SURFACE : new int[0];
        for(int index=-1;index<offsets.length;index++)
        {
            BlockPos centre=(index<0?surface:surface.below(offsets[index])).above();
            var doors=level.getEntitiesOfClass(NervSiloDoorEntity.class,new AABB(centre).inflate(3),
                e->e.getVariant()==variant);
            if(doors.isEmpty()||doors.stream().anyMatch(e->e.entityData.get(DATA_OPEN)<.999F)
                    ||!level.getBlockState(centre).isAir())return false;
        }
        return true;
    }

    /** The pilot can be released only after the actual surface seal bears weight. */
    public static boolean hasClosedSurfaceSupport(ServerLevel level, BlockPos surfaceBed)
    {
        BlockPos centre = surfaceBed.above();
        Set<Long> sealed = SEALED.get(level);
        if (sealed == null || !sealed.contains(centre.asLong()))
        {
            return false;
        }
        BlockPos.MutableBlockPos cursor = new BlockPos.MutableBlockPos();
        for (int x = -PHYSICAL_RADIUS; x <= PHYSICAL_RADIUS; x++)
        {
            for (int z = -PHYSICAL_RADIUS; z <= PHYSICAL_RADIUS; z++)
            {
                cursor.set(centre.getX() + x, centre.getY(), centre.getZ() + z);
                if (!level.hasChunkAt(cursor) || !level.getBlockState(cursor).equals(PHYSICAL_HATCH))
                {
                    return false;
                }
            }
        }
        return true;
    }

    private static void reconcilePlane(ServerLevel level,int variant,BlockPos surfaceBed,float targetOpen,int stage)
    {
        Vec3 centre = new Vec3(surfaceBed.getX() + 0.5D,
                surfaceBed.getY() + 1.01D,
                surfaceBed.getZ() + 0.5D);
        AABB search = new AABB(centre, centre).inflate(3.0D, 3.0D, 3.0D);
        List<NervSiloDoorEntity> matches = level.getEntitiesOfClass(
                NervSiloDoorEntity.class, search,
                entity -> entity.getVariant() == variant);
        matches.sort(Comparator.comparingInt(Entity::getId));
        NervSiloDoorEntity door;
        if (matches.isEmpty())
        {
            door = ModEntities.NERV_SILO_DOOR.get().create(level);
            if (door == null)
            {
                return;
            }
            door.entityData.set(DATA_VARIANT, variant);
            door.entityData.set(DATA_STAGE, stage);
            door.setPos(centre);
            level.addFreshEntity(door);
        }
        else
        {
            door = matches.get(0);
            door.entityData.set(DATA_STAGE, stage);
            if (door.position().distanceToSqr(centre) > 1.0E-8D)
            {
                door.setPos(centre);
            }
            for (int index = 1; index < matches.size(); index++)
            {
                matches.get(index).discard();
            }
        }
        door.setTargetOpen(targetOpen);
        synchronizePhysicalHatch(level, variant, surfaceBed, door,
                targetOpen);
    }

    private static void synchronizePhysicalHatch(ServerLevel level,
            int variant, BlockPos surfaceBed, NervSiloDoorEntity door,
            float targetOpen)
    {
        Set<Long> sealed = SEALED.computeIfAbsent(level,
                ignored -> new HashSet<>());
        BlockPos planeCentre = surfaceBed.above();
        long planeKey=planeCentre.asLong();
        boolean ownsPhysicalLayer = sealed.contains(planeKey)
                || level.getBlockState(planeCentre).is(PHYSICAL_HATCH.getBlock());

        if (targetOpen > 1.0E-3F)
        {
            if(door.entityData.get(DATA_OPEN)<.99F)return;
            if (!ownsPhysicalLayer)
            {
                return;
            }
            BlockPos.MutableBlockPos cursor = new BlockPos.MutableBlockPos();
            for (int dx = -PHYSICAL_RADIUS; dx <= PHYSICAL_RADIUS; dx++)
            {
                for (int dz = -PHYSICAL_RADIUS; dz <= PHYSICAL_RADIUS; dz++)
                {
                    cursor.set(planeCentre.getX() + dx,
                            planeCentre.getY(), planeCentre.getZ() + dz);
                    if (level.hasChunkAt(cursor)
                            && !level.getBlockState(cursor).isAir()
                            &&(!door.isTvBulkhead()||level.getBlockState(cursor).is(PHYSICAL_HATCH.getBlock())))
                    {
                        // An open launch mouth is an unconditional 31x31 air
                        // aperture. Older revisions only removed barriers and
                        // could leave individual trim blocks in the centre.
                        level.setBlock(cursor, Blocks.AIR.defaultBlockState(),
                                UPDATE);
                    }
                }
            }
            sealed.remove(planeKey);
            return;
        }

        // Do not pop a solid roof under an open animated leaf.  The physical
        // layer appears only once the synchronized visual is nearly closed.
        if (door.entityData.get(DATA_OPEN) > 0.05F || sealed.contains(planeKey))
        {
            return;
        }
        boolean complete = true;
        // A recovering body or passenger may still straddle this plane. Hold
        // the rigid leaves open as well as the seal until the volume is clear.
        if(door.isTvBulkhead()&&!level.getEntities(door,new AABB(planeCentre).inflate(PHYSICAL_RADIUS,2,PHYSICAL_RADIUS),
                e->e instanceof net.minecraft.world.entity.LivingEntity).isEmpty())
        {
            door.setTargetOpen(1);return;
        }
        BlockPos.MutableBlockPos cursor = new BlockPos.MutableBlockPos();
        for (int dx = -PHYSICAL_RADIUS; dx <= PHYSICAL_RADIUS; dx++)
        {
            for (int dz = -PHYSICAL_RADIUS; dz <= PHYSICAL_RADIUS; dz++)
            {
                cursor.set(planeCentre.getX() + dx,
                        planeCentre.getY(), planeCentre.getZ() + dz);
                if (!level.hasChunkAt(cursor))
                {
                    complete = false;
                    continue;
                }
                if (!level.getBlockState(cursor).equals(PHYSICAL_HATCH))
                {
                    if(door.isTvBulkhead()&&!level.getBlockState(cursor).isAir()){complete=false;continue;}
                    level.setBlock(cursor, PHYSICAL_HATCH, UPDATE);
                }
            }
        }
        if (complete)
        {
            sealed.add(planeKey);
        }
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
