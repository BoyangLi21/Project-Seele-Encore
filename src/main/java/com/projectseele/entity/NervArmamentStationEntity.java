package com.projectseele.entity;

import com.projectseele.registry.ModItems;
import com.projectseele.world.EvaPilotResolver;
import java.util.Comparator;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.WeakHashMap;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.chat.Component;
import net.minecraft.network.protocol.Packet;
import net.minecraft.network.protocol.game.ClientGamePacketListener;
import net.minecraft.network.syncher.EntityDataAccessor;
import net.minecraft.network.syncher.EntityDataSerializers;
import net.minecraft.network.syncher.SynchedEntityData;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.util.Mth;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EntityDimensions;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.Pose;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.material.PushReaction;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.network.NetworkHooks;

/**
 * Persistent, blockless TV-style armament building.
 *
 * <p>The shaft, hatch and payload are one server-owned entity.  Rendering is
 * continuously interpolated and therefore never rewrites surface blocks one
 * layer at a time.  Phase one carries one vertical Pallet Rifle.</p>
 */
public final class NervArmamentStationEntity extends Entity implements com.projectseele.world.TvEncounterEquipmentControlR45.CargoRackAccess
{
    public static final int STOWED = 0;
    public static final int OPENING = 1;
    public static final int RISING = 2;
    public static final int READY = 3;
    public static final int EMPTY = 4;
    public static final int LOWERING = 5;
    public static final int CLOSING = 6;
    public static final int DOOR_OPENING = 7;
    public static final int DOOR_CLOSING = 8;

    private static final int HATCH_TICKS = 24;
    private static final int RISE_TICKS = 100;
    private static final int EMPTY_HOLD_TICKS = 30;
    private static final int LOWER_TICKS = 80;
    private static final int DOOR_TICKS = 30;
    public static final double EVA_PICKUP_RANGE = 24.0D;
    private static final Map<ServerLevel,UUID> COMMAND_STATION =
            Collections.synchronizedMap(new WeakHashMap<>());
    private static final net.minecraft.server.level.TicketType<net.minecraft.world.level.ChunkPos> COMMAND_TICKET=
            net.minecraft.server.level.TicketType.create("seele_armament_command",java.util.Comparator.comparingLong(net.minecraft.world.level.ChunkPos::toLong),120);
    public static void keepCommandStationLoaded(ServerLevel level,net.minecraft.core.BlockPos pos)
    {
        var chunk=new net.minecraft.world.level.ChunkPos(pos);level.getChunkSource().addRegionTicket(COMMAND_TICKET,chunk,2,chunk);level.getChunkAt(pos);
    }

    private static final EntityDataAccessor<Integer> DATA_STATE =
            SynchedEntityData.defineId(NervArmamentStationEntity.class,
                    EntityDataSerializers.INT);
    private static final EntityDataAccessor<Float> DATA_LIFT =
            SynchedEntityData.defineId(NervArmamentStationEntity.class,
                    EntityDataSerializers.FLOAT);
    private static final EntityDataAccessor<Float> DATA_HATCH =
            SynchedEntityData.defineId(NervArmamentStationEntity.class,
                    EntityDataSerializers.FLOAT);
    private static final EntityDataAccessor<Boolean> DATA_STOCKED =
            SynchedEntityData.defineId(NervArmamentStationEntity.class,
                    EntityDataSerializers.BOOLEAN);
    private static final EntityDataAccessor<Float> DATA_DOOR =
            SynchedEntityData.defineId(NervArmamentStationEntity.class,
                    EntityDataSerializers.FLOAT);

    private int phaseTicks;
    private float clientLift;
    private float clientLiftO;
    private float clientHatch;
    private float clientHatchO;
    private float clientDoor;
    private float clientDoorO;
    private boolean deployQueued;

    public NervArmamentStationEntity(
            EntityType<? extends NervArmamentStationEntity> type, Level level)
    {
        super(type, level);
        this.noPhysics = true;
        this.setNoGravity(true);
        this.setInvulnerable(true);
    }

    @Override
    protected void defineSynchedData()
    {
        this.entityData.define(DATA_STATE, STOWED);
        this.entityData.define(DATA_LIFT, 0.0F);
        this.entityData.define(DATA_HATCH, 0.0F);
        this.entityData.define(DATA_STOCKED, true);
        this.entityData.define(DATA_DOOR, 0.0F);
    }

