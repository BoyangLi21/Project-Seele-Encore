package com.projectseele.entity;

import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.syncher.EntityDataAccessor;
import net.minecraft.network.syncher.EntityDataSerializers;
import net.minecraft.network.syncher.SynchedEntityData;
import net.minecraft.core.Direction;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.player.Player;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.material.PushReaction;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import org.joml.Quaternionf;
import org.joml.Vector3f;

import com.projectseele.world.S20PhysicalElevatorDirector;

/**
 * Ephemeral visual mag-lev deck. It replaces thousands of moving block
 * updates while the EVA itself remains the authoritative physical vehicle.
 */
public final class NervCarrierPlatformEntity extends Entity
{
    private static final EntityDataAccessor<Float> DATA_REPAIR_R33=SynchedEntityData.defineId(NervCarrierPlatformEntity.class,EntityDataSerializers.FLOAT);
    public void setRepairProgressR33(float progress){entityData.set(DATA_REPAIR_R33,progress);}
    public float repairProgressR33(){return entityData.get(DATA_REPAIR_R33);}
    private static final EntityDataAccessor<Integer> DATA_VARIANT =
            SynchedEntityData.defineId(NervCarrierPlatformEntity.class,
                    EntityDataSerializers.INT);
    private static final EntityDataAccessor<Boolean> DATA_PERSONNEL_LIFT =
            SynchedEntityData.defineId(NervCarrierPlatformEntity.class,
                    EntityDataSerializers.BOOLEAN);
    private static final EntityDataAccessor<Integer> DATA_LIFT_ACCENT =
            SynchedEntityData.defineId(NervCarrierPlatformEntity.class,
                    EntityDataSerializers.INT);
    private static final EntityDataAccessor<Boolean> DATA_LIFT_DOOR_OPEN =
            SynchedEntityData.defineId(NervCarrierPlatformEntity.class,
                    EntityDataSerializers.BOOLEAN);
    private static final EntityDataAccessor<Boolean> DATA_PERSISTENT_LIFT =
            SynchedEntityData.defineId(NervCarrierPlatformEntity.class,
                    EntityDataSerializers.BOOLEAN);
    private static final EntityDataAccessor<String> DATA_LIFT_ID =
            SynchedEntityData.defineId(NervCarrierPlatformEntity.class,
                    EntityDataSerializers.STRING);
    private static final EntityDataAccessor<Integer> DATA_LIFT_EXIT =
            SynchedEntityData.defineId(NervCarrierPlatformEntity.class,
                    EntityDataSerializers.INT);
    private static final EntityDataAccessor<Integer> DATA_RESTRAINT_PROGRESS =
            SynchedEntityData.defineId(NervCarrierPlatformEntity.class,
                    EntityDataSerializers.INT);
    private static final EntityDataAccessor<Boolean> DATA_RESTRAINT_GANTRY =
            SynchedEntityData.defineId(NervCarrierPlatformEntity.class,
                    EntityDataSerializers.BOOLEAN);
    private static final EntityDataAccessor<Boolean> DATA_PLUG_CRANE =
            SynchedEntityData.defineId(NervCarrierPlatformEntity.class,
                    EntityDataSerializers.BOOLEAN);
    private static final EntityDataAccessor<Integer> DATA_CRANE_BOTTOM_OFFSET =
            SynchedEntityData.defineId(NervCarrierPlatformEntity.class,
                    EntityDataSerializers.INT);
    private static final EntityDataAccessor<Integer> DATA_LCL_LEVEL_MILLI =
            SynchedEntityData.defineId(NervCarrierPlatformEntity.class,
                    EntityDataSerializers.INT);
    private static final EntityDataAccessor<Integer> DATA_CRANE_PLUG = SynchedEntityData.defineId(NervCarrierPlatformEntity.class,EntityDataSerializers.INT);
    private static final EntityDataAccessor<Boolean> DATA_CRANE_REFERENCE = SynchedEntityData.defineId(NervCarrierPlatformEntity.class,EntityDataSerializers.BOOLEAN);
    private static final EntityDataAccessor<Vector3f> DATA_CRANE_ANCHOR = SynchedEntityData.defineId(NervCarrierPlatformEntity.class,EntityDataSerializers.VECTOR3);
    private static final EntityDataAccessor<Quaternionf> DATA_CRANE_ROTATION = SynchedEntityData.defineId(NervCarrierPlatformEntity.class,EntityDataSerializers.QUATERNION);
    public void linkCranePlug(EntryPlugCarrierEntity plug)
    {
        boolean coupled=plug!=null&&!plug.isLockedToEva();
        if(plug!=null&&(coupled||!hasCraneReference()))
        {
            var pose=plug.getCanonicalTransform();Vec3 anchor=pose.transformPoint(com.projectseele.world.EntryPlugKinematics.CRANE_ATTACHMENT_P).subtract(position());
            if(coupled||(anchor.horizontalDistance()<12&&anchor.y<2&&anchor.y>-90))
            {
                entityData.set(DATA_CRANE_ANCHOR,new Vector3f((float)anchor.x,(float)anchor.y,(float)anchor.z));entityData.set(DATA_CRANE_ROTATION,pose.rotation());entityData.set(DATA_CRANE_REFERENCE,true);
            }
        }
        this.entityData.set(DATA_CRANE_PLUG,coupled?plug.getId():-1);
        if(hasDeclaredMachineFrameR52()){if(coupled)getPersistentData().putUUID("R52CranePlug",plug.getUUID());else getPersistentData().remove("R52CranePlug");}
    }
    public EntryPlugCarrierEntity getCranePlug(){var e=level().getEntity(entityData.get(DATA_CRANE_PLUG));if(e==null&&level() instanceof net.minecraft.server.level.ServerLevel server&&getPersistentData().hasUUID("R52CranePlug"))e=server.getEntity(getPersistentData().getUUID("R52CranePlug"));return e instanceof EntryPlugCarrierEntity p?p:null;}
    public boolean hasCraneReference(){return entityData.get(DATA_CRANE_REFERENCE);}
    public Vec3 getCraneReferenceAnchor(){var p=entityData.get(DATA_CRANE_ANCHOR);return new Vec3(p.x,p.y,p.z);}
    public Quaternionf getCraneReferenceRotation(){return new Quaternionf(entityData.get(DATA_CRANE_ROTATION));}
    /** Ground owner records the observed capsule pose before an uncoupled
     * approach. Publishing this reference performs no motion or attachment. */
    public void setCraneReferenceR52(com.projectseele.world.RigidTransform pose)
    {if(level().isClientSide||!hasDeclaredMachineFrameR52()||!isPlugCrane())throw new IllegalStateException("Actual declared ground crane required");var anchor=pose.transformPoint(com.projectseele.world.EntryPlugKinematics.CRANE_ATTACHMENT_P).subtract(position());entityData.set(DATA_CRANE_ANCHOR,new Vector3f((float)anchor.x,(float)anchor.y,(float)anchor.z));entityData.set(DATA_CRANE_ROTATION,pose.rotation());entityData.set(DATA_CRANE_REFERENCE,true);}
    private static final EntityDataAccessor<Boolean> DATA_DECLARED_MACHINE_R52=SynchedEntityData.defineId(NervCarrierPlatformEntity.class,EntityDataSerializers.BOOLEAN);
    private static final EntityDataAccessor<Quaternionf> DATA_DECLARED_MACHINE_Q_R52=SynchedEntityData.defineId(NervCarrierPlatformEntity.class,EntityDataSerializers.QUATERNION);
    private static final EntityDataAccessor<String> DATA_DECLARED_COLLISION_SHA_R52=SynchedEntityData.defineId(NervCarrierPlatformEntity.class,EntityDataSerializers.STRING);
    private static final EntityDataAccessor<CompoundTag> DATA_LOWER_FRAME_R52=SynchedEntityData.defineId(NervCarrierPlatformEntity.class,EntityDataSerializers.COMPOUND_TAG);
    public CompoundTag footGuideStationStateR52(){return entityData.get(DATA_LOWER_FRAME_R52).getCompound("FootGuideStation").copy();}
    public void acceptFootGuideStationStateR52(com.projectseele.world.NervFootGuideStationR52.DeclaredState proof){if(proof==null||!proof.current(this))throw new IllegalStateException("Current checked fixed station state required");var tag=entityData.get(DATA_LOWER_FRAME_R52).copy();tag.put("FootGuideStation",proof.next());entityData.set(DATA_LOWER_FRAME_R52,tag);}
    public CompoundTag originalCarrierStateR52(){return entityData.get(DATA_LOWER_FRAME_R52).getCompound("OriginalCarrier").copy();}
    public void acceptOriginalCarrierStateR52(com.projectseele.world.NervOriginalCarrierR52.DeclaredState proof){if(proof==null||!proof.current(this))throw new IllegalStateException("Current checked original carrier state required");var tag=entityData.get(DATA_LOWER_FRAME_R52).copy();tag.put("OriginalCarrier",proof.next());entityData.set(DATA_LOWER_FRAME_R52,tag);}
    public boolean lowerFrameDeclaredR52(){return entityData.get(DATA_LOWER_FRAME_R52).getString("Source").equals(com.projectseele.world.NervLowerFrameR52.SOURCE_SHA);}
    public float lowerFrameProgressR52(float partial){var t=entityData.get(DATA_LOWER_FRAME_R52);if(!lowerFrameDeclaredR52())return Float.NaN;float p=t.getInt("Progress")/1000F;if(!level().isClientSide)return p;return net.minecraft.util.Mth.lerp((float)net.minecraft.util.Mth.clamp(level().getGameTime()-t.getLong("At")+(double)partial,0,1),t.getInt("Previous")/1000F,p);}
    public void declareLowerFrameR52(){if(level().isClientSide||!isRestraintGantry()||!hasDeclaredMachineFrameR52()||!entityData.get(DATA_LOWER_FRAME_R52).isEmpty())throw new IllegalStateException("Only a new actual original-bay gantry admits the lower-frame source");var t=new CompoundTag();t.putString("Source",com.projectseele.world.NervLowerFrameR52.SOURCE_SHA);t.putInt("Progress",0);t.putInt("Previous",0);t.putLong("At",level().getGameTime());entityData.set(DATA_LOWER_FRAME_R52,t);}
    public void setLowerFrameProgressR52(float progress){if(level().isClientSide||!lowerFrameDeclaredR52()||!Float.isFinite(progress)||progress<0||progress>1)throw new IllegalStateException("Actual server lower-frame source required");var t=entityData.get(DATA_LOWER_FRAME_R52).copy();t.putInt("Previous",t.getInt("Progress"));t.putInt("Progress",Math.round(progress*1000));t.putLong("At",level().getGameTime());entityData.set(DATA_LOWER_FRAME_R52,t);}
    private static CompoundTag serviceDriveFrameR52(com.projectseele.world.RigidTransform f){var t=new CompoundTag();t.putDouble("X",f.translation().x);t.putDouble("Y",f.translation().y);t.putDouble("Z",f.translation().z);t.putFloat("Qx",f.qx());t.putFloat("Qy",f.qy());t.putFloat("Qz",f.qz());t.putFloat("Qw",f.qw());return t;}
    private static com.projectseele.world.RigidTransform serviceDriveFrameR52(CompoundTag t){return new com.projectseele.world.RigidTransform(new Vec3(t.getDouble("X"),t.getDouble("Y"),t.getDouble("Z")),t.getFloat("Qx"),t.getFloat("Qy"),t.getFloat("Qz"),t.getFloat("Qw"));}
    public com.projectseele.world.NervServiceFootDriveR52.Spec declaredServiceFootDriveR52(){var t=entityData.get(DATA_LOWER_FRAME_R52).getCompound("FootDrive");if(!lowerFrameDeclaredR52()||!t.getString("RigSource").equals(com.projectseele.world.NervFootGuideRigR52.SOURCE_SHA))return null;return new com.projectseele.world.NervServiceFootDriveR52.Spec(getUnitVariant(),serviceDriveFrameR52(t.getCompound("Bay")),serviceDriveFrameR52(t.getCompound("Hatch")),t.getDouble("Tier"),t.getDouble("FoundationTop"));}
    public void declareServiceFootDriveR52(com.projectseele.world.NervServiceFootDriveR52.Spec s){if(level().isClientSide||!lowerFrameDeclaredR52()||s.variant()!=getUnitVariant())throw new IllegalStateException("Actual lower-frame controller required for service foot drive");var old=declaredServiceFootDriveR52();if(old!=null){if(!old.equals(s))throw new IllegalStateException("Existing physical foot drive cannot be relocated or reset");return;}var all=entityData.get(DATA_LOWER_FRAME_R52).copy();if(all.contains("FootDrive"))throw new IllegalStateException("Existing foot-drive source requires explicit commissioning repair");var t=new CompoundTag();t.putString("RigSource",com.projectseele.world.NervFootGuideRigR52.SOURCE_SHA);t.put("Bay",serviceDriveFrameR52(s.bay()));t.put("Hatch",serviceDriveFrameR52(s.hatch()));t.putDouble("Tier",s.firstTier());t.putDouble("FoundationTop",s.foundationTop());t.putInt("Progress",0);t.putInt("Previous",0);t.putLong("At",level().getGameTime());t.putFloat("LeadRise",0);t.putFloat("PreviousLeadRise",0);t.putLong("LeadAt",level().getGameTime());all.put("FootDrive",t);entityData.set(DATA_LOWER_FRAME_R52,all);}
    public float serviceGuideBridgeR52(float partial){if(declaredServiceFootDriveR52()==null)return Float.NaN;var t=entityData.get(DATA_LOWER_FRAME_R52).getCompound("FootDrive");float p=t.getInt("Progress")/1000F;return level().isClientSide?net.minecraft.util.Mth.lerp((float)net.minecraft.util.Mth.clamp(level().getGameTime()-t.getLong("At")+(double)partial,0,1),t.getInt("Previous")/1000F,p):p;}
    /** Fixed bay running heads retain their own real lift sample after the
     * original carrier leaves. A distant carrier never drives this hardware. */
    public CompoundTag serviceLeadStateR52(){return entityData.get(DATA_LOWER_FRAME_R52).getCompound("FootDrive").copy();}
    public void acceptServiceLeadStateR52(com.projectseele.world.NervOriginalCarrierR52.DeclaredLeadState proof){if(proof==null||!proof.current(this))throw new IllegalStateException("Current coupled original-carrier lead proof required");var all=entityData.get(DATA_LOWER_FRAME_R52).copy();all.put("FootDrive",proof.next());entityData.set(DATA_LOWER_FRAME_R52,all);}
    public long serviceLeadAtR52(){var t=serviceLeadStateR52();return t.contains("LeadAt")?Math.max(t.getLong("LeadAt"),t.getLong("At")):Long.MIN_VALUE;}
    public float serviceLeadRiseR52(float partial){var t=serviceLeadStateR52();if(declaredServiceFootDriveR52()==null||!t.contains("LeadRise")||!t.contains("PreviousLeadRise")||!t.contains("LeadAt"))return Float.NaN;float rise=t.getFloat("LeadRise"),before=t.getFloat("PreviousLeadRise");if(!Float.isFinite(rise+before)||rise<0||rise>1||before<0||before>1)return Float.NaN;return level().isClientSide?net.minecraft.util.Mth.lerp((float)net.minecraft.util.Mth.clamp(level().getGameTime()-t.getLong("LeadAt")+(double)partial,0,1),before,rise):rise;}
    public void setServiceGuideBridgeR52(float p){if(level().isClientSide||declaredServiceFootDriveR52()==null||!Float.isFinite(p)||p<0||p>1)throw new IllegalStateException("Actual bounded service bridge sample required");var all=entityData.get(DATA_LOWER_FRAME_R52).copy();var t=all.getCompound("FootDrive").copy();t.putInt("Previous",t.getInt("Progress"));t.putInt("Progress",Math.round(p*1000));t.putLong("At",level().getGameTime());all.put("FootDrive",t);entityData.set(DATA_LOWER_FRAME_R52,all);}
    public String declaredCollisionSourceR52(){return this.entityData.get(DATA_DECLARED_COLLISION_SHA_R52);}
    public void configureDeclaredCollisionSourceR52(String sha){if(level().isClientSide||!sha.matches("[0-9a-f]{64}"))throw new IllegalStateException("Actual Root collision source required");this.entityData.set(DATA_DECLARED_COLLISION_SHA_R52,sha);}
    public boolean hasDeclaredMachineFrameR52(){return this.entityData.get(DATA_DECLARED_MACHINE_R52);}
    public Quaternionf declaredMachineRotationR52(){return new Quaternionf(this.entityData.get(DATA_DECLARED_MACHINE_Q_R52));}
    /** Explicit controller data after physical frame readback; no position or
     * collision changes are performed by this synchronization. */
    public void configureDeclaredMachineFrameR52(Quaternionf rotation)
    {
        if(!(this.level() instanceof net.minecraft.server.level.ServerLevel level)||!com.projectseele.world.NervRouteRuntimeR52.claimed(level)||!Float.isFinite(rotation.lengthSquared())||Math.abs(rotation.lengthSquared()-1)>.0001F)throw new IllegalStateException("Claimed measured machine quaternion required");
        this.entityData.set(DATA_DECLARED_MACHINE_Q_R52,new Quaternionf(rotation));this.entityData.set(DATA_DECLARED_MACHINE_R52,true);
    }
    private static final int CONTROL_TIMEOUT_TICKS = 40;
    public static final int LIFT_IDLE_OPEN = 0;
    public static final int LIFT_DOOR_CLOSING = 1;
    public static final int LIFT_STARTING = 2;
    public static final int LIFT_MOVING = 3;
    public static final int LIFT_BRAKING = 4;
    public static final int LIFT_LEVELING = 5;
    public static final int LIFT_DOOR_OPENING = 6;
    public static final int LIFT_FAULT = 7;
    public static final int LIFT_RECOVERY_HOLD = 8;
    private static final int DOOR_CLOSE_TICKS = 60;
    private static final int DOOR_OPEN_TICKS = 20;
    private static final int DOOR_SLIDE_TICKS = 20;
    private static final int MAX_LIFT_PASSENGERS = 9;
    private static final int CONTROL_DEBOUNCE_TICKS = 6;
    private static final double LIFT_MAX_SPEED = 1.6D;
    private static final double LIFT_ACCELERATION = 0.04D;
    private static final double LIFT_LEVELING_SPEED = 0.15D;
    private static final double LIFT_ARRIVAL_TOLERANCE = 0.03D;
    /** Even the 523-block surface shaft completes well inside this window. */
    private static final int LIFT_TRAVEL_WATCHDOG_TICKS = 1200;

