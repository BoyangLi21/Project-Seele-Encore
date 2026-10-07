package com.projectseele.entity;

import java.util.UUID;

import com.projectseele.world.EntryPlugDirector;
import com.projectseele.world.EntryPlugKinematics;
import com.projectseele.world.EvaHangarBuilder;
import com.projectseele.world.FacilityV2EvaRuntime;
import com.projectseele.world.IntegratedNervMapBuilder;
import com.projectseele.world.RigidTransform;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.chat.Component;
import net.minecraft.network.syncher.EntityDataAccessor;
import net.minecraft.network.syncher.EntityDataSerializers;
import net.minecraft.network.syncher.SynchedEntityData;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.sounds.SoundSource;
import net.minecraft.util.Mth;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.effect.MobEffectInstance;
import net.minecraft.world.effect.MobEffects;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.entity.PathfinderMob;
import net.minecraft.world.entity.ai.attributes.AttributeSupplier;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.entity.player.Player;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.ClipContext;
import net.minecraft.world.phys.HitResult;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import org.joml.Quaternionf;
import org.joml.Vector3f;
import org.jetbrains.annotations.Nullable;
import software.bernie.geckolib.animatable.GeoEntity;
import software.bernie.geckolib.core.animatable.instance.AnimatableInstanceCache;
import software.bernie.geckolib.core.animation.AnimatableManager;
import software.bernie.geckolib.util.GeckoLibUtil;

/**
 * Physical, passenger-carrying entry plug suspended above an EVA wet cage.
 * It exists separately from the EVA so boarding and insertion are observable.
 */