    @Override
    protected void readAdditionalSaveData(CompoundTag tag)
    {
        this.entityData.set(DATA_STATE,
                Mth.clamp(tag.getInt("StationState"), STOWED, DOOR_CLOSING));
        this.entityData.set(DATA_LIFT,
                Mth.clamp(tag.getFloat("LiftProgress"), 0.0F, 1.0F));
        this.entityData.set(DATA_HATCH,
                Mth.clamp(tag.getFloat("HatchProgress"), 0.0F, 1.0F));
        this.entityData.set(DATA_STOCKED,
                !tag.contains("Stocked") || tag.getBoolean("Stocked"));
        int restoredState = this.getStationState();
        float migratedDoor = tag.contains("DoorProgress")
                ? tag.getFloat("DoorProgress")
                : restoredState == READY || restoredState == EMPTY
                        ? 1.0F : 0.0F;
        this.entityData.set(DATA_DOOR,
                Mth.clamp(migratedDoor, 0.0F, 1.0F));
        this.phaseTicks = Math.max(0, tag.getInt("PhaseTicks"));
        this.deployQueued = tag.getBoolean("DeployQueued");
    }

    @Override
    protected void addAdditionalSaveData(CompoundTag tag)
    {
        tag.putInt("StationState", this.getStationState());
        tag.putFloat("LiftProgress", this.entityData.get(DATA_LIFT));
        tag.putFloat("HatchProgress", this.entityData.get(DATA_HATCH));
        tag.putBoolean("Stocked", this.isStocked());
        tag.putFloat("DoorProgress", this.entityData.get(DATA_DOOR));
        tag.putInt("PhaseTicks", this.phaseTicks);
        tag.putBoolean("DeployQueued", this.deployQueued);
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
            this.clientLiftO = this.clientLift;
            this.clientHatchO = this.clientHatch;
            this.clientLift = this.entityData.get(DATA_LIFT);
            this.clientHatch = this.entityData.get(DATA_HATCH);
            this.clientDoorO = this.clientDoor;
            this.clientDoor = this.entityData.get(DATA_DOOR);
            return;
        }