    private int ticksWithoutControl;
    private int persistentLiftState = LIFT_IDLE_OPEN;
    private int persistentLiftPhaseTicks;
    private double persistentLiftTargetY;
    private double persistentLiftVelocity;
    private int persistentLiftStateRevision;
    private long persistentLiftLastMotionEpoch;
    private long persistentLiftPendingMotionEpoch;
    private long persistentLiftActiveMotionEpoch;
    private double persistentLiftLowerY = Double.NaN;
    private double persistentLiftUpperY = Double.NaN;
    private long lastPersistentLiftControlTick = Long.MIN_VALUE;
    private float clientCranePreviousOffset = -2.0F;
    private float clientCraneCurrentOffset = -2.0F;
    private boolean clientCraneOffsetInitialized;
    private float clientLclPreviousLevel;
    private float clientLclCurrentLevel;
    private boolean clientLclLevelInitialized;
    private float clientRestraintPrevious,clientRestraintCurrent;
    private boolean clientRestraintInitialized;

    public NervCarrierPlatformEntity(
            EntityType<? extends NervCarrierPlatformEntity> type, Level level)
    {
        super(type, level);
        this.noPhysics = true;
        this.setNoGravity(true);
    }

    @Override
    protected void defineSynchedData()
    {
        this.entityData.define(DATA_DECLARED_COLLISION_SHA_R52,"");this.entityData.define(DATA_DECLARED_MACHINE_R52,false);this.entityData.define(DATA_DECLARED_MACHINE_Q_R52,new Quaternionf());this.entityData.define(DATA_LOWER_FRAME_R52,new CompoundTag());
        this.entityData.define(DATA_VARIANT, EvaUnit01Entity.UNIT_01);
        this.entityData.define(DATA_REPAIR_R33,-1F);
        this.entityData.define(DATA_PERSONNEL_LIFT, false);
        this.entityData.define(DATA_LIFT_ACCENT, 0);
        this.entityData.define(DATA_LIFT_DOOR_OPEN, false);
        this.entityData.define(DATA_PERSISTENT_LIFT, false);
        this.entityData.define(DATA_LIFT_ID, "");
        this.entityData.define(DATA_LIFT_EXIT,
                Direction.NORTH.get2DDataValue());
        this.entityData.define(DATA_RESTRAINT_PROGRESS, 0);
        this.entityData.define(DATA_RESTRAINT_GANTRY, false);
        this.entityData.define(DATA_PLUG_CRANE, false);
        this.entityData.define(DATA_CRANE_PLUG, -1);
        this.entityData.define(DATA_CRANE_REFERENCE,false);
        this.entityData.define(DATA_CRANE_ANCHOR,new Vector3f());
        this.entityData.define(DATA_CRANE_ROTATION,new Quaternionf());
        this.entityData.define(DATA_CRANE_BOTTOM_OFFSET, -2000);
        this.entityData.define(DATA_LCL_LEVEL_MILLI, 0);
    }