public final class EntryPlugCarrierEntity extends PathfinderMob
        implements GeoEntity
{
    private static final int[] SAFE_DISMOUNT_VERTICAL_OFFSETS = {
            0, 1, -1, 2, -2, 3, -3, 4, -4
    };
    public static final int STAGE_SUSPENDED = 0;
    public static final int STAGE_OCCUPIED = 1;
    public static final int STAGE_INSERTING = 2;
    /** Crane is drawing the capsule back out of the airframe with its pilot. */
    public static final int STAGE_EJECTING = 3;
    /** Emergency pyrotechnics are throwing the occupied capsule clear. */
    public static final int STAGE_FIELD_EJECTING = 4;
    /** Emergency capsule has landed and is no longer owned by a cage crane. */
    public static final int STAGE_FIELD_LANDED = 5;
    /**
     * The same physical capsule is seated inside its EVA. It remains the
     * player's vehicle and rides the airframe as a hidden nested passenger.
     */
    public static final int STAGE_LOCKED = 6;
    /** A failed PREPARE is braking and retracing the authored insertion path. */
    public static final int STAGE_ABORT_RETURNING = 7;
    public static final int STAGE_ABORT_DOCKED = 8;

    /** Hatch open at the boarding bridge; the capsule is safe to enter. */
    public static final int CABIN_OPEN = 0;
    /** Pilot seated, hatch sealed, optical feed still completely disconnected. */
    public static final int CABIN_SEALED_DARK = 1;
    /** PREPARE accepted and the local capsule is filling with LCL. */
    public static final int CABIN_LCL_FILLING = 2;
    /** A10 nerve connection and external optical synchronization are running. */
    public static final int CABIN_SYNCHRONIZING = 3;
    /** Optical feed is live; ownership is about to transfer to the airframe. */
    public static final int CABIN_ONLINE = 4;
    /** Returned to the wet cage: hatch sealed, normal cabin view, no overlay. */
    public static final int CABIN_RECOVERED_IDLE = 5;
    /** Percent reached outside the EVA before the seated plug takes over. */
    public static final int CABIN_TRANSFER_PERCENT = 70;
    /** Door animation is eight percentage points per server tick. */
    public static final int HATCH_SEAL_TICKS = 13;

    private int ejectionTicks;
    private static final EntityDataAccessor<Boolean> DATA_TV_WET_EJECTION_HELD_R44=
            SynchedEntityData.defineId(EntryPlugCarrierEntity.class,EntityDataSerializers.BOOLEAN);
    private CompoundTag tvPersonnelWetTagR44=new CompoundTag();
    private net.minecraft.nbt.Tag tvPersonnelWetOpaqueR44;
    private boolean tvPersonnelWetPersistenceInvalidR44;
    private String tvPersonnelWetFaultR44="";
    private Vec3 fieldEjectionStart = Vec3.ZERO;
    private Vec3 fieldEjectionEscape = Vec3.ZERO;
    private Vec3 fieldEjectionLanding = Vec3.ZERO;

    private static final EntityDataAccessor<Integer> DATA_VARIANT =
            SynchedEntityData.defineId(EntryPlugCarrierEntity.class,
                    EntityDataSerializers.INT);
    private static final EntityDataAccessor<Integer> DATA_STAGE =
            SynchedEntityData.defineId(EntryPlugCarrierEntity.class,
                    EntityDataSerializers.INT);
    /**
     * Monotonic mechanical-generation counter.  Stage changes and their epoch
     * are published together on the server thread, allowing directors and
     * clients to reject a stale insertion/rollback decision after a reload or
     * an abort request.
     */
    private static final EntityDataAccessor<Integer> DATA_STAGE_EPOCH =
            SynchedEntityData.defineId(EntryPlugCarrierEntity.class,
                    EntityDataSerializers.INT);
    private static final EntityDataAccessor<Integer> DATA_PROGRESS =
            SynchedEntityData.defineId(EntryPlugCarrierEntity.class,
                    EntityDataSerializers.INT);
    private static final EntityDataAccessor<Integer> DATA_CABIN_STAGE =
            SynchedEntityData.defineId(EntryPlugCarrierEntity.class,
                    EntityDataSerializers.INT);
    private static final EntityDataAccessor<Integer> DATA_CABIN_PROGRESS =
            SynchedEntityData.defineId(EntryPlugCarrierEntity.class,
                    EntityDataSerializers.INT);
    /**
     * Visual hatch travel, 0 = pressure shell closed and 100 = fully open.
     * This is separate from {@link #DATA_CABIN_STAGE}: boarding must lock
     * immediately, while the two physical door leaves still need several
     * frames to close rather than vanishing between clicks.
     */
    private static final EntityDataAccessor<Integer> DATA_HATCH_OPEN =
            SynchedEntityData.defineId(EntryPlugCarrierEntity.class,
                    EntityDataSerializers.INT);
    private static final EntityDataAccessor<Boolean> DATA_CANONICAL_POSE =
            SynchedEntityData.defineId(EntryPlugCarrierEntity.class,
                    EntityDataSerializers.BOOLEAN);
    private static final EntityDataAccessor<Vector3f> DATA_POSE_TRANSLATION =
            SynchedEntityData.defineId(EntryPlugCarrierEntity.class,
                    EntityDataSerializers.VECTOR3);
    private static final EntityDataAccessor<Float> DATA_POSE_QX =
            SynchedEntityData.defineId(EntryPlugCarrierEntity.class,
                    EntityDataSerializers.FLOAT);
    private static final EntityDataAccessor<Float> DATA_POSE_QY =
            SynchedEntityData.defineId(EntryPlugCarrierEntity.class,
                    EntityDataSerializers.FLOAT);
    private static final EntityDataAccessor<Float> DATA_POSE_QZ =
            SynchedEntityData.defineId(EntryPlugCarrierEntity.class,
                    EntityDataSerializers.FLOAT);
    private static final EntityDataAccessor<Float> DATA_POSE_QW =
            SynchedEntityData.defineId(EntryPlugCarrierEntity.class,
                    EntityDataSerializers.FLOAT);
    private static final EntityDataAccessor<Integer> DATA_POSE_SEQUENCE =
            SynchedEntityData.defineId(EntryPlugCarrierEntity.class,
                    EntityDataSerializers.INT);
    private static final EntityDataAccessor<Integer> DATA_HOST_EVA_ID =
            SynchedEntityData.defineId(EntryPlugCarrierEntity.class,
                    EntityDataSerializers.INT);
    private static final EntityDataAccessor<Boolean> DATA_SHELL_VISIBLE =
            SynchedEntityData.defineId(EntryPlugCarrierEntity.class,
                    EntityDataSerializers.BOOLEAN);
    /** Pilot/entity code may request a rollback, but only the director may
     * advance the mechanical insertion stage. */
    private static final EntityDataAccessor<Boolean> DATA_ABORT_REQUESTED =
            SynchedEntityData.defineId(EntryPlugCarrierEntity.class,
                    EntityDataSerializers.BOOLEAN);

    private static final EntityDataAccessor<Integer> DATA_LAB_SLOT_R47 =
            SynchedEntityData.defineId(EntryPlugCarrierEntity.class,EntityDataSerializers.INT);
    private RigidTransform laboratoryDockR47=RigidTransform.identity();
    private final AnimatableInstanceCache geoCache =
            GeckoLibUtil.createInstanceCache(this);
    private RigidTransform clientPreviousRotation = RigidTransform.identity();
    private RigidTransform clientCurrentRotation = RigidTransform.identity();
    private int clientRotationUpdateTick = Integer.MIN_VALUE;
    private Vec3 clientPreviousPosePosition=Vec3.ZERO;
    private Vec3 clientCurrentPosePosition=Vec3.ZERO;
    private boolean clientPoseInitialized;
    private boolean clientPoseBatchDirtyR49,clientStageBatchDirtyR49,clientHardBatchDirtyR49,clientCabinBatchDirtyR49;
    private float clientPreviousCabinProgress;
    private float clientCurrentCabinProgress;
    private int clientCabinProgressUpdateTick = Integer.MIN_VALUE;
    @Nullable
    private UUID hostEvaUuid;
    private int nextBoardingDiagnosticTick;
    private RigidTransform lockedSocketToPlug = new RigidTransform(
            new Vec3(0.0D, 0.0D, -EntryPlugKinematics.LOCK_DEPTH_BLOCKS),
            0.0F, 0.0F, 0.0F, 1.0F);

    public EntryPlugCarrierEntity(
            EntityType<? extends EntryPlugCarrierEntity> type, Level level)
    {
        super(type, level);
        this.noPhysics = true;
        this.noCulling = true;
        this.setNoGravity(true);
        this.setPersistenceRequired();
    }

    public static AttributeSupplier.Builder createAttributes()
    {
        return Mob.createMobAttributes()
                .add(Attributes.MAX_HEALTH, 40.0D)
                .add(Attributes.MOVEMENT_SPEED, 0.0D)
                .add(Attributes.KNOCKBACK_RESISTANCE, 1.0D);
    }

    public int laboratorySlotR47(){return this.entityData.get(DATA_LAB_SLOT_R47);}
    public void configureLaboratoryR47(int slot,int variant,RigidTransform dock)
    {
        if(this.level().isClientSide||slot<0||slot>1||this.getLinkedEva()!=null)
            throw new IllegalStateException("Only independent laboratory fixtures can be configured");
        this.entityData.set(DATA_LAB_SLOT_R47,slot);this.assignVariant(variant);
        this.laboratoryDockR47=dock;this.setCanonicalTransform(dock);
        this.entityData.set(DATA_STAGE,STAGE_SUSPENDED);this.setLabHatchR47(true);
        this.setNoAi(true);this.setPersistenceRequired();
    }
    public void laboratoryMotionR47(float depth)
    {
        if(this.level().isClientSide||this.laboratorySlotR47()<0)return;
        depth=Mth.clamp(depth,0,1.8F);var dock=this.laboratoryDockR47;
        var point=dock.translation().add(dock.transformVector(new Vec3(0,0,-depth)));
        this.setCanonicalTransform(new RigidTransform(point,dock.qx(),dock.qy(),dock.qz(),dock.qw()));
    }
    public void setLabHatchR47(boolean open)
    {
        if(!this.level().isClientSide&&this.laboratorySlotR47()>=0)
        {
            this.entityData.set(DATA_CABIN_STAGE,open?CABIN_OPEN:CABIN_SEALED_DARK);
            this.entityData.set(DATA_CABIN_PROGRESS,0);
        }
    }

    @Override
    protected void registerGoals()
    {
        // The overhead insertion crane is the sole movement authority.
    }

    @Override
    protected void defineSynchedData()
    {
        super.defineSynchedData();
        this.entityData.define(DATA_VARIANT, EvaUnit01Entity.UNIT_01);
        this.entityData.define(DATA_LAB_SLOT_R47,-1);
        this.entityData.define(DATA_INDEPENDENT_UN,false);
        this.entityData.define(DATA_STAGE, STAGE_SUSPENDED);
        this.entityData.define(DATA_TV_WET_EJECTION_HELD_R44,false);
        this.entityData.define(DATA_STAGE_EPOCH, 0);
        this.entityData.define(DATA_PROGRESS, 0);
        this.entityData.define(DATA_CABIN_STAGE, CABIN_OPEN);
        this.entityData.define(DATA_CABIN_PROGRESS, 0);
        this.entityData.define(DATA_HATCH_OPEN, 100);
        this.entityData.define(DATA_CANONICAL_POSE, false);
        this.entityData.define(DATA_POSE_TRANSLATION, new Vector3f());
        this.entityData.define(DATA_POSE_QX, 0.0F);
        this.entityData.define(DATA_POSE_QY, 0.0F);
        this.entityData.define(DATA_POSE_QZ, 0.0F);
        this.entityData.define(DATA_POSE_QW, 1.0F);
        this.entityData.define(DATA_POSE_SEQUENCE, 0);
        this.entityData.define(DATA_HOST_EVA_ID, -1);
        this.entityData.define(DATA_SHELL_VISIBLE, true);
        this.entityData.define(DATA_ABORT_REQUESTED, false);
        this.entityData.define(DATA_HARD_POSE_R31,0);
    }

    private static final net.minecraft.network.syncher.EntityDataAccessor<Boolean> DATA_INDEPENDENT_UN=net.minecraft.network.syncher.SynchedEntityData.defineId(EntryPlugCarrierEntity.class,net.minecraft.network.syncher.EntityDataSerializers.BOOLEAN);
    // An explicit geometric discontinuity, committed after the complete metadata batch.
    private static final EntityDataAccessor<Integer> DATA_HARD_POSE_R31=
            SynchedEntityData.defineId(EntryPlugCarrierEntity.class,EntityDataSerializers.INT);
    public boolean isIndependentUNPlug(){return entityData.get(DATA_INDEPENDENT_UN);}
    public void assignIndependentEva(EvaPrototypeEntity eva){entityData.set(DATA_INDEPENDENT_UN,true);hostEvaUuid=eva.getUUID();entityData.set(DATA_HOST_EVA_ID,eva.getId());}

    public boolean hasCanonicalPose()
    {
        return this.entityData.get(DATA_CANONICAL_POSE);
    }

    public RigidTransform getCanonicalTransform()
    {
        Vector3f syncedTranslation = this.entityData.get(DATA_POSE_TRANSLATION);
        Vec3 translation = this.hasCanonicalPose()
                ? new Vec3(syncedTranslation.x(), syncedTranslation.y(),
                        syncedTranslation.z()) : this.position();
        return new RigidTransform(translation,
                this.entityData.get(DATA_POSE_QX),
                this.entityData.get(DATA_POSE_QY),
                this.entityData.get(DATA_POSE_QZ),
                this.entityData.get(DATA_POSE_QW));
    }

    public Quaternionf getCanonicalRotation(float partialTick)
    {
        if(this.tvPersonnelWetEjectionHeldR44())return this.getCanonicalTransform().rotation();
        RigidTransform attached=this.lockedBodyRenderTransformR31(partialTick);
        if(attached!=null)return attached.rotation();
        if (!this.level().isClientSide)
        {
            return this.getCanonicalTransform().rotation();
        }
        if (this.tickCount != this.clientRotationUpdateTick)
        {
            return this.clientCurrentRotation.rotation();
        }
        /*
         * The dock and socket frames cross the quaternion hemisphere seam
         * near the first insertion movement.  Canonical persistence keeps
         * w >= 0, but two adjacent network samples can consequently describe
         * the same continuous motion with opposite q/-q representatives.
         * A renderer-side slerp then produced one 33 ms, roughly 180-degree
         * inversion (visible in the 2026-08-14 capture at 7.85 s).  Unwrap
         * the target into the previous sample's hemisphere and use nlerp;
         * pose deltas are one server tick apart, so nlerp is both smooth and
         * incapable of taking the long arc through the inverted capsule.
         */
        Quaternionf previous = this.clientPreviousRotation.rotation();
        Quaternionf current = this.clientCurrentRotation.rotation();
        if (previous.dot(current) < 0.0F)
        {
            current.set(-current.x, -current.y, -current.z, -current.w);
        }
        float alpha = Mth.clamp(partialTick, 0.0F, 1.0F);
        return new Quaternionf(
                Mth.lerp(alpha, previous.x, current.x),
                Mth.lerp(alpha, previous.y, current.y),
                Mth.lerp(alpha, previous.z, current.z),
                Mth.lerp(alpha, previous.w, current.w)).normalize();
    }

    /** Render-frame transform shared by the shell and first-person camera. */
    public RigidTransform getInterpolatedCanonicalTransform(float partialTick)
    {
        if(this.tvPersonnelWetEjectionHeldR44())return this.getCanonicalTransform();
        RigidTransform attached=this.lockedBodyRenderTransformR31(partialTick);
        if(attached!=null)return attached;
        if (!this.level().isClientSide || !this.hasCanonicalPose())
        {
            return this.getCanonicalTransform();
        }
        float alpha = Mth.clamp(partialTick, 0.0F, 1.0F);
        // A vehicle correction can change vanilla position history after the
        // pose packet. The shell, hatch and cabin instead share this stream.
        Vec3 translation=!clientPoseInitialized?getCanonicalTransform().translation()
                :this.tickCount==clientRotationUpdateTick?clientPreviousPosePosition.lerp(clientCurrentPosePosition,alpha)
                :clientCurrentPosePosition;
        Quaternionf rotation = this.getCanonicalRotation(partialTick);
        return new RigidTransform(translation, rotation.x, rotation.y,
                rotation.z, rotation.w);
    }

    @Nullable
    private RigidTransform lockedBodyRenderTransformR31(float partial)
    {
        if(!this.level().isClientSide||!this.hasCanonicalPose()||!this.isLockedToEva())return null;
        var unit=this.getLinkedEva();
        return unit!=null&&(EvaAirTransportR31.active(unit)||EvaShutdownR30.displayed(unit))?EntryPlugKinematics.lockedTransform(unit,Mth.clamp(partial,0,1)):null;
    }

    /** Camera marker inside the sealed capsule, never on its exterior AABB. */
    public Vec3 getInterpolatedPilotEyePosition(float partialTick)
    {
        return this.getInterpolatedCanonicalTransform(partialTick)
                .transformPoint(EntryPlugKinematics.PILOT_EYE_P);
    }

    /**
     * Vanilla mobile-entity packets normally ease position over several
     * client ticks.  The entry plug's canonical quaternion is a one-server-
     * tick pose stream, so letting vanilla use its longer translation clock
     * makes the mesh rotate around a stale pivot.  That mismatch is most
     * visible at the dock-to-insertion boundary and while the observer turns
     * their camera.  Consume every authoritative pose over the same single
     * tick used by {@link #getCanonicalRotation(float)}.
     */
    @Override
    public void lerpTo(double x, double y, double z, float yRot, float xRot,
                       int lerpSteps, boolean teleport)
    {
        if (this.level().isClientSide && this.hasCanonicalPose())
        {
            /*
             * Translation is part of DATA_POSE_SEQUENCE below.  Consuming the
             * separate vanilla movement packet as a second interpolation
             * clock is what made the capsule and its first-person seat drift
             * by one render frame while the crane changed pitch.
             */
            this.lerpSteps = 0;
            return;
        }
        super.lerpTo(x, y, z, yRot, xRot, 1, teleport);
    }

    /**
     * The crane/director publishes one translation + quaternion pose. Renderer,
     * hatch, seat and interaction markers all derive from this state.
     */
    public void setCanonicalTransform(RigidTransform transform)
    {
        setCanonicalTransform(transform,false);
    }

    /** Administrative reset is a discontinuity, never an insertion arc. */
    public void snapCanonicalTransformR31(RigidTransform transform)
    {
        setCanonicalTransform(transform,true);
        this.lerpSteps=0;
        this.xo=this.xOld=this.getX();this.yo=this.yOld=this.getY();this.zo=this.zOld=this.getZ();
        int generation=this.entityData.get(DATA_HARD_POSE_R31);
        this.entityData.set(DATA_HARD_POSE_R31,generation==Integer.MAX_VALUE?1:generation+1);
    }

    private void setCanonicalTransform(RigidTransform transform,boolean force)
    {
        RigidTransform current = this.getCanonicalTransform();
        boolean unchanged = this.hasCanonicalPose()
                && current.translation().distanceToSqr(transform.translation())
                        <= 1.0D / (4096.0D * 4096.0D)
                && current.rotationErrorDegrees(transform) <= 0.01D;
        if (unchanged&&!force)
        {
            // Do not publish a fresh pose sequence for the same dock frame.
            // The stage edge used to send an otherwise-identical quaternion
            // and restart client interpolation, which read as a one-frame
            // kick immediately before the capsule began its insertion arc.
            return;
        }
        this.setPos(transform.translation());
        this.entityData.set(DATA_POSE_TRANSLATION, new Vector3f(
                (float) transform.translation().x,
                (float) transform.translation().y,
                (float) transform.translation().z));
        this.entityData.set(DATA_POSE_QX, transform.qx());
        this.entityData.set(DATA_POSE_QY, transform.qy());
        this.entityData.set(DATA_POSE_QZ, transform.qz());
        this.entityData.set(DATA_POSE_QW, transform.qw());
        this.entityData.set(DATA_CANONICAL_POSE, true);
        int sequence=this.entityData.get(DATA_POSE_SEQUENCE);
        this.entityData.set(DATA_POSE_SEQUENCE,sequence==Integer.MAX_VALUE?1:sequence+1);
        if (!this.level().isClientSide && this.isVehicle())
        {
            /*
             * Logistics advances the canonical pose from the server-level
             * END tick, after the ordinary entity/passenger tick has already
             * run.  Without this reconciliation the authoritative pilot seat
             * remained one pose sample behind the rendered capsule and was
             * corrected on the next tick, which reads as first-person shake
             * while looking around.  Move only position here; player view
             * yaw/pitch remains wholly mouse-owned in positionRider().
             */
            for (Entity passenger : this.getPassengers())
            {
                this.positionRider(passenger, Entity::setPos);
            }
        }
    }

    public Vec3 transformPlugMarker(Vec3 marker)
    {
        return this.getCanonicalTransform().transformPoint(marker);
    }

    public int getAssignedVariant()
    {
        return this.isIndependentUNPlug()?-1:this.entityData.get(DATA_VARIANT);
    }

    public void assignVariant(int variant)
    {
        int safe = Math.max(EvaUnit01Entity.UNIT_00,
                Math.min(EvaUnit01Entity.UNIT_02, variant));
        this.entityData.set(DATA_VARIANT, safe);
        this.setCustomName(Component.literal(String.format(
                "NERV ENTRY PLUG / EVA-%02d", safe)));
        this.setCustomNameVisible(false);
    }

    public int getInsertionStage()
    {
        return this.entityData.get(DATA_STAGE);
    }

    private void setInsertionStage(int stage)
    {
        int safe = Math.max(STAGE_SUSPENDED,
                Math.min(STAGE_ABORT_DOCKED, stage));
        if (this.entityData.get(DATA_STAGE) == safe)
        {
            return;
        }
        this.entityData.set(DATA_STAGE, safe);
        advanceInsertionEpoch();
    }

    public int getInsertionEpoch()
    {
        return this.entityData.get(DATA_STAGE_EPOCH);
    }

    /**
     * Server-thread compare-and-set used by the mechanical director.  A stale
     * callback may not advance or rewind a capsule that has already entered a
     * different phase.
     */
    public boolean transitionInsertionStage(int expectedStage, int nextStage)
    {
        return this.transitionInsertionStage(expectedStage,
                this.getInsertionEpoch(), nextStage);
    }

    public boolean transitionInsertionStage(
            int expectedStage, int expectedEpoch, int nextStage)
    {
        if (this.level().isClientSide
                || this.getInsertionStage() != expectedStage
                || this.getInsertionEpoch() != expectedEpoch
                || !allowedInsertionTransition(expectedStage, nextStage))
        {
            return false;
        }
        this.setInsertionStage(nextStage);
        return this.getInsertionStage() == Math.max(STAGE_SUSPENDED,
                Math.min(STAGE_ABORT_DOCKED, nextStage));
    }

    private static boolean allowedInsertionTransition(int from, int to)
    {
        return switch (from)
        {
            case STAGE_SUSPENDED -> to == STAGE_OCCUPIED;
            case STAGE_OCCUPIED -> to == STAGE_SUSPENDED
                    || to == STAGE_INSERTING
                    || to == STAGE_ABORT_DOCKED;
            case STAGE_INSERTING -> to == STAGE_LOCKED
                    || to == STAGE_ABORT_RETURNING;
            case STAGE_LOCKED -> to == STAGE_INSERTING
                    || to == STAGE_EJECTING
                    || to == STAGE_FIELD_EJECTING
                    || to == STAGE_ABORT_RETURNING;
            case STAGE_EJECTING -> to == STAGE_OCCUPIED
                    || to == STAGE_SUSPENDED;
            case STAGE_FIELD_EJECTING -> to == STAGE_FIELD_LANDED;
            case STAGE_FIELD_LANDED -> to == STAGE_OCCUPIED;
            case STAGE_ABORT_RETURNING -> to == STAGE_ABORT_DOCKED;
            case STAGE_ABORT_DOCKED -> to == STAGE_OCCUPIED
                    || to == STAGE_SUSPENDED;
            default -> false;
        };
    }

    private void advanceInsertionEpoch()
    {
        int current = this.entityData.get(DATA_STAGE_EPOCH);
        this.entityData.set(DATA_STAGE_EPOCH,
                current == Integer.MAX_VALUE ? 1 : current + 1);
    }

    public int getInsertionProgress()
    {
        return this.entityData.get(DATA_PROGRESS);
    }

    public void setInsertionProgress(int progress)
    {
        this.entityData.set(DATA_PROGRESS, Math.max(0, Math.min(100, progress)));
    }

    public boolean isLockedToEva()
    {
        return this.getInsertionStage() == STAGE_LOCKED
                && (this.hostEvaUuid != null
                    || this.entityData.get(DATA_HOST_EVA_ID) >= 0
                    || this.getVehicle() instanceof EvaUnit01Entity);
    }

    public boolean isShellVisible()
    {
        return this.entityData.get(DATA_SHELL_VISIBLE);
    }

    public boolean isInsertionAbortRequested()
    {
        return this.entityData.get(DATA_ABORT_REQUESTED);
    }

    public void requestInsertionAbort()
    {
        if (this.getInsertionStage() == STAGE_INSERTING)
        {
            this.entityData.set(DATA_ABORT_REQUESTED, true);
            this.sealCabin();
        }
    }

    public void clearInsertionAbortRequest()
    {
        this.entityData.set(DATA_ABORT_REQUESTED, false);
    }

    @Nullable
    public UUID getHostEvaUuid()
    {
        return this.hostEvaUuid;
    }

    /**
     * Resolves the airframe without forcing a chunk load. The direct nested
     * vehicle is authoritative; synchronized IDs cover the client, and UUIDs
     * restore the link after a server reload.
     */
    @Nullable
    public EvaUnit01Entity getLinkedEva()
    {
        if (this.getVehicle() instanceof EvaUnit01Entity direct)
        {
            return direct;
        }
        int entityId = this.entityData.get(DATA_HOST_EVA_ID);
        Entity byId = entityId >= 0 ? this.level().getEntity(entityId) : null;
        if (byId instanceof EvaUnit01Entity eva)
        {
            return eva;
        }
        if (!this.level().isClientSide && this.hostEvaUuid != null
                && this.level() instanceof net.minecraft.server.level.ServerLevel server)
        {
            Entity byUuid = server.getEntity(this.hostEvaUuid);
            if (byUuid instanceof EvaUnit01Entity eva)
            {
                return eva;
            }
        }
        return null;
    }

    /**
     * Seats this exact entity in the dorsal socket. The pilot is deliberately
     * not transferred: EVA -> plug -> pilot remains one persistent ride chain.
     */
    public boolean lockToEva(EvaUnit01Entity unit)
    {
        if (this.level().isClientSide || unit.level() != this.level()
                || (!this.isVehicle() && !(unit instanceof EvaPrototypeEntity un && com.projectseele.world.UNAirLiftR29.emptyLoading(un))))
        {
            return false;
        }
        RigidTransform socket = unit.getEntryPlugSocketTransform();
        RigidTransform seated = EntryPlugKinematics.lockedTransform(unit);
        this.lockedSocketToPlug = socket.inverse().compose(seated);
        this.hostEvaUuid = unit.getUUID();
        this.entityData.set(DATA_HOST_EVA_ID, unit.getId());
        this.clearInsertionAbortRequest();
        this.setCanonicalTransform(seated);
        if (!this.startRiding(unit, true))
        {
            this.hostEvaUuid = null;
            this.entityData.set(DATA_HOST_EVA_ID, -1);
            this.entityData.set(DATA_SHELL_VISIBLE, true);
            return false;
        }
        if (!this.transitionInsertionStage(STAGE_INSERTING, STAGE_LOCKED))
        {
            this.stopRiding();
            this.hostEvaUuid = null;
            this.entityData.set(DATA_HOST_EVA_ID, -1);
            this.entityData.set(DATA_SHELL_VISIBLE, true);
            return false;
        }
        // Hide only after the nested EVA -> plug -> pilot ride chain exists.
        // Hiding before startRiding exposed one outside-world frame to the
        // first-person camera at the end of insertion.
        this.entityData.set(DATA_SHELL_VISIBLE, false);
        this.setInsertionProgress(100);
        this.setCabinSequenceProgress(CABIN_TRANSFER_PERCENT);
        return true;
    }

    /** Detaches the same capsule for hangar extraction or field ejection. */
    public void unlockFromEva()
    {
        if(this.level().isClientSide)return;
        if (this.getVehicle() instanceof EvaUnit01Entity)
        {
            this.stopRiding();
        }
        this.hostEvaUuid = null;
        this.entityData.set(DATA_HOST_EVA_ID, -1);
        this.entityData.set(DATA_SHELL_VISIBLE, true);
    }

    /** Operator recovery keeps the same independent capsule and never spawns a replacement. */
    public void resetIndependentAtDock(EvaPrototypeEntity eva)
    {
        if(this.level().isClientSide||!this.isIndependentUNPlug()
                ||!eva.getPersistentData().hasUUID("UNPlug")
                ||!eva.getPersistentData().getUUID("UNPlug").equals(this.getUUID()))
            throw new IllegalStateException("Independent capsule identity mismatch");
        this.ejectPassengers();this.unlockFromEva();eva.clearEntryPlugLink(this);this.assignIndependentEva(eva);
        this.setInsertionStage(STAGE_SUSPENDED);this.setInsertionProgress(0);this.setCabinRecoveryProgress(0);
        this.clearInsertionAbortRequest();this.snapCanonicalTransformR31(com.projectseele.world.UNPlugDirector.dock(eva));this.openCabin();
        this.ejectionTicks=0;this.fieldEjectionStart=this.fieldEjectionEscape=this.fieldEjectionLanding=Vec3.ZERO;
        this.lockedSocketToPlug=new RigidTransform(new Vec3(0,0,-EntryPlugKinematics.LOCK_DEPTH_BLOCKS),0,0,0,1);
        eva.getPersistentData().putInt("UNSequenceTicks",0);
    }

    public boolean beginFieldEjection(Vec3 start, Vec3 escape, Vec3 landing)
    {
        int stage = this.getInsertionStage();
        int epoch = this.getInsertionEpoch();
        if (!this.transitionInsertionStage(stage, epoch,
                STAGE_FIELD_EJECTING))
        {
            return false;
        }
        this.fieldEjectionStart = start;
        this.fieldEjectionEscape = escape;
        this.fieldEjectionLanding = landing;
        this.ejectionTicks = 0;
        this.setInsertionProgress(100);
        return true;
    }

    public Vec3 getFieldEjectionStart()
    {
        return this.fieldEjectionStart;
    }

    public Vec3 getFieldEjectionEscape()
    {
        return this.fieldEjectionEscape;
    }

    public Vec3 getFieldEjectionLanding()
    {
        return this.fieldEjectionLanding;
    }

    public int getCabinStage()
    {
        return this.entityData.get(DATA_CABIN_STAGE);
    }

    public int getCabinProgress()
    {
        return this.entityData.get(DATA_CABIN_PROGRESS);
    }

    public float getCabinProgress(float partialTick)
    {
        if (!this.level().isClientSide
                || this.tickCount != this.clientCabinProgressUpdateTick)
        {
            return this.entityData.get(DATA_CABIN_PROGRESS);
        }
        return Mth.lerp(Mth.clamp(partialTick, 0.0F, 1.0F),
                this.clientPreviousCabinProgress,
                this.clientCurrentCabinProgress);
    }

    public boolean isHatchOpen()
    {
        if(this.laboratorySlotR47()>=0)
            return this.getCabinStage()==CABIN_OPEN&&this.entityData.get(DATA_HATCH_OPEN)==100;
        return this.getCabinStage() == CABIN_OPEN && !this.isVehicle();
    }

    public float getHatchOpenAmount()
    {
        return this.entityData.get(DATA_HATCH_OPEN) / 100.0F;
    }

    public boolean isHatchFullySealed()
    {
        return this.getCabinStage() != CABIN_OPEN
                && this.entityData.get(DATA_HATCH_OPEN) == 0;
    }

    public void sealCabin()
    {
        this.entityData.set(DATA_CABIN_STAGE, CABIN_SEALED_DARK);
        this.entityData.set(DATA_CABIN_PROGRESS, 0);
    }

    public void beginCabinPreparation()
    {
        if (this.isVehicle())
        {
            /*
             * PREPARE may be pressed immediately after boarding, while the two
             * pressure-door leaves are still travelling.  Keep the capsule
             * optically offline until the hatch is physically shut.  A plug
             * returned through RECOVER legitimately begins at
             * CABIN_RECOVERED_IDLE; PARKED + occupied is the higher-level
             * authority to restart the sequence, so reset every stale visual
             * stage here instead of silently ignoring the next PREPARE.
             */
            this.entityData.set(DATA_CABIN_STAGE, CABIN_SEALED_DARK);
            this.entityData.set(DATA_CABIN_PROGRESS, 0);
        }
    }

    /**
     * Advances the continuous cockpit sequence. The visual stage is derived
     * here so server logistics cannot publish a percentage and a contradictory
     * label on separate ticks.
     */
    public void setCabinSequenceProgress(int progress)
    {
        int safe = Math.max(0, Math.min(CABIN_TRANSFER_PERCENT, progress));
        this.entityData.set(DATA_CABIN_PROGRESS, safe);
        if (safe <= 0)
        {
            this.entityData.set(DATA_CABIN_STAGE, CABIN_SEALED_DARK);
        }
        else if (safe < 45)
        {
            this.entityData.set(DATA_CABIN_STAGE, CABIN_LCL_FILLING);
        }
        else if (safe < CABIN_TRANSFER_PERCENT)
        {
            this.entityData.set(DATA_CABIN_STAGE, CABIN_SYNCHRONIZING);
        }
        else
        {
            this.entityData.set(DATA_CABIN_STAGE, CABIN_ONLINE);
        }
    }

    public void openCabin()
    {
        if (!this.isVehicle()
                && (this.getInsertionStage() == STAGE_SUSPENDED
                    || this.getInsertionStage() == STAGE_FIELD_LANDED))
        {
            this.entityData.set(DATA_CABIN_STAGE, CABIN_OPEN);
            this.entityData.set(DATA_CABIN_PROGRESS, 0);
        }
    }

    public boolean boardPassenger(Entity passenger)
    {
        int stage = this.getInsertionStage();
        if (this.level().isClientSide
                || (stage != STAGE_SUSPENDED
                    && stage != STAGE_FIELD_LANDED)
                || this.isVehicle()
                || passenger.isPassenger())
        {
            return false;
        }
        int epoch = this.getInsertionEpoch();
        // Publish OCCUPIED before the vanilla ride callback runs.  Passenger
        // callbacks may query the capsule immediately; leaving it SUSPENDED
        // during startRiding made both real and dummy pilots intermittently
        // reject an otherwise valid docked plug.
        if (!this.transitionInsertionStage(stage, epoch, STAGE_OCCUPIED))
        {
            return false;
        }
        if (!passenger.startRiding(this, true))
        {
            this.transitionInsertionStage(STAGE_OCCUPIED,
                    this.getInsertionEpoch(), stage);
            if (this.tickCount >= this.nextBoardingDiagnosticTick)
            {
                this.nextBoardingDiagnosticTick = this.tickCount + 20;
                com.projectseele.ProjectSeele.LOGGER.warn(
                        "NERV entry-plug boarding rejected by ride graph: eva={} plug={} pilot={} stage={} pilotVehicle={}",
                        this.getAssignedVariant(), this.getStringUUID(),
                        passenger.getStringUUID(), stage,
                        passenger.getVehicle() == null ? "none"
                                : passenger.getVehicle().getStringUUID());
            }
            return false;
        }
        if (this.level() instanceof net.minecraft.server.level.ServerLevel
                serverLevel)
        {
            if(this.laboratorySlotR47()<0)EntryPlugDirector.claimBoardedPlug(serverLevel, this);
        }
        this.sealCabin();
        this.level().playSound(null, this.blockPosition(),
                SoundEvents.IRON_TRAPDOOR_CLOSE, SoundSource.BLOCKS,
                1.2F, 0.72F);
        return true;
    }

    @Override
    public float getPickRadius()
    {
        // The imported shell and its open hatch are wider than the entity's
        // slim insertion collision body.  This only extends selection; the
        // server still validates hatch state, range and line of sight.
        return 3.5F;
    }

    @Override
    public boolean isPickable()
    {
        return this.entityData.get(DATA_SHELL_VISIBLE);
    }

    @Override
    public boolean canBeCollidedWith()
    {
        return this.entityData.get(DATA_SHELL_VISIBLE);
    }

    /**
     * Server-authoritative hatch interaction for the physical capsule.
     *
     * <p>The client extends the use ray because the imported shell is much
     * larger than a vanilla interaction target. This method repeats every
     * meaningful gate so a packet cannot board a sealed or remote plug.
     */
    public InteractionResult tryBoardFromHatch(Player player)
    {
        if (this.level().isClientSide)
        {
            return InteractionResult.SUCCESS;
        }
        if ((isIndependentUNPlug() && getLinkedEva()!=null && getLinkedEva().isNervLogisticsLocked()) || !this.isHatchOpen() || this.getInsertionStage() != STAGE_SUSPENDED
                || this.isVehicle() || player.isPassenger())
        {
            player.displayClientMessage(Component.literal(
                    "Entry-plug hatch is sealed or under crane control."), true);
            return InteractionResult.CONSUME;
        }
        Vec3 eye = player.getEyePosition();
        Vec3 hatch = this.hasCanonicalPose()
                ? this.transformPlugMarker(
                        EntryPlugKinematics.HATCH_PORTAL_CENTRE_P)
                : this.getBoundingBox().getCenter();
        Vec3 direction = hatch.subtract(eye);
        double interactionRange = EvaScale.ENTRY_PLUG_INTERACTION_RANGE;
        if (direction.lengthSqr() > interactionRange * interactionRange
                || direction.lengthSqr() < 1.0E-4D
                || direction.normalize().dot(player.getViewVector(1.0F))
                        < 0.35D)
        {
            player.displayClientMessage(Component.literal(
                    "Stand on the boarding bridge and face the entry-plug hatch."),
                    true);
            return InteractionResult.CONSUME;
        }
        net.minecraft.world.phys.BlockHitResult hit = this.level().clip(
                new ClipContext(eye, hatch, ClipContext.Block.COLLIDER,
                        ClipContext.Fluid.NONE, player));
        if (hit.getType() != HitResult.Type.MISS
                && hit.getLocation().distanceToSqr(hatch) > 3.0D * 3.0D)
        {
            player.displayClientMessage(Component.literal(
                    "Entry-plug hatch is obstructed."), true);
            return InteractionResult.CONSUME;
        }
        return this.boardPassenger(player)
                ? InteractionResult.CONSUME : InteractionResult.FAIL;
    }

    @Override
    public InteractionResult mobInteract(Player player, InteractionHand hand)
    {
        if (this.level().isClientSide)
        {
            return InteractionResult.SUCCESS;
        }
        if (this.getInsertionStage() == STAGE_INSERTING)
        {
            player.displayClientMessage(Component.literal(
                    "Entry plug is already under crane control."), true);
            return InteractionResult.CONSUME;
        }
        Entity occupant = this.getFirstPassenger();
        if (occupant != null)
        {
            // A seated pilot is invisible — they are inside the capsule — so
            // naming the occupant is the only way to tell a boarded plug from
            // one that is wrongly reporting itself full.
            player.displayClientMessage(Component.literal(
                    "Entry plug is already occupied by "
                            + occupant.getName().getString()
                            + " (/seele eva dummy stop to clear)."), true);
            return InteractionResult.CONSUME;
        }
        return this.tryBoardFromHatch(player);
    }

    @Override
    protected boolean canAddPassenger(Entity passenger)
    {
        return this.getPassengers().isEmpty()
                && (passenger instanceof Player
                    || passenger instanceof TrainingPilotEntity);
    }

    @Override
    protected void removePassenger(Entity passenger)
    {
        passengerAuthorityTraceR44(passenger,"plug_before_remove_passenger");
        super.removePassenger(passenger);
        // A client passenger-list refresh must not abort insertion, open the
        // cabin or change synchronized progress. The server owns those edges.
        if(this.level().isClientSide){passengerAuthorityTraceR44(passenger,"plug_after_client_graph_only");return;}
        if(this.laboratorySlotR47()>=0)
        {
            com.projectseele.world.SynchLabDirectorR47.passengerRemovedR47(this,passenger);
            return;
        }
        if (this.getInsertionStage() == STAGE_INSERTING)
        {
            // Losing the pilot is an abort request, not permission to open a
            // pressure hatch halfway through the EVA/bridge sweep volume.
            this.requestInsertionAbort();
        }
        else if (this.getInsertionStage() == STAGE_OCCUPIED)
        {
            // A pilot may climb back out while the same capsule is safely at
            // its dock.  Publish SUSPENDED before opening so openCabin cannot
            // accidentally authorize an OCCUPIED capsule elsewhere.
            this.transitionInsertionStage(STAGE_OCCUPIED,
                    this.getInsertionEpoch(), STAGE_SUSPENDED);
            this.openCabin();
        }
        else
        {
            this.openCabin();
        }
        if (passenger instanceof Player player)
        {
            // Reveal the pilot when they climb out of the plug. A plug->EVA
            // insertion transfer shows the body for a single tick before the
            // airframe hides it again, which is imperceptible.
            player.setInvisible(false);
            // The plug can sit high on the airframe's back after an ejection, so
            // glide the pilot down instead of dropping them to their death.
            if (!this.level().isClientSide)
            {
                player.addEffect(new MobEffectInstance(
                        MobEffects.SLOW_FALLING, 20 * 12, 0));
            }
        }
        passengerAuthorityTraceR44(passenger,"plug_after_authoritative_remove_cleanup");
    }
    private void passengerAuthorityTraceR44(Entity passenger,String stage)
    {
        if(!com.projectseele.visual.PassengerAuthorityWitnessR44.enabled())return;
        var fields=new com.google.gson.JsonObject();fields.addProperty("insertion_stage",this.getInsertionStage());fields.addProperty("insertion_epoch",this.getInsertionEpoch());
        fields.addProperty("abort_requested",this.isInsertionAbortRequested());fields.addProperty("host_uuid",this.hostEvaUuid==null?"":this.hostEvaUuid.toString());
        fields.addProperty("host_id",this.entityData.get(DATA_HOST_EVA_ID));fields.addProperty("shell_visible",this.entityData.get(DATA_SHELL_VISIBLE));
        fields.addProperty("cabin_stage",this.getCabinStage());fields.addProperty("cabin_progress",this.getCabinProgress());
        com.projectseele.visual.PassengerAuthorityWitnessR44.capture(this,passenger,stage,fields);
    }

    @Override
    protected void positionRider(Entity passenger, Entity.MoveFunction move)
    {
        if (!this.hasPassenger(passenger))
        {
            return;
        }
        Vec3 seat = this.hasCanonicalPose()
                ? this.transformPlugMarker(EntryPlugKinematics.PILOT_SEAT_P)
                : this.position().add(0.0D, 0.35D, 0.0D);
        EvaUnit01Entity linkedEva = this.getLinkedEva();
        if (this.isLockedToEva() && linkedEva != null)
        {
            seat = linkedEva.getPilotCameraSeatPosition(passenger);
        }
        move.accept(passenger, seat.x,
                this.isLockedToEva() && linkedEva != null
                        ? seat.y : seat.y - passenger.getBbHeight() * 0.5D,
                seat.z);
        if (this.isLockedToEva())
        {
            // Once optical synchronization is live, mouse look belongs to the
            // EVA. During crane motion the capsule frame still owns yaw/pitch.
            return;
        }
        if (passenger instanceof Player)
        {
            /*
             * Never fight a real pilot's mouse at 20 Hz.  The former code
             * rewrote yaw and pitch from the plug frame every server tick;
             * client mouse-look then moved between those packets and snapped
             * back on the next one.  From first person that made both the plug
             * and every fixed cage prop appear to jitter or flicker whenever
             * the player looked around.  The capsule still owns the passenger
             * position, while a human remains free to look around the cabin.
             */
            return;
        }
        Vec3 view = this.hasCanonicalPose()
                ? this.getCanonicalTransform().transformVector(
                        EntryPlugKinematics.PILOT_VIEW_FORWARD_P)
                : this.getLookAngle();
        float yaw = (float) Math.toDegrees(
                Math.atan2(-view.x, view.z));
        float pitch = (float) Math.toDegrees(
                Math.asin(-Math.max(-1.0D, Math.min(1.0D, view.y))));
        passenger.setYRot(yaw);
        passenger.setXRot(pitch);
    }

    /** Immediately reconciles the nested pilot after the host EVA teleports. */
    public void syncPilotPositionNow()
    {
        for (Entity passenger : this.getPassengers())
        {
            this.positionRider(passenger,
                    (entity, x, y, z) ->
                    {
                        entity.setPos(x, y, z);
                        entity.xo = x;
                        entity.yo = y;
                        entity.zo = z;
                        entity.setDeltaMovement(Vec3.ZERO);
                        entity.fallDistance = 0.0F;
                    });
        }
    }

    @Override
    public Vec3 getDismountLocationForPassenger(
            net.minecraft.world.entity.LivingEntity passenger)
    {
        if(this.laboratorySlotR47()>=0)
            return new Vec3(this.laboratoryDockR47.translation().x-4,-468,-117.5);
        /*
         * At the wet cage the reviewed boarding endpoint is authoritative.
         * Searching down from the capsule first used to find incidental solid
         * faces as much as twenty blocks below the bridge, then drop the pilot
         * into the surrounding LCL.  Prefer the actual bridge/service landing
         * while the capsule is docked.
         */
        Vec3 dockExit = this.findDockBoardingDismount(passenger, 3);
        if (dockExit != null)
        {
            return dockExit;
        }

        Vec3 preferred;
        if (!this.hasCanonicalPose())
        {
            float radians = (float) Math.toRadians(this.getYRot());
            preferred = this.position().add(Math.cos(radians) * 2.0D,
                    -2.0D, Math.sin(radians) * 2.0D);
            Vec3 safe = this.findDryDismount(passenger, preferred);
            if (safe != null)
            {
                return safe;
            }
            Vec3 boarding = this.formalDockBoardingAnchor();
            return boarding != null ? boarding : passenger.position();
        }
        Vec3 left = this.transformPlugMarker(
                EntryPlugKinematics.PILOT_DISMOUNT_LEFT_P);
        Vec3 right = this.transformPlugMarker(
                EntryPlugKinematics.PILOT_DISMOUNT_RIGHT_P);
        Vec3 safeLeft = this.findDryDismount(passenger, left);
        if (safeLeft != null)
        {
            return safeLeft;
        }
        Vec3 safeRight = this.findDryDismount(passenger, right);
        if (safeRight != null)
        {
            return safeRight;
        }
        if (this.getInsertionStage() == STAGE_FIELD_LANDED)
        {
            // A field-ejected capsule has no relationship to the wet-cage
            // boarding bridge.  The former generic fallback used that bridge
            // and teleported a surviving pilot hundreds of blocks back into
            // the hangar. Search only around the landed capsule; if damaged
            // terrain offers no proven standing cell, remain beside it under
            // the slow-falling protection granted by removePassenger().
            Vec3 local = this.findDryDismount(passenger,
                    this.position(), 12);
            return local != null ? local
                    : this.position().add(0.0D, 0.75D, 0.0D);
        }
        Vec3 safeBoarding = this.findDockBoardingDismount(passenger, 12);
        if (safeBoarding != null)
        {
            return safeBoarding;
        }
        // A docked capsule is suspended over LCL, so the passenger's current
        // vehicle-space coordinate is never a safe last resort.  Fall back to
        // the reviewed bridge endpoint even if damaged scenery prevented the
        // collision scan from proving a nearby standing cell.
        Vec3 boarding = this.formalDockBoardingAnchor();
        return boarding != null ? boarding : passenger.position();
    }

    @Nullable
    private Vec3 findDockBoardingDismount(LivingEntity passenger,
                                          int horizontalRadius)
    {
        int stage = this.getInsertionStage();
        if (!(this.level() instanceof ServerLevel server)
                || this.isPassenger()
                || (stage != STAGE_SUSPENDED && stage != STAGE_OCCUPIED
                    && stage != STAGE_ABORT_DOCKED))
        {
            return null;
        }
        Vec3 boarding = this.formalDockBoardingAnchor();
        if (boarding == null)
        {
            return null;
        }
        return this.findDryDismount(passenger,
                boarding, horizontalRadius);
    }

    @Nullable
    private Vec3 formalDockBoardingAnchor()
    {
        if(isIndependentUNPlug())
        {
            EvaUnit01Entity host=getLinkedEva();
            if(host instanceof EvaPrototypeEntity un && com.projectseele.world.UNPlugDirector.atDock(un))
                return com.projectseele.world.UNPlugDirector.dock(un).transformPoint(EntryPlugKinematics.HATCH_PORTAL_CENTRE_P).add(4,-1.6,0);
            return null;
        }
        if (!(this.level() instanceof ServerLevel server))
        {
            return null;
        }
        int variant = this.getAssignedVariant();
        BlockPos boarding = FacilityV2EvaRuntime.ready(server, variant)
                ? FacilityV2EvaRuntime.boardingPosition(server, variant)
                : EvaHangarBuilder.boardingPosition(
                        com.projectseele.world.RegionalFacilityLayout.evaOrigin(server), variant);
        return Vec3.atBottomCenterOf(boarding);
    }

    /** Finds a real catwalk floor and never ejects a pilot into wet-cage LCL. */
    @Nullable
    private Vec3 findDryDismount(LivingEntity passenger, Vec3 anchor)
    {
        return this.findDryDismount(passenger, anchor, 12);
    }

    @Nullable
    private Vec3 findDryDismount(LivingEntity passenger, Vec3 anchor,
                                 int horizontalRadius)
    {
        BlockPos centre = BlockPos.containing(anchor);
        for (int radius = 0; radius <= horizontalRadius; radius++)
        {
            for (int dy : SAFE_DISMOUNT_VERTICAL_OFFSETS)
            {
                for (int dx = -radius; dx <= radius; dx++)
                {
                    for (int dz = -radius; dz <= radius; dz++)
                    {
                        if (radius > 0 && Math.max(Math.abs(dx), Math.abs(dz))
                                != radius)
                        {
                            continue;
                        }
                        BlockPos floor = centre.offset(dx, dy - 1, dz);
                        BlockPos feet = floor.above();
                        BlockPos head = feet.above();
                        if (!this.level().getBlockState(floor)
                                .isFaceSturdy(this.level(), floor, Direction.UP)
                                || !this.level().getFluidState(feet).isEmpty()
                                || !this.level().getFluidState(head).isEmpty()
                                || !this.level().getBlockState(feet)
                                        .getCollisionShape(this.level(), feet)
                                        .isEmpty()
                                || !this.level().getBlockState(head)
                                        .getCollisionShape(this.level(), head)
                                        .isEmpty())
                        {
                            continue;
                        }
                        Vec3 candidate = new Vec3(feet.getX() + 0.5D,
                                feet.getY(), feet.getZ() + 0.5D);
                        AABB moved = passenger.getBoundingBox().move(
                                candidate.subtract(passenger.position()));
                        if (this.level().noCollision(passenger, moved))
                        {
                            return candidate;
                        }
                    }
                }
            }
        }
        return null;
    }

    @Override
    public void tick()
    {
        if(this.laboratorySlotR47()<0&&this.level() instanceof ServerLevel level&&com.projectseele.world.EntryPlugDisposalR31.destroyed(level,this.getUUID()))
        {this.discard();return;}
        super.tick();
        if(!this.level().isClientSide&&this.isIndependentUNPlug())
            com.projectseele.world.UNRecoveryR22.remember(this);
        this.noPhysics = true;
        this.setNoGravity(true);
        this.setDeltaMovement(Vec3.ZERO);
        this.fallDistance = 0.0F;
        if (!this.level().isClientSide
                && this.entityData.get(DATA_SHELL_VISIBLE))
        {
            this.keepPlayersOutsideShell();
        }
        for (Entity passenger : this.getPassengers())
        {
            this.positionRider(passenger, Entity::setPos);
        }
        if(this.laboratorySlotR47()>=0)
        {
            if(!this.level().isClientSide)
            {
                int hatch=this.entityData.get(DATA_HATCH_OPEN);
                int target=this.getCabinStage()==CABIN_OPEN?100:0;
                if(hatch!=target&&(target>hatch||!this.hatchClosingObstructed()))
                    this.entityData.set(DATA_HATCH_OPEN,Mth.clamp(hatch+(target>hatch?8:-8),0,100));
            }
            return;
        }
        if (!this.level().isClientSide)
        {
            if (this.getInsertionStage() == STAGE_LOCKED)
            {
                EvaUnit01Entity host = this.getLinkedEva();
                if (host != null)
                {
                    this.hostEvaUuid = host.getUUID();
                    this.entityData.set(DATA_HOST_EVA_ID, host.getId());
                    RigidTransform wanted =
                            host.getEntryPlugSocketTransform()
                                    .compose(this.lockedSocketToPlug);
                    RigidTransform current = this.getCanonicalTransform();
                    if (current.translation().distanceToSqr(
                            wanted.translation()) > 1.0E-6D
                            || current.rotationErrorDegrees(wanted)
                            > 0.01D)
                    {
                        this.setCanonicalTransform(wanted);
                    }
                    if (this.getVehicle() != host && !this.startRiding(host, true))
                    {
                        host.markEntryPlugLinkFault(this);
                    }
                    else
                    {
                        this.entityData.set(DATA_SHELL_VISIBLE, false);
                    }
                }
            }
            int hatch = this.entityData.get(DATA_HATCH_OPEN);
            int target = this.getCabinStage() == CABIN_OPEN
                    && !this.isVehicle() ? 100 : 0;
            if (hatch != target)
            {
                boolean closingObstructed = target == 0 && hatch > 0
                        && this.hatchClosingObstructed();
                if (!closingObstructed)
                {
                    int step = target > hatch ? 8 : -8;
                    this.entityData.set(DATA_HATCH_OPEN,
                            Math.max(0, Math.min(100, hatch + step)));
                }
            }
            if (this.getInsertionStage() == STAGE_EJECTING)
            {
                // Driven from the capsule itself: the logistics tick calls
                // ensureSuspended every tick while an EVA is parked, which would
                // otherwise snap the plug — pilot aboard — straight back to its
                // cage instead of letting the crane withdraw it.
                if(!this.refreshTvPersonnelWetHoldR44())
                {
                    this.ejectionTicks++;
                    EntryPlugDirector.tickEjection(this, this.ejectionTicks);
                }
            }
            else if (this.getInsertionStage() == STAGE_FIELD_EJECTING)
            {
                this.entityData.set(DATA_TV_WET_EJECTION_HELD_R44,false);
                this.ejectionTicks++;
                EntryPlugDirector.tickFieldEjection(this, this.ejectionTicks);
            }
            else
            {
                this.entityData.set(DATA_TV_WET_EJECTION_HELD_R44,false);
                this.ejectionTicks = 0;
            }
            EntryPlugDirector.keepPassengerState(this);
        }
    }

    /**
     * The crane must remain no-physics so blocks cannot derail its scripted
     * path, but that normally also lets a standing player enter the rendered
     * capsule and make it disappear at the near plane.  Resolve only foreign
     * players against the authored oriented body box; the seated pilot is an
     * intentional occupant and is excluded.
     */
    private void keepPlayersOutsideShell()
    {
        if (!this.hasCanonicalPose())
        {
            return;
        }
        RigidTransform pose = this.getCanonicalTransform();
        AABB envelope = EntryPlugKinematics.worldBounds(pose,
                EntryPlugKinematics.BODY_OBB_CENTRE_P,
                EntryPlugKinematics.BODY_OBB_HALF_EXTENTS)
                .inflate(0.45D);
        RigidTransform inverse = pose.inverse();
        Vec3 axisX = pose.transformVector(new Vec3(1.0D, 0.0D, 0.0D));
        Vec3 axisY = pose.transformVector(new Vec3(0.0D, 1.0D, 0.0D));
        Vec3 axisZ = pose.transformVector(new Vec3(0.0D, 0.0D, 1.0D));
        for (Player player : this.level().getEntitiesOfClass(Player.class,
                envelope, candidate -> !candidate.isSpectator()
                        && !this.hasPassenger(candidate)))
        {
            AABB playerBox = player.getBoundingBox();
            Vec3 centre = playerBox.getCenter();
            Vec3 local = inverse.transformPoint(centre)
                    .subtract(EntryPlugKinematics.BODY_OBB_CENTRE_P);
            double halfX = playerBox.getXsize() * 0.5D;
            double halfY = playerBox.getYsize() * 0.5D;
            double halfZ = playerBox.getZsize() * 0.5D;
            double projectedX = projectedHalfExtent(
                    axisX, halfX, halfY, halfZ);
            double projectedY = projectedHalfExtent(
                    axisY, halfX, halfY, halfZ);
            double projectedZ = projectedHalfExtent(
                    axisZ, halfX, halfY, halfZ);
            double penetrationX =
                    EntryPlugKinematics.BODY_OBB_HALF_EXTENTS.x
                            + projectedX - Math.abs(local.x);
            double penetrationY =
                    EntryPlugKinematics.BODY_OBB_HALF_EXTENTS.y
                            + projectedY - Math.abs(local.y);
            double penetrationZ =
                    EntryPlugKinematics.BODY_OBB_HALF_EXTENTS.z
                            + projectedZ - Math.abs(local.z);
            if (penetrationX <= 0.0D || penetrationY <= 0.0D
                    || penetrationZ <= 0.0D)
            {
                continue;
            }

            Vec3 escapeAxis = axisX;
            double localCoordinate = local.x;
            double penetration = penetrationX;
            if (penetrationY < penetration)
            {
                escapeAxis = axisY;
                localCoordinate = local.y;
                penetration = penetrationY;
            }
            if (penetrationZ < penetration)
            {
                escapeAxis = axisZ;
                localCoordinate = local.z;
                penetration = penetrationZ;
            }
            double side = localCoordinate < 0.0D ? -1.0D : 1.0D;
            Vec3 correction = escapeAxis.scale(side * (penetration + 0.04D));
            Vec3 corrected = player.position().add(correction);
            if (player instanceof ServerPlayer serverPlayer)
            {
                /*
                 * setPos alone is not an authoritative client correction for
                 * a remote player.  The client can consequently spend several
                 * frames inside the no-physics shell, clip its near plane and
                 * make the capsule appear to vanish.  Publish the exact OBB
                 * escape while preserving the observer's view direction.
                 */
                serverPlayer.connection.teleport(
                        corrected.x, corrected.y, corrected.z,
                        serverPlayer.getYRot(), serverPlayer.getXRot());
            }
            else
            {
                player.setPos(corrected);
            }
            player.hasImpulse = true;
            player.hurtMarked = true;
            Vec3 velocity = player.getDeltaMovement();
            double inwardVelocity = velocity.dot(escapeAxis) * side;
            if (inwardVelocity < 0.0D)
            {
                player.setDeltaMovement(velocity.subtract(
                        escapeAxis.scale(inwardVelocity * side)));
            }
        }
    }

    /** Plays the cockpit sequence backwards while the capsule is extracted. */
    public void setCabinRecoveryProgress(int progress)
    {
        int safe = Math.max(0, Math.min(CABIN_TRANSFER_PERCENT, progress));
        if (safe <= 0)
        {
            this.entityData.set(DATA_CABIN_PROGRESS, 0);
            this.entityData.set(DATA_CABIN_STAGE, CABIN_RECOVERED_IDLE);
            return;
        }
        this.setCabinSequenceProgress(safe);
    }

    private static double projectedHalfExtent(Vec3 axis,
                                               double halfX,
                                               double halfY,
                                               double halfZ)
    {
        return Math.abs(axis.x) * halfX
                + Math.abs(axis.y) * halfY
                + Math.abs(axis.z) * halfZ;
    }

    /** Holds the physical door open while any foreign collision occupies the
     * complete left/right leaf sweep. The seated pilot and host airframe are
     * authored occupants, not obstructions. */
    private boolean hatchClosingObstructed()
    {
        if (!this.hasCanonicalPose())
        {
            return false;
        }
        net.minecraft.world.phys.AABB sweep =
                EntryPlugKinematics.hatchClosingSweep(
                        this.getCanonicalTransform()).deflate(0.025D);
        if (this.level().getBlockCollisions(this, sweep).iterator().hasNext())
        {
            return true;
        }
        EvaUnit01Entity host = this.getLinkedEva();
        return !this.level().getEntities(this, sweep, entity ->
                entity.isAlive() && entity != host
                        && !this.hasPassenger(entity)
                        && entity.isPickable()).isEmpty();
    }

    @Override
    public boolean hurt(DamageSource source, float amount)
    {
        if(this.level().isClientSide)return this.getInsertionStage()==STAGE_FIELD_LANDED&&!this.isVehicle()&&!this.isPassenger();
        if(!(amount>0)||this.isInvulnerableTo(source))return false;
        return com.projectseele.world.EntryPlugDisposalR31.destroyLanded(this);
    }

    @Override
    public boolean isPushable()
    {
        return false;
    }

    @Override
    public boolean removeWhenFarAway(double distanceToClosestPlayer)
    {
        return false;
    }

    @Override
    public void addAdditionalSaveData(CompoundTag tag)
    {
        super.addAdditionalSaveData(tag);
        if(this.laboratorySlotR47()>=0)
        {
            tag.putInt("LaboratorySlotR47",this.laboratorySlotR47());var dock=this.laboratoryDockR47;
            tag.putDouble("LaboratoryX",dock.translation().x);tag.putDouble("LaboratoryY",dock.translation().y);tag.putDouble("LaboratoryZ",dock.translation().z);
            tag.putFloat("LaboratoryQx",dock.qx());tag.putFloat("LaboratoryQy",dock.qy());tag.putFloat("LaboratoryQz",dock.qz());tag.putFloat("LaboratoryQw",dock.qw());
        }
        tag.putBoolean("IndependentUN",isIndependentUNPlug());
        tag.putInt("EvaVariant", this.getAssignedVariant());
        tag.putInt("InsertionStage", this.getInsertionStage());
        tag.putInt("InsertionEpoch", this.getInsertionEpoch());
        tag.putInt("InsertionProgress", this.getInsertionProgress());
        tag.putInt("CabinStage", this.getCabinStage());
        tag.putInt("CabinProgress", this.getCabinProgress());
        tag.putInt("HatchOpen", this.entityData.get(DATA_HATCH_OPEN));
        tag.putBoolean("CanonicalPose", this.hasCanonicalPose());
        tag.putFloat("PoseQX", this.entityData.get(DATA_POSE_QX));
        tag.putFloat("PoseQY", this.entityData.get(DATA_POSE_QY));
        tag.putFloat("PoseQZ", this.entityData.get(DATA_POSE_QZ));
        tag.putFloat("PoseQW", this.entityData.get(DATA_POSE_QW));
        if (this.hostEvaUuid != null)
        {
            tag.putUUID("HostEva", this.hostEvaUuid);
        }
        tag.putBoolean("ShellVisible", this.isShellVisible());
        tag.putBoolean("InsertionAbortRequested",
                this.isInsertionAbortRequested());
        putTransform(tag, "LockedSocketToPlug", this.lockedSocketToPlug);
        tag.putInt("EjectionTicks", this.ejectionTicks);
        putVector(tag, "FieldStart", this.fieldEjectionStart);
        putVector(tag, "FieldEscape", this.fieldEjectionEscape);
        putVector(tag, "FieldLanding", this.fieldEjectionLanding);
        this.saveTvPersonnelWetR44(tag);
    }

    @Override
    public void readAdditionalSaveData(CompoundTag tag)
    {
        super.readAdditionalSaveData(tag);
        this.entityData.set(DATA_LAB_SLOT_R47,tag.contains("LaboratorySlotR47")?tag.getInt("LaboratorySlotR47"):-1);
        if(this.laboratorySlotR47()>=0)
            this.laboratoryDockR47=new RigidTransform(new Vec3(tag.getDouble("LaboratoryX"),tag.getDouble("LaboratoryY"),tag.getDouble("LaboratoryZ")),
                    tag.getFloat("LaboratoryQx"),tag.getFloat("LaboratoryQy"),tag.getFloat("LaboratoryQz"),tag.getFloat("LaboratoryQw"));
        entityData.set(DATA_INDEPENDENT_UN,tag.getBoolean("IndependentUN"));
        if (tag.contains("EvaVariant"))
        {
            this.assignVariant(tag.getInt("EvaVariant"));
        }
        if (tag.contains("InsertionStage"))
        {
            this.entityData.set(DATA_STAGE, Math.max(STAGE_SUSPENDED,
                    Math.min(STAGE_ABORT_DOCKED,
                            tag.getInt("InsertionStage"))));
        }
        this.entityData.set(DATA_STAGE_EPOCH, Math.max(0,
                tag.getInt("InsertionEpoch")));
        if (tag.contains("InsertionProgress"))
        {
            this.setInsertionProgress(tag.getInt("InsertionProgress"));
        }
        if (tag.contains("CabinStage"))
        {
            this.entityData.set(DATA_CABIN_STAGE, Math.max(CABIN_OPEN,
                    Math.min(CABIN_RECOVERED_IDLE,
                            tag.getInt("CabinStage"))));
            this.entityData.set(DATA_CABIN_PROGRESS, Math.max(0,
                    Math.min(CABIN_TRANSFER_PERCENT,
                            tag.getInt("CabinProgress"))));
        }
        else if (this.isVehicle())
        {
            this.sealCabin();
        }
        if (tag.contains("HatchOpen"))
        {
            this.entityData.set(DATA_HATCH_OPEN, Math.max(0,
                    Math.min(100, tag.getInt("HatchOpen"))));
        }
        else
        {
            this.entityData.set(DATA_HATCH_OPEN,
                    this.getCabinStage() == CABIN_OPEN ? 100 : 0);
        }
        if (tag.getBoolean("CanonicalPose"))
        {
            RigidTransform saved = new RigidTransform(this.position(),
                    tag.getFloat("PoseQX"), tag.getFloat("PoseQY"),
                    tag.getFloat("PoseQZ"), tag.getFloat("PoseQW"));
            this.setCanonicalTransform(saved);
            this.clientPreviousRotation = new RigidTransform(Vec3.ZERO,
                    saved.qx(), saved.qy(), saved.qz(), saved.qw());
            this.clientCurrentRotation = this.clientPreviousRotation;
        }
        this.hostEvaUuid = tag.hasUUID("HostEva")
                ? tag.getUUID("HostEva") : null;
        this.entityData.set(DATA_HOST_EVA_ID, -1);
        this.entityData.set(DATA_SHELL_VISIBLE,
                tag.contains("ShellVisible")
                        ? tag.getBoolean("ShellVisible")
                        : this.getInsertionStage() != STAGE_LOCKED);
        this.entityData.set(DATA_ABORT_REQUESTED,
                tag.getBoolean("InsertionAbortRequested"));
        this.lockedSocketToPlug = getTransform(tag,
                "LockedSocketToPlug", this.lockedSocketToPlug);
        this.ejectionTicks = Math.max(0, tag.getInt("EjectionTicks"));
        this.fieldEjectionStart = getVector(tag, "FieldStart", this.position());
        this.fieldEjectionEscape = getVector(tag, "FieldEscape", this.position());
        this.fieldEjectionLanding = getVector(tag, "FieldLanding", this.position());
        this.loadTvPersonnelWetR44(tag);
    }

    public boolean tvPersonnelWetEjectionHeldR44(){return this.entityData.get(DATA_TV_WET_EJECTION_HELD_R44);}
    public int ejectionTicksR44(){return this.ejectionTicks;}
    public String tvPersonnelWetFaultR44(){return this.tvPersonnelWetFaultR44;}
    public boolean tvPersonnelWetPersistenceInvalidR44(){return this.tvPersonnelWetPersistenceInvalidR44;}
    public boolean hasSavedTvPersonnelOwnershipR44()
    {
        return this.tvPersonnelWetTagR44.hasUUID("Owner")&&this.tvPersonnelWetTagR44.getUUID("Owner").equals(this.getUUID())
                &&this.tvPersonnelWetTagR44.getString("Dimension").equals("projectseele:geofront");
    }
    public boolean refreshTvPersonnelWetHoldR44()
    {
        if(this.level().isClientSide)return this.tvPersonnelWetEjectionHeldR44();
        var decision=com.projectseele.world.TvPersonnelOwnedMotionR44.wetPlug(this);
        String fault=decision.owned()?(this.tvPersonnelWetPersistenceInvalidR44?"湿舱弹出时钟保存数据未知，保留原NBT。":decision.fault().orElse("")):"";
        boolean held=decision.owned()&&!fault.isEmpty();
        this.entityData.set(DATA_TV_WET_EJECTION_HELD_R44,held);this.tvPersonnelWetFaultR44=fault;
        if(held)
        {
            this.setDeltaMovement(Vec3.ZERO);
            if(this.laboratorySlotR47()<0)com.projectseele.world.TvPersonnelOwnedMotionR44.keepWetMachines((ServerLevel)this.level(),this.getAssignedVariant());
        }
        return held;
    }
    private void saveTvPersonnelWetR44(CompoundTag tag)
    {
        if(this.tvPersonnelWetPersistenceInvalidR44)
        {
            if(this.tvPersonnelWetOpaqueR44!=null)tag.put("TvPersonnelWetEjectionR44",this.tvPersonnelWetOpaqueR44.copy());
            else if(!this.tvPersonnelWetTagR44.isEmpty())tag.put("TvPersonnelWetEjectionR44",this.tvPersonnelWetTagR44.copy());
            return;
        }
        var decision=com.projectseele.world.TvPersonnelOwnedMotionR44.wetPlug(this);
        if(!decision.owned()&&this.tvPersonnelWetTagR44.isEmpty())return;
        CompoundTag saved=this.tvPersonnelWetTagR44.copy();saved.putInt("Version",1);saved.putUUID("Owner",this.getUUID());
        saved.putString("Dimension","projectseele:geofront");saved.putInt("Variant",this.getAssignedVariant());
        saved.putInt("StageEpoch",this.getInsertionEpoch());saved.putInt("EjectionTicks",this.ejectionTicks);
        saved.putBoolean("Active",decision.owned());saved.putBoolean("Held",this.tvPersonnelWetEjectionHeldR44());
        tag.put("TvPersonnelWetEjectionR44",saved);this.tvPersonnelWetTagR44=saved.copy();
    }
    private void loadTvPersonnelWetR44(CompoundTag tag)
    {
        if(!tag.contains("TvPersonnelWetEjectionR44"))return;
        if(!(tag.get("TvPersonnelWetEjectionR44") instanceof CompoundTag))
        {
            this.tvPersonnelWetOpaqueR44=tag.get("TvPersonnelWetEjectionR44").copy();this.tvPersonnelWetPersistenceInvalidR44=true;
        }
        else
        {
            this.tvPersonnelWetTagR44=tag.getCompound("TvPersonnelWetEjectionR44").copy();var saved=this.tvPersonnelWetTagR44;
            this.tvPersonnelWetPersistenceInvalidR44=saved.getInt("Version")!=1||!this.hasSavedTvPersonnelOwnershipR44()
                    ||saved.getInt("Variant")!=this.getAssignedVariant()||saved.getInt("StageEpoch")!=this.getInsertionEpoch()
                    ||saved.getInt("EjectionTicks")!=this.ejectionTicks;
        }
        // Read does not declare the plant clear. Initial metadata carries a
        // hold; the real loaded-section check in tick is the release authority.
        if(com.projectseele.world.TvPersonnelOwnedMotionR44.wetPlug(this).owned())
            this.entityData.set(DATA_TV_WET_EJECTION_HELD_R44,true);
    }

    private static void putVector(CompoundTag tag, String key, Vec3 value)
    {
        tag.putDouble(key + "X", value.x);
        tag.putDouble(key + "Y", value.y);
        tag.putDouble(key + "Z", value.z);
    }

    private static Vec3 getVector(CompoundTag tag, String key, Vec3 fallback)
    {
        if (!tag.contains(key + "X") || !tag.contains(key + "Y")
                || !tag.contains(key + "Z"))
        {
            return fallback;
        }
        return new Vec3(tag.getDouble(key + "X"), tag.getDouble(key + "Y"),
                tag.getDouble(key + "Z"));
    }

    private static void putTransform(CompoundTag tag, String key,
                                     RigidTransform transform)
    {
        putVector(tag, key + "T", transform.translation());
        tag.putFloat(key + "QX", transform.qx());
        tag.putFloat(key + "QY", transform.qy());
        tag.putFloat(key + "QZ", transform.qz());
        tag.putFloat(key + "QW", transform.qw());
    }

    private static RigidTransform getTransform(CompoundTag tag, String key,
                                               RigidTransform fallback)
    {
        if (!tag.contains(key + "QW"))
        {
            return fallback;
        }
        return new RigidTransform(getVector(tag, key + "T",
                fallback.translation()), tag.getFloat(key + "QX"),
                tag.getFloat(key + "QY"), tag.getFloat(key + "QZ"),
                tag.getFloat(key + "QW"));
    }

    @Override
    public void onSyncedDataUpdated(EntityDataAccessor<?> key)
    {
        super.onSyncedDataUpdated(key);
        if(!this.level().isClientSide)return;
        // SynchedEntityData packs its hash-map values, not accessor-ID order.
        // A sequence/epoch callback can therefore precede its quaternion fields.
        if(DATA_POSE_SEQUENCE.equals(key)||DATA_POSE_TRANSLATION.equals(key)||DATA_CANONICAL_POSE.equals(key)
                ||DATA_POSE_QX.equals(key)||DATA_POSE_QY.equals(key)||DATA_POSE_QZ.equals(key)||DATA_POSE_QW.equals(key))
            this.clientPoseBatchDirtyR49=true;
        if(DATA_STAGE_EPOCH.equals(key))this.clientStageBatchDirtyR49=true;
        if(DATA_HARD_POSE_R31.equals(key))this.clientHardBatchDirtyR49=true;
        if(DATA_CABIN_PROGRESS.equals(key))this.clientCabinBatchDirtyR49=true;
    }

    @Override
    public void onSyncedDataUpdated(java.util.List<SynchedEntityData.DataValue<?>> values)
    {
        super.onSyncedDataUpdated(values);
        if(!this.level().isClientSide)return;
        boolean poseChanged=this.clientPoseBatchDirtyR49;
        boolean hard=this.clientHardBatchDirtyR49;
        this.clientPoseBatchDirtyR49=this.clientStageBatchDirtyR49=this.clientHardBatchDirtyR49=false;
        if(this.clientCabinBatchDirtyR49)
        {
            this.clientCabinBatchDirtyR49=false;
            if(this.clientCabinProgressUpdateTick!=this.tickCount)
                this.clientPreviousCabinProgress=this.clientCurrentCabinProgress;
            this.clientCurrentCabinProgress=this.entityData.get(DATA_CABIN_PROGRESS);
            this.clientCabinProgressUpdateTick=this.tickCount;
        }
        // A stage label alone has no geometric displacement. Preserve the
        // current shell/camera blend; an explicit hard-pose generation snaps it.
        if(!this.hasCanonicalPose()||!poseChanged&&!hard)return;
        RigidTransform pose=this.getCanonicalTransform();
        RigidTransform rotation=new RigidTransform(Vec3.ZERO,pose.qx(),pose.qy(),pose.qz(),pose.qw());
        if(hard||!this.clientPoseInitialized)
        {
            this.clientPreviousPosePosition=this.clientCurrentPosePosition=pose.translation();
            this.clientPreviousRotation=this.clientCurrentRotation=rotation;
            this.clientRotationUpdateTick=Integer.MIN_VALUE;
            this.setPos(pose.translation());this.lerpSteps=0;
            this.xo=this.xOld=this.getX();this.yo=this.yOld=this.getY();this.zo=this.zOld=this.getZ();
            this.clientPoseInitialized=true;
        }
        else
        {
            // Several complete batches can arrive in one client tick. They
            // replace one target while retaining the same tick-start sample.
            if(this.clientRotationUpdateTick!=this.tickCount)
            {
                this.clientPreviousPosePosition=this.clientCurrentPosePosition;
                this.clientPreviousRotation=this.clientCurrentRotation;
            }
            this.clientCurrentPosePosition=pose.translation();this.clientCurrentRotation=rotation;
            this.clientRotationUpdateTick=this.tickCount;
            this.setPos(pose.translation());this.lerpSteps=0;
            this.xo=this.clientPreviousPosePosition.x;this.yo=this.clientPreviousPosePosition.y;this.zo=this.clientPreviousPosePosition.z;
        }
        for(Entity passenger:this.getPassengers())this.positionRider(passenger,Entity::setPos);
    }

    @Override
    public void registerControllers(
            AnimatableManager.ControllerRegistrar controllers)
    {
        // The logistics director supplies the physical transform.
    }

    @Override
    public AnimatableInstanceCache getAnimatableInstanceCache()
    {
        return this.geoCache;
    }
}