        this.phaseTicks++;
        if(this.level() instanceof ServerLevel server&&this.getStationState()!=STOWED&&this.getStationState()!=READY&&this.tickCount%40==0)
            keepCommandStationLoaded(server,this.blockPosition());
        switch (this.getStationState())
        {
            case OPENING ->
            {
                this.setHatch(ease(this.phaseTicks / (float)HATCH_TICKS));
                if (this.phaseTicks >= HATCH_TICKS)
                {
                    this.setHatch(1.0F);
                    this.transition(RISING);
                }
            }
            case RISING ->
            {
                this.setLift(ease(this.phaseTicks / (float)RISE_TICKS));
                if (this.phaseTicks >= RISE_TICKS)
                {
                    this.setLift(1.0F);
                    this.transition(DOOR_OPENING);
                }
            }
            case DOOR_OPENING ->
            {
                this.setDoor(ease(this.phaseTicks / (float)DOOR_TICKS));
                if (this.phaseTicks >= DOOR_TICKS)
                {
                    this.setDoor(1.0F);
                    this.transition(READY);
                }
            }
            case EMPTY ->
            {
                if (this.phaseTicks >= EMPTY_HOLD_TICKS)
                {
                    this.transition(DOOR_CLOSING);
                }
            }
            case DOOR_CLOSING ->
            {
                this.setDoor(1.0F - ease(
                        this.phaseTicks / (float)DOOR_TICKS));
                if (this.phaseTicks >= DOOR_TICKS)
                {
                    this.setDoor(0.0F);
                    this.transition(LOWERING);
                }
            }
            case LOWERING ->
            {
                this.setLift(1.0F - ease(
                        this.phaseTicks / (float)LOWER_TICKS));
                if (this.phaseTicks >= LOWER_TICKS)
                {
                    this.setLift(0.0F);
                    this.transition(CLOSING);
                }
            }
            case CLOSING ->
            {
                this.setHatch(1.0F - ease(
                        this.phaseTicks / (float)HATCH_TICKS));
                if (this.phaseTicks >= HATCH_TICKS)
                {
                    this.setHatch(0.0F);
                    this.entityData.set(DATA_STOCKED, !com.projectseele.world.TvMissionEquipmentR45.missionRack(this)
                    ||com.projectseele.world.TvMissionEquipmentR45.physicalStockPresent(this));
                    if (this.deployQueued)
                    {
                        this.deployQueued = false;
                        this.transition(OPENING);
                    }
                    else
                    {
                        this.transition(STOWED);
                    }
                }
            }
            default -> { }
        }
    }

    public int getStationState()
    {
        return this.entityData.get(DATA_STATE);
    }

    public boolean isStocked()
    {
        return this.entityData.get(DATA_STOCKED);
    }

    public boolean isReadyAndStocked()
    {
        return this.getStationState() == READY && this.isStocked();
    }

    public String stateName()
    {
        return switch (this.getStationState())
        {
            case OPENING -> "OPENING";
            case RISING -> "RISING";
            case READY -> "READY";
            case EMPTY -> "EMPTY";
            case LOWERING -> "LOWERING";
            case CLOSING -> "CLOSING";
            case DOOR_OPENING -> "DOOR_OPENING";
            case DOOR_CLOSING -> "DOOR_CLOSING";
            default -> "STOWED";
        };
    }

    public float getLiftProgress(float partialTick)
    {
        return Mth.lerp(partialTick, this.clientLiftO, this.clientLift);
    }

    public float getHatchProgress(float partialTick)
    {
        return Mth.lerp(partialTick, this.clientHatchO, this.clientHatch);
    }

    public float getDoorProgress(float partialTick)
    {
        return Mth.lerp(partialTick, this.clientDoorO, this.clientDoor);
    }

    /** Server-authoritative lift height used by the command-room telemetry. */
    public int getLiftPercent()
    {
        return Mth.clamp(Math.round(this.entityData.get(DATA_LIFT) * 100.0F),
                0, 100);
    }

    /**
     * Returns the one loaded armament building linked to the NERV command
     * bus.  The UUID cache avoids a global entity scan on every telemetry
     * frame; a scan occurs only after load or if that entity disappears.
     */
    public static NervArmamentStationEntity commandStation(ServerLevel level)
    {
        UUID cached = COMMAND_STATION.get(level);
        if (cached != null
                && level.getEntity(cached) instanceof
                NervArmamentStationEntity station
                && station.isAlive()
                && !com.projectseele.world.TvMissionEquipmentR45.missionRack(station))
        {
            return station;
        }
        NervArmamentStationEntity selected = null;
        for (Entity entity : level.getAllEntities())
        {
            if (entity instanceof NervArmamentStationEntity station
                    && station.isAlive()
                    && !com.projectseele.world.TvMissionEquipmentR45.missionRack(station)
                    && (selected == null || station.getUUID().compareTo(
                            selected.getUUID()) < 0))
            {
                selected = station;
            }
        }
        if (selected == null)
        {
            COMMAND_STATION.remove(level);
        }
        else
        {
            COMMAND_STATION.put(level, selected.getUUID());
        }
        return selected;
    }

    public boolean deploy()
    {
        if (this.level().isClientSide)
        {
            return false;
        }
        if (this.getStationState() == EMPTY
                || this.getStationState() == DOOR_CLOSING
                || this.getStationState() == LOWERING
                || this.getStationState() == CLOSING)
        {
            this.deployQueued = true;
            return true;
        }
        if (this.getStationState() != STOWED)
        {
            return false;
        }
        this.entityData.set(DATA_STOCKED, !com.projectseele.world.TvMissionEquipmentR45.missionRack(this)
                    ||com.projectseele.world.TvMissionEquipmentR45.physicalStockPresent(this));
        this.setDoor(0.0F);
        this.transition(OPENING);
        return true;
    }

    public boolean recall()
    {
        if (this.level().isClientSide
                || (this.getStationState() != READY
                && this.getStationState() != DOOR_OPENING))
        {
            return false;
        }
        this.transition(DOOR_CLOSING);
        return true;
    }

    private boolean issueRifle(Player player, EvaUnit01Entity eva)
    {
        if(com.projectseele.world.TvMissionEquipmentR45.missionRack(this))return false;
        if (!this.isReadyAndStocked()
                || horizontalDistanceSqr(eva.position(), this.position())
                        > EVA_PICKUP_RANGE * EVA_PICKUP_RANGE)
        {
            return false;
        }
        if (!eva.installExternalArmament(EvaUnit01Entity.WEAPON_RIFLE))
        {
            player.displayClientMessage(Component.translatable(
                    "msg.projectseele.armament_already_installed"), true);
            return false;
        }
        this.entityData.set(DATA_STOCKED, false);
        this.transition(EMPTY);
        player.displayClientMessage(Component.translatable(
                "msg.projectseele.armament_rifle_acquired"), true);
        return true;
    }

    public static boolean acquireNearest(ServerLevel level,
            Player player, EvaUnit01Entity eva)
    {
        NervArmamentStationEntity station = nearest(level, eva.position(),
                EVA_PICKUP_RANGE, true);
        var missionCargo=com.projectseele.world.TvMissionEquipmentR45.nearestPhysicalCargo(level,eva);
        if(missionCargo!=null)return missionCargo.issueTvMissionEquipmentR45(player,eva);
        return station != null && station.issueRifle(player, eva);
    }
    /** Real finite cargo handoff; the old rifle replenish path stays separate. */
    public boolean issueTvMissionEquipmentR45(net.minecraft.world.entity.LivingEntity actualPilot,EvaUnit01Entity eva)
    {
        if(!com.projectseele.world.TvMissionEquipmentR45.issueFromStation(this,eva,actualPilot))return false;
        this.entityData.set(DATA_STOCKED,false);this.transition(EMPTY);
        eva.acceptIssuedTvMissionEquipmentR45();return true;
    }

    public boolean issueToAssignedPilotR30(TrainingPilotEntity pilot,EvaUnit01Entity eva)
    {
        if(com.projectseele.world.TvMissionEquipmentR45.missionRack(this))return false;
        if(this.level().isClientSide||eva.getPilotEntity()!=pilot||pilot.getAssignedVariant()!=eva.getUnitVariant()
                ||!eva.isPoweredOn()||!this.isReadyAndStocked()
                ||horizontalDistanceSqr(eva.position(),this.position())>EVA_PICKUP_RANGE*EVA_PICKUP_RANGE
                ||!eva.installExternalArmament(EvaUnit01Entity.WEAPON_RIFLE))return false;
        this.entityData.set(DATA_STOCKED,false);this.transition(EMPTY);return true;
    }

    public static NervArmamentStationEntity nearest(Level level, Vec3 centre,
            double range, boolean readyOnly)
    {
        AABB bounds = new AABB(centre, centre).inflate(range, 40.0D, range);
        List<NervArmamentStationEntity> stations = level.getEntitiesOfClass(
                NervArmamentStationEntity.class, bounds,
                station -> !readyOnly || station.isReadyAndStocked());
        return stations.stream().min(Comparator.comparingDouble(
                station -> horizontalDistanceSqr(
                        station.position(), centre))).orElse(null);
    }

    @Override
    public InteractionResult interact(Player player, InteractionHand hand)
    {
        if (this.level().isClientSide)
        {
            return InteractionResult.SUCCESS;
        }
        if(player instanceof net.minecraft.server.level.ServerPlayer serverPlayer
                &&com.projectseele.world.TvMissionEquipmentR45.deliverHeldCargo(this,serverPlayer,hand))
        {this.entityData.set(DATA_STOCKED,true);return InteractionResult.CONSUME;}
        if(hand==InteractionHand.MAIN_HAND && player instanceof net.minecraft.server.level.ServerPlayer carrier
                &&player.isShiftKeyDown()&&com.projectseele.world.TvMissionEquipmentR45.collectStoredCargo(this,carrier,hand))
        {this.entityData.set(DATA_STOCKED,false);this.transition(EMPTY);return InteractionResult.CONSUME;}
        if(player instanceof net.minecraft.server.level.ServerPlayer groundCrew
                &&com.projectseele.world.TvMissionEquipmentR45.returnNearbyCargo(this,groundCrew))
        {this.entityData.set(DATA_STOCKED,true);return InteractionResult.CONSUME;}
        EvaUnit01Entity eva = EvaPilotResolver.controlTarget(player);
        if (eva != null)
        {
            if(com.projectseele.world.TvMissionEquipmentR45.stockedFor(this,eva))
                return this.issueTvMissionEquipmentR45(player,eva)?InteractionResult.CONSUME:InteractionResult.FAIL;
            if(com.projectseele.world.TvMissionEquipmentR45.returnToStation(this,eva))
            {this.entityData.set(DATA_STOCKED,true);eva.refreshTvMissionEquipmentR45();return InteractionResult.CONSUME;}
            return this.issueRifle(player, eva)
                    ? InteractionResult.CONSUME : InteractionResult.FAIL;
        }
        if (player.hasPermissions(2))
        {
            boolean changed = this.getStationState() == STOWED
                    ? this.deploy() : this.recall();
            return changed ? InteractionResult.CONSUME : InteractionResult.PASS;
        }
        return InteractionResult.PASS;
    }

    @Override
    public ItemStack getPickResult()
    {
        return new ItemStack(ModItems.EVA_PALLET_RIFLE.get());
    }

    @Override
    public EntityDimensions getDimensions(Pose pose)
    {
        float height = 1.0F + 43.0F * this.entityData.get(DATA_LIFT);
        return EntityDimensions.fixed(11.0F, height);
    }

    @Override
    public boolean isPickable()
    {
        return this.getStationState() != STOWED;
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

    private void transition(int state)
    {
        this.entityData.set(DATA_STATE, state);
        this.phaseTicks = 0;
    }

    private void setLift(float progress)
    {
        this.entityData.set(DATA_LIFT, Mth.clamp(progress, 0.0F, 1.0F));
        this.refreshDimensions();
    }

    private void setHatch(float progress)
    {
        this.entityData.set(DATA_HATCH, Mth.clamp(progress, 0.0F, 1.0F));
    }

    private void setDoor(float progress)
    {
        this.entityData.set(DATA_DOOR, Mth.clamp(progress, 0.0F, 1.0F));
    }

    private static float ease(float value)
    {
        float t = Mth.clamp(value, 0.0F, 1.0F);
        return t * t * (3.0F - 2.0F * t);
    }

    private static double horizontalDistanceSqr(Vec3 first, Vec3 second)
    {
        double dx = first.x - second.x;
        double dz = first.z - second.z;
        return dx * dx + dz * dz;
    }
}