    public int getUnitVariant()
    {
        return this.entityData.get(DATA_VARIANT);
    }

    public void assignVariant(int variant)
    {
        int safe = Math.max(EvaUnit01Entity.UNIT_00,
                Math.min(EvaUnit01Entity.UNIT_02, variant));
        if (this.entityData.get(DATA_VARIANT) != safe)
        {
            this.entityData.set(DATA_VARIANT, safe);
        }
    }

    /**
     * Visual extension of the wet-cage restraint towers, encoded as 0..1000
     * so every client renders the same hydraulic travel without trusting its
     * frame rate. The logistics lock remains the physical authority.
     */
    public void setRestraintProgress(float progress)
    {
        int quantized = Math.round(Math.max(0.0F,
                Math.min(1.0F, progress)) * 1000.0F);
        if (this.entityData.get(DATA_RESTRAINT_PROGRESS) != quantized)
        {
            this.entityData.set(DATA_RESTRAINT_PROGRESS, quantized);
        }
    }

    public float getRestraintProgress()
    {
        return this.entityData.get(DATA_RESTRAINT_PROGRESS) / 1000.0F;
    }

    public float getRestraintProgress(float partial)
    {
        return clientRestraintInitialized?net.minecraft.util.Mth.lerp(partial,clientRestraintPrevious,clientRestraintCurrent):getRestraintProgress();
    }

