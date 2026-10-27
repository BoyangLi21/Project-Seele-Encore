package com.projectseele.entity;

import com.projectseele.registry.ModEntities;
import com.projectseele.world.NervSiloHatchGeometryR52;
import com.projectseele.world.RigidTransform;
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
import net.minecraft.world.phys.shapes.CollisionContext;
import org.joml.Quaternionf;
import net.minecraftforge.network.NetworkHooks;

/** Synchronized visual plus physical weather seal for one EVA surface hatch. */
public final class NervSiloDoorEntity extends Entity
{
    @Override
    protected boolean updateInWaterStateAndDoFluidPushing()
    {
        // Anchored or actuator-driven machinery never receives fluid motion.
        // Its full mechanical bounding box can span hundreds of thousands of cells.
        this.fluidHeight.clear();
        this.forgeFluidTypeHeight.clear();
        this.wasTouchingWater=false;
        return false;
    }

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
    private static final EntityDataAccessor<CompoundTag> DATA_DECLARED_SPEC_R52 =
            SynchedEntityData.defineId(NervSiloDoorEntity.class,EntityDataSerializers.COMPOUND_TAG);

    private boolean declaredClockR52;private long declaredAcceptedAtR52=Long.MIN_VALUE;
    private CompoundTag savedDeclaredR52=new CompoundTag();private boolean invalidDeclaredR52;
    private int clockStepR52,clockDurationR52;private float clockStartR52,clockGoalR52=Float.NaN;
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
        this.entityData.define(DATA_DECLARED_SPEC_R52,new CompoundTag());
    }

    @Override
    protected void readAdditionalSaveData(CompoundTag tag)
    {
        if(!tag.contains("R52DeclaredHatch"))return;var data=tag.getCompound("R52DeclaredHatch").copy();savedDeclaredR52=data;declaredClockR52=true;
        try{if(data.getInt("Version")!=52)throw new IllegalStateException("Hatch sample version changed");var spec=data.getCompound("Spec");readSpec(spec);float raw=data.getFloat("Raw"),target=data.getFloat("Target");if(!Float.isFinite(raw+target)||raw<0||raw>1||target<0||target>1)throw new IllegalStateException("Hatch raw sample changed");entityData.set(DATA_DECLARED_SPEC_R52,spec);entityData.set(DATA_OPEN,raw);entityData.set(DATA_TARGET,target);entityData.set(DATA_VARIANT,data.getInt("Variant"));entityData.set(DATA_STAGE,data.getInt("Stage"));clockStartR52=data.getFloat("ClockStart");clockGoalR52=data.getFloat("ClockGoal");clockStepR52=data.getInt("ClockStep");clockDurationR52=data.getInt("ClockDuration");if(clockStepR52<0||clockDurationR52<0||clockStepR52>clockDurationR52)throw new IllegalStateException("Hatch clock changed");clientOpen=clientOpenO=raw;}
        catch(RuntimeException malformed){invalidDeclaredR52=true;var held=data.getCompound("Spec").copy();held.putBoolean("Held",true);try{if(readSpec(held)==null)throw new IllegalStateException("No held hatch source");float raw=data.getFloat("Raw");if(!Float.isFinite(raw)||raw<0||raw>1)throw new IllegalStateException("No held hatch sample");held.putFloat("PreviousRaw",raw);held.putFloat("CurrentRaw",raw);held.putLong("At",level().getGameTime());entityData.set(DATA_OPEN,raw);}catch(RuntimeException unknown){held=new CompoundTag();held.putBoolean("Held",true);held.putBoolean("GeometryMissing",true);}entityData.set(DATA_DECLARED_SPEC_R52,held);}
    }

    @Override
    protected void addAdditionalSaveData(CompoundTag tag)
    {
        if(!declaredClockR52)return;if(invalidDeclaredR52){tag.put("R52DeclaredHatch",savedDeclaredR52.copy());return;}var data=savedDeclaredR52.copy();data.putInt("Version",52);data.put("Spec",entityData.get(DATA_DECLARED_SPEC_R52).copy());data.putFloat("Raw",entityData.get(DATA_OPEN));data.putFloat("Target",entityData.get(DATA_TARGET));data.putInt("Variant",getVariant());data.putInt("Stage",getBulkheadStage());data.putFloat("ClockStart",clockStartR52);data.putFloat("ClockGoal",clockGoalR52);data.putInt("ClockStep",clockStepR52);data.putInt("ClockDuration",clockDurationR52);tag.put("R52DeclaredHatch",data);
    }

    /** Only declared Root machinery survives a save; legacy runtime leaves remain transient. */
    @Override public boolean shouldBeSaved(){return declaredClockR52&&super.shouldBeSaved();}

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
        if(declaredClockR52)return;
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
        var declared=entityData.get(DATA_DECLARED_SPEC_R52);if(!declared.isEmpty()){float current=declared.contains("CurrentRaw")?declared.getFloat("CurrentRaw"):entityData.get(DATA_OPEN),previous=declared.contains("PreviousRaw")?declared.getFloat("PreviousRaw"):current;float t=(float)Mth.clamp(level().getGameTime()-declared.getLong("At")+(double)partialTick,0,1);return EvaDorsalMechanism.smooth(Mth.lerp(t,previous,current));}
        return EvaDorsalMechanism.smooth(Mth.lerp(partialTick, this.clientOpenO, this.clientOpen));
    }
    /** Actual server state, independent of client display interpolation fields. */
    public float actualOpenProgressR52(){return EvaDorsalMechanism.smooth(this.entityData.get(DATA_OPEN));}

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

    public float proposedDeclaredProgressR52(boolean open)
    {return EvaDorsalMechanism.smooth(proposedRawR52(open));}
    private float proposedRawR52(boolean open)
    {
        if(invalidDeclaredR52)throw new IllegalStateException("Saved declared hatch held");var spec=declaredSpecR52();float current=entityData.get(DATA_OPEN),goal=open?1:0;
        if(spec==null)return Mth.approach(current,goal,isTvBulkhead()?1F/18F:com.projectseele.world.TvLaunchFacility.enabled((ServerLevel)level())?1F/30F:.10F);
        boolean changed=clockGoalR52!=goal;float start=changed?current:clockStartR52;int duration=changed?Math.max(1,(int)Math.ceil(Math.abs(goal-current)*(open?spec.openTicks():spec.closeTicks()))):clockDurationR52;int step=changed?1:Math.min(duration,clockStepR52+1);return step>=duration?goal:start+(goal-start)*step/duration;
    }
    public void advanceDeclaredR52(boolean open)
    {if(!(level() instanceof ServerLevel level)||!com.projectseele.world.NervRouteRuntimeR52.claimed(level))throw new IllegalStateException("Explicit claimed controller required");declaredClockR52=true;if(declaredAcceptedAtR52==level.getGameTime())return;float next=proposedRawR52(open),goal=open?1:0;var spec=declaredSpecR52();if(spec!=null){if(clockGoalR52!=goal){clockStartR52=entityData.get(DATA_OPEN);clockGoalR52=goal;clockDurationR52=Math.max(1,(int)Math.ceil(Math.abs(goal-clockStartR52)*(open?spec.openTicks():spec.closeTicks())));clockStepR52=0;}clockStepR52=Math.min(clockDurationR52,clockStepR52+1);var sample=entityData.get(DATA_DECLARED_SPEC_R52).copy();sample.putFloat("PreviousRaw",entityData.get(DATA_OPEN));sample.putFloat("CurrentRaw",next);sample.putLong("At",level.getGameTime());entityData.set(DATA_DECLARED_SPEC_R52,sample);}declaredAcceptedAtR52=level.getGameTime();entityData.set(DATA_OPEN,next);entityData.set(DATA_TARGET,goal);updateDeclaredBoundsR52();}
    /** Root-controller configuration only; owns no implicit collision cells. */
    public void configureDeclaredR52(int variant,int stage,Vec3 actualPosition,boolean open)
    {
        if(!(this.level() instanceof ServerLevel level)||!com.projectseele.world.NervRouteRuntimeR52.claimed(level)||variant<0||variant>2||stage< -1
                ||this.position().distanceToSqr(actualPosition)>1e-8)throw new IllegalStateException("Actual declared commissioned silo visual required");
        declaredClockR52=true;this.entityData.set(DATA_VARIANT,variant);this.entityData.set(DATA_STAGE,stage);this.setTargetOpen(open?1:0);
    }
    public void configureDeclaredR52(int variant,int stage,RigidTransform frame,boolean open,SiloHatchMechanism.Spec spec)
    {
        if(spec==null||Math.abs(frame.qx())>1e-6||Math.abs(frame.qz())>1e-6||!com.projectseele.world.NervAirTransportManifestR52.same(actualFrameR52(),frame)||invalidDeclaredR52)throw new IllegalStateException("Actual horizontal hatch frame and explicit aperture required");
        var old=declaredSpecR52();if(old!=null&&!old.equals(spec)&&!(old.uprightGuideEarlyVariant()==-1&&spec.uprightGuideEarlyVariant()>=0&&old.equals(spec.withUprightGuideEarlyVariant(-1))))throw new IllegalStateException("Existing declared hatch aperture/clock changed");configureDeclaredR52(variant,stage,frame.translation(),open);var data=entityData.get(DATA_DECLARED_SPEC_R52).copy();writeSpecR53(data,spec);if(!data.contains("CurrentRaw")){data.putFloat("PreviousRaw",entityData.get(DATA_OPEN));data.putFloat("CurrentRaw",entityData.get(DATA_OPEN));data.putLong("At",level().getGameTime());}entityData.set(DATA_DECLARED_SPEC_R52,data);updateDeclaredBoundsR52();
    }
    public void configureDeclaredR52(int variant,int stage,Vec3 position,boolean open,SiloHatchMechanism.Spec spec)
    {configureDeclaredR52(variant,stage,RigidTransform.of(position,new Quaternionf().rotationY((float)Math.toRadians(-getYRot()))),open,spec);}
    private static SiloHatchMechanism.Spec readSpec(CompoundTag data)
    {return data.isEmpty()||data.getBoolean("GeometryMissing")?null:new SiloHatchMechanism.Spec(data.getFloat("OpeningX"),data.getFloat("OpeningZ"),data.getInt("OpenTicks"),data.getInt("CloseTicks"),data.contains("SeparationSign")?data.getInt("SeparationSign"):1,data.contains("BeamBottom")?data.getDouble("BeamBottom"):-2.01,data.getBoolean("ServiceColumnPorts"),data.getBoolean("UprightGuidePorts"),data.contains("ServiceGantryYawDegrees")?data.getInt("ServiceGantryYawDegrees"):0,data.contains("UprightGuideEarlyVariant")?data.getInt("UprightGuideEarlyVariant"):-1);}
    private static void writeSpecR53(CompoundTag data,SiloHatchMechanism.Spec spec)
    {data.putFloat("OpeningX",spec.openingX());data.putFloat("OpeningZ",spec.openingZ());data.putInt("OpenTicks",spec.openTicks());data.putInt("CloseTicks",spec.closeTicks());data.putInt("SeparationSign",spec.separationSign());data.putDouble("BeamBottom",spec.beamBottom());data.putBoolean("ServiceColumnPorts",spec.serviceColumnPorts());data.putInt("ServiceGantryYawDegrees",spec.serviceGantryYawDegrees());data.putBoolean("UprightGuidePorts",spec.uprightGuidePorts());data.putInt("UprightGuideEarlyVariant",spec.uprightGuideEarlyVariant());}
    public boolean declaredGeometryMissingR52(){return entityData.get(DATA_DECLARED_SPEC_R52).getBoolean("GeometryMissing");}
    public SiloHatchMechanism.Spec declaredSpecR52(){return readSpec(entityData.get(DATA_DECLARED_SPEC_R52));}
    public boolean matchesDeclaredR52(SiloHatchMechanism.Spec spec){return !invalidDeclaredR52&&spec!=null&&spec.equals(declaredSpecR52());}
    public RigidTransform actualFrameR52(){return RigidTransform.of(position(),new Quaternionf().rotationY((float)Math.toRadians(-getYRot())));}
    public NervSiloHatchGeometryR52 declaredGeometryR52()
    {try{return com.projectseele.world.NervLowerFrameR52.retiredServiceLeavesR53(getUUID(),getVariant(),declaredSpecR52(),actualFrameR52())
                ?NervSiloHatchGeometryR52.loadRetiredServiceClasspathR53(declaredSpecR52()):NervSiloHatchGeometryR52.loadClasspath(declaredSpecR52());}catch(java.io.IOException missing){throw new IllegalStateException("Declared hatch exact source missing",missing);}}
    private void updateDeclaredBoundsR52(){if(declaredSpecR52()!=null)setBoundingBox(com.projectseele.world.NervRigidMeshSweepR52.transformed(declaredGeometryR52().bounds(actualOpenProgressR52()),actualFrameR52()));}
    public boolean clearDeclaredSweepR52(ServerLevel level,float from,float to,Set<java.util.UUID> own,Set<BlockPos> movingCells,Set<BlockPos> supportCells)
    {return clearDeclaredSweepR52(level,from,to,own,movingCells,supportCells,Set.of());}
    private static boolean peerProxySetsR52(Set<BlockPos> moving,Set<BlockPos> supports,Set<BlockPos> peer)
    {return peer!=null&&(peer.isEmpty()||!peer.isEmpty()&&peer.size()<=512&&Collections.disjoint(peer,moving)&&Collections.disjoint(peer,supports));}
    private static boolean actualGateMeshIntersectsR52(NervSiloHatchGeometryR52 geometry,RigidTransform frame,float from,float to,com.projectseele.world.NervFlightProofR52.ObstacleMesh mesh)
    {return geometry.intersects(frame,from,to,mesh.mesh(),mesh.frame(),mesh.endFrame());}
    /** Owner has verified the paired front's live identity/Spec/closed phase.
     * Only its exact bounded declared floor proxies are dispatched separately; the actual
     * peer actor meshes below are never ignored. Closure volumes stay own-only. */
    public boolean clearDeclaredSweepR52(ServerLevel level,float from,float to,Set<java.util.UUID> own,Set<BlockPos> movingCells,Set<BlockPos> supportCells,Set<BlockPos> peerProxyCells)
    {
        if(invalidDeclaredR52||declaredSpecR52()==null||actualOpenProgressR52()!=from||!peerProxySetsR52(movingCells,supportCells,peerProxyCells)||!peerProxyCells.isEmpty()&&!declaredSpecR52().serviceColumnPorts())return false;
        for(var at:peerProxyCells)if(!level.hasChunkAt(at)||!com.projectseele.world.NervAssemblyOwnerR52.wetFloorMaterialR53(level.getBlockState(at)))return false;var geometry=declaredGeometryR52();var frame=actualFrameR52();
        var detached=com.projectseele.world.NervFlightProofR52.detachedCarrierObstacles(level);if(detached==null)return false;for(var mesh:detached)if(geometry.intersects(frame,from,to,mesh.mesh(),mesh.frame(),mesh.endFrame()))return false;
        if(to<from&&!com.projectseele.world.NervGateClosureR52.clearActualActors(level,this,movingCells))return false;
        java.util.UUID attachedGantry=null;if(declaredSpecR52().serviceColumnPorts()){for(var gantry:level.getEntitiesOfClass(NervCarrierPlatformEntity.class,getBoundingBox().inflate(2),g->g.isRestraintGantry()&&g.getUnitVariant()==getVariant())){if(!gantry.hasDeclaredMachineFrameR52()||!gantry.declaredCollisionSourceR52().equals(com.projectseele.world.NervFlightProofR52.selectedCageSourceR52()))return false;var actual=RigidTransform.of(gantry.position(),gantry.declaredMachineRotationR52());var expected=frame.compose(declaredSpecR52().serviceGantryRelativeFrame());if(!com.projectseele.world.NervAirTransportManifestR52.same(actual,expected))continue;if(attachedGantry!=null)return false;try{for(var member:com.projectseele.world.NervPlantMotionR52.actualRenderedMeshesR52(gantry))if(geometry.movingIntersects(frame,from,to,member.mesh(),member.frame()))return false;}catch(java.io.IOException missing){return false;}attachedGantry=gantry.getUUID();}if(attachedGantry==null)return false;}
        for(var local:geometry.bearingPoints()){var p=frame.transformPoint(local);boolean supported=false;for(var at:supportCells){if(Math.abs(p.x-(at.getX()+.5))>.6||Math.abs(p.z-(at.getZ()+.5))>.6)continue;if(!level.hasChunkAt(at))return false;for(var box:level.getBlockState(at).getCollisionShape(level,at,CollisionContext.of(this)).toAabbs()){var world=box.move(at);if(p.x>world.minX&&p.x<world.maxX&&p.z>world.minZ&&p.z<world.maxZ&&Math.abs(p.y-world.maxY)<=.002)supported=true;}}if(!supported)return false;}
        var sweepBounds=geometry.sweptBounds(frame,from,to);
        var guideSteelSeen=new HashSet<String>();
        for(var rail:com.projectseele.world.NervUprightGuidewayR52.actualPieces(level,sweepBounds))if(guideSteelSeen.add(rail.name())&&geometry.movingIntersects(frame,from,to,rail.steel().mesh(),rail.steel().frame()))return false;
        var seen=new HashSet<BlockPos>();
        for(var box:geometry.envelopes(frame,from,to))
        {
            if(!com.projectseele.world.EntryPlugEjectionR48.loaded(level,box))return false;
            for(var at:BlockPos.betweenClosed(BlockPos.containing(box.minX,box.minY,box.minZ),BlockPos.containing(box.maxX,box.maxY,box.maxZ)))
            {
                var key=at.immutable();if(!seen.add(key)||movingCells.contains(key)||peerProxyCells.contains(key))continue;
                var state=level.getBlockState(key);if(state.isAir())continue;
                for(var shape:state.getCollisionShape(level,key,CollisionContext.of(this)).toAabbs())if(geometry.intersects(frame,from,to,shape.move(key)))return false;
            }
        }
        // Query the union once. All live geometry and the exact gantry-contact
        // exception retain the same full-motion narrow-phase checks.
        for(var actor:level.getEntities(this,sweepBounds.inflate(200),e->e.isAlive()&&!e.isSpectator()&&(e instanceof net.minecraft.world.entity.LivingEntity||e.canBeCollidedWith()||e instanceof UNTransportEntity||e instanceof EntryPlugCarrierEntity||e instanceof NervSiloDoorEntity||e instanceof NervHangarDoorEntity||e instanceof NervCarrierPlatformEntity)))
        {
            if(actor.getUUID().equals(attachedGantry))continue;
            var meshes=com.projectseele.world.NervFlightProofR52.actualObstacleMeshes(actor);
            if(meshes==null)
            {
                var bounds=actor instanceof UNTransportEntity aircraft?aircraft.getBoundingBoxForCulling():actor.getBoundingBox();
                if(geometry.intersects(frame,from,to,bounds))return false;
            }
            else if(meshes.isEmpty())
            {
                if(geometry.intersects(frame,from,to,actor.getBoundingBox()))return false;
            }
            else for(var mesh:meshes)if(actualGateMeshIntersectsR52(geometry,frame,from,to,mesh))return false;
        }
        return true;
    }

    public static void reconcile(ServerLevel level, int variant,
            BlockPos surfaceBed, float targetOpen)
    {
        if(com.projectseele.world.NervLegacyGenerationGuardR52.retired(level))return;
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
        if(com.projectseele.world.NervLegacyGenerationGuardR52.retired(level))return;
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
        if(com.projectseele.world.NervLegacyGenerationGuardR52.retired(level))return;
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
