package com.projectseele.entity;

import com.projectseele.registry.ModEntities;
import com.projectseele.world.NervHangarGateGeometryR52;
import com.projectseele.world.RigidTransform;
import java.util.*;
import net.minecraft.core.BlockPos;
import net.minecraft.world.phys.shapes.CollisionContext;
import org.joml.Quaternionf;
import java.util.Comparator;
import java.util.List;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.DoubleTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.nbt.Tag;
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

/** Transient visual leaves for one physical wet-cage pressure gate. */
public final class NervHangarDoorEntity extends Entity
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

    private static final EntityDataAccessor<Integer> DATA_VARIANT =
            SynchedEntityData.defineId(NervHangarDoorEntity.class,
                    EntityDataSerializers.INT);
    private static final EntityDataAccessor<Float> DATA_OPEN =
            SynchedEntityData.defineId(NervHangarDoorEntity.class,
                    EntityDataSerializers.FLOAT);
    private static final EntityDataAccessor<Float> DATA_TARGET =
            SynchedEntityData.defineId(NervHangarDoorEntity.class,
                    EntityDataSerializers.FLOAT);

    private boolean declaredClockR52;private long declaredAcceptedAtR52=Long.MIN_VALUE;
    private float clientOpen;
    private static final EntityDataAccessor<Float> DATA_HEIGHT = SynchedEntityData.defineId(NervHangarDoorEntity.class, EntityDataSerializers.FLOAT);
    private static final EntityDataAccessor<Float> DATA_WIDTH = SynchedEntityData.defineId(NervHangarDoorEntity.class, EntityDataSerializers.FLOAT);
    private static final EntityDataAccessor<CompoundTag> DATA_STACK_R52=SynchedEntityData.defineId(NervHangarDoorEntity.class,EntityDataSerializers.COMPOUND_TAG);
    private CompoundTag savedStackR52=new CompoundTag();private boolean invalidStackR52;private float clockStartR52,clockGoalR52=Float.NaN;private int clockStepR52,clockDurationR52;
    private static final EntityDataAccessor<Float> DATA_DEPTH_SCALE=SynchedEntityData.defineId(NervHangarDoorEntity.class,EntityDataSerializers.FLOAT);
    public float visualDepthScale(){return entityData.get(DATA_DEPTH_SCALE);}
    public float visualHeight(){return entityData.get(DATA_HEIGHT);}
    public float visualWidth(){return entityData.get(DATA_WIDTH);}
    public boolean isSectionalUNGate(){return getVariant()==3&&visualWidth()>40;}
    private float clientOpenO;
    private boolean wasMoving;

    public NervHangarDoorEntity(EntityType<? extends NervHangarDoorEntity> type,
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
        this.entityData.define(DATA_OPEN, 0.0F);
        this.entityData.define(DATA_TARGET, 0.0F);
        this.entityData.define(DATA_HEIGHT, 65.0F);
        this.entityData.define(DATA_WIDTH, 33.0F);
        this.entityData.define(DATA_DEPTH_SCALE, 1.0F);
        this.entityData.define(DATA_STACK_R52,new CompoundTag());
    }

    @Override protected void readAdditionalSaveData(CompoundTag tag)
    {if(!tag.contains("R52SideStack")){if(tag.contains("UNHangarLeafR54")){var leaf=tag.getCompound("UNHangarLeafR54");float raw=leaf.getFloat("Raw"),target=leaf.getFloat("Target"),width=leaf.getFloat("Width"),height=leaf.getFloat("Height"),depth=leaf.getFloat("Depth");if(!Float.isFinite(raw+target+width+height+depth)||raw<0||raw>1||target<0||target>1||width<=0||height<=0||depth<=0)throw new IllegalStateException("Invalid original UN hangar leaf state");entityData.set(DATA_VARIANT,3);entityData.set(DATA_OPEN,raw);entityData.set(DATA_TARGET,target);entityData.set(DATA_WIDTH,width);entityData.set(DATA_HEIGHT,height);entityData.set(DATA_DEPTH_SCALE,depth);}return;}savedStackR52=tag.getCompound("R52SideStack").copy();declaredClockR52=true;try{if(savedStackR52.getInt("Version")!=52)throw new IllegalStateException("Unknown side-stack sample");var spec=savedStackR52.getCompound("Spec");var measured=readSpec(spec);float raw=savedStackR52.getFloat("Raw"),target=savedStackR52.getFloat("Target");if(measured==null||!Float.isFinite(raw+target)||raw<0||raw>1||target<0||target>1)throw new IllegalStateException("Unknown side-stack progress");entityData.set(DATA_STACK_R52,spec);entityData.set(DATA_OPEN,raw);entityData.set(DATA_TARGET,target);entityData.set(DATA_VARIANT,savedStackR52.getInt("Variant"));entityData.set(DATA_WIDTH,measured.width());entityData.set(DATA_HEIGHT,measured.height());clockStartR52=savedStackR52.getFloat("ClockStart");clockGoalR52=savedStackR52.getFloat("ClockGoal");clockStepR52=savedStackR52.getInt("ClockStep");clockDurationR52=savedStackR52.getInt("ClockDuration");if(clockStepR52<0||clockDurationR52<0||clockStepR52>clockDurationR52)throw new IllegalStateException("Unknown side-stack clock");setBoundingBox(com.projectseele.world.NervRigidMeshSweepR52.transformed(declaredGeometryR52().bounds(actualOpenProgressR52()),actualFrameR52()));}catch(RuntimeException bad){invalidStackR52=true;holdSavedVisualR52();}}
    @Override protected void addAdditionalSaveData(CompoundTag tag)
    {if(invalidStackR52){tag.put("R52SideStack",savedStackR52.copy());return;}if(declaredStackR52()==null){if(getVariant()==3){var leaf=new CompoundTag();leaf.putFloat("Raw",entityData.get(DATA_OPEN));leaf.putFloat("Target",entityData.get(DATA_TARGET));leaf.putFloat("Width",entityData.get(DATA_WIDTH));leaf.putFloat("Height",entityData.get(DATA_HEIGHT));leaf.putFloat("Depth",entityData.get(DATA_DEPTH_SCALE));tag.put("UNHangarLeafR54",leaf);}return;}var data=savedStackR52.copy();data.putInt("Version",52);data.put("Spec",entityData.get(DATA_STACK_R52).copy());data.putFloat("Raw",entityData.get(DATA_OPEN));data.putFloat("Target",entityData.get(DATA_TARGET));data.putInt("Variant",getVariant());data.putFloat("ClockStart",clockStartR52);data.putFloat("ClockGoal",clockGoalR52);data.putInt("ClockStep",clockStepR52);data.putInt("ClockDuration",clockDurationR52);tag.put("R52SideStack",data);}

    /** UN leaves retain their own original actuator; NERV uses declared Root machinery. */
    @Override public boolean shouldBeSaved(){return (declaredClockR52||getVariant()==3)&&super.shouldBeSaved();}

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
        float next = Mth.approach(current,
                this.entityData.get(DATA_TARGET), this.getVariant()==3?0.0125F:0.075F);
        boolean moving=Math.abs(next-current)>1.0E-4F;
        if(moving&&(!wasMoving||this.tickCount%40==0))this.level().playSound(null,this.getX(),this.getY()+30,this.getZ(),com.projectseele.registry.ModSounds.FACILITY.get("facility_hydraulic").get(),net.minecraft.sounds.SoundSource.BLOCKS,1.0F,.8F);
        if(!moving&&wasMoving)this.level().playSound(null,this.getX(),this.getY()+30,this.getZ(),com.projectseele.registry.ModSounds.FACILITY.get("facility_lock").get(),net.minecraft.sounds.SoundSource.BLOCKS,1.3F,.8F);
        wasMoving=moving;
        if (Math.abs(next - current) > 1.0E-4F)
        {
            this.entityData.set(DATA_OPEN, next);
        }
    }

    public int getVariant()
    {
        return this.entityData.get(DATA_VARIANT);
    }

    public float getOpenProgress(float partialTick)
    {
        if(declaredStackR52()!=null){if(!level().isClientSide)return actualOpenProgressR52();var data=entityData.get(DATA_STACK_R52);double t=Mth.clamp(level().getGameTime()-data.getLong("At")+(double)partialTick,0,1);return EvaDorsalMechanism.smooth(Mth.lerp((float)t,data.getFloat("PreviousRaw"),data.getFloat("CurrentRaw")));}
        if(!this.level().isClientSide)return this.entityData.get(DATA_OPEN);
        return Mth.lerp(partialTick, this.clientOpenO, this.clientOpen);
    }

    public static void reconcile(ServerLevel level,int variant,Vec3 centre,boolean open)
    {reconcile(level,variant,centre,open,1F);}
    /** Rear leaves occupy separate shallow tracks inside the original three-metre wall. */
    public static void reconcileRear(ServerLevel level,int variant,Vec3 centre,boolean open)
    {reconcile(level,variant,centre,open,.35F);}
    public static void reconcileUNR54(ServerLevel level,Vec3 centre,boolean open,float missingProgress)
    {if(missingProgress!=0&&missingProgress!=1)throw new IllegalArgumentException("Completed original UN endpoint required");reconcile(level,3,centre,open,1F,missingProgress);}
    private static void reconcile(ServerLevel level,int variant,Vec3 centre,boolean open,float depthScale)
    {reconcile(level,variant,centre,open,depthScale,open?1F:0F);}
    private static void reconcile(ServerLevel level,int variant,Vec3 centre,boolean open,float depthScale,float missingProgress)
    {
        if(variant>=0&&variant<3&&com.projectseele.world.NervRouteRuntimeR52.claimed(level))
        {com.projectseele.world.NervRouteRuntimeR52.hangarDoor(level,variant,open);return;}
        AABB search = new AABB(centre, centre).inflate(3.0D);
        List<NervHangarDoorEntity> matches = level.getEntitiesOfClass(
                NervHangarDoorEntity.class, search,
                entity -> entity.getVariant() == variant);
        matches.sort(Comparator.comparingInt(Entity::getId));
        NervHangarDoorEntity door;
        if (matches.isEmpty())
        {
            door = ModEntities.NERV_HANGAR_DOOR.get().create(level);
            if (door == null)
            {
                return;
            }
            door.entityData.set(DATA_VARIANT, variant);
            door.entityData.set(DATA_OPEN,missingProgress);
            door.setPos(centre.x, centre.y, centre.z);
            level.addFreshEntity(door);
        }
        else
        {
            door = matches.get(0);
            if (door.position().distanceToSqr(centre) > 1.0E-8D)
            {
                door.setPos(centre.x, centre.y, centre.z);
            }
            for (int index = 1; index < matches.size(); index++)
            {
                matches.get(index).discard();
            }
        }
        door.entityData.set(DATA_DEPTH_SCALE,depthScale);
        float target = open ? 1.0F : 0.0F;
        door.entityData.set(DATA_HEIGHT, variant < 3 && com.projectseele.world.FacilityLayoutR29.active(level.getServer())
                ? (float)Math.max(65,-370-centre.y) : 65.0F);
        door.entityData.set(DATA_WIDTH,variant==3?(float)com.projectseele.world.UNHangarDimensionsR31.width(level):33.0F);
        if (Math.abs(door.entityData.get(DATA_TARGET) - target) > 1.0E-4F)
        {
            door.entityData.set(DATA_TARGET, target);
        }
    }

    public float proposedDeclaredProgressR52(boolean open)
    {return declaredStackR52()==null?Mth.approach(this.entityData.get(DATA_OPEN),open?1:0,.075F):EvaDorsalMechanism.smooth(proposedRawR52(open));}
    // Opening uses two authored clock samples per tick; closing retains its original cadence.
    private float proposedRawR52(boolean open){if(invalidStackR52)throw new IllegalStateException("Saved side-stack held");var spec=declaredStackR52();float goal=open?1:0,current=entityData.get(DATA_OPEN);boolean changed=clockGoalR52!=goal;float start=changed?current:clockStartR52;int duration=changed?Math.max(1,(int)Math.ceil(Math.abs(goal-current)*(open?spec.openTicks():spec.closeTicks()))):clockDurationR52;int step=changed?(open?2:1):Math.min(duration,clockStepR52+(open?2:1));return step>=duration?goal:start+(goal-start)*step/duration;}
    public void advanceDeclaredR52(boolean open)
    {if(!(level() instanceof ServerLevel level)||!com.projectseele.world.NervRouteRuntimeR52.claimed(level))throw new IllegalStateException("Explicit claimed controller required");declaredClockR52=true;if(declaredAcceptedAtR52==level.getGameTime())return;var spec=declaredStackR52();float current=entityData.get(DATA_OPEN),goal=open?1:0,next=spec==null?proposedDeclaredProgressR52(open):proposedRawR52(open);if(spec!=null){if(clockGoalR52!=goal){clockStartR52=current;clockGoalR52=goal;clockDurationR52=Math.max(1,(int)Math.ceil(Math.abs(goal-current)*(open?spec.openTicks():spec.closeTicks())));clockStepR52=0;}clockStepR52=Math.min(clockDurationR52,clockStepR52+(open?2:1));var data=entityData.get(DATA_STACK_R52).copy();data.putFloat("PreviousRaw",current);data.putFloat("CurrentRaw",next);data.putLong("At",level.getGameTime());entityData.set(DATA_STACK_R52,data);}declaredAcceptedAtR52=level.getGameTime();entityData.set(DATA_OPEN,next);entityData.set(DATA_TARGET,goal);if(spec!=null)setBoundingBox(com.projectseele.world.NervRigidMeshSweepR52.transformed(declaredGeometryR52().bounds(actualOpenProgressR52()),actualFrameR52()));}
    /** Only an installed Root directory configures its existing original UUID. */
    public void applyDeclaredR52(int variant,float width,float height,boolean open)
    {
        if(level().isClientSide)return;
        if(variant<0||variant>2||!Float.isFinite(width)||!Float.isFinite(height)||width<=0||height<=0)
            throw new IllegalArgumentException("Explicit Root door dimensions required");
        declaredClockR52=true;entityData.set(DATA_VARIANT,variant);entityData.set(DATA_WIDTH,width);entityData.set(DATA_HEIGHT,height);entityData.set(DATA_TARGET,open?1F:0F);
    }
    public void applyDeclaredR52(int variant,NervHangarGateGeometryR52.Spec spec,boolean open)
    {
        var previous=declaredStackR52();
        boolean fixedFloor=com.projectseele.world.NervR50CarrierModeR53.enabled()&&previous!=null&&spec!=null
            &&spec.bottomSeal()==null&&previous.width()==spec.width()&&previous.height()==spec.height()
            &&previous.openTicks()==spec.openTicks()&&previous.closeTicks()==spec.closeTicks()
            &&previous.depthDirection()==spec.depthDirection()
            &&(previous.leafLowerExtensionM()==spec.leafLowerExtensionM()
                ||previous.leafLowerExtensionM()==0&&spec.leafLowerExtensionM()==5
                    &&entityData.get(DATA_OPEN)==0&&entityData.get(DATA_TARGET)==0);
        if(invalidStackR52||spec==null||previous!=null&&!previous.equals(spec)&&!fixedFloor)
            throw new IllegalStateException("Actual side-stack specification required");
        applyDeclaredR52(variant,spec.width(),spec.height(),open);
        var data=entityData.get(DATA_STACK_R52).copy();writeSpecR52(data,spec);
        if(!data.contains("CurrentRaw")){data.putFloat("CurrentRaw",entityData.get(DATA_OPEN));data.putFloat("PreviousRaw",entityData.get(DATA_OPEN));data.putLong("At",level().getGameTime());}
        entityData.set(DATA_STACK_R52,data);
        setBoundingBox(com.projectseele.world.NervRigidMeshSweepR52.transformed(declaredGeometryR52().bounds(actualOpenProgressR52()),actualFrameR52()));
    }
    private static void writeSpecR52(CompoundTag data,NervHangarGateGeometryR52.Spec spec)
    {
        data.putFloat("Width",spec.width());data.putFloat("Height",spec.height());data.putInt("OpenTicks",spec.openTicks());data.putInt("CloseTicks",spec.closeTicks());data.putInt("DepthDirection",spec.depthDirection());
        data.putDouble("LeafLowerExtensionM",spec.leafLowerExtensionM());
        if(spec.bottomSeal()==null){data.remove("FloorSeal");return;}
        var seal=new CompoundTag();seal.putInt("Version",spec.bottomSeal().version());if(spec.bottomSeal().version()==2)seal.putInt("RetainedBoxCount",spec.bottomSeal().retainedBoxCount());seal.putDouble("DropM",spec.bottomSeal().dropM());seal.putDouble("RetreatLocalZ",spec.bottomSeal().retreatLocalZ());var rows=new ListTag();
        for(var b:spec.bottomSeal().closedBoxes()){var row=new ListTag();for(double v:new double[]{b.minX(),b.minY(),b.minZ(),b.maxX(),b.maxY(),b.maxZ()})row.add(DoubleTag.valueOf(v));rows.add(row);}seal.put("ClosedBoxes",rows);data.put("FloorSeal",seal);
    }
    private static NervHangarGateGeometryR52.BottomSeal readFloorSealR52(CompoundTag data)
    {
        if(!data.contains("FloorSeal"))return null;
        if(!data.contains("FloorSeal",Tag.TAG_COMPOUND))throw new IllegalStateException("Unknown actual floor-seal tag");var t=data.getCompound("FloorSeal");
        if((t.getInt("Version")!=1&&t.getInt("Version")!=2)||t.getInt("Version")==2&&!t.contains("RetainedBoxCount",Tag.TAG_INT)||!t.contains("DropM",Tag.TAG_ANY_NUMERIC)||!t.contains("RetreatLocalZ",Tag.TAG_ANY_NUMERIC)||!t.contains("ClosedBoxes",Tag.TAG_LIST))throw new IllegalStateException("Unknown actual floor-seal version/fields");
        var rows=t.getList("ClosedBoxes",Tag.TAG_LIST);if(rows.isEmpty()||rows.size()>512)throw new IllegalStateException("Missing or unbounded actual floor-seal boxes");var boxes=new ArrayList<NervHangarGateGeometryR52.SealBox>();
        for(var value:rows){var r=(ListTag)value;if(r.size()!=6||r.getElementType()!=Tag.TAG_DOUBLE)throw new IllegalStateException("Unknown actual floor-seal bounds");boxes.add(new NervHangarGateGeometryR52.SealBox(r.getDouble(0),r.getDouble(1),r.getDouble(2),r.getDouble(3),r.getDouble(4),r.getDouble(5)));}
        return new NervHangarGateGeometryR52.BottomSeal(boxes,t.getDouble("DropM"),t.getDouble("RetreatLocalZ"),t.getInt("Version"),t.getInt("Version")==2?t.getInt("RetainedBoxCount"):0);
    }
    private static NervHangarGateGeometryR52.Spec readSpec(CompoundTag t){return t.isEmpty()||t.getBoolean("GeometryMissing")?null:new NervHangarGateGeometryR52.Spec(t.getFloat("Width"),t.getFloat("Height"),t.getInt("OpenTicks"),t.getInt("CloseTicks"),t.contains("DepthDirection")?t.getInt("DepthDirection"):1,readFloorSealR52(t),t.getDouble("LeafLowerExtensionM"));}
    public boolean declaredGeometryMissingR52(){return entityData.get(DATA_STACK_R52).getBoolean("GeometryMissing");}
    private void holdSavedVisualR52(){var held=savedStackR52.getCompound("Spec").copy();held.putBoolean("Held",true);try{var spec=readSpec(held);float raw=savedStackR52.getFloat("Raw");if(spec==null||!Float.isFinite(raw)||raw<0||raw>1)throw new IllegalStateException("No held stack source sample");held.putFloat("PreviousRaw",raw);held.putFloat("CurrentRaw",raw);held.putLong("At",level().getGameTime());entityData.set(DATA_OPEN,raw);entityData.set(DATA_WIDTH,spec.width());entityData.set(DATA_HEIGHT,spec.height());}catch(RuntimeException missing){held=new CompoundTag();held.putBoolean("Held",true);held.putBoolean("GeometryMissing",true);}entityData.set(DATA_STACK_R52,held);}
    public NervHangarGateGeometryR52.Spec declaredStackR52(){return readSpec(entityData.get(DATA_STACK_R52));}
    public boolean matchesDeclaredR52(NervHangarGateGeometryR52.Spec spec){return !invalidStackR52&&spec!=null&&spec.equals(declaredStackR52())&&visualWidth()==spec.width()&&visualHeight()==spec.height();}
    public float actualOpenProgressR52(){return EvaDorsalMechanism.smooth(entityData.get(DATA_OPEN));}
    /** Administrative reset restores the same declared gate and its clock. */
    public void restoreDeclaredClosedR53()
    {
        if(!(level() instanceof ServerLevel)||declaredStackR52()==null)
            throw new IllegalStateException("Original declared hangar gate is not loaded");
        invalidStackR52=false;
        clockStartR52=clockGoalR52=0;
        clockStepR52=clockDurationR52=0;
        declaredAcceptedAtR52=level().getGameTime();
        entityData.set(DATA_OPEN,0F);
        entityData.set(DATA_TARGET,0F);
        var sample=entityData.get(DATA_STACK_R52).copy();
        sample.putFloat("PreviousRaw",0);
        sample.putFloat("CurrentRaw",0);
        sample.putLong("At",level().getGameTime());
        entityData.set(DATA_STACK_R52,sample);
        setBoundingBox(com.projectseele.world.NervRigidMeshSweepR52.transformed(declaredGeometryR52().bounds(0),actualFrameR52()));
    }
    public RigidTransform actualFrameR52(){return RigidTransform.of(position(),new Quaternionf().rotationY((float)Math.toRadians(-getYRot())));}
    public NervHangarGateGeometryR52 declaredGeometryR52(){try{return NervHangarGateGeometryR52.loadClasspath(declaredStackR52());}catch(java.io.IOException missing){throw new IllegalStateException("Side-stack source absent",missing);}}
    private static boolean actualWetSealFaceR52(Vec3 p,Vec3 n,List<AABB> boxes)
    {
        int axis=Math.abs(n.x)>.999999?0:Math.abs(n.y)>.999999?1:Math.abs(n.z)>.999999?2:-1;if(axis<0)return false;
        double[] point={p.x,p.y,p.z},normal={n.x,n.y,n.z};int first=(axis+1)%3,second=(axis+2)%3;
        for(double a:new double[]{-.10,0,.10})for(double b:new double[]{-.10,0,.10})
        {var sample=point.clone();sample[first]+=a;sample[second]+=b;boolean bearing=false;
            for(var w:boxes){double[] bounds={w.minX,w.minY,w.minZ,w.maxX,w.maxY,w.maxZ};double face=normal[axis]<0?bounds[axis]:bounds[axis+3];if(Math.abs(sample[axis]-face)<=.0002&&sample[first]>=bounds[first]-.0002&&sample[first]<=bounds[first+3]+.0002&&sample[second]>=bounds[second]-.0002&&sample[second]<=bounds[second+3]+.0002)bearing=true;}
            if(!bearing)return false;}
        return true;
    }
    private boolean actualWetSealWallBearingsR52(ServerLevel level,NervHangarGateGeometryR52 geo,RigidTransform frame,Set<BlockPos> supports)
    {
        if(geo.bottomSealBearingPointsR52().isEmpty())return true;var boxes=new ArrayList<AABB>();
        for(var at:supports){if(!level.hasChunkAt(at))return false;for(var shape:level.getBlockState(at).getCollisionShape(level,at,CollisionContext.of(this)).toAabbs())boxes.add(shape.move(at));}
        for(var local:geo.bottomSealBearingPointsR52())
        {
            var point=frame.transformPoint(local);
            // A finite bearing patch can straddle a block edge. Its centre's
            // declared backing alone does not contain the neighbouring face.
            var patch=new ArrayList<AABB>(boxes);
            for(var at:BlockPos.betweenClosed(BlockPos.containing(point.add(-.101,-.101,-.101)),BlockPos.containing(point.add(.101,.101,.101))))
            {
                var chunk=level.getChunkSource().getChunkNow(at.getX()>>4,at.getZ()>>4);
                if(chunk==null)return false;
                for(var shape:chunk.getBlockState(at).getCollisionShape(level,at,CollisionContext.of(this)).toAabbs())patch.add(shape.move(at));
            }
            if(!actualWetSealFaceR52(point,frame.transformVector(new Vec3(-Math.signum(local.x),0,0)),patch))return false;
        }
        return true;
    }
    public boolean declaredSupportsBearR52(ServerLevel level,Set<BlockPos> supports)
    {
        if(invalidStackR52||declaredStackR52()==null)return false;var geo=declaredGeometryR52();var frame=actualFrameR52();
        for(var local:geo.bearingPoints()){var p=frame.transformPoint(local);boolean bearing=false;for(var at:supports){if(!level.hasChunkAt(at))return false;for(var box:level.getBlockState(at).getCollisionShape(level,at,CollisionContext.of(this)).toAabbs()){var actual=box.move(at);if(p.x>actual.minX&&p.x<actual.maxX&&p.z>actual.minZ&&p.z<actual.maxZ&&Math.abs(p.y-actual.maxY)<=.002)bearing=true;}}if(!bearing)return false;}
        return actualWetSealWallBearingsR52(level,geo,frame,supports);
    }
    public boolean clearDeclaredSweepR52(ServerLevel level,float from,float to,Set<UUID> own,Set<BlockPos> moving,Set<BlockPos> supports)
    {
        if(invalidStackR52||declaredStackR52()==null||actualOpenProgressR52()!=from)return false;var geo=declaredGeometryR52();var frame=actualFrameR52();var detached=com.projectseele.world.NervFlightProofR52.detachedCarrierObstacles(level);if(detached==null)return false;for(var mesh:detached)if(geo.intersects(frame,from,to,mesh.mesh(),mesh.frame(),mesh.endFrame()))return false;if(to<from&&!com.projectseele.world.NervGateClosureR52.clearActualActors(level,this,moving))return false;
        if(!declaredSupportsBearR52(level,supports))return false;
        var seen=new HashSet<BlockPos>();
        for(var box:geo.envelopes(frame,from,to))
        {
            if(!com.projectseele.world.EntryPlugEjectionR48.loaded(level,box))return false;
            for(var at:BlockPos.betweenClosed(BlockPos.containing(box.minX,box.minY,box.minZ),BlockPos.containing(box.maxX,box.maxY,box.maxZ)))
            {
                var key=at.immutable();if(!seen.add(key)||moving.contains(key))continue;
                var state=level.getBlockState(key);if(state.isAir())continue;
                for(var shape:state.getCollisionShape(level,key,CollisionContext.of(this)).toAabbs())if(geo.intersects(frame,from,to,shape.move(key)))return false;
            }
        }
        // The union includes every former per-leaf search area. Snapshot live
        // actors once; exact full-motion geometry still decides obstruction.
        for(var actor:level.getEntities(this,geo.sweptBounds(frame,from,to).inflate(200),e->e.isAlive()&&!e.isSpectator()&&(e instanceof net.minecraft.world.entity.LivingEntity||e.canBeCollidedWith()||e instanceof UNTransportEntity||e instanceof EntryPlugCarrierEntity||e instanceof NervSiloDoorEntity||e instanceof NervHangarDoorEntity||e instanceof NervCarrierPlatformEntity)))
        {
            var meshes=com.projectseele.world.NervFlightProofR52.actualObstacleMeshes(actor);
            if(meshes==null)
            {
                var bounds=actor instanceof UNTransportEntity aircraft?aircraft.getBoundingBoxForCulling():actor.getBoundingBox();
                if(geo.intersects(frame,from,to,bounds))return false;
            }
            else if(meshes.isEmpty())
            {
                if(geo.intersects(frame,from,to,actor.getBoundingBox()))return false;
            }
            else for(var mesh:meshes)if(geo.intersects(frame,from,to,mesh.mesh(),mesh.frame(),mesh.endFrame()))return false;
        }
        return com.projectseele.world.CarrierTransferRailsR53.clearGateSweep(level,this,from,to,own,moving,supports);
    }

    @Override public boolean isPickable() { return false; }
    @Override public boolean isPushable() { return false; }
    @Override public boolean hurt(DamageSource source, float amount) { return false; }
    @Override public PushReaction getPistonPushReaction() { return PushReaction.IGNORE; }
}