    /**
     * Marks this visual as the fixed wet-cage restraint gantry rather than the
     * moving transport deck.  Progress zero therefore means "jaws fully
     * retracted", not "turn into a carrier and leave the hangar".
     */
    public void configureRestraintGantry()
    {
        this.noCulling = true;
        if (this.entityData.get(DATA_PLUG_CRANE))
        {
            this.entityData.set(DATA_PLUG_CRANE, false);
        }
        if (!this.entityData.get(DATA_RESTRAINT_GANTRY))
        {
            this.entityData.set(DATA_RESTRAINT_GANTRY, true);
        }
        if (this.entityData.get(DATA_PERSONNEL_LIFT))
        {
            this.entityData.set(DATA_PERSONNEL_LIFT, false);
        }
        if (this.entityData.get(DATA_PERSISTENT_LIFT))
        {
            this.entityData.set(DATA_PERSISTENT_LIFT, false);
        }
        this.ticksWithoutControl = 0;
    }

    public boolean isRestraintGantry()
    {
        return this.entityData.get(DATA_RESTRAINT_GANTRY);
    }

    /** Non-saving visual for the moving entry-plug bridge crane. */
    public void configurePlugCrane(int variant, double bottomOffset)
    {
        this.noCulling = true;
        this.assignVariant(variant);
        this.entityData.set(DATA_PLUG_CRANE, true);
        this.entityData.set(DATA_RESTRAINT_GANTRY, false);
        this.entityData.set(DATA_PERSONNEL_LIFT, false);
        this.entityData.set(DATA_PERSISTENT_LIFT, false);
        int quantized = (int) Math.round(
                Math.min(-0.001D, bottomOffset) * 1000.0D);
        int current = this.entityData.get(DATA_CRANE_BOTTOM_OFFSET);
        if (current != quantized)
        {
            this.entityData.set(DATA_CRANE_BOTTOM_OFFSET, quantized);
        }
        this.ticksWithoutControl = 0;
    }

    public boolean isPlugCrane()
    {
        return this.entityData.get(DATA_PLUG_CRANE);
    }

    public float actualCraneBottomOffsetR52(){return this.entityData.get(DATA_CRANE_BOTTOM_OFFSET)/1000F;}

    public float getCraneBottomOffset(float partialTick)
    {
        return this.clientCranePreviousOffset
                + (this.clientCraneCurrentOffset
                - this.clientCranePreviousOffset)
                * Math.max(0.0F, Math.min(1.0F, partialTick));
    }

    public void setLclVisualLevel(float layers)
    {
        int quantized = Math.round(Math.max(0.0F,
                Math.min(44.0F, layers)) * 1000.0F);
        if (this.entityData.get(DATA_LCL_LEVEL_MILLI) != quantized)
        {
            this.entityData.set(DATA_LCL_LEVEL_MILLI, quantized);
        }
    }

    public float getLclVisualLevel(float partialTick)
    {
        float alpha = Math.max(0.0F, Math.min(1.0F, partialTick));
        return this.clientLclPreviousLevel
                + (this.clientLclCurrentLevel
                - this.clientLclPreviousLevel) * alpha;
    }

    /**
     * Reuses the tracked, non-saving carrier entity as a human-scale lift
     * cabin. The server still owns passenger motion; this flag only changes
     * the client silhouette and door state.
     */
    public void configurePersonnelLift(int accent)
    {
        this.entityData.set(DATA_PLUG_CRANE, false);
        this.entityData.set(DATA_RESTRAINT_GANTRY, false);
        this.entityData.set(DATA_PERSONNEL_LIFT, true);
        this.entityData.set(DATA_LIFT_ACCENT, Math.max(0,
                Math.min(4, accent)));
    }

    /**
     * Configures a saved, continuously present lift cabin. This mode is
     * intentionally separate from the short-lived EVA carrier silhouette.
     */
    public void configurePersistentLift(String liftId, int accent)
    {
        this.configurePersistentLift(liftId, accent,
                Double.NaN, Double.NaN);
    }

    public void configurePersistentLift(String liftId, int accent,
                                        double lowerY, double upperY)
    {
        this.configurePersonnelLift(accent);
        this.entityData.set(DATA_PERSISTENT_LIFT, true);
        this.entityData.set(DATA_LIFT_ID, liftId == null ? "" : liftId);
        this.persistentLiftState = LIFT_IDLE_OPEN;
        this.persistentLiftPhaseTicks = 0;
        this.persistentLiftTargetY = this.getY();
        this.persistentLiftLowerY = lowerY;
        this.persistentLiftUpperY = upperY;
        this.persistentLiftVelocity = 0.0D;
        this.persistentLiftPendingMotionEpoch = 0L;
        this.persistentLiftActiveMotionEpoch = 0L;
        this.persistentLiftStateRevision++;
        this.setLiftDoorOpen(true);
        this.ticksWithoutControl = 0;
    }

    public boolean isPersistentLift()
    {
        return this.entityData.get(DATA_PERSISTENT_LIFT);
    }

    public String getLiftId()
    {
        return this.entityData.get(DATA_LIFT_ID);
    }

    public int getPersistentLiftState()
    {
        return this.persistentLiftState;
    }

    public boolean isPersistentLiftIdle()
    {
        return this.isPersistentLift()
                && this.persistentLiftState == LIFT_IDLE_OPEN;
    }

    public boolean isPersistentLiftRecoveryHold()
    {
        return this.isPersistentLift()
                && this.persistentLiftState == LIFT_RECOVERY_HOLD;
    }

    public int getPersistentLiftStateRevision()
    {
        return this.persistentLiftStateRevision;
    }

    public double getPersistentLiftTargetY()
    {
        return this.persistentLiftTargetY;
    }

    public void setLiftExit(Direction exit)
    {
        if (exit != null && exit.getAxis() != Direction.Axis.Y)
        {
            this.entityData.set(DATA_LIFT_EXIT, exit.get2DDataValue());
        }
    }

    public Direction getLiftExit()
    {
        return Direction.from2DDataValue(
                this.entityData.get(DATA_LIFT_EXIT));
    }

