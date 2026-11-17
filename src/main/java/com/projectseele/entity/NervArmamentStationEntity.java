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
    private static final EntityDataAccessor<Integer> DATA_PAYLOAD_R47 =
            SynchedEntityData.defineId(NervArmamentStationEntity.class,EntityDataSerializers.INT);
    /** A spare-weapon tower's station: the tower's number in the city, the side of its door, its height, its door. Empty otherwise. */
    private static final EntityDataAccessor<CompoundTag> DATA_TOWER_R64 =
            SynchedEntityData.defineId(NervArmamentStationEntity.class,EntityDataSerializers.COMPOUND_TAG);
    /** Of a tower: the run under way, and while stowed the end the city rests at (ArmamentTowerLogicR64.LOWERED, RAISED or NONE). */
    private static final EntityDataAccessor<Integer> DATA_TOWER_RUN_R64 =
            SynchedEntityData.defineId(NervArmamentStationEntity.class,EntityDataSerializers.INT);

    private int phaseTicks;
    private float clientLift;
    private float clientLiftO;
    private float clientHatch;
    private float clientHatchO;
    private float clientDoor;
    private float clientDoorO;
    private boolean deployQueued;
    private boolean surfaceStateInitializedR54;
    /** Not saved: a tower's run ends with the session it began in. */
    private boolean towerRunLiveR64;
    private int towerReadyTicksR64;
    private net.minecraft.world.level.block.state.BlockState[] towerClientCellsR64;
    private int towerClientCellsRunR64;

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
        this.entityData.define(DATA_PAYLOAD_R47,EvaUnit01Entity.WEAPON_RIFLE);
        this.entityData.define(DATA_TOWER_R64,new CompoundTag());
        this.entityData.define(DATA_TOWER_RUN_R64,0);
    }

    @Override
    protected void readAdditionalSaveData(CompoundTag tag)
    {
        this.setPayloadR47(tag.contains("PayloadR47")?tag.getInt("PayloadR47"):EvaUnit01Entity.WEAPON_RIFLE);
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
        if(tag.contains("TowerR64",net.minecraft.nbt.Tag.TAG_COMPOUND))
        {
            this.entityData.set(DATA_TOWER_R64,tag.getCompound("TowerR64").copy());
            this.entityData.set(DATA_TOWER_RUN_R64,Mth.clamp(tag.getInt("TowerRunR64"),0,2));
        }
    }

    @Override
    protected void addAdditionalSaveData(CompoundTag tag)
    {
        tag.putInt("PayloadR47",this.payloadR47());
        tag.putInt("StationState", this.getStationState());
        tag.putFloat("LiftProgress", this.entityData.get(DATA_LIFT));
        tag.putFloat("HatchProgress", this.entityData.get(DATA_HATCH));
        tag.putBoolean("Stocked", this.isStocked());
        tag.putFloat("DoorProgress", this.entityData.get(DATA_DOOR));
        tag.putInt("PhaseTicks", this.phaseTicks);
        tag.putBoolean("DeployQueued", this.deployQueued);
        if(this.towerR64()>=0)
        {
            tag.put("TowerR64",this.entityData.get(DATA_TOWER_R64).copy());
            tag.putInt("TowerRunR64",this.towerRunR64());
        }
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
            if(this.towerR64()>=0)this.sampleTowerCellsR64();
            return;
        }

        if(com.projectseele.world.TvMissionEquipmentR45.surfaceSupplyRackR50(this))
        {this.maintainSurfaceSupplyR50();return;}
        if(!com.projectseele.world.EquipmentVaultsR47.beforeMechanicalTick(this))return;
        if(!com.projectseele.world.ArmamentTowersR64.beforeMechanicalTick(this))return;
        this.phaseTicks++;
        // A tower that stands ready has blocks out: its chunk stays loaded until they are back.
        boolean tower=this.towerR64()>=0;
        if(this.level() instanceof ServerLevel server&&this.getStationState()!=STOWED&&(tower||this.getStationState()!=READY)&&this.tickCount%40==0)
            keepCommandStationLoaded(server,this.blockPosition());
        // With the city raised a tower has no pod to lift: its roof locks take the hatch's place, then the door.
        int run=tower?this.towerRunR64():com.projectseele.world.ArmamentTowerLogicR64.NONE;
        boolean raisedRun=run==com.projectseele.world.ArmamentTowerLogicR64.RAISED;
        int hatchTicks=raisedRun?com.projectseele.config.SeeleConfig.ARMAMENT_TOWER_LOCK_TICKS.get():NervArmamentStationEntity.HATCH_TICKS;
        int doorTicks=raisedRun?com.projectseele.config.SeeleConfig.ARMAMENT_TOWER_DOOR_TICKS.get():NervArmamentStationEntity.DOOR_TICKS;
        switch (this.getStationState())
        {
            case OPENING ->
            {
                this.setHatch(ease(this.phaseTicks / (float)hatchTicks));
                if (this.phaseTicks >= hatchTicks)
                {
                    this.setHatch(1.0F);
                    this.transition(tower?com.projectseele.world.ArmamentTowerLogicR64.afterOpening(run):RISING);
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
                this.setDoor(ease(this.phaseTicks / (float)doorTicks));
                if (this.phaseTicks >= doorTicks)
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
                        this.phaseTicks / (float)doorTicks));
                if (this.phaseTicks >= doorTicks)
                {
                    this.setDoor(0.0F);
                    this.transition(tower?com.projectseele.world.ArmamentTowerLogicR64.afterDoorClosing(run):LOWERING);
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
                        this.phaseTicks / (float)hatchTicks));
                if (this.phaseTicks >= hatchTicks)
                {
                    this.setHatch(0.0F);
                    if(tower)
                    {
                        // The lot's hatch is back before the tower counts as stowed: a city trip waits for that.
                        if(!com.projectseele.world.ArmamentTowersR64.finishRun(this))return;
                        this.entityData.set(DATA_STOCKED,true);this.towerRunLiveR64=false;this.transition(STOWED);return;
                    }
                    if(this.payloadR47()==EvaUnit01Entity.WEAPON_RIFLE)this.entityData.set(DATA_STOCKED, !com.projectseele.world.TvMissionEquipmentR45.missionRack(this)
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
                && station.isAlive()&&station.towerR64()<0
                &&station.payloadR47()==EvaUnit01Entity.WEAPON_RIFLE
                && !com.projectseele.world.TvMissionEquipmentR45.missionRack(station))
        {
            return station;
        }
        NervArmamentStationEntity selected = null;
        for (Entity entity : level.getAllEntities())
        {
            if (entity instanceof NervArmamentStationEntity station
                    && station.isAlive()&&station.towerR64()<0
                    &&station.payloadR47()==EvaUnit01Entity.WEAPON_RIFLE
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

    // ---- Spare-weapon towers (R64): one station bound to an A-1 armament building of the lifting city ----

    /** The tower's number in the city's table, or -1 for an ordinary lift station. */
    public int towerR64()
    {
        CompoundTag tower=this.entityData.get(DATA_TOWER_R64);
        return tower.contains("Tower")?tower.getInt("Tower"):-1;
    }
    /** The side the door is on: 0 south, 1 west, 2 north, 3 east. */
    public int towerFacingR64(){return this.entityData.get(DATA_TOWER_R64).getInt("Facing")&3;}
    public int towerHeightR64(){return this.entityData.get(DATA_TOWER_R64).getInt("Height");}
    public int towerRunR64(){return this.entityData.get(DATA_TOWER_RUN_R64);}
    public boolean towerRunLiveR64(){return this.towerRunLiveR64;}
    public com.projectseele.world.ArmamentTowerLogicR64.Lot towerLotR64()
    {var at=this.blockPosition();return new com.projectseele.world.ArmamentTowerLogicR64.Lot(at.getX(),at.getY(),at.getZ());}
    public com.projectseele.world.ArmamentTowerLogicR64.Door towerDoorR64()
    {
        CompoundTag tower=this.entityData.get(DATA_TOWER_R64);
        int width=tower.getInt("DoorWidth"),height=tower.getInt("DoorHeight"),bottom=tower.getInt("DoorBottom");
        return width>0&&width%2==1&&width<=15&&height>0&&bottom>0
                ?new com.projectseele.world.ArmamentTowerLogicR64.Door(width,height,bottom)
                :new com.projectseele.world.ArmamentTowerLogicR64.Door(15,38,1);
    }
    /** Binds this station to a tower; called on every pass, so a changed table reaches a station that already exists. */
    public void bindTowerR64(int tower,int facing,int height,com.projectseele.world.ArmamentTowerLogicR64.Door door)
    {
        CompoundTag tag=new CompoundTag();
        tag.putInt("Tower",tower);tag.putInt("Facing",facing&3);tag.putInt("Height",height);
        tag.putInt("DoorWidth",door.width());tag.putInt("DoorHeight",door.height());tag.putInt("DoorBottom",door.bottom());
        if(!tag.equals(this.entityData.get(DATA_TOWER_R64))){this.entityData.set(DATA_TOWER_R64,tag);this.refreshDimensions();}
    }
    /** While stowed, clients are told which end the city rests at: that decides which blocks they remember the look of. */
    public void showCityModeR64(int mode)
    {if(this.getStationState()==STOWED&&this.towerRunR64()!=mode)this.entityData.set(DATA_TOWER_RUN_R64,mode);}
    /** Starts a run from stowed; the towers' keeper has checked the city and the blocks. */
    public boolean beginTowerRunR64(int run)
    {
        if(this.level().isClientSide||this.towerR64()<0||this.getStationState()!=STOWED
                ||run==com.projectseele.world.ArmamentTowerLogicR64.NONE)return false;
        this.entityData.set(DATA_TOWER_RUN_R64,run);this.entityData.set(DATA_STOCKED,true);
        this.setDoor(0F);this.setLift(0F);this.setHatch(0F);
        this.towerRunLiveR64=true;this.towerReadyTicksR64=0;this.transition(OPENING);return true;
    }
    /** Brings a tower in from wherever its run stands; a phase turned round carries on from where it was. */
    public boolean recallTowerR64()
    {
        if(this.level().isClientSide||this.towerR64()<0)return false;
        boolean raised=this.towerRunR64()==com.projectseele.world.ArmamentTowerLogicR64.RAISED;
        int lock=raised?com.projectseele.config.SeeleConfig.ARMAMENT_TOWER_LOCK_TICKS.get():HATCH_TICKS;
        int door=raised?com.projectseele.config.SeeleConfig.ARMAMENT_TOWER_DOOR_TICKS.get():DOOR_TICKS;
        int elapsed=this.phaseTicks;
        switch(this.getStationState())
        {
            case OPENING -> {this.transition(CLOSING);this.phaseTicks=com.projectseele.world.ArmamentTowerLogicR64.reversedTicks(elapsed,lock,lock);}
            case RISING -> {this.transition(LOWERING);this.phaseTicks=com.projectseele.world.ArmamentTowerLogicR64.reversedTicks(elapsed,RISE_TICKS,LOWER_TICKS);}
            case DOOR_OPENING -> {this.transition(DOOR_CLOSING);this.phaseTicks=com.projectseele.world.ArmamentTowerLogicR64.reversedTicks(elapsed,door,door);}
            case READY -> this.transition(DOOR_CLOSING);
            default -> {return false;}
        }
        return true;
    }
    /** Ends a run at once, stowed. The towers' keeper has put the blocks back. */
    public void resetTowerRunR64()
    {
        this.setDoor(0F);this.setLift(0F);this.setHatch(0F);
        this.towerRunLiveR64=false;this.towerReadyTicksR64=0;this.deployQueued=false;this.transition(STOWED);
    }
    /** Ticks this tower has stood ready with nobody taking the weapon; the count starts again after combat. */
    public int towerReadyTicksR64(boolean combat)
    {
        if(this.getStationState()!=READY||combat)this.towerReadyTicksR64=0;else this.towerReadyTicksR64++;
        return this.towerReadyTicksR64;
    }
    /** For the command room: how far the weapon is out, by the pod's lift with the city lowered and by the door with it raised. */
    public int towerShownPercentR64()
    {
        float shown=this.towerRunR64()==com.projectseele.world.ArmamentTowerLogicR64.RAISED?this.entityData.get(DATA_DOOR):this.entityData.get(DATA_LIFT);
        return this.getStationState()==STOWED?0:Mth.clamp(Math.round(shown*100F),0,100);
    }
    /**
     * Clients remember what the hatch or the door looks like while its blocks are in place, and draw that moving
     * once the blocks are out. Null if nothing was seen: the renderer then draws plain plates.
     */
    public net.minecraft.world.level.block.state.BlockState[] towerClientCellsR64()
    {return this.towerClientCellsRunR64==this.towerRunR64()?this.towerClientCellsR64:null;}
    private void sampleTowerCellsR64()
    {
        int run=this.towerRunR64(),state=this.getStationState();
        boolean inPlace=state==STOWED||run==com.projectseele.world.ArmamentTowerLogicR64.RAISED&&state==OPENING;
        if(!inPlace||run==com.projectseele.world.ArmamentTowerLogicR64.NONE)return;
        if(this.towerClientCellsR64!=null&&this.towerClientCellsRunR64==run&&this.tickCount%20!=0)return;
        var cells=com.projectseele.world.ArmamentTowerLogicR64.cells(run,this.towerLotR64(),this.towerFacingR64(),this.towerDoorR64());
        var states=new net.minecraft.world.level.block.state.BlockState[cells.size()];
        var at=new net.minecraft.core.BlockPos.MutableBlockPos();int solid=0;
        for(int i=0;i<states.length;i++)
        {
            int[] cell=cells.get(i);states[i]=this.level().getBlockState(at.set(cell[0],cell[1],cell[2]));
            if(!states[i].isAir())solid++;
        }
        // The block changes of a run starting can arrive a moment before its state: an emptier look never replaces a fuller one.
        if(solid*2>=states.length||this.towerClientCellsR64==null||this.towerClientCellsRunR64!=run)
        {this.towerClientCellsR64=solid>0?states:null;this.towerClientCellsRunR64=run;}
    }
    /** The station stands in the lot's hatch layer, and inside the building when the city is raised: light is read in the open in front of the door. */
    @Override
    public Vec3 getLightProbePosition(float partialTick)
    {
        if(this.towerR64()<0)return super.getLightProbePosition(partialTick);
        int facing=this.towerFacingR64();double out=com.projectseele.world.ArmamentTowerLogicR64.HALF+2.5D;
        return this.position().add(com.projectseele.world.ArmamentTowerLogicR64.stepX(facing)*out,3.0D,
                com.projectseele.world.ArmamentTowerLogicR64.stepZ(facing)*out);
    }

    public boolean deploy()
    {
        if (this.level().isClientSide)
        {
            return false;
        }
        if(this.towerR64()>=0)return com.projectseele.world.ArmamentTowersR64.requestDeploy(this);
        if(com.projectseele.world.TvMissionEquipmentR45.surfaceSupplyRackR50(this))
        {this.surfaceStateInitializedR54=true;this.deployQueued=true;this.maintainSurfaceSupplyR50();return this.isStocked();}
        if(this.payloadR47()!=EvaUnit01Entity.WEAPON_RIFLE&&!this.isStocked())return false;
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
        if(this.payloadR47()==EvaUnit01Entity.WEAPON_RIFLE)this.entityData.set(DATA_STOCKED, !com.projectseele.world.TvMissionEquipmentR45.missionRack(this)
                    ||com.projectseele.world.TvMissionEquipmentR45.physicalStockPresent(this));
        this.setDoor(0.0F);
        this.transition(OPENING);
        return true;
    }

    public boolean recall()
    {
        if(this.towerR64()>=0)return !this.level().isClientSide&&com.projectseele.world.ArmamentTowersR64.requestRecall(this);
        if(com.projectseele.world.TvMissionEquipmentR45.surfaceSupplyRackR50(this))
        {if(this.level().isClientSide)return false;this.deployQueued=false;this.maintainSurfaceSupplyR50();return true;}
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
        if(!EvaEquipmentPolicyR45.allowed(this.payloadR47(),eva.getUnitVariant(),eva.isExperimentalUnit()))
        {
            player.displayClientMessage(Component.translatable(this.payloadR47()==7
                    ?"msg.projectseele.weapon_vault_unit00_only":"msg.projectseele.weapon_vault_unit02_only"),true);
            return false;
        }
        if (!com.projectseele.world.EquipmentVaultsR47.issueR47(this,eva))
        {
            player.displayClientMessage(Component.translatable(
                    "msg.projectseele.armament_already_installed"), true);
            return false;
        }
        this.entityData.set(DATA_STOCKED, false);
        this.transition(EMPTY);
        player.displayClientMessage(Component.translatable(
                this.payloadR47()==7?"msg.projectseele.shield_deployed":this.payloadR47()==6
                        ?"msg.projectseele.sword_deployed":"msg.projectseele.armament_rifle_acquired"), true);
        return true;
    }

    public static boolean acquireNearest(ServerLevel level,
            Player player, EvaUnit01Entity eva)
    {
        NervArmamentStationEntity station = nearest(level, eva.position(),
                EVA_PICKUP_RANGE, true);
        if(station!=null&&!EvaEquipmentPolicyR45.allowed(station.payloadR47(),eva.getUnitVariant(),eva.isExperimentalUnit()))
            station=level.getEntitiesOfClass(NervArmamentStationEntity.class,
                    eva.getBoundingBox().inflate(EVA_PICKUP_RANGE,40,EVA_PICKUP_RANGE),
                    candidate->candidate.isReadyAndStocked()
                            &&EvaEquipmentPolicyR45.allowed(candidate.payloadR47(),eva.getUnitVariant(),eva.isExperimentalUnit())
                            &&horizontalDistanceSqr(candidate.position(),eva.position())<=EVA_PICKUP_RANGE*EVA_PICKUP_RANGE)
                    .stream().min(Comparator.comparingDouble(eva::distanceToSqr)).orElse(null);
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
    /** One committed new supply receipt updates the same physical rack's real stock. */
    public boolean commissionTvMissionSupplyR50(int unit,String receipt)
    {
        if(!com.projectseele.world.TvMissionEquipmentR45.commissionNewSupply(this,unit,receipt))return false;
        this.entityData.set(DATA_STOCKED,true);return true;
    }
    /** The mountain shield uses its well; the original fixed-gun source stays at its service level. */
    private void maintainSurfaceSupplyR50()
    {
        boolean stocked=com.projectseele.world.TvMissionEquipmentR45.physicalStockPresent(this);
        this.entityData.set(DATA_STOCKED,stocked);
        var mission=com.projectseele.world.TvCampaignSavedData.get((ServerLevel)this.level());
        if(!stocked||java.util.Set.of("cancel","failure","combat_victory","episode_archived").contains(mission.phase)
                ||!surfaceStateInitializedR54&&mission.active.isEmpty())this.deployQueued=false;
        surfaceStateInitializedR54=true;
        boolean open=stocked&&this.deployQueued;
        if(this.payloadR47()!=7)
        {
            this.setLift(1F);this.setHatch(1F);
            float door=Mth.clamp(this.entityData.get(DATA_DOOR)+(open?1F:-1F)/DOOR_TICKS,0F,1F);
            this.setDoor(door);
            this.entityData.set(DATA_STATE,door==1?READY:door==0?STOWED:open?DOOR_OPENING:DOOR_CLOSING);
            this.phaseTicks=0;return;
        }
        if(!com.projectseele.world.EquipmentVaultsR47.surfaceShieldLidR54(this))return;
        float door=this.entityData.get(DATA_DOOR),lift=this.entityData.get(DATA_LIFT),hatch=this.entityData.get(DATA_HATCH);
        if(open)
        {
            hatch=Mth.clamp(hatch+1F/HATCH_TICKS,0,1);
            if(hatch>=1)lift=Mth.clamp(lift+1F/RISE_TICKS,0,1);
            if(lift>=1)door=Mth.clamp(door+1F/DOOR_TICKS,0,1);
        }
        else
        {
            door=Mth.clamp(door-1F/DOOR_TICKS,0,1);
            if(door<=0)lift=Mth.clamp(lift-1F/LOWER_TICKS,0,1);
            if(lift<=0)hatch=Mth.clamp(hatch-1F/HATCH_TICKS,0,1);
        }
        this.setDoor(door);this.setLift(lift);this.setHatch(hatch);
        this.entityData.set(DATA_STATE,open?(hatch<1?OPENING:lift<1?RISING:door<1?DOOR_OPENING:READY)
                :(door>0?DOOR_CLOSING:lift>0?LOWERING:hatch>0?CLOSING:STOWED));
        com.projectseele.world.EquipmentVaultsR47.surfaceShieldLidR54(this);
        this.phaseTicks=0;
    }
    /** Atomic fixed-gun transfer updates this same finite rack's display without replenishing a payload. */
    public void refreshFiniteMissionStockR52()
    {if(!this.level().isClientSide&&com.projectseele.world.TvMissionEquipmentR45.surfaceSupplyRackR50(this))this.maintainSurfaceSupplyR50();}

    public boolean issueToAssignedPilotR30(TrainingPilotEntity pilot,EvaUnit01Entity eva)
    {
        if(com.projectseele.world.TvMissionEquipmentR45.missionRack(this))return false;
        if(this.level().isClientSide||eva.getPilotEntity()!=pilot||pilot.getAssignedVariant()!=eva.getUnitVariant()
                ||!eva.isPoweredOn()||!this.isReadyAndStocked()
                ||horizontalDistanceSqr(eva.position(),this.position())>EVA_PICKUP_RANGE*EVA_PICKUP_RANGE
                ||!com.projectseele.world.EquipmentVaultsR47.issueR47(this,eva))return false;
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
        float height = 1.0F + this.presentedHeightR64();
        return EntityDimensions.fixed(this.rackHalfWidthR47()*2+3, height);
    }

    /**
     * How high the offered weapon stands above the station: the pod's lift, or for a tower in the standing building
     * the opened part of its door. The hand-over asks that the EVA's hull be within four blocks of this box, so with
     * the door up an EVA standing on a kerb, a wreck or a low roof still reaches the weapon behind it.
     */
    private float presentedHeightR64()
    {
        if(this.towerR64()>=0&&this.towerRunR64()==com.projectseele.world.ArmamentTowerLogicR64.RAISED)
        {var door=this.towerDoorR64();return this.entityData.get(DATA_DOOR)*(door.bottom()+door.height());}
        return this.podTravelR47()*this.entityData.get(DATA_LIFT);
    }
    public int payloadR47(){return this.entityData.get(DATA_PAYLOAD_R47);}
    public int rackHalfWidthR47(){return this.towerR64()>=0?com.projectseele.world.ArmamentTowerLogicR64.HALF-1:this.payloadR47()==7?14:4;}
    /** Full-size SMG depth is 12.952 m; its original 7 m interior is retired. */
    public int rackHalfDepthR54(){return this.towerR64()<0&&this.payloadR47()==EvaUnit01Entity.WEAPON_RIFLE?8:this.rackHalfWidthR47();}

    @Override
    protected AABB makeBoundingBox()
    {
        if(this.entityData==null||this.payloadR47()!=EvaUnit01Entity.WEAPON_RIFLE)return super.makeBoundingBox();
        double width=this.rackHalfWidthR47()+1.5D,depth=this.rackHalfDepthR54()+1.5D;
        double height=1.0D+this.presentedHeightR64();
        return new AABB(this.getX()-width,this.getY(),this.getZ()-depth,
                this.getX()+width,this.getY()+height,this.getZ()+depth);
    }

    @Override
    public AABB getBoundingBoxForCulling()
    {
        if(this.towerR64()>=0)
        {
            // The hatch plates slide out past the lot, and the roof locks sit on top of the standing building.
            double reach=2*com.projectseele.world.ArmamentTowerLogicR64.HALF+2.0D;
            return new AABB(this.getX()-reach,this.getY()-this.podTravelR47()-1.0D,this.getZ()-reach,
                    this.getX()+reach,this.getY()+Math.max(this.podHeightR47(),this.towerHeightR64())+8.0D,this.getZ()+reach);
        }
        if(this.payloadR47()!=EvaUnit01Entity.WEAPON_RIFLE)return super.getBoundingBoxForCulling();
        double width=2*this.rackHalfWidthR47()+2.0D,depth=this.rackHalfDepthR54()+1.5D;
        return new AABB(this.getX()-width,this.getY()-this.podTravelR47(),this.getZ()-depth,
                this.getX()+width,this.getY()+this.podHeightR47()+2.0D,this.getZ()+depth);
    }

    public float podTravelR47(){return this.towerR64()>=0?com.projectseele.world.ArmamentTowerLogicR64.POD_TRAVEL:this.payloadR47()==7?53.0F:43.0F;}
    public float podHeightR47(){return this.payloadR47()==7?52.0F:42.0F;}
    public void setPayloadR47(int payload)
    {this.entityData.set(DATA_PAYLOAD_R47,payload==2||payload==6||payload==7?payload:EvaUnit01Entity.WEAPON_RIFLE);this.refreshDimensions();}
    @Override public void onSyncedDataUpdated(EntityDataAccessor<?> key)
    {
        super.onSyncedDataUpdated(key);
        if(DATA_LIFT.equals(key)||DATA_PAYLOAD_R47.equals(key)||DATA_TOWER_R64.equals(key)
                ||this.towerR64()>=0&&(DATA_DOOR.equals(key)||DATA_TOWER_RUN_R64.equals(key)))this.refreshDimensions();
    }
    public void returnStoredPayloadR47()
    {
        if(com.projectseele.world.TvMissionEquipmentR45.surfaceSupplyRackR50(this))
        {if(!this.level().isClientSide)this.maintainSurfaceSupplyR50();return;}
        if(!this.level().isClientSide&&this.payloadR47()!=EvaUnit01Entity.WEAPON_RIFLE)
            this.entityData.set(DATA_STOCKED,true);
    }

    @Override
    public boolean isPickable()
    {
        return this.getStationState() != STOWED || this.entityData.get(DATA_LIFT)>0;
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
        if(this.towerR64()>=0)this.refreshDimensions();
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