    /**
     * Arms one already-recorded trip after the fixed landing doors have
     * actually closed.  Unlike the old two-tick heartbeat, this lease cannot
     * expire merely because entity and server-event ticks run in a different
     * order.  The epoch is minted once by the shaft authority for one trip.
     */
    public boolean activatePersistentLiftMotion(long motionEpoch)
    {
        if (!this.isPersistentLift()
                || motionEpoch <= 0L
                || motionEpoch != this.persistentLiftPendingMotionEpoch
                || motionEpoch < this.persistentLiftLastMotionEpoch)
        {
            return false;
        }
        this.persistentLiftActiveMotionEpoch = motionEpoch;
        return true;
    }

    /** Compatibility bridge for the quarantined pre-S20 lift director. */
    @Deprecated
    public void authorizePersistentLiftMotion(boolean allowed)
    {
        if (allowed && this.persistentLiftPendingMotionEpoch > 0L)
        {
            this.activatePersistentLiftMotion(
                    this.persistentLiftPendingMotionEpoch);
        }
        else if (!allowed && this.isPersistentLiftTranslating())
        {
            this.revokePersistentLiftMotion();
        }
    }

    public void revokePersistentLiftMotion()
    {
        this.persistentLiftActiveMotionEpoch = 0L;
        if (this.isPersistentLiftTranslating())
        {
            this.persistentLiftState = LIFT_RECOVERY_HOLD;
            this.persistentLiftVelocity = 0.0D;
            this.persistentLiftPhaseTicks = 0;
            this.persistentLiftStateRevision++;
            this.setLiftDoorOpen(false);
        }
    }

    public long getPersistentLiftLastMotionEpoch()
    {
        return this.persistentLiftLastMotionEpoch;
    }

    public long getPersistentLiftPendingMotionEpoch()
    {
        return this.persistentLiftPendingMotionEpoch;
    }

    public boolean isPersistentLiftTranslating()
    {
        return this.persistentLiftState == LIFT_STARTING
                || this.persistentLiftState == LIFT_MOVING
                || this.persistentLiftState == LIFT_BRAKING
                || this.persistentLiftState == LIFT_LEVELING;
    }

    /**
     * Crash recovery always restarts from rest toward one audited landing.
     * It never resumes a serialized velocity.
     */
    public boolean recoverPersistentLiftTo(double stableFloorY,
                                           long motionEpoch)
    {
        if (!this.isPersistentLiftRecoveryHold()
                || motionEpoch <= this.persistentLiftLastMotionEpoch
                || !this.isValidPersistentLiftTarget(stableFloorY))
        {
            return false;
        }
        this.persistentLiftLastMotionEpoch = motionEpoch;
        this.persistentLiftPendingMotionEpoch = motionEpoch;
        this.persistentLiftActiveMotionEpoch = motionEpoch;
        this.persistentLiftTargetY = stableFloorY;
        this.persistentLiftVelocity = 0.0D;
        this.persistentLiftPhaseTicks = 0;
        this.persistentLiftStateRevision++;
        this.setLiftDoorOpen(false);
        if (Math.abs(this.getY() - stableFloorY)
                <= LIFT_ARRIVAL_TOLERANCE)
        {
            this.finishPersistentLiftTravel();
        }
        else
        {
            this.persistentLiftState = LIFT_STARTING;
        }
        return true;
    }

    /** Compatibility bridge for the quarantined pre-S20 lift director. */
    @Deprecated
    public boolean recoverPersistentLiftTo(double stableFloorY)
    {
        return this.recoverPersistentLiftTo(stableFloorY,
                this.persistentLiftLastMotionEpoch + 1L);
    }

    public void forcePersistentLiftFault()
    {
        if (!this.isPersistentLift())
        {
            return;
        }
        this.persistentLiftState = LIFT_FAULT;
        this.persistentLiftVelocity = 0.0D;
        this.persistentLiftPendingMotionEpoch = 0L;
        this.persistentLiftActiveMotionEpoch = 0L;
        this.persistentLiftStateRevision++;
        this.setLiftDoorOpen(false);
    }

    public boolean isAtLiftY(double y)
    {
        return Math.abs(this.getY() - y) <= 0.08D;
    }

    /**
     * The fixed landing door may mirror the cabin door only while the cabin
     * is level with that landing. During the boarding delay both remain open;
     * once either leaf starts closing every landing is locked.
     */
    public boolean canOpenLandingDoorAt(double y)
    {
        return this.isPersistentLift()
                && this.isLiftDoorOpen()
                && this.isAtLiftY(y)
                && (this.persistentLiftState == LIFT_IDLE_OPEN
                || this.persistentLiftState == LIFT_DOOR_CLOSING);
    }

    public boolean beginPersistentLiftTravel(double targetY,
                                             long motionEpoch)
    {
        if (!this.isPersistentLiftIdle()
                || !this.isValidPersistentLiftTarget(targetY)
                || motionEpoch <= this.persistentLiftLastMotionEpoch
                || Math.abs(this.getY() - targetY)
                <= LIFT_ARRIVAL_TOLERANCE)
        {
            return false;
        }
        this.persistentLiftLastMotionEpoch = motionEpoch;
        this.persistentLiftPendingMotionEpoch = motionEpoch;
        this.persistentLiftActiveMotionEpoch = 0L;
        this.persistentLiftTargetY = targetY;
        this.persistentLiftState = LIFT_DOOR_CLOSING;
        this.persistentLiftPhaseTicks = 0;
        this.persistentLiftStateRevision++;
        // Leave the physical and rendered door open for the first two
        // seconds so the caller can step into the already-present cabin.
        this.setLiftDoorOpen(true);
        return true;
    }

    /** Compatibility bridge for the quarantined pre-S20 lift director. */
    @Deprecated
    public boolean beginPersistentLiftTravel(double targetY)
    {
        return this.beginPersistentLiftTravel(targetY,
                this.persistentLiftLastMotionEpoch + 1L);
    }

    public boolean isPersonnelLift()
    {
        return this.entityData.get(DATA_PERSONNEL_LIFT);
    }

    public int getLiftAccent()
    {
        return this.entityData.get(DATA_LIFT_ACCENT);
    }

    public void setLiftDoorOpen(boolean open)
    {
        this.entityData.set(DATA_LIFT_DOOR_OPEN, open);
    }

    public boolean isLiftDoorOpen()
    {
        return this.entityData.get(DATA_LIFT_DOOR_OPEN);
    }

    public void moveControlled(double x, double y, double z)
    {
        this.ticksWithoutControl = 0;
        this.setPos(x, y, z);
        this.setDeltaMovement(Vec3.ZERO);
        this.hasImpulse = true;
    }

    @Override
    public void lerpTo(double x, double y, double z, float yRot, float xRot,
                       int lerpSteps, boolean teleport)
    {
        // The plug and its crane publish one sample per server tick.  A
        // two-tick crane interpolation trails the capsule by one whole sample;
        // use the same one-tick render interval as EntryPlugCarrierEntity.
        super.lerpTo(x, y, z, yRot, xRot, 1, teleport);
    }

    /** Keeps a fixed visual alive without publishing a teleport every tick. */
    public void holdStatic(double x, double y, double z)
    {
        this.ticksWithoutControl = 0;
        this.setDeltaMovement(Vec3.ZERO);
        if (this.distanceToSqr(x, y, z) > 1.0E-8D)
        {
            this.setPos(x, y, z);
            this.resetInterpolationFrame();
            this.hasImpulse = true;
        }
    }

    /** Prevents one-frame interpolation from an obsolete pre-unload pose. */
    public void resetInterpolationFrame()
    {
        this.xo = this.getX();
        this.yo = this.getY();
        this.zo = this.getZ();
        this.yRotO = this.getYRot();
        this.xRotO = this.getXRot();
    }

    @Override
    public void tick()
    {
        super.tick();
        if (this.level().isClientSide && this.isPlugCrane())
        {
            float synced = this.entityData.get(DATA_CRANE_BOTTOM_OFFSET)
                    / 1000.0F;
            if (!this.clientCraneOffsetInitialized)
            {
                this.clientCranePreviousOffset = synced;
                this.clientCraneCurrentOffset = synced;
                this.clientCraneOffsetInitialized = true;
            }
            else
            {
                this.clientCranePreviousOffset =
                        this.clientCraneCurrentOffset;
                this.clientCraneCurrentOffset = synced;
            }
        }
        if (this.level().isClientSide && this.isRestraintGantry())
        {
            float restraint=getRestraintProgress();
            if(!clientRestraintInitialized){clientRestraintPrevious=clientRestraintCurrent=restraint;clientRestraintInitialized=true;}
            else{clientRestraintPrevious=clientRestraintCurrent;clientRestraintCurrent=restraint;}
            float synced = this.entityData.get(DATA_LCL_LEVEL_MILLI)
                    / 1000.0F;
            if (!this.clientLclLevelInitialized)
            {
                this.clientLclPreviousLevel = synced;
                this.clientLclCurrentLevel = synced;
                this.clientLclLevelInitialized = true;
            }
            else
            {
                this.clientLclPreviousLevel = this.clientLclCurrentLevel;
                this.clientLclCurrentLevel = synced;
            }
        }
        this.noPhysics = true;
        this.setNoGravity(true);
        this.setDeltaMovement(Vec3.ZERO);
        if (!this.level().isClientSide
                && !this.isPersistentLift()
                && !this.hasDeclaredMachineFrameR52()
                && ++this.ticksWithoutControl > CONTROL_TIMEOUT_TICKS)
        {
            this.discard();
        }
        if (!this.level().isClientSide && this.isPersistentLift())
        {
            this.tickPersistentLift();
        }
    }

    @Override
    protected void readAdditionalSaveData(CompoundTag tag)
    {
        entityData.set(DATA_LOWER_FRAME_R52,tag.getCompound("LowerFrameR52").copy());
        if(tag.getBoolean("DeclaredMechanicalR52"))
        {
            var q=readFloatsR52(tag,"MechanicalRotationR52");if(q.length!=4)throw new IllegalStateException("Incomplete saved declared machine quaternion");var rotation=new Quaternionf(q[0],q[1],q[2],q[3]);if(!Float.isFinite(rotation.lengthSquared())||Math.abs(rotation.lengthSquared()-1)>.0001F)throw new IllegalStateException("Invalid saved declared machine quaternion");
            entityData.set(DATA_DECLARED_MACHINE_Q_R52,rotation);entityData.set(DATA_DECLARED_MACHINE_R52,true);entityData.set(DATA_DECLARED_COLLISION_SHA_R52,tag.getString("MechanicalSourceR52"));
            if(tag.getBoolean("PlugCraneR52"))configurePlugCrane(tag.getInt("EvaVariant"),tag.getInt("CraneBottomMilliR52")/1000D);
            entityData.set(DATA_RESTRAINT_PROGRESS,tag.getInt("RestraintMilliR52"));entityData.set(DATA_LCL_LEVEL_MILLI,tag.getInt("LclMilliR52"));
            if(tag.getBoolean("CraneReferenceR52")){var a=readDoublesR52(tag,"CraneAnchorR52");var r=readFloatsR52(tag,"CraneRotationR52");if(a.length!=3||r.length!=4)throw new IllegalStateException("Incomplete saved hoist reference");entityData.set(DATA_CRANE_REFERENCE,true);entityData.set(DATA_CRANE_ANCHOR,new Vector3f((float)a[0],(float)a[1],(float)a[2]));entityData.set(DATA_CRANE_ROTATION,new Quaternionf(r[0],r[1],r[2],r[3]));}
        }
        if (tag.contains("EvaVariant"))
        {
            this.assignVariant(tag.getInt("EvaVariant"));
        }
        if (tag.getBoolean("PersonnelLift"))
        {
            this.configurePersonnelLift(tag.getInt("LiftAccent"));
            this.setLiftDoorOpen(tag.getBoolean("LiftDoorOpen"));
        }
        if (tag.getBoolean("RestraintGantry"))
        {
            this.configureRestraintGantry();
        }
        if (tag.getBoolean("PersistentLift"))
        {
            this.entityData.set(DATA_PERSISTENT_LIFT, true);
            this.entityData.set(DATA_LIFT_ID, tag.getString("LiftId"));
            if (tag.contains("LiftExit"))
            {
                this.entityData.set(DATA_LIFT_EXIT,
                        tag.getInt("LiftExit"));
            }
            int savedState = tag.getInt("LiftState");
            this.persistentLiftState = isMotionState(savedState)
                    ? LIFT_RECOVERY_HOLD : savedState;
            this.persistentLiftPhaseTicks = tag.getInt("LiftPhaseTicks");
            this.persistentLiftTargetY = tag.getDouble("LiftTargetY");
            this.persistentLiftLowerY = tag.contains("LiftLowerY")
                    ? tag.getDouble("LiftLowerY") : Double.NaN;
            this.persistentLiftUpperY = tag.contains("LiftUpperY")
                    ? tag.getDouble("LiftUpperY") : Double.NaN;
            this.persistentLiftVelocity = 0.0D;
            this.persistentLiftStateRevision =
                    Math.max(0, tag.getInt("LiftStateRevision")) + 1;
            this.persistentLiftLastMotionEpoch = Math.max(0L,
                    tag.getLong("LiftLastMotionEpoch"));
            this.persistentLiftPendingMotionEpoch = 0L;
            this.persistentLiftActiveMotionEpoch = 0L;
            if (this.persistentLiftState == LIFT_RECOVERY_HOLD)
            {
                this.setLiftDoorOpen(false);
            }
        }
    }

    @Override
    protected void addAdditionalSaveData(CompoundTag tag)
    {
        tag.put("LowerFrameR52",entityData.get(DATA_LOWER_FRAME_R52).copy());
        if(hasDeclaredMachineFrameR52())
        {tag.putBoolean("DeclaredMechanicalR52",true);var q=declaredMachineRotationR52();writeFloatsR52(tag,"MechanicalRotationR52",new float[]{q.x,q.y,q.z,q.w});tag.putString("MechanicalSourceR52",declaredCollisionSourceR52());tag.putBoolean("PlugCraneR52",isPlugCrane());tag.putInt("CraneBottomMilliR52",entityData.get(DATA_CRANE_BOTTOM_OFFSET));tag.putInt("RestraintMilliR52",entityData.get(DATA_RESTRAINT_PROGRESS));tag.putInt("LclMilliR52",entityData.get(DATA_LCL_LEVEL_MILLI));tag.putBoolean("CraneReferenceR52",hasCraneReference());if(hasCraneReference()){var a=getCraneReferenceAnchor();var r=getCraneReferenceRotation();writeDoublesR52(tag,"CraneAnchorR52",new double[]{a.x,a.y,a.z});writeFloatsR52(tag,"CraneRotationR52",new float[]{r.x,r.y,r.z,r.w});}}
        tag.putInt("EvaVariant", this.getUnitVariant());
        tag.putBoolean("PersonnelLift", this.isPersonnelLift());
        tag.putBoolean("RestraintGantry", this.isRestraintGantry());
        tag.putInt("LiftAccent", this.getLiftAccent());
        tag.putBoolean("LiftDoorOpen", this.isLiftDoorOpen());
        tag.putBoolean("PersistentLift", this.isPersistentLift());
        tag.putString("LiftId", this.getLiftId());
        tag.putInt("LiftExit",
                this.entityData.get(DATA_LIFT_EXIT));
        tag.putInt("LiftState", this.persistentLiftState);
        tag.putInt("LiftPhaseTicks", this.persistentLiftPhaseTicks);
        tag.putDouble("LiftTargetY", this.persistentLiftTargetY);
        if (Double.isFinite(this.persistentLiftLowerY)
                && Double.isFinite(this.persistentLiftUpperY))
        {
            tag.putDouble("LiftLowerY", this.persistentLiftLowerY);
            tag.putDouble("LiftUpperY", this.persistentLiftUpperY);
        }
        tag.putDouble("LiftVelocity", this.persistentLiftVelocity);
        tag.putInt("LiftStateRevision", this.persistentLiftStateRevision);
        tag.putLong("LiftLastMotionEpoch",
                this.persistentLiftLastMotionEpoch);
    }

    private static void writeFloatsR52(CompoundTag tag,String key,float[] values){var list=new net.minecraft.nbt.ListTag();for(float v:values)list.add(net.minecraft.nbt.FloatTag.valueOf(v));tag.put(key,list);}
    private static void writeDoublesR52(CompoundTag tag,String key,double[] values){var list=new net.minecraft.nbt.ListTag();for(double v:values)list.add(net.minecraft.nbt.DoubleTag.valueOf(v));tag.put(key,list);}
    private static float[] readFloatsR52(CompoundTag tag,String key){var list=tag.getList(key,net.minecraft.nbt.Tag.TAG_FLOAT);var out=new float[list.size()];for(int i=0;i<out.length;i++)out[i]=list.getFloat(i);return out;}
    private static double[] readDoublesR52(CompoundTag tag,String key){var list=tag.getList(key,net.minecraft.nbt.Tag.TAG_DOUBLE);var out=new double[list.size()];for(int i=0;i<out.length;i++)out[i]=list.getDouble(i);return out;}

    @Override
    public boolean shouldBeSaved()
    {
        // Lifts are authored world infrastructure. Carrier decks and wet-cage
        // gantries are reconstructed by their runtime owners after loading;
        // serialising them used to leave an unowned copy behind and the next
        // runtime copy then z-fought with it every frame.
        return this.isPersistentLift()||this.hasDeclaredMachineFrameR52();
    }

    @Override
    public boolean hurt(DamageSource source, float amount)
    {
        return false;
    }

    @Override
    public boolean isPickable()
    {
        return this.isPersistentLift();
    }

    @Override
    public boolean isPushable()
    {
        return false;
    }

    @Override
    public InteractionResult interact(Player player, InteractionHand hand)
    {
        if (!this.isPersistentLift()
                || !this.isPersistentLiftIdle()
                || !this.isLiftDoorOpen())
        {
            return InteractionResult.PASS;
        }
        if (!this.level().isClientSide)
        {
            player.startRiding(this, true);
        }
        return InteractionResult.sidedSuccess(this.level().isClientSide);
    }

    @Override
    public InteractionResult interactAt(Player player, Vec3 hit,
                                        InteractionHand hand)
    {
        if (!this.isPersistentLift()
                || !this.hasConfiguredLiftLandings()
                || !this.isInsidePersistentLiftCabin(player))
        {
            return super.interactAt(player, hit, hand);
        }

        double yaw = Math.toRadians(-this.getYRot());
        double localX = hit.x * Math.cos(yaw) - hit.z * Math.sin(yaw);
        double localZ = hit.x * Math.sin(yaw) + hit.z * Math.cos(yaw);
        boolean onPanel = localX >= 1.85D && localX <= 2.45D
                && localZ >= 0.45D && localZ <= 1.55D
                && hit.y >= 1.00D && hit.y <= 2.15D;
        if (!onPanel)
        {
            return super.interactAt(player, hit, hand);
        }
        if (!this.level().isClientSide)
        {
            if (player instanceof ServerPlayer serverPlayer)
            {
                S20PhysicalElevatorDirector.handleCabinControl(
                        serverPlayer, this, hit.y >= 1.55D);
            }
        }
        return InteractionResult.sidedSuccess(this.level().isClientSide);
    }

    @Override
    public PushReaction getPistonPushReaction()
    {
        return PushReaction.IGNORE;
    }

    @Override
    protected boolean canAddPassenger(Entity passenger)
    {
        return this.isPersistentLift()
                && passenger instanceof Player
                && this.getPassengers().size() < MAX_LIFT_PASSENGERS;
    }

    @Override
    protected void positionRider(Entity passenger, Entity.MoveFunction move)
    {
        if (!this.hasPassenger(passenger))
        {
            return;
        }
        int index = Math.max(0, this.getPassengers().indexOf(passenger));
        double offsetX = (index % 3 - 1) * 1.15D;
        double offsetZ = (index / 3 - 1) * 0.95D;
        move.accept(passenger, this.getX() + offsetX,
                this.getY() + 0.18D, this.getZ() + offsetZ);
    }

    @Override
    public Vec3 getDismountLocationForPassenger(LivingEntity passenger)
    {
        // Never place a rider outside the car while the shaft is open below
        // them.  Sneak-dismounts and transient client remounts can otherwise
        // eject a player 3.4 blocks into an empty shaft during travel.
        if (this.isPersistentLift()
                && (!this.isPersistentLiftIdle()
                || !this.isLiftDoorOpen()))
        {
            return this.position().add(0.0D, 0.2D, 0.0D);
        }
        Direction exit = this.getLiftExit();
        return this.position().add(exit.getStepX() * 3.4D,
                0.2D, exit.getStepZ() * 3.4D);
    }

    private void tickPersistentLift()
    {
        switch (this.persistentLiftState)
        {
            case LIFT_DOOR_CLOSING ->
            {
                this.persistentLiftPhaseTicks++;
                if (this.persistentLiftPhaseTicks
                        >= DOOR_CLOSE_TICKS - DOOR_SLIDE_TICKS)
                {
                    this.setLiftDoorOpen(false);
                }
                if (this.persistentLiftPhaseTicks >= DOOR_CLOSE_TICKS)
                {
                    if (!this.boardWaitingPassengers())
                    {
                        this.persistentLiftState = LIFT_IDLE_OPEN;
                        this.persistentLiftPhaseTicks = 0;
                        this.persistentLiftVelocity = 0.0D;
                        this.persistentLiftStateRevision++;
                        this.setLiftDoorOpen(true);
                        break;
                    }
                    this.persistentLiftState = LIFT_STARTING;
                    this.persistentLiftPhaseTicks = 0;
                    this.persistentLiftVelocity = 0.0D;
                }
            }
            case LIFT_STARTING, LIFT_MOVING, LIFT_BRAKING,
                    LIFT_LEVELING ->
            {
                if (this.persistentLiftActiveMotionEpoch <= 0L
                        || this.isLiftDoorOpen())
                {
                    this.persistentLiftState = LIFT_RECOVERY_HOLD;
                    this.persistentLiftVelocity = 0.0D;
                    this.persistentLiftStateRevision++;
                    this.setLiftDoorOpen(false);
                }
                else
                {
                    this.tickPersistentLiftMotion();
                }
            }
            case LIFT_DOOR_OPENING ->
            {
                this.persistentLiftPhaseTicks++;
                if (this.persistentLiftPhaseTicks >= DOOR_OPEN_TICKS)
                {
                    this.persistentLiftState = LIFT_IDLE_OPEN;
                    this.persistentLiftPhaseTicks = 0;
                    this.setLiftDoorOpen(true);
                }
            }
            case LIFT_FAULT ->
            {
                this.persistentLiftVelocity = 0.0D;
                this.setLiftDoorOpen(false);
            }
            case LIFT_RECOVERY_HOLD ->
            {
                this.persistentLiftVelocity = 0.0D;
                this.setLiftDoorOpen(false);
            }
            default ->
            {
                this.persistentLiftState = LIFT_IDLE_OPEN;
                this.persistentLiftPhaseTicks = 0;
                this.persistentLiftVelocity = 0.0D;
                this.setLiftDoorOpen(true);
            }
        }
    }

    private void tickPersistentLiftMotion()
    {
        // A rider who briefly dismounted inside the closed car (for example
        // because of an input packet arriving on the same tick as departure)
        // must remain attached to the one authoritative moving transform.
        if (!this.boardWaitingPassengers())
        {
            this.persistentLiftState = LIFT_RECOVERY_HOLD;
            this.persistentLiftVelocity = 0.0D;
            this.persistentLiftPhaseTicks = 0;
            this.persistentLiftStateRevision++;
            this.setLiftDoorOpen(false);
            return;
        }
        this.persistentLiftPhaseTicks++;
        if (this.persistentLiftPhaseTicks > LIFT_TRAVEL_WATCHDOG_TICKS)
        {
            /*
             * Never leave a cabin permanently reporting IN TRANSIT.  The
             * shaft authority will recover this stopped car to the nearest
             * audited landing on its next heartbeat.
             */
            this.persistentLiftState = LIFT_RECOVERY_HOLD;
            this.persistentLiftVelocity = 0.0D;
            this.persistentLiftPhaseTicks = 0;
            this.persistentLiftStateRevision++;
            this.setLiftDoorOpen(false);
            return;
        }
        double delta = this.persistentLiftTargetY - this.getY();
        double remaining = Math.abs(delta);
        if (remaining <= LIFT_ARRIVAL_TOLERANCE)
        {
            this.finishPersistentLiftTravel();
            return;
        }

        double brakingSpeed = Math.sqrt(
                2.0D * LIFT_ACCELERATION * remaining);
        double desiredSpeed = Math.min(LIFT_MAX_SPEED, brakingSpeed);
        if (remaining <= 0.75D)
        {
            desiredSpeed = Math.min(desiredSpeed, LIFT_LEVELING_SPEED);
            this.persistentLiftState = LIFT_LEVELING;
        }
        else if (desiredSpeed + 0.01D
                < this.persistentLiftVelocity)
        {
            this.persistentLiftState = LIFT_BRAKING;
        }
        else if (this.persistentLiftVelocity
                < LIFT_MAX_SPEED - 0.01D)
        {
            this.persistentLiftState = LIFT_STARTING;
        }
        else
        {
            this.persistentLiftState = LIFT_MOVING;
        }

        if (this.persistentLiftVelocity < desiredSpeed)
        {
            this.persistentLiftVelocity = Math.min(desiredSpeed,
                    this.persistentLiftVelocity + LIFT_ACCELERATION);
        }
        else
        {
            this.persistentLiftVelocity = Math.max(desiredSpeed,
                    this.persistentLiftVelocity - LIFT_ACCELERATION);
        }
        double step = Math.min(remaining,
                Math.max(LIFT_ARRIVAL_TOLERANCE,
                        this.persistentLiftVelocity));
        this.moveControlled(this.getX(),
                this.getY() + Math.copySign(step, delta), this.getZ());
        for (Entity passenger : this.getPassengers())
        {
            this.positionRider(passenger, Entity::setPos);
            passenger.resetFallDistance();
        }
        if (Math.abs(this.persistentLiftTargetY - this.getY())
                <= LIFT_ARRIVAL_TOLERANCE)
        {
            this.finishPersistentLiftTravel();
        }
    }

    private void finishPersistentLiftTravel()
    {
        this.moveControlled(this.getX(),
                this.persistentLiftTargetY, this.getZ());
        this.persistentLiftVelocity = 0.0D;
        this.persistentLiftPendingMotionEpoch = 0L;
        this.persistentLiftActiveMotionEpoch = 0L;
        this.persistentLiftState = LIFT_DOOR_OPENING;
        this.persistentLiftPhaseTicks = 0;
        this.persistentLiftStateRevision++;
    }

    private boolean isValidPersistentLiftTarget(double targetY)
    {
        return Double.isFinite(targetY)
                && targetY >= this.level().getMinBuildHeight()
                && targetY <= this.level().getMaxBuildHeight() - 5.0D;
    }

    private static boolean isMotionState(int state)
    {
        return state == LIFT_DOOR_CLOSING
                || state == LIFT_STARTING
                || state == LIFT_MOVING
                || state == LIFT_BRAKING
                || state == LIFT_LEVELING
                || state == LIFT_DOOR_OPENING;
    }

    private boolean boardWaitingPassengers()
    {
        AABB cabinInterior = new AABB(
                this.getX() - 2.15D, this.getY() - 0.4D,
                this.getZ() - 2.15D,
                this.getX() + 2.15D, this.getY() + 3.5D,
                this.getZ() + 2.15D);
        for (Player player : this.level().getEntitiesOfClass(
                Player.class, cabinInterior, candidate ->
                        !candidate.isPassenger()))
        {
            if (this.getPassengers().size() >= MAX_LIFT_PASSENGERS)
            {
                return false;
            }
            if (!player.startRiding(this, true))
            {
                return false;
            }
        }
        return this.level().getEntitiesOfClass(
                Player.class, cabinInterior, candidate ->
                        !candidate.isPassenger()
                                && !candidate.isSpectator()).isEmpty();
    }

    private boolean hasConfiguredLiftLandings()
    {
        return Double.isFinite(this.persistentLiftLowerY)
                && Double.isFinite(this.persistentLiftUpperY)
                && this.persistentLiftLowerY < this.persistentLiftUpperY;
    }

    private boolean isInsidePersistentLiftCabin(Player player)
    {
        if (this.hasPassenger(player))
        {
            return true;
        }
        return player.getBoundingBox().intersects(new AABB(
                this.getX() - 2.2D, this.getY() - 0.25D,
                this.getZ() - 2.2D,
                this.getX() + 2.2D, this.getY() + 3.45D,
                this.getZ() + 2.2D));
    }

    public boolean consumePersistentLiftControlDebounce()
    {
        long now = this.level().getGameTime();
        if (now - this.lastPersistentLiftControlTick
                < CONTROL_DEBOUNCE_TICKS)
        {
            return false;
        }
        this.lastPersistentLiftControlTick = now;
        return true;
    }
}
