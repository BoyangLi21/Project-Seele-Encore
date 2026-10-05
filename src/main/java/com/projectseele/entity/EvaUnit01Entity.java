package com.projectseele.entity;

import java.util.List;
import java.util.UUID;
import java.util.function.Function;

import com.projectseele.ProjectSeele;
import com.projectseele.capability.EvaPilotCapability;
import com.projectseele.capability.EvaPilotData;
import com.projectseele.config.SeeleConfig;
import com.projectseele.combat.AtFieldRules;
import com.projectseele.fx.AtFieldFX;
import com.projectseele.fx.StrategicExplosionDirector;
import com.projectseele.network.ClientboundCannonBeamPacket;
import com.projectseele.network.ClientboundEvaArrivalSyncPacket;
import com.projectseele.network.ClientboundNukeFxPacket;
import com.projectseele.network.ClientboundRifleTracerPacket;
import com.projectseele.network.SeeleNetwork;
import com.projectseele.registry.ModSounds;
import com.projectseele.registry.ModEntities;
import com.projectseele.world.IntegratedNervMapBuilder;
import com.projectseele.world.EvaHangarBuilder;
import com.projectseele.world.EvaLogisticsDirector;
import com.projectseele.world.EntryPlugDirector;
import com.projectseele.world.EntryPlugKinematics;
import com.projectseele.world.FacilityV2EvaRuntime;
import com.projectseele.world.NervCarrierVisuals;
import com.projectseele.world.PerformanceCounters;
import com.projectseele.world.RigidTransform;
import com.projectseele.world.UmbilicalPylonBlockEntity;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.Registries;
import net.minecraft.core.particles.DustParticleOptions;
import net.minecraft.core.particles.BlockParticleOption;
import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.ChatFormatting;
import net.minecraft.network.chat.Component;
import net.minecraft.network.protocol.game.ClientboundTeleportEntityPacket;
import net.minecraft.network.syncher.EntityDataAccessor;
import net.minecraft.network.syncher.EntityDataSerializers;
import net.minecraft.network.syncher.SynchedEntityData;
import net.minecraft.resources.ResourceKey;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.sounds.SoundEvent;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.sounds.SoundSource;
import net.minecraft.tags.DamageTypeTags;
import net.minecraft.util.Mth;
import net.minecraft.world.DifficultyInstance;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.damagesource.DamageTypes;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EntityDimensions;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.MobSpawnType;
import net.minecraft.world.entity.MoverType;
import net.minecraft.world.entity.PathfinderMob;
import net.minecraft.world.entity.Pose;
import net.minecraft.world.entity.SpawnGroupData;
import net.minecraft.world.entity.ai.attributes.AttributeSupplier;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.entity.projectile.ProjectileUtil;
import net.minecraft.world.level.ClipContext;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.ServerLevelAccessor;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.portal.PortalInfo;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraft.world.phys.EntityHitResult;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.common.ForgeMod;
import net.minecraftforge.common.util.ITeleporter;
import net.minecraftforge.network.PacketDistributor;
import org.jetbrains.annotations.Nullable;
import software.bernie.geckolib.animatable.GeoEntity;
import software.bernie.geckolib.core.animatable.instance.AnimatableInstanceCache;
import software.bernie.geckolib.core.animation.AnimatableManager;
import software.bernie.geckolib.core.animation.AnimationController;
import software.bernie.geckolib.core.animation.AnimationState;
import software.bernie.geckolib.core.animation.RawAnimation;
import software.bernie.geckolib.core.object.PlayState;
import software.bernie.geckolib.util.GeckoLibUtil;

/**
 * EVA Unit-01: rideable 60-block war machine and the pilot's body in every
 * Angel fight. Carries contact weapons, a positron cannon, automatic pallet
 * SMG and N2 self-destruct, plus an A.T. Field shield pool. All pilot input
 * arrives via {@code ServerboundEvaControlPacket}.
 */
public class EvaUnit01Entity extends PathfinderMob implements GeoEntity, FirstBattleSignals.Actor, com.projectseele.world.TvEncounterEquipmentControlR45.CannonAccess
{
    private static final boolean DORSAL_SIGNALS_READY=EvaDorsalMechanism.bootstrap() && EvaTerrainSupport.bootstrap() && EvaShutdownR30.bootstrap() && EvaAirTransportR31.bootstrap() && EvaCombatR31.bootstrap() && EvaGameplayMotionR32.bootstrap() && EvaCombatSupportR33.bootstrap() && EvaBayRepairR33.bootstrap() && EvaBerserkMotionR34.bootstrap() && EvaCapturedLocomotionR44.bootstrap() && EvaWeaponHandlingR45.bootstrap();
    private static final EntityDataAccessor<Integer> MECHANICAL_REVISION_R30=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.INT);
    private static final FirstBattleSignals.SignalSet FIRST_BATTLE=new FirstBattleSignals.SignalSet(EvaUnit01Entity.class);
    @Override public FirstBattleSignals.SignalSet firstBattleSignals(){return FIRST_BATTLE;}
    @Override public boolean isFirstBattleEva(){return true;}
    public boolean isFirstBattleActive(){return FIRST_BATTLE.active(this);}
    public void beginFirstBattle(FirstBattleSignals.Spec spec,int partner)
    {
        int oldWeapon=this.getWeapon();this.cancelLiveActionsForStanceChange();this.chargingHeld=false;this.selectWeapon(WEAPON_FISTS);
        FIRST_BATTLE.begin(this,spec,partner,oldWeapon);
    }
    public void endFirstBattle()
    {
        if(!isFirstBattleActive())return;int weapon=FIRST_BATTLE.end(this);this.cancelLiveActionsForStanceChange();
        if(EvaEquipmentPolicyR45.allowed(weapon,this.getUnitVariant(),this.isExperimentalUnit()))this.selectWeapon(weapon);
        this.wasAirborne=false;this.explicitJumpInProgress=false;this.explicitJumpObservedAirborne=false;this.clientExplicitJumpInProgress=false;this.clientJumpImpulsePending=false;this.fallDistance=0;
        this.syncPassengerAssembly();
    }
    public void completeFirstBattle()
    {
        var finalPose=FirstBattleClip.finalEvaPose(this);
        this.endFirstBattle();this.entityData.set(DATA_BERSERK,false);this.entityData.set(DATA_BERSERK_TICKS,0);this.berserkRecoveryTicks=0;
        EvaBerserkMotionR34.clear(this);EvaDorsalMechanism.afterBerserk(this);
        if(this.isPowerDepleted())EvaShutdownR30.restAfterFirstBattle(this,finalPose);
    }
    public static final int WEAPON_FISTS = 0;
    public static final int WEAPON_KNIFE = 1;
    public static final int WEAPON_CANNON = 2;
    public static final int WEAPON_LANCE = 3;
    public static final int WEAPON_RIFLE = 4;
    public static final int WEAPON_N2 = 5;
    public static final int WEAPON_SWORD_R45 = 6;
    public static final int WEAPON_SHIELD_R45 = 7;
    private static final int LAST_WEAPON_R45 = WEAPON_SHIELD_R45;
    public static final int ARMAMENT_MASK_FISTS = 1 << WEAPON_FISTS;
    public static final int ARMAMENT_MASK_KNIFE = 1 << WEAPON_KNIFE;
    public static final int ARMAMENT_MASK_RIFLE = 1 << WEAPON_RIFLE;
    public static final int ARMAMENT_MASK_N2 = 1 << WEAPON_N2;
    public static final int ARMAMENT_MASK_SWORD_R45 = 1 << WEAPON_SWORD_R45;
    public static final int ARMAMENT_MASK_SHIELD_R45 = 1 << WEAPON_SHIELD_R45;
    public static final int UNIT_00 = 0;
    public static final int UNIT_01 = 1;
    public static final int UNIT_02 = 2;

    public boolean isExperimentalUnit()
    {
        return false;
    }
    public String experimentalAssetName() { return "eva_prototype"; }
    public static final int VISUAL_NORMAL = 0;
    public static final int VISUAL_IDLE = 1;
    public static final int VISUAL_WALK_CONTACT = 2;
    public static final int VISUAL_KNIFE_WINDUP = 3;
    public static final int VISUAL_KNIFE_CONTACT = 4;
    public static final int VISUAL_KNIFE_RECOVERY = 5;
    public static final int VISUAL_CROUCH = 6;
    public static final int VISUAL_PRONE = 7;
    public static final int VISUAL_LANCE_WINDUP = 8;
    public static final int VISUAL_LANCE_CONTACT = 9;
    public static final int VISUAL_LANCE_RECOVERY = 10;
    public static final int VISUAL_CANNON = 11;
    public static final int VISUAL_PRONE_CANNON = 12;
    public static final int VISUAL_RUN_CONTACT = 13;
    public static final int VISUAL_JUMP = 14;
    public static final int VISUAL_FALL = 15;
    public static final int VISUAL_CROUCH_WALK = 16;
    public static final int VISUAL_CRAWL = 17;
    public static final int VISUAL_KNIFE_READY = 18;
    public static final int VISUAL_LANCE_READY = 19;
    public static final int VISUAL_RIFLE = 20;
    public static final int VISUAL_CROUCH_KNIFE_CONTACT = 21;
    public static final int VISUAL_PRONE_KNIFE_CONTACT = 22;
    public static final int VISUAL_CROUCH_LANCE_CONTACT = 23;
    public static final int VISUAL_PRONE_LANCE_CONTACT = 24;
    public static final int VISUAL_N2_READY = 25;
    public static final int VISUAL_RIFLE_WALK_CONTACT = 26;
    public static final int VISUAL_CROUCH_RIFLE_CONTACT = 27;
    public static final int VISUAL_PRONE_RIFLE = 28;
    public static final int VISUAL_LIVE_MELEE = 29;
    public static final int VISUAL_LIVE_KNIFE = 30;
    public static final int VISUAL_LIVE_LANCE = 31;
    public static final int VISUAL_LIVE_RIFLE = 32;
    public static final int VISUAL_LIVE_KNIFE_HEAVY = 33;
    public static final int VISUAL_LIVE_JUMP = 34;
    public static final int LAUNCH_IDLE = 0;
    public static final int LAUNCH_LOCKED = 1;
    public static final int LAUNCH_ASCENT = 2;
    public static final int LAUNCH_CLEAR = 3;
    public static final float SILO_BAY_YAW = 180.0F;

    private static final float MELEE_FIST_DAMAGE = 20.0F;
    private static final float MELEE_KNIFE_DAMAGE = 60.0F;
    private static final float MELEE_LANCE_DAMAGE = 120.0F;
    private static final int MELEE_COOLDOWN_TICKS = 12;
    private static final int MELEE_INPUT_BUFFER_TICKS = 16;
    private static final float ORDINARY_ATTACK_SOURCE_FPS = 60.0F;
    private static final float ORDINARY_ATTACK_PLAYBACK_SPEED = 1.5F;
    // Inclusive live clip ranges are 0..44, 45..107 and 108..140.
    // Store intervals rather than sample counts so phase 1.0 reaches the
    // exact final authored sample at the requested 1.5x playback speed.
    private static final int[] ORDINARY_ATTACK_FRAME_INTERVALS =
            {44, 62, 32};
    private static final int[] ORDINARY_ATTACK_CONTACT_FRAMES =
            {29, 48, 17};
    // Reach geometry follows the shared 60-block frame.
    private static final double MELEE_REACH = EvaScale.fromLegacy(10.0D);
    private static final double MELEE_RADIUS = EvaScale.fromLegacy(7.5D);
    // Smash: crouch + attack. Slow, heavy, area knockdown.
    private static final float SMASH_FIST_DAMAGE = 35.0F;
    private static final float SMASH_KNIFE_DAMAGE = 80.0F;
    private static final float SMASH_LANCE_DAMAGE = 160.0F;
    private static final int SMASH_COOLDOWN_TICKS = 60;
    private static final double SMASH_RADIUS = EvaScale.fromLegacy(11.0D);
    private static final float STOMP_DAMAGE = 50.0F;
    private static final int STOMP_COOLDOWN_TICKS = 50;
    private static final double STOMP_RADIUS = EvaScale.fromLegacy(9.4D);
    private static final float KICK_SOURCE_FPS = 60.0F;
    private static final float KICK_PLAYBACK_SPEED = 1.5F;
    private static final int KICK_FRAME_INTERVALS = 83;
    private static final int KICK_CONTACT_FRAME = 48;
    private static final float KNIFE_SOURCE_FPS = 60.0F;
    private static final int KNIFE_FORWARD_FRAME_INTERVALS = 172;
    private static final int KNIFE_REVERSE_FRAME_INTERVALS = 125;
    private static final int CROSS_ACTION_BUFFER_TICKS = 30;
    // First arrested thrust, before the held twist/retraction, in the 60 Hz clips.
    private static final int KNIFE_FORWARD_CONTACT_FRAME = 44;
    private static final int KNIFE_REVERSE_CONTACT_FRAME = 24;
    private static final float AT_FIELD_MAX = 200.0F;
    private static final float AT_FIELD_REGEN = 0.4F;
    private static final int AT_FIELD_REGEN_DELAY = 100;
    private static final float AT_FIELD_MIN_TO_RAISE = 20.0F;
    private static final float NORMAL_WIDTH = EvaScale.NORMAL_WIDTH;
    private static final float NORMAL_HEIGHT = EvaScale.NORMAL_HEIGHT;
    private static final float CROUCH_HEIGHT = EvaScale.CROUCH_HEIGHT;
    // Z is a true belly-down crawl: wide and very low, distinct from the
    // Shift kneel / Unit-00 shield brace.
    private static final float PRONE_WIDTH = EvaScale.PRONE_WIDTH;
    private static final float PRONE_HEIGHT = EvaScale.PRONE_HEIGHT;
    private static final float WALK_SPEED = 0.42F;
    private static final float CROUCH_SPEED = 0.18F;
    private static final float PRONE_SPEED = 0.10F;
    private static final float SPRINT_SPEED = 0.78F;
    private static final double JUMP_VELOCITY = 5.3D;
    private static final float MELEE_RATE_R43 = 1.5F;
    private static final double AIRFRAME_GRAVITY = 0.42D;
    private static final double JUMP_SUPPORT_PROBE = 0.75D;
    private static final int JUMP_COOLDOWN_TICKS = 10;
    private static final int JUMP_BUFFER_TICKS = 20;
    private static final int JUMP_COYOTE_TICKS = 5;
    private static final int PASSIVE_FALL_CONFIRM_TICKS = 6;
    private static final int PASSIVE_FALL_SPEED_CONFIRM_TICKS = 10;
    private static final double PASSIVE_FALL_MIN_SPEED = -1.50D;
    private static final double PASSIVE_FALL_MIN_DROP =
            EvaScale.fromLegacy(1.60D);
    private static final float PILOT_HEAD_YAW_LIMIT = 62.0F;
    private static final float PILOT_BODY_IDLE_DEAD_ZONE = 24.0F;
    private static final float PILOT_BODY_MOVING_DEAD_ZONE = 6.0F;
    private static final float PILOT_BODY_IDLE_TURN_PER_TICK = 2.5F;
    private static final float PILOT_BODY_MOVING_TURN_PER_TICK = 6.0F;
    private static final int LAUNCH_ASCENT_TICKS = 34;
    private static final int LAUNCH_CLEAR_TICKS = 18;
    private static final double LAUNCH_TARGET_ABOVE_BED =
            EvaScale.fromLegacy(32.0D);
    private static final double CONTINUOUS_ASCENT_BLOCKS_PER_TICK = 3.0D;
    private static final int CONTINUOUS_EXIT_HEADROOM = 82;
    private static final int LAUNCH_CARRIER_HALF =
            EvaHangarBuilder.CARRIER_HALF_EXTENT;
    // The pilot is nested EVA -> entry plug -> player.  A locally controlled
    // vehicle ignores the ordinary teleport correction at a shaft exit, so a
    // single packet was vulnerable to the following client ride tick putting
    // the camera back underground.  Three authoritative ticks are short
    // enough to avoid a visible carrier pause while making the complete ride
    // chain converge before control is returned.
    /*
     * Keep the authoritative sortie position alive for one full second.  A
     * locally controlled nested pilot ignores ordinary vehicle teleport
     * packets during a frame hitch; three ticks was too short and left the
     * first-person camera trapped at the bottom of the launch shaft.
     */
    private static final int CONTINUOUS_SURFACE_SYNC_TICKS = 20;
    private static final double SILO_ENTRY_MIN_HEIGHT =
            EvaScale.fromLegacy(24.0D);
    private static final double SILO_ENTRY_MAX_HEIGHT =
            EvaScale.fromLegacy(29.5D);
    private static final double SILO_ENTRY_MIN_REAR_DOT = 0.62D;
    private static final double SILO_ENTRY_MIN_DISTANCE =
            EvaScale.fromLegacy(0.75D);
    private static final double SILO_ENTRY_MAX_DISTANCE =
            EvaScale.fromLegacy(9.5D);
    private static final double ENTRY_PLUG_USE_REACH =
            EvaScale.fromLegacy(8.25D);
    private static final double ENTRY_PLUG_AIM_RADIUS =
            EvaScale.fromLegacy(2.0D);
    // Final entry-plug pivots in the reviewed 2.5x Tiger meshes. Keeping the
    // three sockets explicit makes interaction follow each airframe instead
    // of guessing from the entity AABB or a legacy cube body's chest.
    private static final double ENTRY_PLUG_HEIGHT_00 = 26.9164D;
    private static final double ENTRY_PLUG_HEIGHT_01 = 26.9170D;
    private static final double ENTRY_PLUG_HEIGHT_02 = 26.9178D;
    public static final double ENTRY_PLUG_REAR_OFFSET = 1.25D;
    private static final int LAUNCH_PASSENGER_RESTORE_GRACE_TICKS = 40;
    private static final int NO_LAUNCH_CARRIER = Integer.MIN_VALUE;
    /** Mechanical elevation envelope of the shared cannon/body aim rig. */
    public static final float MIN_CANNON_AIM_PITCH = -55.0F;
    public static final float MAX_CANNON_AIM_PITCH = 55.0F;
    // Muzzle sockets measured from the reviewed 2.5x Tiger rig and the
    // locally installed TV Pallet Rifle. The ray still starts at the pilot's
    // eye for fair aiming; tracers and sound start at the visible muzzle.
    // Re-measured from the current 5x Tiger rig and the installed 292-triangle
    // Pallet Rifle far cap. Preview coordinates are divided by 16 and then
    // multiplied by EvaScale.RENDER_SCALE; the previous legacy constants put
    // the tracer roughly six blocks beyond and three blocks above the barrel.
    private static final double RIFLE_STANDING_PIVOT_HEIGHT = 46.7184D;
    private static final double RIFLE_STANDING_PIVOT_FORWARD = 0.0D;
    private static final double RIFLE_STANDING_MUZZLE_FORWARD = 30.8104D;
    private static final double RIFLE_STANDING_MUZZLE_UP = 0.0D;
    private static final double RIFLE_STANDING_MUZZLE_RIGHT = 3.2323D;
    private static final double RIFLE_PRONE_PIVOT_HEIGHT = 9.4404D;
    private static final double RIFLE_PRONE_PIVOT_FORWARD = 0.0D;
    private static final double RIFLE_PRONE_MUZZLE_FORWARD = 49.5601D;
    private static final double RIFLE_PRONE_MUZZLE_UP = 0.0D;
    private static final double RIFLE_PRONE_MUZZLE_RIGHT = 5.5370D;
    // Far-cap coordinates measured from the installed Kantrophe positron
    // cannon after the final two-hand pose. The old 12.5-block approximation
    // began the beam inside the receiver, visibly behind the barrel.
    private static final double CANNON_STANDING_PIVOT_HEIGHT =
            EvaScale.fromLegacy(24.2201D);
    private static final double CANNON_STANDING_PIVOT_FORWARD =
            EvaScale.fromLegacy(0.0D);
    private static final double CANNON_STANDING_MUZZLE_FORWARD =
            EvaScale.fromLegacy(22.4417D);
    private static final double CANNON_STANDING_MUZZLE_UP =
            EvaScale.fromLegacy(0.5960D);
    private static final double CANNON_STANDING_MUZZLE_RIGHT =
            EvaScale.fromLegacy(1.2263D);
    private static final double CANNON_PRONE_PIVOT_HEIGHT =
            EvaScale.fromLegacy(3.9523D);
    private static final double CANNON_PRONE_PIVOT_FORWARD =
            EvaScale.fromLegacy(9.9317D);
    private static final double CANNON_PRONE_MUZZLE_FORWARD =
            EvaScale.fromLegacy(23.9289D);
    private static final double CANNON_PRONE_MUZZLE_UP =
            EvaScale.fromLegacy(-0.3676D);
    private static final double CANNON_PRONE_MUZZLE_RIGHT =
            EvaScale.fromLegacy(0.6284D);
    /** Starts the visible tracer just beyond the barrel cap instead of inside it. */
    private static final double MUZZLE_SURFACE_CLEARANCE = 0.25D;
    // Full-cycle travel measured from the real animated foot contacts after
    // the 2.5x model scale. Gecko's default 1x playback made the limbs cycle
    // several times faster than the chassis actually crossed the ground.
    private static final double WALK_STRIDE_BLOCKS = 22.5901D;
    private static final double RUN_STRIDE_BLOCKS = 40.4589D;
    private static final double CROUCH_STRIDE_BLOCKS = 9.2990D;
    private static final double CRAWL_STRIDE_BLOCKS = 5.0046D;
    private static final double WALK_CYCLE_SECONDS = 1.01667D;
    private static final double RUN_CYCLE_SECONDS = 0.80000D;
    // Strides and periods are measured from the ACCAD R32 actions.
    // Cadence gains keep a sixty-block EVA responsive at gameplay
    // speed without changing the human joint curves or their phase.
    private static final double WALK_CADENCE_GAIN = 1.75D;
    private static final double RUN_CADENCE_GAIN = 3.50D;
    private static final double CROUCH_CYCLE_SECONDS = 1.0D;
    private static final double CRAWL_CYCLE_SECONDS = 1.4D;

    private static final EntityDataAccessor<Integer> DATA_WEAPON =
            SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.INT);
    private static final EntityDataAccessor<Integer> DATA_ARMAMENT_MASK =
            SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.INT);
    private static final EntityDataAccessor<Boolean> DATA_AT_ON =
            SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.BOOLEAN);
    private static final EntityDataAccessor<Float> DATA_AT_ENERGY =
            SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.FLOAT);
    private static final EntityDataAccessor<Boolean> DATA_MISSION_SHIELD_R45 =
            SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.BOOLEAN);
    private static final EntityDataAccessor<Integer> DATA_CANNON_CHARGE =
            SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.INT);
    private static final EntityDataAccessor<Integer> DATA_CANNON_COOLDOWN =
            SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.INT);
    private static final EntityDataAccessor<Float> DATA_CANNON_AIM_PITCH =
            SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.FLOAT);
    private static final EntityDataAccessor<Float> DATA_RIFLE_CROUCH=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.FLOAT);
    private static final EntityDataAccessor<Float> DATA_RIFLE_PRONE=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.FLOAT);
    private static final EntityDataAccessor<Float> DATA_RIFLE_READY=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.FLOAT);
    private static final EntityDataAccessor<Float> DATA_RIFLE_SIGHT_R45=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.FLOAT);
    private final EvaPoseSignalClock rifleSightClockR45=new EvaPoseSignalClock();
    private boolean rifleSightHeldR45;
    private java.util.UUID rifleSightPilotR45;
    private long rifleSightRequestedAtR45;
    private static final EntityDataAccessor<Float> DATA_RIFLE_RECOIL=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.FLOAT);
    private static final EntityDataAccessor<Float> DATA_RIFLE_GAIT=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.FLOAT);
    private static final EntityDataAccessor<Float> DATA_RIFLE_MOVE=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.FLOAT);
    private static final EntityDataAccessor<Float> DATA_RIFLE_RUN=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.FLOAT);
    private static final EntityDataAccessor<Float> DATA_RIFLE_STANCE=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.FLOAT);
    private float rifleCrouchPrevious,riflePronePrevious,rifleReadyPrevious,rifleRecoilPrevious;
    private final float[] rifleSignalPrevious=new float[8],rifleSignalCurrent=new float[8];
    private final int[] rifleSignalTicks=new int[8];
    private final EvaPoseSignalClock[] poseSignalClocks={new EvaPoseSignalClock(),new EvaPoseSignalClock(),new EvaPoseSignalClock(),new EvaPoseSignalClock(),new EvaPoseSignalClock(),new EvaPoseSignalClock(),new EvaPoseSignalClock(),new EvaPoseSignalClock()};
    private final EvaPoseSignalClock actionSignalClock=new EvaPoseSignalClock();
    private float rifleStanceVelocity;
    private boolean rifleStanceInitialized;
    private double riflePreviousX=Double.NaN,riflePreviousZ;
    private int rifleZeroTravelTicksR45;
    private static final EntityDataAccessor<Integer> DATA_N2_ARM_TICKS =
            SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.INT);
    private static final EntityDataAccessor<Boolean> DATA_CROUCHING =
            SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.BOOLEAN);
    private static final EntityDataAccessor<Boolean> DATA_SPRINTING =
            SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.BOOLEAN);
    private static final EntityDataAccessor<Boolean> DATA_PRONE =
            SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.BOOLEAN);
    // Nailed to Tiferet by the SEELE scenario: pose locked, gravity off.
    private static final EntityDataAccessor<Boolean> DATA_CRUCIFIED =
            SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.BOOLEAN);
    private static final EntityDataAccessor<Boolean> DATA_MELEE_LEFT =
            SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.BOOLEAN);
    private static final EntityDataAccessor<Integer> DATA_MELEE_SEQUENCE =
            SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.INT);
    private static final EntityDataAccessor<Integer> DATA_ORDINARY_ATTACK_STAGE =
            SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.INT);
    private static final EntityDataAccessor<Integer> DATA_SMASH_SEQUENCE =
            SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.INT);
    private static final EntityDataAccessor<Integer> DATA_KICK_SEQUENCE =
            SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.INT);
    private static final EntityDataAccessor<Boolean> DATA_KICK_ACTIVE =
            SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.BOOLEAN);
    private static final EntityDataAccessor<Boolean> DATA_HEAVY_ACTIVE =
            SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.BOOLEAN);
    private static final EntityDataAccessor<Integer> DATA_KNIFE_TYPE =
            SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.INT);
    private static final EntityDataAccessor<Float> DATA_LIVE_ACTION_PHASE =
            SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.FLOAT);
    private static final EntityDataAccessor<Integer> DATA_JUMP_SEQUENCE =
            SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.INT);
    private static final EntityDataAccessor<Integer> DATA_ACTIVATION_TICKS =
            SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.INT);
    private static final EntityDataAccessor<Boolean> DATA_ENTRY_PLUG_INSERTED =
            SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.BOOLEAN);
    private static final EntityDataAccessor<Boolean> DATA_NERV_LOGISTICS_LOCKED =
            SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.BOOLEAN);
    private static final EntityDataAccessor<Float> DATA_NERV_LOGISTICS_YAW =
            SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.FLOAT);
    private static final EntityDataAccessor<Integer> DATA_VISUAL_POSE =
            SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.INT);
    private static final EntityDataAccessor<Integer> DATA_LAUNCH_PHASE =
            SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.INT);
    private static final EntityDataAccessor<Integer> DATA_LAUNCH_TICKS =
            SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.INT);
    private static final EntityDataAccessor<Boolean> DATA_RECOVERY_RACK_R39 = SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.BOOLEAN);
    private static final EntityDataAccessor<Boolean> DATA_CARRIER_FRAME_R39 = SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.BOOLEAN);
    private static final EntityDataAccessor<Boolean> DATA_CARRIER_MOTION_ACTIVE =
            SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.BOOLEAN);
    private static final EntityDataAccessor<Integer> DATA_CARRIER_MOTION_START =
            SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.INT);
    private static final EntityDataAccessor<Integer> DATA_CARRIER_MOTION_DURATION =
            SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.INT);
    private static final EntityDataAccessor<Boolean> DATA_TV_PERSONNEL_CLOCK_HELD_R44 =
            SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.BOOLEAN);
    private static final EntityDataAccessor<String> DATA_TV_PERSONNEL_FROZEN_R44 =
            SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.STRING);
    private static final EntityDataAccessor<Integer> DATA_TV_PERSONNEL_ELAPSED_R44 =
            SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.INT);
    private static final EntityDataAccessor<String> DATA_TV_PERSONNEL_SESSION_R44 =
            SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.STRING);
    private static final EntityDataAccessor<Float> DATA_CARRIER_FROM_X =
            SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.FLOAT);
    private static final EntityDataAccessor<Float> DATA_CARRIER_FROM_Y =
            SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.FLOAT);
    private static final EntityDataAccessor<Float> DATA_CARRIER_FROM_Z =
            SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.FLOAT);
    private static final EntityDataAccessor<Float> DATA_CARRIER_TO_X =
            SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.FLOAT);
    private static final EntityDataAccessor<Float> DATA_CARRIER_TO_Y =
            SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.FLOAT);
    private static final EntityDataAccessor<Float> DATA_CARRIER_TO_Z =
            SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.FLOAT);
    private static final EntityDataAccessor<Integer> DATA_POWER_TICKS =
            SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.INT);
    private static final EntityDataAccessor<Boolean> DATA_POWERED_VISUAL_R46 =
            SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.BOOLEAN);
    private static final EntityDataAccessor<Boolean> DATA_POWER_CONNECTED =
            SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.BOOLEAN);
    private static final EntityDataAccessor<Boolean> DATA_UMBILICAL_SEVERED =
            SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.BOOLEAN);
    private static final EntityDataAccessor<Integer> DATA_POWER_ANCHOR_X =
            SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.INT);
    private static final EntityDataAccessor<Integer> DATA_POWER_ANCHOR_Y =
            SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.INT);
    private static final EntityDataAccessor<Integer> DATA_POWER_ANCHOR_Z =
            SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.INT);
    private static final EntityDataAccessor<Float> DATA_PILOT_SYNCHRONIZATION =
            SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.FLOAT);
    private static final EntityDataAccessor<Boolean> DATA_BERSERK =
            SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.BOOLEAN);
    private static final EntityDataAccessor<Integer> DATA_BERSERK_TICKS =
            SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.INT);
    private static final EntityDataAccessor<Integer> DATA_MOTION_LAB_PHYSICS_PREVIEW =
            SynchedEntityData.defineId(EvaUnit01Entity.class, EntityDataSerializers.INT);
    private static final EntityDataAccessor<Boolean> DATA_MOTION_LAB_ACTIVE =
            SynchedEntityData.defineId(EvaUnit01Entity.class,
                    EntityDataSerializers.BOOLEAN);
    private static final EntityDataAccessor<Boolean> DATA_MOTION_LAB_RUNNING =
            SynchedEntityData.defineId(EvaUnit01Entity.class,
                    EntityDataSerializers.BOOLEAN);

    private static final RawAnimation ANIM_IDLE = RawAnimation.begin().thenLoop("animation.eva_unit01.idle");
    private static final RawAnimation ANIM_DORMANT = RawAnimation.begin().thenLoop("animation.eva_unit01.dormant");
    private static final RawAnimation ANIM_WALK = RawAnimation.begin().thenLoop("animation.eva_unit01.walk");
    private static final RawAnimation ANIM_JOG = RawAnimation.begin().thenLoop("animation.eva_unit01.jog");
    private static final RawAnimation ANIM_RUN = RawAnimation.begin().thenLoop("animation.eva_unit01.run");
    private static final RawAnimation ANIM_CROUCH = RawAnimation.begin().thenLoop("animation.eva_unit01.crouch");
    private static final RawAnimation ANIM_CROUCH_WALK = RawAnimation.begin().thenLoop("animation.eva_unit01.crouch_walk");
    private static final RawAnimation ANIM_TAKEOFF = RawAnimation.begin().thenPlay("animation.eva_unit01.takeoff");
    private static final RawAnimation ANIM_JUMP = RawAnimation.begin().thenLoop("animation.eva_unit01.jump");
    // One shared airborne instance prevents an animation restart at the
    // velocity apex. The compatibility `fall` JSON remains for visual tools.
    private static final RawAnimation ANIM_FALL = ANIM_JUMP;
    private static final RawAnimation ANIM_PRONE = RawAnimation.begin().thenLoop("animation.eva_unit01.prone");
    private static final RawAnimation ANIM_CRUCIFIED = RawAnimation.begin().thenLoop("animation.eva_unit01.crucified");
    private static final RawAnimation ANIM_CRAWL = RawAnimation.begin().thenLoop("animation.eva_unit01.crawl");
    private static final RawAnimation ANIM_AIM = RawAnimation.begin().thenLoop("animation.eva_unit01.aim");
    private static final RawAnimation ANIM_RIFLE_AIM = RawAnimation.begin().thenLoop("animation.eva_unit01.rifle_aim");
    private static final RawAnimation ANIM_PRONE_AIM = RawAnimation.begin().thenLoop("animation.eva_unit01.prone_aim");
    private static final RawAnimation ANIM_PRONE_RIFLE_AIM = RawAnimation.begin().thenLoop("animation.eva_unit01.prone_rifle_aim");
    private static final RawAnimation ANIM_N2_READY = RawAnimation.begin().thenLoop("animation.eva_unit01.n2_ready");
    private static final RawAnimation ANIM_LANCE_READY = RawAnimation.begin().thenLoop("animation.eva_unit01.lance_ready");
    private static final RawAnimation ANIM_LANCE_CARRY = RawAnimation.begin().thenLoop("animation.eva_unit01.lance_carry");
    private static final RawAnimation ANIM_SHIELD_BRACE = RawAnimation.begin().thenLoop("animation.eva_unit01.shield_brace");
    private static final RawAnimation ANIM_MELEE = RawAnimation.begin().thenPlay("animation.eva_unit01.melee");
    private static final RawAnimation ANIM_MELEE_LEFT = RawAnimation.begin().thenPlay("animation.eva_unit01.melee_left");
    private static final RawAnimation ANIM_KNIFE_READY = RawAnimation.begin().thenLoop("animation.eva_unit01.knife_ready");
    private static final RawAnimation ANIM_KNIFE = RawAnimation.begin().thenPlay("animation.eva_unit01.knife");
    private static final RawAnimation ANIM_KNIFE_LEFT = RawAnimation.begin().thenPlay("animation.eva_unit01.knife_left");
    private static final RawAnimation ANIM_KNIFE_HEAVY = RawAnimation.begin().thenPlay("animation.eva_unit01.knife_heavy");
    private static final RawAnimation ANIM_LANCE_THRUST = RawAnimation.begin().thenPlay("animation.eva_unit01.lance_thrust");
    private static final RawAnimation ANIM_PRONE_MELEE = RawAnimation.begin().thenPlay("animation.eva_unit01.prone_melee");
    private static final RawAnimation ANIM_PRONE_MELEE_LEFT = RawAnimation.begin().thenPlay("animation.eva_unit01.prone_melee_left");
    private static final RawAnimation ANIM_PRONE_KNIFE = RawAnimation.begin().thenPlay("animation.eva_unit01.prone_knife");
    private static final RawAnimation ANIM_PRONE_KNIFE_HEAVY = RawAnimation.begin().thenPlay("animation.eva_unit01.prone_knife_heavy");
    private static final RawAnimation ANIM_PRONE_LANCE_THRUST = RawAnimation.begin().thenPlay("animation.eva_unit01.prone_lance_thrust");
    private static final RawAnimation ANIM_PRONE_SMASH = RawAnimation.begin().thenPlay("animation.eva_unit01.prone_smash");
    private static final RawAnimation ANIM_CROUCH_MELEE = RawAnimation.begin().thenPlay("animation.eva_unit01.crouch_melee");
    private static final RawAnimation ANIM_CROUCH_MELEE_LEFT = RawAnimation.begin().thenPlay("animation.eva_unit01.crouch_melee_left");
    private static final RawAnimation ANIM_CROUCH_KNIFE = RawAnimation.begin().thenPlay("animation.eva_unit01.crouch_knife");
    private static final RawAnimation ANIM_CROUCH_KNIFE_HEAVY = RawAnimation.begin().thenPlay("animation.eva_unit01.crouch_knife_heavy");
    private static final RawAnimation ANIM_CROUCH_LANCE_THRUST = RawAnimation.begin().thenPlay("animation.eva_unit01.crouch_lance_thrust");
    private static final RawAnimation ANIM_CROUCH_SMASH = RawAnimation.begin().thenPlay("animation.eva_unit01.crouch_smash");
    private static final RawAnimation ANIM_PRONE_KNIFE_READY = RawAnimation.begin().thenLoop("animation.eva_unit01.prone_knife_ready");
    private static final RawAnimation ANIM_PRONE_LANCE_READY = RawAnimation.begin().thenLoop("animation.eva_unit01.prone_lance_ready");
    private static final RawAnimation ANIM_SMASH = RawAnimation.begin().thenPlay("animation.eva_unit01.smash");
    private static final RawAnimation ANIM_CANNON_FIRE = RawAnimation.begin().thenPlay("animation.eva_unit01.cannon_fire");
    private static final RawAnimation ANIM_PRONE_CANNON_FIRE = RawAnimation.begin().thenPlay("animation.eva_unit01.prone_cannon_fire");
    private static final RawAnimation ANIM_RIFLE_FIRE = RawAnimation.begin().thenPlay("animation.eva_unit01.rifle_fire");
    private static final RawAnimation ANIM_PRONE_RIFLE_FIRE = RawAnimation.begin().thenPlay("animation.eva_unit01.prone_rifle_fire");
    private static final RawAnimation ANIM_LAND = RawAnimation.begin().thenPlay("animation.eva_unit01.land");
    private static final RawAnimation ANIM_STOMP = RawAnimation.begin().thenPlay("animation.eva_unit01.stomp");
    private static final RawAnimation ANIM_ACTIVATION = RawAnimation.begin().thenPlay("animation.eva_unit01.activation");
    private static final RawAnimation ANIM_VISUAL_IDLE = RawAnimation.begin().thenLoop("animation.eva_unit01.visual_idle");
    private static final RawAnimation ANIM_VISUAL_WALK = RawAnimation.begin().thenLoop("animation.eva_unit01.visual_walk_contact");
    private static final RawAnimation ANIM_VISUAL_RUN = RawAnimation.begin().thenLoop("animation.eva_unit01.visual_run_contact");
    private static final RawAnimation ANIM_VISUAL_JUMP = RawAnimation.begin().thenLoop("animation.eva_unit01.visual_jump");
    private static final RawAnimation ANIM_VISUAL_FALL = RawAnimation.begin().thenLoop("animation.eva_unit01.visual_fall");
    private static final RawAnimation ANIM_VISUAL_CROUCH_WALK = RawAnimation.begin().thenLoop("animation.eva_unit01.visual_crouch_walk");
    private static final RawAnimation ANIM_VISUAL_CRAWL = RawAnimation.begin().thenLoop("animation.eva_unit01.visual_crawl");
    private static final RawAnimation ANIM_VISUAL_KNIFE_READY = RawAnimation.begin().thenLoop("animation.eva_unit01.visual_knife_ready");
    private static final RawAnimation ANIM_VISUAL_LANCE_READY = RawAnimation.begin().thenLoop("animation.eva_unit01.visual_lance_ready");
    private static final RawAnimation ANIM_VISUAL_KNIFE_WINDUP = RawAnimation.begin().thenLoop("animation.eva_unit01.visual_knife_windup");
    private static final RawAnimation ANIM_VISUAL_KNIFE_CONTACT = RawAnimation.begin().thenLoop("animation.eva_unit01.visual_knife_contact");
    private static final RawAnimation ANIM_VISUAL_KNIFE_RECOVERY = RawAnimation.begin().thenLoop("animation.eva_unit01.visual_knife_recovery");
    private static final RawAnimation ANIM_VISUAL_KNIFE_HEAVY_CONTACT = RawAnimation.begin().thenLoop("animation.eva_unit01.visual_knife_heavy_contact");
    private static final RawAnimation ANIM_VISUAL_LANCE_WINDUP = RawAnimation.begin().thenLoop("animation.eva_unit01.visual_lance_windup");
    private static final RawAnimation ANIM_VISUAL_LANCE_CONTACT = RawAnimation.begin().thenLoop("animation.eva_unit01.visual_lance_contact");
    private static final RawAnimation ANIM_VISUAL_LANCE_RECOVERY = RawAnimation.begin().thenLoop("animation.eva_unit01.visual_lance_recovery");
    private static final RawAnimation ANIM_VISUAL_CANNON = RawAnimation.begin().thenLoop("animation.eva_unit01.visual_cannon");
    private static final RawAnimation ANIM_VISUAL_RIFLE = RawAnimation.begin().thenLoop("animation.eva_unit01.visual_rifle");
    private static final RawAnimation ANIM_VISUAL_CROUCH_KNIFE_CONTACT = RawAnimation.begin().thenLoop("animation.eva_unit01.visual_crouch_knife_contact");
    private static final RawAnimation ANIM_VISUAL_PRONE_KNIFE_CONTACT = RawAnimation.begin().thenLoop("animation.eva_unit01.visual_prone_knife_contact");
    private static final RawAnimation ANIM_VISUAL_CROUCH_LANCE_CONTACT = RawAnimation.begin().thenLoop("animation.eva_unit01.visual_crouch_lance_contact");
    private static final RawAnimation ANIM_VISUAL_PRONE_LANCE_CONTACT = RawAnimation.begin().thenLoop("animation.eva_unit01.visual_prone_lance_contact");
    private static final RawAnimation ANIM_VISUAL_N2_READY = RawAnimation.begin().thenLoop("animation.eva_unit01.visual_n2_ready");
    private static final RawAnimation ANIM_VISUAL_RIFLE_WALK_CONTACT = RawAnimation.begin().thenLoop("animation.eva_unit01.visual_rifle_walk_contact");
    private static final RawAnimation ANIM_VISUAL_CROUCH_RIFLE_CONTACT = RawAnimation.begin().thenLoop("animation.eva_unit01.visual_crouch_rifle_contact");
    private static final RawAnimation ANIM_VISUAL_PRONE_RIFLE = RawAnimation.begin().thenLoop("animation.eva_unit01.visual_prone_rifle");
    private static final RawAnimation ANIM_BERSERK_ROAR = RawAnimation.begin().thenPlay("animation.eva_unit01.berserk_roar");
    private static final RawAnimation ANIM_BERSERK_RUN = RawAnimation.begin().thenLoop("animation.eva_unit01.berserk_run");
    private static final RawAnimation ANIM_BERSERK_CLAW_R = RawAnimation.begin().thenPlay("animation.eva_unit01.berserk_claw_r");
    private static final RawAnimation ANIM_BERSERK_CLAW_L = RawAnimation.begin().thenPlay("animation.eva_unit01.berserk_claw_l");
    private static final RawAnimation ANIM_BERSERK_POUNCE = RawAnimation.begin().thenPlay("animation.eva_unit01.berserk_pounce");

    private final AnimatableInstanceCache geoCache = GeckoLibUtil.createInstanceCache(this);

    private boolean chargingHeld;
    private int meleeCooldown;
    private int meleeInputBufferTicks;
    private int ordinaryAttackVisualTicks;
    private int ordinaryAttackComboStage = -1;
    private boolean gameplayOrdinaryContactR32;
    private final com.projectseele.combat.EvaContactHitsR45 ordinaryAcceptedTargetsR45=new com.projectseele.combat.EvaContactHitsR45();
    private int ordinaryAttackComboGraceTicks;
    private int ordinaryAttackElapsedTicks;
    private float ordinaryAttackDurationAtStart;
    private int ordinaryAttackRootStage;
    private int pendingOrdinaryContactTicks;
    private int pendingOrdinaryContactStage = -1;
    private int smashCooldown;
    private int heavyTicks, heavyDuration, heavyElapsed;
    private boolean heavyContact, queuedHeavy, queuedMeleeAfterHeavy, queuedKickAfterHeavy;
    private int stompCooldown;
    private int kickVisualTicks;
    private int kickElapsedTicks;
    private float kickDurationAtStart;
    private Vec3 liveCombatRootPrevious = Vec3.ZERO;
    private int pendingKickContactTicks;
    private int ordinaryAfterKickBufferTicks;
    private int kickAfterOrdinaryBufferTicks;
    private int knifeVisualTicks;
    private int pendingKnifeContactTicks;
    private int queuedKnifeInput = -1;
    private int knifeElapsedTicks;
    private float knifeDurationAtStart;
    private boolean knifeReverseMotion;
    private int rifleCooldown;
    private boolean leftSwing;
    private int atRegenDelay;
    private int jumpCooldown;
    private int jumpBufferTicks;
    private int groundedGraceTicks;
    private int lastJumpRequestId = Integer.MIN_VALUE;
    private boolean crouchingDimensions;
    private boolean proneDimensions;
    private boolean wasAirborne;
    private int serverAirborneTicks;
    private boolean explicitJumpInProgress;
    private boolean explicitJumpObservedAirborne;
    private int explicitJumpAuthorizationTicks;
    private boolean pilotMovementRequested;
    public boolean pilotLocomotionRequestedR45(){return pilotMovementRequested;}
    private int clientMeleeSequence;
    private int clientMeleeStartTick = -1000;
    private int clientMeleeWeapon = -1;
    private boolean clientMeleeLeft;
    private int clientOrdinaryAttackStage = -1;
    private int clientSmashSequence;
    private int clientSmashStartTick = -1000;
    private int clientSmashWeapon = -1;
    private int clientKickSequence;
    private int clientKickStartTick = -1000;
    private float clientActionPhasePrevious;
    private float clientActionPhase;
    private int clientActionPhaseTick;
    private int clientRootFamily = -1;
    private int clientRootSequence = -1;
    private Vec3 clientRootPrevious = Vec3.ZERO;
    private int clientJumpSequence;
    private boolean clientJumpImpulsePending;
    private boolean clientExplicitJumpInProgress;
    private boolean clientExplicitJumpObservedAirborne;
    private int clientExplicitJumpAuthorizationTicks;
    private double clientAirborneStartY;
    /** Client-only filtered locomotion signals; never used for hit detection. */
    private double clientVisualHorizontalSpeed;
    private double clientVisualVerticalSpeed;
    private boolean clientVisualMoving;
    private boolean clientVisualAirborne;
    private boolean clientVisualAscending;
    private int clientVisualGroundTicks;
    private int clientVisualAirTicks;
    private boolean clientVisualRunning;
    private int clientVisualRunReleaseTicks;
    private int clientBaseAnimationSelection = Integer.MIN_VALUE;
    @Nullable
    private BlockPos launchBedPos;
    private int launchCarrierY = NO_LAUNCH_CARRIER;
    private boolean launchContinuousRoute;
    /** A locked carrier may not move until the operations console releases it. */
    private boolean launchCommandReleased;
    private boolean launchRecoveryPending;
    private int launchPassengerRestoreGraceTicks;
    private float launchLockedYaw;
    @Nullable
    private ResourceKey<Level> sortieDestinationDimension;
    @Nullable
    private BlockPos sortieDestinationBed;
    @Nullable
    private BlockPos sortieParkingBed;
    private int powerCheckCooldown;
    private int berserkRecoveryTicks;
    private int berserkAttackCooldown;
    private int berserkTargetSearchCooldown;
    private int berserkPounceVisualCooldown;
    private int berserkPatternR37;
    @Nullable
    private UUID lockedEntryPlugUuid;
    private Vec3 autonomousInputR30=Vec3.ZERO;
    private long autonomousInputAtR30=Long.MIN_VALUE;
    private boolean entryPlugLinkFaultLogged;

    public EvaUnit01Entity(EntityType<? extends EvaUnit01Entity> type, Level level)
    {
        super(type, level);
        this.setMaxUpStep(2.6F);
    }

    public static AttributeSupplier.Builder createAttributes()
    {
        return PathfinderMob.createMobAttributes()
                .add(Attributes.MAX_HEALTH, 300.0D)
                .add(Attributes.MOVEMENT_SPEED, 0.42D)
                .add(Attributes.KNOCKBACK_RESISTANCE, 1.0D)
                .add(Attributes.ATTACK_DAMAGE, 12.0D)
                .add(ForgeMod.STEP_HEIGHT_ADDITION.get(), 1.0D)
                .add(ForgeMod.ENTITY_GRAVITY.get(), AIRFRAME_GRAVITY);
    }

    @Override
    protected void defineSynchedData()
    {
        super.defineSynchedData();
        FIRST_BATTLE.define(this.entityData);
        EvaDorsalMechanism.define(this.entityData);
        EvaTerrainSupport.define(this.entityData);
        EvaShutdownR30.define(this.entityData);
        EvaAirTransportR31.define(this.entityData);
        EvaGameplayMotionR32.define(this.entityData);
        EvaWeaponHandlingR45.define(this.entityData);
        EvaCombatSupportR33.define(this.entityData);
        EvaBerserkMotionR34.define(this.entityData);
        EvaBayRepairR33.define(this.entityData);
        EvaCombatR31.define(this.entityData);
        EvaCapturedLocomotionR44.define(this.entityData);
        this.entityData.define(MECHANICAL_REVISION_R30,0);
        this.entityData.define(DATA_WEAPON, WEAPON_KNIFE);
        this.entityData.define(DATA_ARMAMENT_MASK, this.intrinsicArmamentMask());
        this.entityData.define(DATA_AT_ON, false);
        this.entityData.define(DATA_AT_ENERGY, AT_FIELD_MAX);
        this.entityData.define(DATA_MISSION_SHIELD_R45, false);
        this.entityData.define(DATA_CANNON_CHARGE, 0);
        this.entityData.define(DATA_CANNON_COOLDOWN, 0);
        this.entityData.define(DATA_CANNON_AIM_PITCH, 0.0F);
        this.entityData.define(DATA_RIFLE_CROUCH,0F);this.entityData.define(DATA_RIFLE_PRONE,0F);
        this.entityData.define(DATA_RIFLE_READY,0F);this.entityData.define(DATA_RIFLE_RECOIL,0F);
        this.entityData.define(DATA_RIFLE_SIGHT_R45,0F);
        this.entityData.define(DATA_RIFLE_GAIT,0F);this.entityData.define(DATA_RIFLE_MOVE,0F);this.entityData.define(DATA_RIFLE_RUN,0F);
        this.entityData.define(DATA_RIFLE_STANCE,0F);
        this.entityData.define(DATA_N2_ARM_TICKS, 0);
        this.entityData.define(DATA_CROUCHING, false);
        this.entityData.define(DATA_SPRINTING, false);
        this.entityData.define(DATA_PRONE, false);
        this.entityData.define(DATA_CRUCIFIED, false);
        this.entityData.define(DATA_MELEE_LEFT, false);
        this.entityData.define(DATA_MELEE_SEQUENCE, 0);
        this.entityData.define(DATA_ORDINARY_ATTACK_STAGE, -1);
        this.entityData.define(DATA_SMASH_SEQUENCE, 0);
        this.entityData.define(DATA_KICK_SEQUENCE, 0);
        this.entityData.define(DATA_KICK_ACTIVE, false);
        this.entityData.define(DATA_HEAVY_ACTIVE, false);
        this.entityData.define(DATA_KNIFE_TYPE, -1);
        this.entityData.define(DATA_LIVE_ACTION_PHASE, 0.0F);
        this.entityData.define(DATA_JUMP_SEQUENCE, 0);
        this.entityData.define(DATA_ACTIVATION_TICKS, 0);
        this.entityData.define(DATA_ENTRY_PLUG_INSERTED, false);
        this.entityData.define(DATA_NERV_LOGISTICS_LOCKED, false);
        this.entityData.define(DATA_NERV_LOGISTICS_YAW, SILO_BAY_YAW);
        this.entityData.define(DATA_CARRIER_RISE_R26,0F);
        this.entityData.define(DATA_VISUAL_POSE, VISUAL_NORMAL);
        this.entityData.define(DATA_LAUNCH_PHASE, LAUNCH_IDLE);
        this.entityData.define(DATA_LAUNCH_TICKS, 0);
        this.entityData.define(DATA_RECOVERY_RACK_R39, false);
        this.entityData.define(DATA_CARRIER_FRAME_R39, false);
        this.entityData.define(DATA_CARRIER_MOTION_ACTIVE, false);
        this.entityData.define(DATA_CARRIER_MOTION_START, 0);
        this.entityData.define(DATA_CARRIER_MOTION_DURATION, 1);
        this.entityData.define(DATA_TV_PERSONNEL_CLOCK_HELD_R44, false);
        this.entityData.define(DATA_TV_PERSONNEL_FROZEN_R44, "0,0,0");
        this.entityData.define(DATA_TV_PERSONNEL_ELAPSED_R44,0);
        this.entityData.define(DATA_TV_PERSONNEL_SESSION_R44,"0");
        this.entityData.define(DATA_CARRIER_FROM_X, 0.0F);
        this.entityData.define(DATA_CARRIER_FROM_Y, 0.0F);
        this.entityData.define(DATA_CARRIER_FROM_Z, 0.0F);
        this.entityData.define(DATA_CARRIER_TO_X, 0.0F);
        this.entityData.define(DATA_CARRIER_TO_Y, 0.0F);
        this.entityData.define(DATA_CARRIER_TO_Z, 0.0F);
        this.entityData.define(DATA_POWER_TICKS, 0);
        this.entityData.define(DATA_POWERED_VISUAL_R46, false);
        this.entityData.define(DATA_POWER_CONNECTED, false);
        this.entityData.define(DATA_UMBILICAL_SEVERED, false);
        this.entityData.define(DATA_POWER_ANCHOR_X, 0);
        this.entityData.define(DATA_POWER_ANCHOR_Y, 0);
        this.entityData.define(DATA_POWER_ANCHOR_Z, 0);
        this.entityData.define(DATA_PILOT_SYNCHRONIZATION, 40.0F);
        this.entityData.define(DATA_BERSERK, false);
        this.entityData.define(DATA_BERSERK_TICKS, 0);
        this.entityData.define(DATA_MOTION_LAB_PHYSICS_PREVIEW, 0);
        this.entityData.define(DATA_MOTION_LAB_ACTIVE, false);
        this.entityData.define(DATA_MOTION_LAB_RUNNING, false);
    }

    @Override
    public SpawnGroupData finalizeSpawn(ServerLevelAccessor level, DifficultyInstance difficulty,
                                        MobSpawnType reason, @Nullable SpawnGroupData spawnData,
                                        @Nullable CompoundTag dataTag)
    {
        if (SeeleConfig.COMMON_SPEC.isLoaded())
        {
            this.getAttribute(Attributes.MAX_HEALTH).setBaseValue(SeeleConfig.EVA_MAX_HEALTH.get());
            this.setHealth(this.getMaxHealth());
        }
        this.entityData.set(DATA_AT_ENERGY, this.getAtFieldCapacity());
        this.entityData.set(DATA_POWER_TICKS, 0);
        return super.finalizeSpawn(level, difficulty, reason, spawnData, dataTag);
    }

    @Override
    public void addAdditionalSaveData(CompoundTag tag)
    {
        super.addAdditionalSaveData(tag);
        FIRST_BATTLE.save(this,tag);
        EvaShutdownR30.save(this,tag);
        EvaAirTransportR31.save(this,tag);
        EvaDorsalMechanism.save(this,tag);
        tag.putInt("SeeleWeapon", this.getWeapon());
        tag.putInt("SeeleArmamentMask", this.getArmamentMask());
        tag.putInt("SeeleWeaponCustodyVersion", 47);
        tag.putBoolean("SeeleCrucified", this.isCrucified());
        tag.putBoolean("SeeleEntryPlugInserted", this.isEntryPlugInserted());
        if (this.lockedEntryPlugUuid != null)
        {
            tag.putUUID("SeeleLockedEntryPlug", this.lockedEntryPlugUuid);
        }
        tag.putBoolean("SeeleNervLogisticsLocked", this.isNervLogisticsLocked());
        tag.putFloat("SeeleNervLogisticsYaw", this.entityData.get(DATA_NERV_LOGISTICS_YAW));
        tag.putInt("SeelePowerTicks", this.getPowerTicks());
        tag.putBoolean("SeeleBatterySession",this.batterySessionArmed);
        tag.putFloat("SeeleCarrierRise",this.entityData.get(DATA_CARRIER_RISE_R26));
        tag.putBoolean("SeeleUmbilicalSevered", this.isUmbilicalSevered());
        if (this.getUmbilicalAnchor() != null)
            tag.putLong("SeeleUmbilicalAnchor", this.getUmbilicalAnchor().asLong());
        tag.putFloat("SeelePilotSynchronization", this.getPilotSynchronization());
        tag.putBoolean("SeeleBerserk", this.isBerserk());
        EvaBerserkMotionR34.save(this,tag);
        tag.putInt("SeeleBerserkTicks", this.getBerserkTicks());
        tag.putInt("SeeleBerserkRecoveryTicks", this.berserkRecoveryTicks);
        if (this.sortieDestinationDimension != null && this.sortieDestinationBed != null)
        {
            tag.putString("SeeleSortieDimension",
                    this.sortieDestinationDimension.location().toString());
            tag.putLong("SeeleSortieBed", this.sortieDestinationBed.asLong());
            if (this.sortieParkingBed != null)
            {
                tag.putLong("SeeleSortieParkingBed", this.sortieParkingBed.asLong());
            }
        }
        if (this.isLaunchSequenceActive() && this.launchBedPos != null)
        {
            tag.putInt("SeeleLaunchPhase", this.getLaunchPhase());
            tag.putInt("SeeleLaunchTicks", this.getLaunchTicks());
            tag.putInt("SeeleActivationTicks", this.getActivationTicks());
            tag.putLong("SeeleLaunchBed", this.launchBedPos.asLong());
            tag.putFloat("SeeleLaunchYaw", this.launchLockedYaw);
            tag.putBoolean("SeeleLaunchContinuous", this.launchContinuousRoute);
            tag.putBoolean("SeeleLaunchCommandReleased", this.launchCommandReleased);
            if (this.launchCarrierY != NO_LAUNCH_CARRIER)
            {
                tag.putInt("SeeleLaunchCarrierY", this.launchCarrierY);
            }
        }
        this.saveTvPersonnelClockR44(tag);
    }

    @Override
    public void readAdditionalSaveData(CompoundTag tag)
    {
        super.readAdditionalSaveData(tag);
        EvaDorsalMechanism.load(this,tag);
        var gravity=this.getAttribute(ForgeMod.ENTITY_GRAVITY.get());
        if(gravity!=null&&(Math.abs(gravity.getBaseValue()-.08D)<.000001D||Math.abs(gravity.getBaseValue()-.18D)<.000001D||Math.abs(gravity.getBaseValue()-.32D)<.000001D))
            gravity.setBaseValue(AIRFRAME_GRAVITY);
        int intrinsicMask = this.intrinsicArmamentMask();
        int savedWeapon = tag.contains("SeeleWeapon")
                ? EvaEquipmentPolicyR45.normalized(tag.getInt("SeeleWeapon"),this.getUnitVariant(),this.isExperimentalUnit())
                : WEAPON_KNIFE;
        int savedMask = tag.contains("SeeleArmamentMask")
                ? tag.getInt("SeeleArmamentMask") : intrinsicMask;
        // Phase-one armament buildings issue only the TV Pallet Rifle.  Keep
        // built-in equipment unconditionally and preserve that one external
        // entitlement across a legitimate world/server reload.
        int restoredMask = intrinsicMask | (savedMask & ARMAMENT_MASK_RIFLE);
        if(tag.getInt("SeeleWeaponCustodyVersion")>=47&&!this.isExperimentalUnit())
        {
            if(this.getUnitVariant()==UNIT_02)restoredMask|=savedMask&ARMAMENT_MASK_SWORD_R45;
            if(this.getUnitVariant()==UNIT_00)restoredMask|=savedMask&ARMAMENT_MASK_SHIELD_R45;
        }
        restoredMask = com.projectseele.world.TvMissionEquipmentR45.restoreCannonMask(this,restoredMask);
        if ((restoredMask & (1 << savedWeapon)) == 0
                || !EvaEquipmentResourcesR45.ready(this,savedWeapon))
        {
            savedWeapon = WEAPON_KNIFE;
        }
        this.entityData.set(DATA_MISSION_SHIELD_R45,com.projectseele.world.TvMissionEquipmentR45.shieldAuthorized(this));
        this.getPersistentData().putBoolean("TvMissionCannonAppliedR45",com.projectseele.world.TvMissionEquipmentR45.cannonAuthorized(this));
        this.entityData.set(DATA_ARMAMENT_MASK, restoredMask);
        this.entityData.set(DATA_WEAPON, savedWeapon);
        boolean crucified = tag.getBoolean("SeeleCrucified");
        this.entityData.set(DATA_CRUCIFIED, crucified);
        this.entityData.set(DATA_ENTRY_PLUG_INSERTED,
                tag.getBoolean("SeeleEntryPlugInserted"));
        this.lockedEntryPlugUuid = tag.hasUUID("SeeleLockedEntryPlug")
                ? tag.getUUID("SeeleLockedEntryPlug") : null;
        this.entryPlugLinkFaultLogged = false;
        this.entityData.set(DATA_NERV_LOGISTICS_LOCKED,
                tag.getBoolean("SeeleNervLogisticsLocked"));
        this.entityData.set(DATA_NERV_LOGISTICS_YAW,
                tag.contains("SeeleNervLogisticsYaw") ? tag.getFloat("SeeleNervLogisticsYaw") : this.getYRot());
        this.entityData.set(DATA_POWER_TICKS, tag.contains("SeelePowerTicks")
                ? Mth.clamp(tag.getInt("SeelePowerTicks"), 0, this.getPowerCapacityTicks())
                : 0);
        this.entityData.set(DATA_UMBILICAL_SEVERED,
                tag.getBoolean("SeeleUmbilicalSevered"));
        this.entityData.set(DATA_PILOT_SYNCHRONIZATION,
                tag.contains("SeelePilotSynchronization")
                        ? Mth.clamp(tag.getFloat("SeelePilotSynchronization"), 0.0F,
                                EvaPilotData.maxSynchronization())
                        : EvaPilotData.initialSynchronization());
        boolean savedBerserk = tag.getBoolean("SeeleBerserk")
                && this.getUnitVariant() == UNIT_01;
        this.entityData.set(DATA_BERSERK, savedBerserk);
        EvaBerserkMotionR34.load(this,tag);
        this.entityData.set(DATA_BERSERK_TICKS, savedBerserk
                ? Math.max(1, tag.getInt("SeeleBerserkTicks")) : 0);
        this.berserkRecoveryTicks = Math.max(0,
                tag.getInt("SeeleBerserkRecoveryTicks"));
        this.batterySessionArmed=tag.getBoolean("SeeleBatterySession");
        this.entityData.set(DATA_CARRIER_RISE_R26,tag.getFloat("SeeleCarrierRise"));
        this.setUmbilicalAnchor(tag.contains("SeeleUmbilicalAnchor") && !this.isUmbilicalSevered()
                ? BlockPos.of(tag.getLong("SeeleUmbilicalAnchor")) : null);
        ResourceLocation sortieLocation = tag.contains("SeeleSortieDimension")
                ? ResourceLocation.tryParse(tag.getString("SeeleSortieDimension")) : null;
        this.sortieDestinationDimension = sortieLocation == null ? null
                : ResourceKey.create(Registries.DIMENSION, sortieLocation);
        this.sortieDestinationBed = this.sortieDestinationDimension != null
                && tag.contains("SeeleSortieBed")
                ? BlockPos.of(tag.getLong("SeeleSortieBed")) : null;
        this.sortieParkingBed = this.sortieDestinationDimension != null
                && tag.contains("SeeleSortieParkingBed")
                ? BlockPos.of(tag.getLong("SeeleSortieParkingBed")) : null;
        int phase = tag.getInt("SeeleLaunchPhase");
        if (phase >= LAUNCH_LOCKED && phase <= LAUNCH_CLEAR && tag.contains("SeeleLaunchBed"))
        {
            this.launchBedPos = BlockPos.of(tag.getLong("SeeleLaunchBed"));
            this.entityData.set(DATA_LAUNCH_PHASE, phase);
            this.entityData.set(DATA_LAUNCH_TICKS, Math.max(0, tag.getInt("SeeleLaunchTicks")));
            this.entityData.set(DATA_ACTIVATION_TICKS, Math.max(0, tag.getInt("SeeleActivationTicks")));
            this.launchCarrierY = tag.contains("SeeleLaunchCarrierY")
                    ? tag.getInt("SeeleLaunchCarrierY")
                    : Mth.floor(this.getY()) - 1;
            this.launchRecoveryPending = phase == LAUNCH_ASCENT;
            this.launchPassengerRestoreGraceTicks = LAUNCH_PASSENGER_RESTORE_GRACE_TICKS;
            this.launchLockedYaw = tag.contains("SeeleLaunchYaw")
                    ? tag.getFloat("SeeleLaunchYaw") : this.getYRot();
            this.launchContinuousRoute = tag.getBoolean("SeeleLaunchContinuous");
            // Legacy saves already moving through a shaft may resume, but a
            // unit restored on the launch bed must still wait for command.
            this.launchCommandReleased = tag.contains("SeeleLaunchCommandReleased")
                    ? tag.getBoolean("SeeleLaunchCommandReleased")
                    : phase != LAUNCH_LOCKED;
            this.setNoGravity(true);
        }
        else
        {
            // No launch tag is the normal case. Do not call reset here: that
            // would erase a deliberate vanilla NoGravity flag on every EVA
            // simply because the world was reloaded.
            this.entityData.set(DATA_LAUNCH_PHASE, LAUNCH_IDLE);
            this.entityData.set(DATA_LAUNCH_TICKS, 0);
            this.launchBedPos = null;
            this.launchCarrierY = NO_LAUNCH_CARRIER;
            this.launchContinuousRoute = false;
            this.launchCommandReleased = false;
            this.launchRecoveryPending = false;
            this.launchPassengerRestoreGraceTicks = 0;
            this.launchLockedYaw = this.getYRot();
            if (crucified)
            {
                this.setNoGravity(true);
            }
        }
        FIRST_BATTLE.restore(this,tag);
        EvaShutdownR30.load(this,tag);
        EvaAirTransportR31.load(this,tag);
        EvaCombatR31.clear(this);
        this.loadTvPersonnelClockR44(tag);
    }

    // ----- state accessors -----

    public int getWeapon()
    {
        return this.entityData.get(DATA_WEAPON);
    }

    public int getArmamentMask()
    {
        return this.entityData.get(DATA_ARMAMENT_MASK);
    }

    /** Weapons physically built into the airframe rather than rack cargo. */
    private int intrinsicArmamentMask()
    {
        int mask = ARMAMENT_MASK_FISTS | ARMAMENT_MASK_KNIFE;
        if (this.getUnitVariant() == UNIT_00)
        {
            mask |= ARMAMENT_MASK_N2;
        }
        return mask;
    }

    private boolean armamentAvailable(int weapon)
    {
        int mask = this.getArmamentMask();
        return EvaEquipmentPolicyR45.allowed(weapon,this.getUnitVariant(),this.isExperimentalUnit())
                && (mask & (1 << weapon)) != 0
                && EvaEquipmentResourcesR45.ready(this,weapon);
    }

    private void selectWeapon(int weapon)
    {
        EvaSwordActionsR45.clear(this);
        this.cancelHeavyMotion();
        int safeWeapon = EvaEquipmentPolicyR45.normalized(weapon,this.getUnitVariant(),this.isExperimentalUnit());
        if(!EvaEquipmentResourcesR45.ready(this,safeWeapon))safeWeapon=WEAPON_KNIFE;
        this.entityData.set(DATA_WEAPON, safeWeapon);
        this.entityData.set(DATA_CANNON_CHARGE, 0);
        this.entityData.set(DATA_N2_ARM_TICKS, 0);
        if (safeWeapon != WEAPON_CANNON && safeWeapon != WEAPON_RIFLE)
        {
            this.entityData.set(DATA_CANNON_AIM_PITCH, 0.0F);
        }
        this.chargingHeld = false;
        this.meleeInputBufferTicks = 0;
        if (safeWeapon != WEAPON_FISTS)
        {
            this.cancelOrdinaryGroupCAttack();
            this.cancelSideKick();
        }
        if (safeWeapon != WEAPON_KNIFE)
        {
            this.cancelKnifeMotion();
        }
    }

    void commitHandledWeaponR45(int weapon){this.selectWeapon(weapon);}

    public int getPowerTicks()
    {
        return this.entityData.get(DATA_POWER_TICKS);
    }

    public float getPilotSynchronization()
    {
        return this.entityData.get(DATA_PILOT_SYNCHRONIZATION);
    }

    public boolean isBerserk()
    {
        return this.entityData.get(DATA_BERSERK);
    }

    public int getBerserkTicks()
    {
        return this.entityData.get(DATA_BERSERK_TICKS);
    }

    public int getBerserkRecoveryTicks()
    {
        return this.berserkRecoveryTicks;
    }

    private static final EntityDataAccessor<Float> DATA_CARRIER_RISE_R26 = SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.FLOAT);
    private float oldCarrierRiseR26;
    public void setRecoveryRackR39(boolean active){this.entityData.set(DATA_RECOVERY_RACK_R39,active);}
    public boolean recoveryRackR39(){return this.entityData.get(DATA_RECOVERY_RACK_R39);}
    public void setCarrierRiseProgress(float progress) { this.entityData.set(DATA_CARRIER_RISE_R26,Mth.clamp(progress,0,1)); }
    public float carrierRiseProgress(float partial) { return Mth.lerp(partial,this.oldCarrierRiseR26,this.entityData.get(DATA_CARRIER_RISE_R26)); }

    public int getPowerCapacityTicks()
    {
        return SeeleConfig.COMMON_SPEC.isLoaded()
                ? SeeleConfig.EVA_POWER_CAPACITY_TICKS.get() : 6000;
    }

    public boolean isUmbilicalConnected()
    {
        if (this.isExperimentalUnit()) return false;
        return this.entityData.get(DATA_POWER_CONNECTED) || this.isCarrierPowerConnected();
    }

    public boolean isCarrierPowerConnected()
    {
        return !EvaAirTransportR31.active(this) && !this.isBerserk() && !this.isExperimentalUnit() && this.isEntryPlugInserted()
                && this.getPilotEntity()!=null && this.isNervLogisticsLocked()
                && this.carrierRiseProgress(1)>=.999F
                && !(this.getY()>=80 && this.getLaunchPhase()!=LAUNCH_ASCENT);
    }

    public boolean isUmbilicalSevered()
    {
        return this.entityData.get(DATA_UMBILICAL_SEVERED);
    }

    /**
     * Authoritative visual/mechanical power state. A charged battery alone
     * cannot animate an empty airframe: a seated entry plug is part of the
     * control circuit.
     */
    public boolean isPoweredOn()
    {
        // Passenger packets and entity metadata are delivered independently.
        // Observers must not infer the control circuit from a temporarily
        // missing nested pilot, especially outside that passenger's tracking range.
        if(this.level().isClientSide)return this.entityData.get(DATA_POWERED_VISUAL_R46);
        if(EvaAirTransportR31.active(this))return false;
        if(EvaBerserkMotionR34.silent(this))return false;
        if(EvaShutdownR30.wreck(this)||EvaBayRepairR33.active(this))return false;
        if(this.isBerserk())return true;
        if(EvaShutdownR30.disabled(this))return false;
        return this.entityData.get(DATA_MOTION_LAB_ACTIVE)
                || (this.isEntryPlugInserted()
                    && this.getPilotEntity() != null
                    && (this.isUmbilicalConnected()
                        || this.getPowerTicks() > 0));
    }

    public boolean isPowerDepleted()
    {
        return !this.isUmbilicalConnected() && this.getPowerTicks() <= 0;
    }

    /**
     * Restores the canonical cold-cage contract after recovery or world load.
     * It intentionally does nothing while a pilot remains seated.
     */
    public void enterHangarStandby()
    {
        if (this.level().isClientSide || this.getPilotEntity() != null)
        {
            return;
        }
        EvaShutdownR30.stored(this);
        com.projectseele.world.EquipmentVaultsR47.returnStoredR47(this);
        this.setUmbilicalAnchor(null);
        this.entityData.set(DATA_UMBILICAL_SEVERED, false);
        this.entityData.set(DATA_POWER_TICKS, 0);
        this.entityData.set(DATA_ENTRY_PLUG_INSERTED, false);
        this.entityData.set(DATA_AT_ON, false);
        this.entityData.set(DATA_SPRINTING, false);
        // A recovered airframe is stored unarmed. Leaving the previous sortie
        // weapon selected made the dormant arm controller stop while the mesh
        // attachment remained visibly suspended in an open hand.
        this.selectWeapon(WEAPON_FISTS);
        this.entityData.set(DATA_ARMAMENT_MASK,this.getArmamentMask()
                &~(ARMAMENT_MASK_RIFLE|ARMAMENT_MASK_SWORD_R45|ARMAMENT_MASK_SHIELD_R45));
        this.getPersistentData().remove("R47PhysicalShieldIssued");
        this.entityData.set(DATA_CANNON_CHARGE, 0);
        this.entityData.set(DATA_N2_ARM_TICKS, 0);
        this.chargingHeld = false;
        this.clearPilotMotion();
        this.setDeltaMovement(Vec3.ZERO);
    }

    @Nullable
    public BlockPos getUmbilicalAnchor()
    {
        if (!this.entityData.get(DATA_POWER_CONNECTED))
        {
            return null;
        }
        return new BlockPos(this.entityData.get(DATA_POWER_ANCHOR_X),
                this.entityData.get(DATA_POWER_ANCHOR_Y),
                this.entityData.get(DATA_POWER_ANCHOR_Z));
    }

    public int getUnitVariant()
    {
        if (this.getType() == ModEntities.EVA_UNIT00.get())
        {
            return UNIT_00;
        }
        if (this.getType() == ModEntities.EVA_UNIT02.get())
        {
            return UNIT_02;
        }
        return UNIT_01;
    }

    public boolean isAtFieldOn()
    {
        return this.entityData.get(DATA_AT_ON);
    }

    public float getAtFieldEnergy()
    {
        return this.entityData.get(DATA_AT_ENERGY);
    }

    public float getAtFieldCapacity()
    {
        return switch (this.getUnitVariant())
        {
            case UNIT_00 -> 300.0F;
            case UNIT_02 -> 160.0F;
            default -> AT_FIELD_MAX;
        };
    }

    /** Unit-00's kneeling shield posture, used to cover the firing Unit. */
    public boolean isShieldBraced()
    {
        return false;
    }

    public int getCannonCharge()
    {
        return this.entityData.get(DATA_CANNON_CHARGE);
    }

    public int getCannonCooldown()
    {
        return this.entityData.get(DATA_CANNON_COOLDOWN);
    }

    public int getN2ArmTicks()
    {
        return this.entityData.get(DATA_N2_ARM_TICKS);
    }

    public float n2ArmProgress()
    {
        return Mth.clamp(this.getN2ArmTicks() / (float) SeeleConfig.N2_ARM_TICKS.get(), 0.0F, 1.0F);
    }

    /**
     * Physical barrel elevation shared by the visible Gecko rig and the shot
     * ray. Positive pitch points down, matching {@link Player#getXRot()}.
     */
    public float getCannonAimPitch()
    {
        return this.clampPilotWeaponPitch(this.entityData.get(DATA_CANNON_AIM_PITCH),1);
    }
    private boolean batterySessionArmed;

    /** Supported prone fire has a neck/receiver arc, continuous through stance changes. */
    public float clampPilotWeaponPitch(float pitch,float partial)
    {
        float prone=this.rifleProneBlend(partial);
        return Mth.clamp(pitch,Mth.lerp(prone,MIN_CANNON_AIM_PITCH,-10F),
                Mth.lerp(prone,MAX_CANNON_AIM_PITCH,16F));
    }
    public float clampPilotViewPitch(float pitch,float partial)
    {
        if(this.isPilotControlLocked())return pitch;
        float prone=this.rifleProneBlend(partial);
        return Mth.clamp(pitch,Mth.lerp(prone,-90F,-10F),Mth.lerp(prone,90F,16F));
    }
    public float clampPilotWeaponYaw(float yaw,float partial)
    {
        float body=Mth.rotLerp(partial,this.yBodyRotO,this.yBodyRot);
        // A shouldered weapon cannot aim through the pilot's own back while
        // the chassis is still turning. Use the same anatomical yaw envelope
        // as the head; experimental UN controls retain their existing policy.
        float standing=this.isExperimentalUnit()?180F:PILOT_HEAD_YAW_LIMIT;
        float difference=Mth.wrapDegrees(yaw-body),limit=Mth.lerp(this.rifleProneBlend(partial),standing,24F);
        return yaw+Mth.clamp(difference,-limit,limit)-difference;
    }
    public float clampPilotViewYaw(float yaw,float partial)
    {
        if(this.isPilotControlLocked())return yaw;
        // Observing behind the EVA is not permission to twist its held gun
        // through the spine. Preserve standing camera freedom independently.
        float body=Mth.rotLerp(partial,this.yBodyRotO,this.yBodyRot);
        float difference=Mth.wrapDegrees(yaw-body),limit=Mth.lerp(this.rifleProneBlend(partial),180F,24F);
        return yaw+Mth.clamp(difference,-limit,limit)-difference;
    }
    private float rifleSignal(int i,EntityDataAccessor<Float> key,float p)
    {
        if(!this.level().isClientSide)return this.entityData.get(key);
        float value=poseSignalClocks[i].sample(FirstBattleSignals.clientFrameTime());
        return i>=4&&i<=6?EvaCombatSupportR33.renderLocomotionSignalR44(this,p,i,value):value;
    }
    public float rifleCrouchBlend(float p){return rifleSignal(0,DATA_RIFLE_CROUCH,p);}
    public float rifleProneBlend(float p){return rifleSignal(1,DATA_RIFLE_PRONE,p);}
    public float rifleReadyBlend(float p){return rifleSignal(2,DATA_RIFLE_READY,p);}
    public float rifleRecoilBlend(float p){return rifleSignal(3,DATA_RIFLE_RECOIL,p);}
    public static final float RIFLE_READY_FOR_FIRE_R45=.9F;
    public float rifleHeldPoseReadinessR45(float partial)
    {return Mth.clamp(rifleReadyBlend(partial)/RIFLE_READY_FOR_FIRE_R45,0,1);}
    public float rifleGaitPhase(float p){return rifleSignal(4,DATA_RIFLE_GAIT,p);}
    public float rifleMoveBlend(float p){return rifleSignal(5,DATA_RIFLE_MOVE,p);}
    public float rifleRunBlend(float p){return rifleSignal(6,DATA_RIFLE_RUN,p);}
    public float rifleStanceLevel(float p){return rifleSignal(7,DATA_RIFLE_STANCE,p);}
    public float rifleSightBlendR45(float partial)
    {
        return this.level().isClientSide?rifleSightClockR45.sample(FirstBattleSignals.clientFrameTime()):this.entityData.get(DATA_RIFLE_SIGHT_R45);
    }
    public void setRifleSightHeldR45(LivingEntity pilot,boolean held)
    {
        if(this.level().isClientSide||pilot==null||this.getPilotEntity()!=pilot||this.isExperimentalUnit())return;
        if(held&&(this.getWeapon()!=WEAPON_RIFLE||!this.isPoweredOn()||this.isPilotControlLocked()))return;
        this.rifleSightHeldR45=held;this.rifleSightPilotR45=held?pilot.getUUID():null;
        this.rifleSightRequestedAtR45=this.level().getGameTime();
    }
    private void updateRiflePoseSignals()
    {
        rifleCrouchPrevious=this.entityData.get(DATA_RIFLE_CROUCH);riflePronePrevious=this.entityData.get(DATA_RIFLE_PRONE);
        rifleReadyPrevious=this.entityData.get(DATA_RIFLE_READY);rifleRecoilPrevious=this.entityData.get(DATA_RIFLE_RECOIL);
        if(!this.level().isClientSide)
        {
            float wanted=this.isPilotProne()?3F:this.isPilotCrouching()?1F:0F;
            float stance=this.entityData.get(DATA_RIFLE_STANCE);
            float priorStance=stance;
            if(!rifleStanceInitialized){stance=wanted;rifleStanceInitialized=true;}
            float remaining=wanted-stance;
            float desired=Math.copySign(Math.min(.08F,(float)Math.sqrt(2*.012F*Math.abs(remaining))),remaining);
            rifleStanceVelocity=Mth.approach(rifleStanceVelocity,desired,.012F);
            if(Math.abs(remaining)<Math.abs(rifleStanceVelocity)||Math.abs(remaining)<.001F)
            {
                stance=wanted;rifleStanceVelocity=0;
            }
            else stance=Mth.clamp(stance+rifleStanceVelocity,0,3);
            this.entityData.set(DATA_RIFLE_STANCE,stance);
            EvaStanceFoleyR41.tick(this,priorStance,stance);
            double dx=this.getX()-riflePreviousX,dz=this.getZ()-riflePreviousZ;
            double distance=Double.isFinite(dx)?Math.hypot(dx,dz):0;riflePreviousX=this.getX();riflePreviousZ=this.getZ();
            boolean actionDisplacement=!(this instanceof EvaPrototypeEntity)&&!this.isBerserk()
                    &&this.hasLiveActionForRender(0)&&this.isMeleeWeapon();
            boolean moving=distance>.006&&distance<8&&!this.isPilotControlLocked()
                    &&(!actionDisplacement||this.pilotMovementRequested);
            rifleZeroTravelTicksR45=moving?0:Math.min(3,rifleZeroTravelTicksR45+1);
            float oldMove=this.entityData.get(DATA_RIFLE_MOVE),oldRun=this.entityData.get(DATA_RIFLE_RUN);
            // Contact spacing/hit pause can stop translation for a few ticks
            // while forward input remains held. Hold the supporting gait pose
            // and its phase; blending toward idle then back produced a knee snap.
            boolean holdSupport=!moving&&actionDisplacement&&this.pilotMovementRequested
                    &&this.onGround()&&!this.isPilotControlLocked()&&distance<.006&&oldMove>.05F;
            // A mounted position packet can arrive after this tick's sample.
            // Held input plus a bounded two-tick travel gap is not a new idle
            // pose. Keep phase distance-driven; never invent forward movement.
            boolean holdTravelGap=!this.isExperimentalUnit()&&!moving&&!actionDisplacement
                    &&this.pilotMovementRequested&&this.onGround()&&!this.isPilotControlLocked()
                    &&distance<.006&&oldMove>.05F&&rifleZeroTravelTicksR45<=2;
            boolean holdGait=holdSupport||holdTravelGap;
            float move=Mth.approach(oldMove,moving?1F:holdGait?oldMove:0F,.16F);
            float run=Mth.approach(oldRun,holdGait?oldRun:moving&&this.isPilotSprinting()&&!this.isPilotCrouching()?1F:0F,.14F);
            this.entityData.set(DATA_RIFLE_MOVE,move);this.entityData.set(DATA_RIFLE_RUN,run);
            double capturedCycle=EvaCapturedLocomotionR44.serverCycle(this,run,moving?dx:0,moving?dz:0);
            if(moving)
            {
                if(capturedCycle>0)
                {
                    float phase=this.entityData.get(DATA_RIFLE_GAIT)+(float)(1D/(20D*capturedCycle));
                    phase-=Mth.floor(phase);this.entityData.set(DATA_RIFLE_GAIT,phase);
                }
                else
                {
                double standingStride=Mth.lerp(run,
                        EvaBodyPose.locomotionRuntimeStrideR44(this,"walk",EvaBodyPose.locomotionStrideR43(this,"walk",25.8334D*WALK_CADENCE_GAIN)/WALK_CADENCE_GAIN),
                        EvaBodyPose.locomotionRuntimeStrideR44(this,"run",EvaBodyPose.locomotionStrideR43(this,"run",31.3944D*RUN_CADENCE_GAIN)/RUN_CADENCE_GAIN));
                double stride=stance<=1?Mth.lerp(stance,standingStride,15D):Mth.lerp((stance-1)/2,15D,12D);
                stride=EvaCombatSupportR33.stride(this,dx,dz,(float)stride);
                double sign=EvaCombatSupportR33.gaitWeight(this,1)>.5F?1:dx*this.getForward().x+dz*this.getForward().z<0?-1:1;
                float phase=this.entityData.get(DATA_RIFLE_GAIT)+(float)(sign*distance/stride);phase-=Mth.floor(phase);this.entityData.set(DATA_RIFLE_GAIT,phase);
                }
            }
            EvaMovementSounds.tick(this,moving);
            this.entityData.set(DATA_RIFLE_CROUCH,Mth.approach(rifleCrouchPrevious,this.isPilotCrouching()?1F:0F,.12F));
            this.entityData.set(DATA_RIFLE_PRONE,Mth.approach(riflePronePrevious,this.isPilotProne()?1F:0F,1F/6F));
            float readyTarget=this.getWeapon()==WEAPON_RIFLE?(Math.abs(rifleStanceVelocity)>.001F?.35F:1F):0F;
            this.entityData.set(DATA_RIFLE_READY,Mth.approach(rifleReadyPrevious,readyTarget,.12F));
            var sightPilot=this.getPilotEntity();
            if(sightPilot==null||!sightPilot.getUUID().equals(this.rifleSightPilotR45)
                    ||this.getWeapon()!=WEAPON_RIFLE||!this.isPoweredOn()||this.isPilotControlLocked()
                    ||!(sightPilot instanceof ServerPlayer)&&this.level().getGameTime()-this.rifleSightRequestedAtR45>10)
            {this.rifleSightHeldR45=false;this.rifleSightPilotR45=null;}
            float sightTarget=this.rifleSightHeldR45&&Math.abs(rifleStanceVelocity)<.001F&&!this.isPilotSprinting()?1:0;
            this.entityData.set(DATA_RIFLE_SIGHT_R45,Mth.approach(this.entityData.get(DATA_RIFLE_SIGHT_R45),sightTarget,.16F));
            this.entityData.set(DATA_RIFLE_RECOIL,rifleRecoilPrevious<.005F?0F:rifleRecoilPrevious*.52F);
        }
    }

    /** Read-only Phase-A export of the same aim used by weapon gameplay. */
    public Vec3 getAimDirectionForPoseCapture()
    {return this.getAimDirectionForPoseCapture(1);}

    public Vec3 getAimDirectionForPoseCapture(float partial)
    {
        LivingEntity pilot = this.getPilotEntity();
        float yaw = pilot == null ? this.getYRot() : this.level().isClientSide
                ? Mth.rotLerp(partial,pilot.yRotO,pilot.getYRot()) : pilot.getYRot();
        float pitch = (this.getWeapon() == WEAPON_CANNON
                || this.getWeapon() == WEAPON_RIFLE)
                ? pilot!=null&&this.level().isClientSide
                    ? this.clampPilotWeaponPitch(Mth.lerp(partial,pilot.xRotO,pilot.getXRot()),partial)
                    : this.getCannonAimPitch() : 0.0F;
        return Vec3.directionFromRotation(pitch, this.clampPilotWeaponYaw(yaw,partial)).normalize();
    }

    /** Final gameplay muzzle socket; null for non-firearm loadouts. */
    @Nullable
    public Vec3 getMuzzlePositionForPoseCapture(Vec3 aimDirection)
    {
        return switch (this.getWeapon())
        {
            case WEAPON_CANNON -> this.cannonMuzzlePosition(aimDirection);
            case WEAPON_RIFLE -> this.rifleMuzzlePosition(aimDirection);
            default -> null;
        };
    }

    /** Render-space neck yaw: the pilot looks first while the chassis follows. */
    public float pilotHeadYawForRender(float partialTick)
    {
        LivingEntity pilot = this.getPilotEntity();
        if (pilot == null || this.isPilotControlLocked())
        {
            return 0.0F;
        }
        float pilotYaw = Mth.rotLerp(partialTick, pilot.yRotO,
                pilot.getYRot());
        float bodyYaw = Mth.rotLerp(partialTick, this.yRotO,
                this.getYRot());
        return Mth.clamp(Mth.wrapDegrees(pilotYaw - bodyYaw),
                -Mth.lerp(this.rifleProneBlend(partialTick), PILOT_HEAD_YAW_LIMIT, 24.0F),
                Mth.lerp(this.rifleProneBlend(partialTick), PILOT_HEAD_YAW_LIMIT, 24.0F));
    }

    public float pilotHeadPitchForRender(float partialTick)
    {
        LivingEntity pilot = this.getPilotEntity();
        if (pilot == null || this.isPilotControlLocked())
        {
            return 0.0F;
        }
        float low = this.rifleProneBlend(partialTick);
        return Mth.clamp(Mth.lerp(partialTick, pilot.xRotO,
                pilot.getXRot()), Mth.lerp(low, -38.0F, -10.0F),
                Mth.lerp(low, 42.0F, 16.0F));
    }

    /** Contact weapons alone are allowed to neutralize an Angel A.T. Field. */
    public boolean isMeleeWeapon()
    {
        return this.getWeapon() == WEAPON_FISTS || this.getWeapon() == WEAPON_KNIFE
                || this.getWeapon() == WEAPON_LANCE || this.getWeapon()==WEAPON_SWORD_R45;
    }

    public boolean isPilotCrouching()
    {
        if(EvaShutdownR30.displayed(this)&&EvaShutdownR30.mode(this)==EvaShutdownR30.EMPTY)return true;
        return this.entityData.get(DATA_CROUCHING);
    }

    public boolean isPilotSprinting()
    {
        return this.entityData.get(DATA_SPRINTING);
    }

    private boolean hasVisualRunIntent()
    {
        return this.isBerserk() || this.isPilotSprinting()
                || this.entityData.get(DATA_MOTION_LAB_RUNNING);
    }

    private boolean isVisualRunRequested()
    {
        return this.level().isClientSide
                ? this.clientVisualRunning : this.hasVisualRunIntent();
    }

    public boolean isPilotProne()
    {
        if(EvaShutdownR30.displayed(this)&&EvaShutdownR30.wreck(this))return true;
        return this.entityData.get(DATA_PRONE);
    }

    public boolean isCrucified()
    {
        return this.entityData.get(DATA_CRUCIFIED);
    }

    public int getActivationTicks()
    {
        return this.entityData.get(DATA_ACTIVATION_TICKS);
    }

    /** Finite mission cargo, separate from motion-lab and generic rifle masks. */
    public void refreshTvMissionEquipmentR45()
    {
        if(this.level().isClientSide||this.isExperimentalUnit()||this.entityData.get(DATA_MOTION_LAB_ACTIVE))return;
        com.projectseele.world.TvMissionEquipmentR45.reconcile(this);
        boolean allowed=com.projectseele.world.TvMissionEquipmentR45.cannonAuthorized(this);
        boolean applied=this.getPersistentData().getBoolean("TvMissionCannonAppliedR45");
        int mask=this.getArmamentMask();
        if(allowed){this.entityData.set(DATA_ARMAMENT_MASK,mask|(1<<WEAPON_CANNON));this.getPersistentData().putBoolean("TvMissionCannonAppliedR45",true);}
        else if(applied)
        {
            this.entityData.set(DATA_ARMAMENT_MASK,mask&~(1<<WEAPON_CANNON));this.getPersistentData().remove("TvMissionCannonAppliedR45");
            if(this.getWeapon()==WEAPON_CANNON)this.selectWeapon(WEAPON_KNIFE);
        }
        this.entityData.set(DATA_MISSION_SHIELD_R45,com.projectseele.world.TvMissionEquipmentR45.shieldAuthorized(this));
    }
    /** Only a successful physical rack handoff selects the cannon once. */
    public void acceptIssuedTvMissionEquipmentR45()
    {
        this.refreshTvMissionEquipmentR45();
        if(com.projectseele.world.TvMissionEquipmentR45.cannonAuthorized(this))this.selectWeapon(WEAPON_CANNON);
        else if(com.projectseele.world.TvMissionEquipmentR45.shieldAuthorized(this))
        {this.entityData.set(DATA_ARMAMENT_MASK,this.getArmamentMask()|ARMAMENT_MASK_SHIELD_R45);this.selectWeapon(WEAPON_SHIELD_R45);}
    }
    public boolean hasEquippedYashimaShieldR45(){return this.entityData.get(DATA_MISSION_SHIELD_R45);}
    public boolean autonomousShieldBraceR47(TrainingPilotEntity pilot,boolean brace)
    {
        if(this.level().isClientSide||this.getPilotEntity()!=pilot||pilot.getAssignedVariant()!=UNIT_00
                ||!this.isPoweredOn()||!com.projectseele.entity.EvaShieldRigR47.equipped(this)||this.isNervLogisticsLocked()
                ||this.isFirstBattleActive()||EvaShutdownR30.disabled(this))return false;
        this.entityData.set(DATA_CROUCHING,brace);this.entityData.set(DATA_PRONE,false);
        this.updatePoseDimensions();return true;
    }

    /** Installs one server-authorized external weapon from a physical rack. */
    public boolean installExternalArmament(int weapon)
    {
        if (this.level().isClientSide || (weapon!=WEAPON_RIFLE&&weapon!=WEAPON_SWORD_R45&&weapon!=WEAPON_SHIELD_R45)
                ||!EvaEquipmentResourcesR45.ready(this,weapon))
        {
            return false;
        }
        int bit = 1 << weapon;
        int mask = this.getArmamentMask();
        if ((mask & bit) != 0)
        {
            return false;
        }
        this.entityData.set(DATA_ARMAMENT_MASK, mask | bit);
        if(weapon==WEAPON_SHIELD_R45)this.getPersistentData().putBoolean("R47PhysicalShieldIssued",true);
        this.selectWeapon(weapon);
        return true;
    }

    /** Isolated motion-lab loadout; never called by campaign logistics. */
    public void prepareForMotionLab()
    {
        if (this.level().isClientSide)
        {
            return;
        }
        int allWeapons = 0;
        for (int weapon = WEAPON_FISTS; weapon <= WEAPON_N2; weapon++)
        {
            // Longinus/Unit-02 special currently share the withdrawn lance
            // motion set. Keep that set out of human review until a replacement
            // has passed visual approval.
            if (weapon != WEAPON_LANCE)
            {
                allWeapons |= 1 << weapon;
            }
        }
        this.entityData.set(DATA_ARMAMENT_MASK, allWeapons);
        this.entityData.set(DATA_POWER_TICKS, 72_000);
        this.entityData.set(DATA_POWER_CONNECTED, false);
        this.entityData.set(DATA_UMBILICAL_SEVERED, false);
        this.entityData.set(DATA_ENTRY_PLUG_INSERTED, true);
        this.entityData.set(DATA_ACTIVATION_TICKS, 0);
        this.entityData.set(DATA_PILOT_SYNCHRONIZATION,
                EvaPilotData.maxSynchronization());
        this.entityData.set(DATA_MOTION_LAB_PHYSICS_PREVIEW, 0);
        this.entityData.set(DATA_MOTION_LAB_ACTIVE, true);
        this.entityData.set(DATA_MOTION_LAB_RUNNING, false);
        this.setNervLogisticsLocked(false);
        this.selectWeapon(WEAPON_FISTS);
        this.setHealth(this.getMaxHealth());
        this.setPersistenceRequired();
    }

    public boolean selectMotionLabWeapon(int weapon)
    {
        if (this.level().isClientSide
                || !EvaEquipmentPolicyR45.allowed(weapon,this.getUnitVariant(),this.isExperimentalUnit())
                || weapon == WEAPON_LANCE
                || !EvaEquipmentResourcesR45.ready(this,weapon))
        {
            return false;
        }
        this.entityData.set(DATA_ARMAMENT_MASK,
                this.getArmamentMask() | 1 << weapon);
        this.selectWeapon(weapon);
        return true;
    }

    /**
     * Disposable lab-only preview: 0=off, 1=physics replay, 2=recovery,
     * 3=live policy, 4=grounded walk, 5=grounded run. The integer is
     * synchronized so the renderer never relies on scoreboard tags.
     */
    public void setMotionLabPhysicsPreview(int mode)
    {
        if (this.level().isClientSide
                || !this.getTags().contains("seele_motion_lab"))
        {
            return;
        }
        this.entityData.set(DATA_MOTION_LAB_ACTIVE, true);
        this.entityData.set(DATA_MOTION_LAB_PHYSICS_PREVIEW,
                Mth.clamp(mode, 0, 5));
        if (mode > 0)
        {
            this.entityData.set(DATA_MOTION_LAB_RUNNING, false);
        }
    }

    public int getMotionLabPhysicsPreview()
    {
        return this.entityData.get(DATA_MOTION_LAB_PHYSICS_PREVIEW);
    }

    /** Server-only gait flag for the disposable autonomous motion demo. */
    public void setMotionLabDemoGait(boolean sprinting)
    {
        if (this.level().isClientSide
                || !this.getTags().contains("seele_motion_lab")
                || this.getControllingPassenger() != null)
        {
            return;
        }
        this.entityData.set(DATA_MOTION_LAB_ACTIVE, true);
        // Autonomous lab motion is not pilot input. Sharing DATA_SPRINTING
        // made no-passenger cleanup fight the director every server tick.
        this.entityData.set(DATA_MOTION_LAB_RUNNING, sprinting);
        this.entityData.set(DATA_SPRINTING, false);
    }

    /** Runs the accepted takeoff/airborne/landing chain for the lab dummy. */
    public void triggerMotionLabDemoJump(double verticalVelocity)
    {
        if (this.level().isClientSide
                || !this.getTags().contains("seele_motion_lab")
                || !this.onGround())
        {
            return;
        }
        this.entityData.set(DATA_MOTION_LAB_ACTIVE, true);
        if (!EvaGameplayMotionR32.sharedJump(this)) this.triggerAnim("strike", "takeoff");
        this.entityData.set(DATA_JUMP_SEQUENCE,
                this.entityData.get(DATA_JUMP_SEQUENCE) + 1);
        if(EvaGameplayMotionR32.serverMovement(this))
        {
            Vec3 motion=this.getDeltaMovement();this.setDeltaMovement(motion.x,JUMP_VELOCITY,motion.z);
            this.setOnGround(false);this.hasImpulse=true;
        }
        this.explicitJumpInProgress = true;
        this.explicitJumpObservedAirborne = false;
        this.explicitJumpAuthorizationTicks = JUMP_BUFFER_TICKS;
        this.setDeltaMovement(0.0D, verticalVelocity, 0.0D);
        this.hasImpulse = true;
    }

    /**
     * The optical-link cinematic belongs only to initial plug activation.
     * Launch interlocks deliberately pin the same countdown above twenty ticks,
     * so HUD/audio code must not infer an active cinematic from the counter
     * alone once the carrier has entered its launch state machine.
     */
    public boolean isActivationCinematicActive()
    {
        return this.getLaunchPhase() == LAUNCH_IDLE
                && this.getActivationTicks() > 0;
    }

    /** Client acknowledgement for one accepted, authoritative jump impulse. */
    public int getJumpSequence()
    {
        return this.entityData.get(DATA_JUMP_SEQUENCE);
    }

    /** The physical plug remains seated after its insertion animation ends. */
    public boolean isEntryPlugInserted()
    {
        return this.entityData.get(DATA_ENTRY_PLUG_INSERTED);
    }

    @Nullable
    public EntryPlugCarrierEntity getLockedEntryPlug()
    {
        if (this.getFirstPassenger() instanceof EntryPlugCarrierEntity plug
                && plug.isLockedToEva())
        {
            return plug;
        }
        if (!this.level().isClientSide && this.lockedEntryPlugUuid != null
                && this.level() instanceof ServerLevel server)
        {
            Entity linked = server.getEntity(this.lockedEntryPlugUuid);
            if (linked instanceof EntryPlugCarrierEntity plug
                    && plug.isLockedToEva())
            {
                return plug;
            }
        }
        return null;
    }

    @Nullable
    public LivingEntity getPilotEntity()
    {
        Entity direct = this.getFirstPassenger();
        if (direct instanceof Player player)
        {
            return player;
        }
        if (direct instanceof TrainingPilotEntity trainingPilot)
        {
            return trainingPilot;
        }
        EntryPlugCarrierEntity plug = direct instanceof EntryPlugCarrierEntity carrier
                ? carrier : this.getLockedEntryPlug();
        Entity seated = plug == null ? null : plug.getFirstPassenger();
        return seated instanceof LivingEntity living ? living : null;
    }

    /**
     * Completes insertion without transferring or recreating the pilot's
     * capsule. The entity chain becomes EVA -> same plug -> same pilot.
     */
    public boolean bindEntryPlug(EntryPlugCarrierEntity plug,
                                 int completedPercent)
    {
        if(EvaShutdownR30.wreck(this)||EvaBayRepairR33.active(this))return false;
        if (this.level().isClientSide || plug.getVehicle() != this
                || !plug.isLockedToEva()
                || !(plug.getFirstPassenger() instanceof Player
                    || plug.getFirstPassenger() instanceof TrainingPilotEntity
                    || this instanceof EvaPrototypeEntity un && com.projectseele.world.UNAirLiftR29.emptyLoading(un)))
        {
            return false;
        }
        if(EvaShutdownR30.mode(this)==EvaShutdownR30.EMPTY)EvaShutdownR30.clear(this);
        int safeProgress = Mth.clamp(completedPercent, 0, 100);
        int remainingTicks = Mth.clamp(
                Mth.ceil(120.0F * (100 - safeProgress) / 100.0F), 1, 120);
        this.lockedEntryPlugUuid = plug.getUUID();
        this.entryPlugLinkFaultLogged = false;
        this.entityData.set(DATA_ACTIVATION_TICKS, remainingTicks);
        this.entityData.set(DATA_ENTRY_PLUG_INSERTED, true);
        return true;
    }

    public void markEntryPlugLinkFault(EntryPlugCarrierEntity plug)
    {
        if (this.level().isClientSide
                || this.lockedEntryPlugUuid == null
                || !this.lockedEntryPlugUuid.equals(plug.getUUID()))
        {
            return;
        }
        this.entityData.set(DATA_ENTRY_PLUG_INSERTED, false);
        if (!this.entryPlugLinkFaultLogged)
        {
            this.entryPlugLinkFaultLogged = true;
            ProjectSeele.LOGGER.error(
                    "NERV entry-plug link fault: eva={} plug={} stage={}",
                    this.getStringUUID(), plug.getStringUUID(),
                    plug.getInsertionStage());
        }
    }

    public void clearEntryPlugLink(EntryPlugCarrierEntity plug)
    {
        passengerAuthorityTraceR44(plug,"before_clear_entry_plug_link");
        if(this.level().isClientSide&&!com.projectseele.client.visual.RuntimeR44ClientProbe.passengerCleanupBefore(this))
        {
            passengerAuthorityTraceR44(plug,"client_link_preserved");return;
        }
        if (this.lockedEntryPlugUuid == null
                || this.lockedEntryPlugUuid.equals(plug.getUUID()))
        {
            this.lockedEntryPlugUuid = null;
            this.entryPlugLinkFaultLogged = false;
            this.entityData.set(DATA_ENTRY_PLUG_INSERTED, false);
        }
        passengerAuthorityTraceR44(plug,"after_clear_entry_plug_link");
    }

    public boolean isNervLogisticsLocked()
    {
        return this.entityData.get(DATA_NERV_LOGISTICS_LOCKED);
    }

    public void setNervLogisticsLocked(boolean locked)
    {
        if (!this.level().isClientSide)
        {
            if (locked && !this.isNervLogisticsLocked())
            {
                this.entityData.set(DATA_NERV_LOGISTICS_YAW, this.getYRot());
            }
            this.entityData.set(DATA_NERV_LOGISTICS_LOCKED, locked);
            if (locked)
            {
                /*
                 * The logistics flag is also the pre-launch pose contract.
                 * A recovered pilot can leave crouch/prone/aim values in the
                 * synchronized entity data; merely stopping Gecko controllers
                 * then keeps the wrong hitbox and lets the next controller
                 * transition visibly snap the airframe.  Every locked phase
                 * reasserts one upright, input-free cold chassis instead.
                 */
                this.entityData.set(DATA_CROUCHING, false);
                this.entityData.set(DATA_SPRINTING, false);
                this.entityData.set(DATA_PRONE, false);
                this.entityData.set(DATA_VISUAL_POSE, VISUAL_NORMAL);
                this.entityData.set(DATA_CANNON_AIM_PITCH, 0.0F);
                this.entityData.set(DATA_CANNON_CHARGE, 0);
                this.entityData.set(DATA_N2_ARM_TICKS, 0);
                this.chargingHeld = false;
                this.clearJumpRequestState();
                this.updatePoseDimensions();
            }
        }
    }
    /**
     * Full world-space frame of this variant's reviewed dorsal socket.
     */
    public RigidTransform getEntryPlugSocketTransform()
    {
        return EntryPlugKinematics.socketTransform(this);
    }

    /**
     * Compatibility projection for interaction and older visual diagnostics.
     * Geometry authority is {@link #getEntryPlugSocketTransform()}.
     */
    public Vec3 getEntryPlugSocketPosition()
    {
        return this.getEntryPlugSocketTransform().translation();
    }

    /** Measured rear armour depth differs between the three NERV and two UN bodies. */
    public double powerMountRearOffset()
    {
        return this.isExperimentalUnit()?(this.experimentalAssetName().equals("eva_un01")?3.87D:4.13D):switch(this.getUnitVariant()){case UNIT_00->4.22587D;case UNIT_02->4.22709D;default->5.72651D;};
    }
    public double powerSocketRearOffset(){return this.powerMountRearOffset()+2.2D;}

    /** World-space tail of the upper-back power plug, shared by cable and sever FX. */
    public Vec3 getUmbilicalSocketPosition()
    {
        return this.posedPowerMarker(EvaScale.UMBILICAL_SOCKET_HEIGHT,this.powerSocketRearOffset());
    }

    /** Armour-side receptacle for the rigid upper-back umbilical plug. */
    public Vec3 getUmbilicalMountPosition()
    {
        return this.posedPowerMarker(EvaScale.UMBILICAL_MOUNT_HEIGHT,this.powerMountRearOffset());
    }

    private Vec3 posedPowerMarker(double height,double rear)
    {
        var body=EvaBodyPose.sample(this,1);
        var matrix=EvaRifleKinematics.world(this,1).mul(body.matrix("torso_upper"));
        var point=matrix.transformPosition(new org.joml.Vector3f(0,(float)(height/EvaScale.RENDER_SCALE),(float)(rear/EvaScale.RENDER_SCALE)));
        return new Vec3(point.x,point.y,point.z);
    }

    /** Horizontal rear vector shared by dorsal hardware and its renderer. */
    public Vec3 getRearDirection()
    {
        Vec3 rear = this.getForward().multiply(-1.0D, 0.0D, -1.0D);
        return rear.lengthSqr() < 1.0E-6D
                ? new Vec3(0.0D, 0.0D, 1.0D) : rear.normalize();
    }

    /** Client/server-identical narrow ray test for the dorsal plug hardware. */
    public boolean isEntryPlugTargeted(Player player)
    {
        Vec3 eye = player.getEyePosition();
        Vec3 toSocket = this.getEntryPlugSocketPosition().subtract(eye);
        double distanceSqr = toSocket.lengthSqr();
        if (distanceSqr > ENTRY_PLUG_USE_REACH * ENTRY_PLUG_USE_REACH || distanceSqr < 1.0E-6D)
        {
            return false;
        }
        Vec3 look = player.getViewVector(1.0F).normalize();
        double alongRay = toSocket.dot(look);
        if (alongRay <= 0.0D)
        {
            return false;
        }
        double missDistanceSqr = Math.max(0.0D, distanceSqr - alongRay * alongRay);
        return missDistanceSqr <= ENTRY_PLUG_AIM_RADIUS * ENTRY_PLUG_AIM_RADIUS;
    }

    public int getLaunchPhase()
    {
        return this.entityData.get(DATA_LAUNCH_PHASE);
    }

    public int getLaunchTicks()
    {
        return this.entityData.get(DATA_LAUNCH_TICKS);
    }

    /** Current mag-lev carrier layer, or {@link Integer#MIN_VALUE} while parked. */
    public int getLaunchCarrierY()
    {
        return this.launchCarrierY;
    }

    /**
     * Releases an occupied, launch-locked EVA from the remote NERV console.
     * All normal passenger, bed and physical-shaft checks still run inside the
     * launch state machine on the following server tick.
     */
    public boolean releaseLaunchFromCommand()
    {
        Entity occupant = this.getPilotEntity();
        boolean human = occupant instanceof ServerPlayer;
        boolean training = occupant instanceof TrainingPilotEntity;
        if (this.level().isClientSide
                || this.getLaunchPhase() != LAUNCH_LOCKED
                || (!human && !training)
                || this.launchBedPos == null)
        {
            return false;
        }
        // Preflight starts with 20 activation ticks remaining. The TV surface
        // shutter needs 18 stagger ticks + 30 motion ticks, then reconciliation.
        int releaseTicks = this.level() instanceof ServerLevel launchLevel
                &&com.projectseele.world.TvLaunchFacility.enabled(launchLevel)?80:40;
        this.launchCommandReleased = true;
        this.entityData.set(DATA_ACTIVATION_TICKS, releaseTicks);
        this.entityData.set(DATA_LAUNCH_TICKS, releaseTicks);
        if (this.level() instanceof ServerLevel serverLevel
                && this.sortieDestinationBed != null)
        {
            NervSiloDoorEntity.reconcile(serverLevel,
                    this.getUnitVariant(), this.sortieDestinationBed, 1.0F);
        }
        this.enforceLaunchLock();
        if (occupant instanceof ServerPlayer pilot)
        {
            pilot.displayClientMessage(Component.literal(
                    "NERV command has authorized catapult release."), true);
        }
        ProjectSeele.LOGGER.info(
                "NERV remote launch release: eva={} pilot={} bed={}",
                this.getStringUUID(), training ? "NERV-DUMMY"
                        : ((ServerPlayer) occupant).getGameProfile().getName(),
                this.launchBedPos.toShortString());
        return true;
    }

    public boolean isLaunchCommandReleased()
    {
        return this.launchCommandReleased;
    }

    /**
     * Test-stage pilot release. This deliberately shares the authoritative
     * command-release gate instead of bypassing PREPARE, insertion, transport,
     * occupancy, launch-bed or shaft validation.
     */
    public void releaseLaunchFromPilot(ServerPlayer pilot)
    {
        if (this.getPilotEntity() != pilot)
        {
            pilot.displayClientMessage(Component.translatable(
                    "message.projectseele.self_launch_denied")
                    .withStyle(ChatFormatting.RED), true);
            return;
        }
        if (!this.releaseLaunchFromCommand())
        {
            pilot.displayClientMessage(Component.translatable(
                    "message.projectseele.self_launch_denied")
                    .withStyle(ChatFormatting.RED), true);
            return;
        }
        pilot.displayClientMessage(Component.translatable(
                "message.projectseele.self_launch_accepted")
                .withStyle(ChatFormatting.GREEN, ChatFormatting.BOLD), true);
        ProjectSeele.LOGGER.info(
                "NERV test self-launch release: eva={} pilot={} bed={}",
                this.getStringUUID(), pilot.getGameProfile().getName(),
                this.launchBedPos == null ? "missing"
                        : this.launchBedPos.toShortString());
    }

    private boolean hasLaunchPassenger()
    {
        return this.getPilotEntity() instanceof Player
                || this.getPilotEntity() instanceof TrainingPilotEntity;
    }

    /**
     * Pilot-initiated launch abort from inside the airframe (the CANCEL_LAUNCH
     * key). Delegates to the logistics state machine, which validates that the
     * unit is silo-locked and not yet released before recalling it to the wet
     * cage; the pilot is messaged either way.
     */
    public void contextualPilotCR45(ServerPlayer pilot,int directions)
    {
        if(this.level().isClientSide||pilot==null||this.getPilotEntity()!=pilot)return;
        if(directions<0||this.isExperimentalUnit()||this.isNervLogisticsLocked()||this.isLaunchSequenceActive())
        {this.cancelLaunchFromPilot(pilot);return;}
        if(this.chargingHeld||this.rifleSightHeldR45)return;
        EvaFieldActionsR45.request(this,pilot,directions,this.isPilotSprinting());
    }

    public void cancelLaunchFromPilot(ServerPlayer pilot)
    {
        if(this.isExperimentalUnit())
        {
            pilot.displayClientMessage(Component.literal("试验机使用地表格纳库出舱控制"),true);
            return;
        }
        if (!(this.level() instanceof net.minecraft.server.level.ServerLevel serverLevel))
        {
            return;
        }
        EvaLogisticsDirector.ActionResult result =
                EvaLogisticsDirector.requestCancel(serverLevel, this.getUnitVariant());
        pilot.displayClientMessage(Component.literal(result.message())
                .withStyle(result.accepted()
                        ? ChatFormatting.GREEN : ChatFormatting.RED), true);
    }

    /**
     * Cancels a sortie that is locked at the silo but not yet released, so the
     * airframe can be slid back into its wet cage. Refused once command has
     * authorized the catapult or the ascent has already begun. The seated pilot
     * and inserted plug are kept — {@link #resetLaunchSequence()} only clears
     * them when the plug was abandoned empty.
     */
    public boolean cancelPreparedLaunch()
    {
        if (this.level().isClientSide
                || this.getLaunchPhase() != LAUNCH_LOCKED
                || this.launchCommandReleased)
        {
            return false;
        }
        this.resetLaunchSequence();
        this.setNoGravity(true);
        ProjectSeele.LOGGER.info("NERV launch cancelled at silo: eva={}",
                this.getStringUUID());
        return true;
    }

    /** Arms a pilot who entered while the EVA was still inside its wet cage. */
    public boolean armPreparedLaunch(BlockPos bed)
    {
        if (this.isExperimentalUnit() || this.level().isClientSide || this.isLaunchSequenceActive()
                || !this.hasLaunchPassenger()
                || !(this.level() instanceof ServerLevel serverLevel)
                || !EvaLogisticsDirector.isAssignedLowerLaunchBed(
                        serverLevel, this.getUnitVariant(), bed)
                || !this.level().getBlockState(bed).is(Blocks.LODESTONE))
        {
            return false;
        }
        this.alignForSiloBoarding(bed);
        // Only an airframe that reached the silo WITHOUT the wet-cage insertion
        // still needs the activation clip here. One that was already seated in
        // its cage is inserted, and replaying the 120-tick capsule animation at
        // the silo is the second insertion the pilot sees. Leave its activation
        // where the cage clip left it; the launch lock below keeps it caged.
        if (!this.isEntryPlugInserted())
        {
            this.entityData.set(DATA_ACTIVATION_TICKS, 120);
            this.entityData.set(DATA_ENTRY_PLUG_INSERTED, true);
        }
        this.armLaunchBed(bed);
        return true;
    }

    /** Server-authoritative movement shared by horizontal and recovery carriers. */
    public void moveOnNervCarrier(double x, double y, double z, float yaw)
    {
        if (this.level().isClientSide)
        {
            return;
        }
        this.getNavigation().stop();
        this.setTarget(null);
        this.setPos(x, y, z);
        this.setDeltaMovement(Vec3.ZERO);
        this.setRot(yaw, 0.0F);
        this.entityData.set(DATA_NERV_LOGISTICS_YAW, yaw);
        this.yRotO = this.yBodyRot = this.yHeadRot = yaw;
        this.yBodyRotO = this.yHeadRotO = yaw;
        this.xRotO = 0.0F;
        this.fallDistance = 0.0F;
        this.setNoGravity(true);
        this.hasImpulse = true;
        this.syncPassengerAssembly();
    }

    @Override
    public void lerpTo(double x, double y, double z, float yRot, float xRot,
                       int lerpSteps, boolean teleport)
    {
        /*
         * Logistics and launch publish a fractional authoritative transform
         * every server tick.  Always accept those packets and interpolate
         * them locally; the retired shared-clock render override ignored the
         * packet stream and made the giant mesh visibly snap at phase points.
         */
        int steps = this.isNervLogisticsLocked() || this.isLaunchSequenceActive()
                ? 2 : lerpSteps;
        super.lerpTo(x, y, z, yRot, xRot, steps, teleport);
    }

    private void beginCarrierMotion(Vec3 from, Vec3 to, int duration)
    {
        this.clearTvPersonnelHeldFrameR44();
        this.tvPersonnelClockSessionR44++;
        this.entityData.set(DATA_TV_PERSONNEL_SESSION_R44,Long.toString(this.tvPersonnelClockSessionR44));
        this.entityData.set(DATA_CARRIER_FRAME_R39, false);
        this.entityData.set(DATA_CARRIER_FROM_X, (float) from.x);
        this.entityData.set(DATA_CARRIER_FROM_Y, (float) from.y);
        this.entityData.set(DATA_CARRIER_FROM_Z, (float) from.z);
        this.entityData.set(DATA_CARRIER_TO_X, (float) to.x);
        this.entityData.set(DATA_CARRIER_TO_Y, (float) to.y);
        this.entityData.set(DATA_CARRIER_TO_Z, (float) to.z);
        this.entityData.set(DATA_CARRIER_MOTION_DURATION,
                Math.max(1, duration));
        this.entityData.set(DATA_CARRIER_MOTION_START,
                (int) this.level().getGameTime());
        this.entityData.set(DATA_CARRIER_MOTION_ACTIVE, true);
    }

    /** Publishes one deterministic motion clock for the wet-cage rail. */
    public void beginNervCarrierMotion(Vec3 from, Vec3 to, int duration)
    {
        if (!this.level().isClientSide)
        {
            this.beginCarrierMotion(from, to, duration);
        }
    }

    /** Streaming flights publish the actual pair of positions, never a speculative full leg. */
    public void publishAirCarrierFrameR39(Vec3 previous, Vec3 current)
    {
        if(this.level().isClientSide)return;
        beginCarrierMotion(previous,current,1);
        this.entityData.set(DATA_CARRIER_FRAME_R39,true);
        this.entityData.set(DATA_CARRIER_MOTION_START,(int)this.level().getGameTime()-1);
    }

    public Vec3 sampleCarrierMotion(float partialTick)
    {
        if(this.tvPersonnelClockHeldR44())return this.tvPersonnelFrozenPositionR44();
        int duration = Math.max(1,
                this.entityData.get(DATA_CARRIER_MOTION_DURATION));
        /*
         * Subtract the integral clock before introducing a fractional frame.
         * R28 is already beyond 2.4 million game ticks; converting that
         * absolute value to float first leaves only 0.25-tick precision.  At
         * catapult speed that quantized each supposedly smooth frame into an
         * approximately one-block jump.  Moving Elevators keeps its last and
         * current coordinates as doubles; this curve now preserves the same
         * precision contract.
         */
        long elapsedTicks = this.level().getGameTime()
                - (long) this.entityData.get(DATA_CARRIER_MOTION_START);
        double progress = Mth.clamp(
                (elapsedTicks + (double) partialTick) / duration,
                0.0D, 1.0D);
        // Quintic smoothstep matches EvaLogisticsDirector exactly: both the
        // server collision body and every render frame sample one curve.
        double eased = progress * progress * progress
                * (progress * (progress * 6.0D - 15.0D) + 10.0D);
        if (this.getLaunchPhase() == LAUNCH_ASCENT
                && this.entityData.get(DATA_CARRIER_FROM_Y) < -200
                && this.entityData.get(DATA_CARRIER_TO_Y) >= 80)
            eased = com.projectseele.world.LaunchMotionR29.progress(progress);
        if(this.entityData.get(DATA_CARRIER_FRAME_R39))eased=progress;
        return new Vec3(
                Mth.lerp(eased,
                        this.entityData.get(DATA_CARRIER_FROM_X),
                        this.entityData.get(DATA_CARRIER_TO_X)),
                com.projectseele.world.CarrierGuidePath.height(
                        new Vec3(this.entityData.get(DATA_CARRIER_FROM_X),this.entityData.get(DATA_CARRIER_FROM_Y),this.entityData.get(DATA_CARRIER_FROM_Z)),
                        new Vec3(this.entityData.get(DATA_CARRIER_TO_X),this.entityData.get(DATA_CARRIER_TO_Y),this.entityData.get(DATA_CARRIER_TO_Z)),eased),
                Mth.lerp(eased,
                        this.entityData.get(DATA_CARRIER_FROM_Z),
                        this.entityData.get(DATA_CARRIER_TO_Z)));
    }

    public boolean hasActiveCarrierMotion()
    {
        return this.entityData.get(DATA_CARRIER_MOTION_ACTIVE)||this.tvPersonnelClockHeldR44()
                ||this.level().isClientSide&&this.clientCarrierFramePendingR35;
    }
    private boolean clientCarrierFramePendingR35;
    /** Can run outside chunk-gated AI ticks: the server already owns this path. */
    public void syncClientCarrierFrameR35()
    {
        if(!this.level().isClientSide)return;
        if(this.entityData.get(DATA_CARRIER_MOTION_ACTIVE)||this.tvPersonnelClockHeldR44())
        {
            Vec3 previous=this.sampleCarrierMotion(-1),current=this.sampleCarrierMotion(0);
            this.setPos(current.x,current.y,current.z);
            this.xOld=this.xo=previous.x;this.yOld=this.yo=previous.y;this.zOld=this.zo=previous.z;
        }
        else if(this.clientCarrierFramePendingR35&&this.entityData.get(DATA_CARRIER_MOTION_START)!=0)
        {
            double x=this.entityData.get(DATA_CARRIER_TO_X),y=this.entityData.get(DATA_CARRIER_TO_Y),z=this.entityData.get(DATA_CARRIER_TO_Z);
            super.lerpTo(x,y,z,this.getYRot(),this.getXRot(),1,true);this.setPos(x,y,z);
            this.xOld=this.xo=x;this.yOld=this.yo=y;this.zOld=this.zo=z;
        }
        else return;
        this.clientCarrierFramePendingR35=false;this.setDeltaMovement(Vec3.ZERO);this.syncPassengerAssembly();
    }

    /** One render-time frame, matching vanilla's previous/current tick convention. */
    public Vec3 carrierRenderPosition(float partialTick)
    {
        if(this.tvPersonnelClockHeldR44())return this.tvPersonnelFrozenPositionR44();
        return this.hasActiveCarrierMotion()
                ? this.sampleCarrierMotion(partialTick - 1.0F)
                : this.getPosition(partialTick);
    }

    private void endCarrierMotion()
    {
        this.clearTvPersonnelHeldFrameR44();
        this.tvPersonnelOwnedKindR44=0;
        if(!this.level().isClientSide&&this.entityData.get(DATA_CARRIER_MOTION_ACTIVE))
        {
            // Commit the actual stop, including an interrupted transfer. The
            // final frame must not fall back to an old ridden-entity position.
            this.entityData.set(DATA_CARRIER_FROM_X,(float)this.getX());this.entityData.set(DATA_CARRIER_TO_X,(float)this.getX());
            this.entityData.set(DATA_CARRIER_FROM_Y,(float)this.getY());this.entityData.set(DATA_CARRIER_TO_Y,(float)this.getY());
            this.entityData.set(DATA_CARRIER_FROM_Z,(float)this.getZ());this.entityData.set(DATA_CARRIER_TO_Z,(float)this.getZ());
        }
        this.entityData.set(DATA_CARRIER_MOTION_ACTIVE, false);
    }

    private CompoundTag tvPersonnelClockTagR44=new CompoundTag();
    private net.minecraft.nbt.Tag tvPersonnelOpaqueClockPayloadR44;
    private boolean tvPersonnelClockPersistenceInvalidR44;
    private boolean tvPersonnelClockReloadPendingR44;
    private int tvPersonnelOwnedKindR44,tvPersonnelHeldElapsedR44;
    private long tvPersonnelClockSessionR44;
    private String tvPersonnelClockFaultR44="";
    public boolean isStreamingAirCarrierFrameR44(){return this.entityData.get(DATA_CARRIER_FRAME_R39);}
    public boolean hasTimedCarrierMotionR44(){return this.entityData.get(DATA_CARRIER_MOTION_ACTIVE)&&!this.isStreamingAirCarrierFrameR44();}
    public Vec3 carrierMotionFromR44(){return new Vec3(this.entityData.get(DATA_CARRIER_FROM_X),this.entityData.get(DATA_CARRIER_FROM_Y),this.entityData.get(DATA_CARRIER_FROM_Z));}
    public Vec3 carrierMotionToR44(){return new Vec3(this.entityData.get(DATA_CARRIER_TO_X),this.entityData.get(DATA_CARRIER_TO_Y),this.entityData.get(DATA_CARRIER_TO_Z));}
    public int carrierMotionDurationR44(){return Math.max(1,this.entityData.get(DATA_CARRIER_MOTION_DURATION));}
    public int tvPersonnelCarrierElapsedR44()
    {
        if(this.tvPersonnelClockHeldR44())return this.entityData.get(DATA_TV_PERSONNEL_ELAPSED_R44);
        return (int)Math.max(0,Math.min(this.carrierMotionDurationR44(),this.level().getGameTime()-(long)this.entityData.get(DATA_CARRIER_MOTION_START)));
    }
    public boolean tvPersonnelClockHeldR44(){return this.entityData.get(DATA_TV_PERSONNEL_CLOCK_HELD_R44);}
    public long tvPersonnelClockSessionR44(){try{return Long.parseLong(this.entityData.get(DATA_TV_PERSONNEL_SESSION_R44));}catch(NumberFormatException ignored){return 0;}}
    public boolean tvPersonnelClockPersistenceInvalidR44(){return this.tvPersonnelClockPersistenceInvalidR44;}
    public String tvPersonnelClockFaultR44(){return this.tvPersonnelClockFaultR44;}
    public int tvPersonnelSavedKindR44(){return this.tvPersonnelClockTagR44.getInt("Kind");}
    public boolean hasSavedTvPersonnelOwnershipR44()
    {
        return this.tvPersonnelClockTagR44.hasUUID("Owner")&&this.tvPersonnelClockTagR44.getUUID("Owner").equals(this.getUUID())
                &&this.tvPersonnelClockTagR44.getString("Dimension").equals("projectseele:geofront");
    }
    public boolean hasSavedTvPersonnelActiveClockR44(){return this.hasSavedTvPersonnelOwnershipR44()&&this.tvPersonnelClockTagR44.getBoolean("Active");}
    private static String tvPersonnelPositionKeyR44(Vec3 p){return p.x+","+p.y+","+p.z;}
    private Vec3 tvPersonnelFrozenPositionR44()
    {
        try
        {
            String[] q=this.entityData.get(DATA_TV_PERSONNEL_FROZEN_R44).split(",");
            if(q.length==3){double x=Double.parseDouble(q[0]),y=Double.parseDouble(q[1]),z=Double.parseDouble(q[2]);
                if(Double.isFinite(x)&&Double.isFinite(y)&&Double.isFinite(z))return new Vec3(x,y,z);}
        }
        catch(NumberFormatException ignored){ }
        return this.position();
    }
    private void clearTvPersonnelHeldFrameR44()
    {
        if(this.tvPersonnelClockHeldR44()&&!this.level().isClientSide&&this.entityData.get(DATA_CARRIER_MOTION_ACTIVE))
            this.entityData.set(DATA_CARRIER_MOTION_START,(int)(this.level().getGameTime()-this.tvPersonnelHeldElapsedR44));
        this.entityData.set(DATA_TV_PERSONNEL_CLOCK_HELD_R44,false);
        this.tvPersonnelClockReloadPendingR44=false;this.tvPersonnelClockFaultR44="";
    }
    /** Shared by AI and the Director: only the owned motion clocks are stopped. */
    public boolean refreshTvPersonnelClockHoldR44()
    {
        if(this.level().isClientSide)return this.tvPersonnelClockHeldR44();
        var decision=com.projectseele.world.TvPersonnelOwnedMotionR44.unit(this);
        if(!decision.owned())
        {
            this.clearTvPersonnelHeldFrameR44();return false;
        }
        if(this.tvPersonnelOwnedKindR44!=decision.kind())
        {this.tvPersonnelOwnedKindR44=decision.kind();this.tvPersonnelClockSessionR44++;this.entityData.set(DATA_TV_PERSONNEL_SESSION_R44,Long.toString(this.tvPersonnelClockSessionR44));}
        String fault=this.tvPersonnelClockPersistenceInvalidR44?"保存的本机时钟版本或数据未知，保留原NBT并停止。":decision.fault().orElse("");
        if(!fault.isEmpty())
        {
            if(!this.tvPersonnelClockHeldR44())
            {
                this.tvPersonnelHeldElapsedR44=this.entityData.get(DATA_CARRIER_MOTION_ACTIVE)?this.tvPersonnelCarrierElapsedR44():0;
                this.entityData.set(DATA_TV_PERSONNEL_ELAPSED_R44,this.tvPersonnelHeldElapsedR44);
                this.entityData.set(DATA_TV_PERSONNEL_FROZEN_R44,tvPersonnelPositionKeyR44(this.position()));
                this.entityData.set(DATA_TV_PERSONNEL_CLOCK_HELD_R44,true);
            }
            this.tvPersonnelClockFaultR44=fault;this.setDeltaMovement(Vec3.ZERO);
            Vec3 frozen=this.tvPersonnelFrozenPositionR44();
            if(this.position().distanceToSqr(frozen)>1e-12)this.setPos(frozen.x,frozen.y,frozen.z);
            com.projectseele.world.TvPersonnelOwnedMotionR44.keepWetMachines((ServerLevel)this.level(),this.getUnitVariant());
            return true;
        }
        this.clearTvPersonnelHeldFrameR44();return false;
    }
    private void saveTvPersonnelClockR44(CompoundTag tag)
    {
        if(this.tvPersonnelClockPersistenceInvalidR44)
        {if(this.tvPersonnelOpaqueClockPayloadR44!=null)tag.put("SeeleTvPersonnelClockR44",this.tvPersonnelOpaqueClockPayloadR44.copy());
            else if(!this.tvPersonnelClockTagR44.isEmpty())tag.put("SeeleTvPersonnelClockR44",this.tvPersonnelClockTagR44.copy());return;}
        var decision=com.projectseele.world.TvPersonnelOwnedMotionR44.unit(this);
        if(!decision.owned()&&this.tvPersonnelClockTagR44.isEmpty())return;
        CompoundTag saved=this.tvPersonnelClockTagR44.copy();
        saved.putInt("Version",1);saved.putUUID("Owner",this.getUUID());saved.putString("Dimension","projectseele:geofront");
        saved.putInt("Kind",decision.owned()?decision.kind():0);saved.putLong("Session",this.tvPersonnelClockSessionR44);
        saved.putBoolean("Active",decision.owned()&&this.hasTimedCarrierMotionR44());saved.putBoolean("Held",decision.owned()&&this.tvPersonnelClockHeldR44());
        saved.putInt("Duration",this.carrierMotionDurationR44());saved.putInt("Elapsed",this.hasTimedCarrierMotionR44()?this.tvPersonnelCarrierElapsedR44():0);
        Vec3 from=this.carrierMotionFromR44(),to=this.carrierMotionToR44(),frozen=this.tvPersonnelClockHeldR44()?this.tvPersonnelFrozenPositionR44():this.position();
        for(String name:new String[]{"From","To","Frozen"})
        {
            Vec3 p=name.equals("From")?from:name.equals("To")?to:frozen;
            saved.putDouble(name+"X",p.x);saved.putDouble(name+"Y",p.y);saved.putDouble(name+"Z",p.z);
        }
        saved.putInt("LaunchPhase",this.getLaunchPhase());saved.putInt("LaunchTicks",this.getLaunchTicks());saved.putInt("ActivationTicks",this.getActivationTicks());
        tag.put("SeeleTvPersonnelClockR44",saved);this.tvPersonnelClockTagR44=saved.copy();
    }
    private void loadTvPersonnelClockR44(CompoundTag tag)
    {
        if(!tag.contains("SeeleTvPersonnelClockR44"))return;
        if(!(tag.get("SeeleTvPersonnelClockR44") instanceof CompoundTag))
        {
            this.tvPersonnelOpaqueClockPayloadR44=tag.get("SeeleTvPersonnelClockR44").copy();
            this.tvPersonnelClockPersistenceInvalidR44=true;
            this.entityData.set(DATA_TV_PERSONNEL_FROZEN_R44,tvPersonnelPositionKeyR44(this.position()));
            if(com.projectseele.world.TvPersonnelOwnedMotionR44.unit(this).owned())this.entityData.set(DATA_TV_PERSONNEL_CLOCK_HELD_R44,true);
            return;
        }
        this.tvPersonnelClockTagR44=tag.getCompound("SeeleTvPersonnelClockR44").copy();
        CompoundTag saved=this.tvPersonnelClockTagR44;this.tvPersonnelClockReloadPendingR44=true;
        boolean valid=saved.getInt("Version")==1&&this.hasSavedTvPersonnelOwnershipR44();
        int duration=saved.getInt("Duration"),elapsed=saved.getInt("Elapsed"),kind=saved.getInt("Kind");
        valid&=duration>=1&&duration<=100000&&elapsed>=0&&elapsed<=duration&&kind>=0&&kind<=3&&saved.getLong("Session")>=0;
        for(String name:new String[]{"From","To","Frozen"})for(String axis:new String[]{"X","Y","Z"})
            valid&=saved.contains(name+axis)&&Double.isFinite(saved.getDouble(name+axis));
        this.tvPersonnelClockPersistenceInvalidR44=!valid;
        Vec3 frozen=valid?new Vec3(saved.getDouble("FrozenX"),saved.getDouble("FrozenY"),saved.getDouble("FrozenZ")):this.position();
        this.entityData.set(DATA_TV_PERSONNEL_FROZEN_R44,tvPersonnelPositionKeyR44(frozen));
        if(valid)
        {
            this.tvPersonnelOwnedKindR44=kind;this.tvPersonnelClockSessionR44=saved.getLong("Session");this.tvPersonnelHeldElapsedR44=elapsed;
            this.entityData.set(DATA_TV_PERSONNEL_SESSION_R44,Long.toString(this.tvPersonnelClockSessionR44));
            this.entityData.set(DATA_TV_PERSONNEL_ELAPSED_R44,elapsed);
            this.entityData.set(DATA_CARRIER_FROM_X,(float)saved.getDouble("FromX"));this.entityData.set(DATA_CARRIER_FROM_Y,(float)saved.getDouble("FromY"));this.entityData.set(DATA_CARRIER_FROM_Z,(float)saved.getDouble("FromZ"));
            this.entityData.set(DATA_CARRIER_TO_X,(float)saved.getDouble("ToX"));this.entityData.set(DATA_CARRIER_TO_Y,(float)saved.getDouble("ToY"));this.entityData.set(DATA_CARRIER_TO_Z,(float)saved.getDouble("ToZ"));
            this.entityData.set(DATA_CARRIER_MOTION_DURATION,duration);this.entityData.set(DATA_CARRIER_MOTION_START,(int)(this.level().getGameTime()-elapsed));
            this.entityData.set(DATA_CARRIER_MOTION_ACTIVE,saved.getBoolean("Active"));this.entityData.set(DATA_CARRIER_FRAME_R39,false);
        }
        // The packet's first held frame is available before any client clock
        // samples. Only an attached, loaded, checked plant may clear this.
        if(com.projectseele.world.TvPersonnelOwnedMotionR44.unit(this).owned())this.entityData.set(DATA_TV_PERSONNEL_CLOCK_HELD_R44,true);
    }

    public void endNervCarrierMotion()
    {
        if (!this.level().isClientSide)
        {
            this.endCarrierMotion();
        }
    }

    public int mechanicalRevisionR30(){return this.entityData.get(MECHANICAL_REVISION_R30);}

    /** A mechanical handoff must discard the previous action and stance, not just its velocity. */
    public void normalizeAfterTransportR30(boolean stored)
    {
        if(level().isClientSide)return;
        boolean preserveProne=!stored&&EvaAirTransportR31.pickupProne(this);
        boolean preserveCrouch=!stored&&EvaAirTransportR31.pickupCrouch(this);
        EvaAirTransportR31.clear(this);EvaCombatR31.clear(this);CombatFeelR31.clear(this);
        this.entityData.set(DATA_CARRIER_RISE_R26,0F);this.oldCarrierRiseR26=0;
        endNervCarrierMotion();cancelLiveActionsForStanceChange();cancelHeavyMotion();clearJumpRequestState();
        if(isLaunchSequenceActive())resetLaunchSequence();
        if(stored)clearSortieDestination();
        this.entityData.set(DATA_CROUCHING,preserveCrouch);this.entityData.set(DATA_PRONE,preserveProne);this.entityData.set(DATA_SPRINTING,false);
        this.entityData.set(DATA_VISUAL_POSE,VISUAL_NORMAL);this.entityData.set(DATA_ACTIVATION_TICKS,0);
        this.entityData.set(DATA_CANNON_CHARGE,0);this.entityData.set(DATA_CANNON_AIM_PITCH,0F);this.entityData.set(DATA_N2_ARM_TICKS,0);
        for(var key:java.util.List.of(DATA_RIFLE_CROUCH,DATA_RIFLE_PRONE,DATA_RIFLE_READY,DATA_RIFLE_RECOIL,DATA_RIFLE_GAIT,DATA_RIFLE_MOVE,DATA_RIFLE_RUN,DATA_RIFLE_STANCE))this.entityData.set(key,0F);
        this.rifleSightHeldR45=false;this.rifleSightPilotR45=null;this.entityData.set(DATA_RIFLE_SIGHT_R45,0F);
        this.entityData.set(DATA_RIFLE_STANCE,preserveProne?3F:preserveCrouch?1F:0F);
        this.entityData.set(DATA_RIFLE_PRONE,preserveProne?1F:0F);
        this.entityData.set(DATA_RIFLE_CROUCH,preserveCrouch?1F:0F);this.rifleStanceVelocity=0;
        this.chargingHeld=false;this.rifleStanceInitialized=true;this.setTarget(null);this.getNavigation().stop();
        this.getPersistentData().putBoolean("UNTransportAutoload",false);
        this.getPersistentData().remove("R30AwaitingIntake");this.getPersistentData().remove("R30AwaitingNervRecovery");
        this.getPersistentData().remove("R31GroundHold");this.getPersistentData().remove("R31GroundHoldAt");
        EvaShutdownR30.waitingR31(this,false);
        EvaDorsalMechanism.set(this,0,0);setDeltaMovement(Vec3.ZERO);setNervLogisticsLocked(stored);setNoGravity(stored);updatePoseDimensions();
        this.entityData.set(MECHANICAL_REVISION_R30,mechanicalRevisionR30()+1);
        if(!stored)EvaShutdownR30.ensureUnpilotedR31(this);
    }

    /** Local action clocks are not part of SynchedEntityData and need their own invalidation. */
    public void resetClientMechanicalClocksR30()
    {
        if(!level().isClientSide)return;
        clearJumpRequestState();clientRootFamily=-1;clientRootSequence=-1;clientRootPrevious=Vec3.ZERO;
        clientMeleeStartTick=clientSmashStartTick=clientKickStartTick=-1000;
        clientActionPhasePrevious=clientActionPhase=this.entityData.get(DATA_LIVE_ACTION_PHASE);clientActionPhaseTick=tickCount;
        var keys=java.util.List.of(DATA_RIFLE_CROUCH,DATA_RIFLE_PRONE,DATA_RIFLE_READY,DATA_RIFLE_RECOIL,DATA_RIFLE_GAIT,DATA_RIFLE_MOVE,DATA_RIFLE_RUN,DATA_RIFLE_STANCE);
        // A newly tracked actor may already have a nonzero mechanical epoch
        // and a valid stationary prone/rifle pose. Seed from this complete
        // metadata packet; forcing zero can outlive it indefinitely because
        // unchanged server values do not generate another data update.
        for(int i=0;i<rifleSignalCurrent.length;i++){float value=this.entityData.get(keys.get(i));rifleSignalCurrent[i]=rifleSignalPrevious[i]=value;rifleSignalTicks[i]=tickCount;poseSignalClocks[i].snap(value);}
        actionSignalClock.snap(clientActionPhase);EvaDorsalMechanism.clearViewR30(this);refreshDimensions();
    }

    public void stowHandsForShutdownR30()
    {
        if(level().isClientSide)return;cancelLiveActionsForStanceChange();cancelHeavyMotion();chargingHeld=false;
        entityData.set(DATA_AT_ON,false);entityData.set(DATA_CANNON_CHARGE,0);entityData.set(DATA_N2_ARM_TICKS,0);selectWeapon(WEAPON_FISTS);
    }

    /** Keeps EVA -> entry plug -> pilot together after authoritative motion. */
    private void syncPassengerAssembly()
    {
        for (Entity passenger : this.getPassengers())
        {
            this.positionRider(passenger, Entity::setPos);
            if (passenger instanceof EntryPlugCarrierEntity plug)
            {
                plug.syncPilotPositionNow();
            }
        }
    }

    /** Clears combat/launch motion before the surface carrier descends. */
    public void prepareForNervRecovery()
    {
        if (this.isLaunchSequenceActive())
        {
            this.resetLaunchSequence();
        }
        this.clearSortieDestination();
        this.entityData.set(DATA_CROUCHING, false);
        this.entityData.set(DATA_PRONE, false);
        this.entityData.set(DATA_SPRINTING, false);
        this.entityData.set(DATA_CANNON_CHARGE, 0);
        this.entityData.set(DATA_N2_ARM_TICKS, 0);
        this.chargingHeld = false;
        this.clearPilotMotion();
        this.updatePoseDimensions();
        this.setNoGravity(true);
    }
    /** The armed carrier bed remains known while the EVA is rising above scan range. */
    @Nullable
    public BlockPos getLaunchBedPosition()
    {
        return this.launchBedPos;
    }

    public boolean isLaunchSequenceActive()
    {
        return this.getLaunchPhase() != LAUNCH_IDLE;
    }

    public boolean hasSortieDestination()
    {
        return this.sortieDestinationDimension != null && this.sortieDestinationBed != null;
    }

    @Nullable
    public ResourceKey<Level> getSortieDestinationDimension()
    {
        return this.sortieDestinationDimension;
    }

    @Nullable
    public BlockPos getSortieDestinationBed()
    {
        return this.sortieDestinationBed;
    }

    /** Arms one exact surface shaft for the next completed launch. */
    public void setSortieDestination(ResourceKey<Level> dimension, BlockPos bed)
    {
        this.sortieDestinationDimension = dimension;
        this.sortieDestinationBed = bed.immutable();
    }

    /** Keeps an unpiloted linked EVA frozen on its assigned underground carrier. */
    public void setSortieParkingBed(BlockPos bed)
    {
        this.sortieParkingBed = bed.immutable();
    }

    public void clearSortieDestination()
    {
        this.sortieDestinationDimension = null;
        this.sortieDestinationBed = null;
        this.sortieParkingBed = null;
    }

    /** Moves an unoccupied parked EVA between audited launch facilities. */
    @Nullable
    public EvaUnit01Entity transferUnpilotedTo(ServerLevel destination, Vec3 position,
                                                float yaw)
    {
        if (this.isVehicle() || this.isPassenger() || this.isLaunchSequenceActive()
                || this.level() == destination)
        {
            return null;
        }
        Entity moved = this.changeDimension(destination,
                directTeleporter(position, Vec3.ZERO, yaw, 0.0F));
        if (!(moved instanceof EvaUnit01Entity relocated))
        {
            return null;
        }
        relocated.setRot(yaw, 0.0F);
        relocated.yRotO = relocated.yBodyRot = relocated.yHeadRot = yaw;
        relocated.setYBodyRot(yaw);
        relocated.setYHeadRot(yaw);
        relocated.setDeltaMovement(Vec3.ZERO);
        relocated.setNoGravity(false);
        return relocated;
    }

    /** A NERV launch bed is identified by the lodestone directly under the carrier. */
    @Nullable
    public BlockPos findLaunchBed()
    {
        if(this.isExperimentalUnit())return null;
        BlockPos base = BlockPos.containing(this.getX(), this.getY() - 0.2D, this.getZ());
        BlockPos nearest = null;
        double nearestDistance = Double.MAX_VALUE;
        for (int depth = 0; depth <= 2; depth++)
        {
            for (int x = -LAUNCH_CARRIER_HALF;
                 x <= LAUNCH_CARRIER_HALF; x++)
            {
                for (int z = -LAUNCH_CARRIER_HALF;
                     z <= LAUNCH_CARRIER_HALF; z++)
                {
                    BlockPos candidate = base.offset(x, -depth, z);
                    if (!this.level().getBlockState(candidate).is(Blocks.LODESTONE))
                    {
                        continue;
                    }
                    if (this.level() instanceof ServerLevel server
                            && FacilityV2EvaRuntime.ready(
                            server, this.getUnitVariant()))
                    {
                        if (!EvaLogisticsDirector.isAssignedLowerLaunchBed(
                                server, this.getUnitVariant(), candidate))
                        {
                            continue;
                        }
                    }
                    else if (this.level() instanceof ServerLevel server
                            ? EvaHangarBuilder.isHangarBed(server, candidate)
                            : EvaHangarBuilder.isHangarBed(candidate))
                    {
                        continue;
                    }
                    double distance = this.distanceToSqr(candidate.getX() + 0.5D,
                            this.getY(), candidate.getZ() + 0.5D);
                    if (distance < nearestDistance)
                    {
                        nearest = candidate.immutable();
                        nearestDistance = distance;
                    }
                }
            }
        }
        return nearest;
    }

    private boolean launchBedClaimedByAnother(BlockPos bed)
    {
        if (!(this.level() instanceof ServerLevel serverLevel))
        {
            return false;
        }
        AABB area = new AABB(bed).inflate(16.0D, 64.0D, 16.0D);
        return !serverLevel.getEntitiesOfClass(EvaUnit01Entity.class, area,
                unit -> unit != this && unit.isAlive() && unit.isLaunchSequenceActive()
                        && bed.equals(unit.getLaunchBedPosition())).isEmpty();
    }

    public float getActivationProgress(float partialTick)
    {
        return Mth.clamp((120.0F - this.getActivationTicks() + partialTick) / 120.0F, 0.0F, 1.0F);
    }

    public int getVisualPose()
    {
        return this.entityData.get(DATA_VISUAL_POSE);
    }

    /** Development-only fixed pose used by the screenshot Visual Lab. */
    public void setVisualPose(int pose)
    {
        int safePose = Mth.clamp(pose, VISUAL_NORMAL, VISUAL_LIVE_JUMP);
        this.entityData.set(DATA_VISUAL_POSE, safePose);
        if (safePose == VISUAL_KNIFE_WINDUP || safePose == VISUAL_KNIFE_CONTACT
                || safePose == VISUAL_KNIFE_RECOVERY || safePose == VISUAL_KNIFE_READY
                || safePose == VISUAL_CROUCH_KNIFE_CONTACT
                || safePose == VISUAL_PRONE_KNIFE_CONTACT
                || safePose == VISUAL_LIVE_KNIFE
                || safePose == VISUAL_LIVE_KNIFE_HEAVY)
        {
            this.entityData.set(DATA_WEAPON, WEAPON_KNIFE);
        }
        else if (safePose == VISUAL_CANNON || safePose == VISUAL_PRONE_CANNON)
        {
            this.entityData.set(DATA_WEAPON, WEAPON_CANNON);
        }
        else if (safePose == VISUAL_RIFLE || safePose == VISUAL_RIFLE_WALK_CONTACT
                || safePose == VISUAL_CROUCH_RIFLE_CONTACT
                || safePose == VISUAL_PRONE_RIFLE
                || safePose == VISUAL_LIVE_RIFLE)
        {
            this.entityData.set(DATA_WEAPON, WEAPON_RIFLE);
        }
        else if (safePose == VISUAL_LANCE_WINDUP || safePose == VISUAL_LANCE_CONTACT
                || safePose == VISUAL_LANCE_RECOVERY || safePose == VISUAL_LANCE_READY
                || safePose == VISUAL_CROUCH_LANCE_CONTACT
                || safePose == VISUAL_PRONE_LANCE_CONTACT
                || safePose == VISUAL_LIVE_LANCE)
        {
            this.entityData.set(DATA_WEAPON, WEAPON_LANCE);
        }
        else if (safePose == VISUAL_N2_READY)
        {
            this.entityData.set(DATA_WEAPON, WEAPON_N2);
        }
        else if (safePose != VISUAL_NORMAL)
        {
            this.entityData.set(DATA_WEAPON, WEAPON_FISTS);
        }
        if (safePose != VISUAL_NORMAL)
        {
            this.setDeltaMovement(Vec3.ZERO);
        }
    }

    /** Cockpit readout uses the persistent pilot value plus live airframe load. */
    public float getSynchronizationRatio(float partialTick)
    {
        float pilotValue = this.getPilotSynchronization();
        if (this.getActivationTicks() > 0)
        {
            return pilotValue * getActivationProgress(partialTick);
        }
        float hullPenalty = (1.0F - this.getHealth() / this.getMaxHealth()) * 11.0F;
        float fieldGain = this.isAtFieldOn() ? 1.6F : 0.0F;
        float motion = this.getDeltaMovement().horizontalDistanceSqr() > 0.002D
                ? Mth.sin((this.tickCount + partialTick) * 0.38F) * 1.25F
                : Mth.sin((this.tickCount + partialTick) * 0.08F) * 0.45F;
        float cannonLoad = this.getCannonCharge() > 0 ? -1.8F * this.chargeProgress() : 0.0F;
        return Mth.clamp(pilotValue - hullPenalty + fieldGain + motion + cannonLoad,
                0.0F, EvaPilotData.maxSynchronization());
    }

    /** Nail to / release from the Tree. Gravity and pose follow the flag. */
    public void setCrucified(boolean crucified)
    {
        this.entityData.set(DATA_CRUCIFIED, crucified);
        this.setNoGravity(crucified);
        if (crucified)
        {
            this.setDeltaMovement(Vec3.ZERO);
            // The cross silhouette is authoritative: held weapons and Visual
            // Lab poses must not layer an aim animation over the outstretched
            // arms during the Third-Impact ritual.
            this.entityData.set(DATA_WEAPON, WEAPON_FISTS);
            this.entityData.set(DATA_VISUAL_POSE, VISUAL_NORMAL);
            this.entityData.set(DATA_CANNON_CHARGE, 0);
            this.entityData.set(DATA_CANNON_AIM_PITCH, 0.0F);
            this.entityData.set(DATA_N2_ARM_TICKS, 0);
            this.entityData.set(DATA_CROUCHING, false);
            this.entityData.set(DATA_PRONE, false);
            this.entityData.set(DATA_SPRINTING, false);
        }
    }

    public boolean isSwingingLeftArm()
    {
        return this.swingingArm == InteractionHand.OFF_HAND;
    }

    /** Camera-rig attack state, driven by the same server command as GeckoLib. */
    public float getCockpitAttackAnim(float partialTick)
    {
        float elapsed = this.tickCount - this.clientMeleeStartTick + partialTick;
        return elapsed >= 0.0F && elapsed < 10.0F ? elapsed / 10.0F : 0.0F;
    }

    public boolean isCockpitSwingingLeft()
    {
        return this.clientMeleeLeft;
    }

    public int getOrdinaryAttackStage()
    {
        return this.level().isClientSide
                ? this.clientOrdinaryAttackStage
                : this.entityData.get(DATA_ORDINARY_ATTACK_STAGE);
    }

    public float getOrdinaryAttackProgress(float partialTick)
    {
        int stage = this.getOrdinaryAttackStage();
        if (stage < 0)
        {
            return 0.0F;
        }
        return this.liveActionProgress(partialTick);
    }

    /** Never let a client clock outrun the authoritative contact/root timeline. */
    private float liveActionProgress(float partialTick)
    {
        if(CombatFeelR31.hitPaused(this))return CombatFeelR31.frozenPhase(this);
        if (!this.level().isClientSide) return this.entityData.get(DATA_LIVE_ACTION_PHASE);
        return actionSignalClock.sample(FirstBattleSignals.clientFrameTime());
    }

    private float ordinaryAttackDurationTicks(int stage)
    {
        return this.ordinaryAttackBaseDurationTicks(stage) / MELEE_RATE_R43;
    }

    private float ordinaryAttackBaseDurationTicks(int stage)
    {
        float authored=EvaGameplayMotionR32.authoredOrdinaryTicksR45(this,stage);
        if(authored>0)return authored/Math.min(1.08F,EvaPilotCapability.attackSpeedMultiplier(this.getPilotSynchronization()));
        if(EvaGameplayMotionR32.directed(this))return (stage==1?25F:stage==2?27F:23F)/Math.min(1.08F,EvaPilotCapability.attackSpeedMultiplier(this.getPilotSynchronization()));
        if(EvaCombatSupportR33.ready(this))return (stage==1?27F:stage==2?29F:24F)/Math.min(1.08F,EvaPilotCapability.attackSpeedMultiplier(this.getPilotSynchronization()));
        if(EvaGameplayMotionR32.ready(this))return (stage==1?18F:stage==2?17F:16F)/EvaPilotCapability.attackSpeedMultiplier(this.getPilotSynchronization());
        int logicalStage = stage == 3 ? 0 : stage;
        int safeStage = Mth.clamp(logicalStage, 0,
                ORDINARY_ATTACK_FRAME_INTERVALS.length - 1);
        float authoredTicks = ORDINARY_ATTACK_FRAME_INTERVALS[safeStage]
                * 20.0F / ORDINARY_ATTACK_SOURCE_FPS
                / ORDINARY_ATTACK_PLAYBACK_SPEED;
        return authoredTicks / EvaPilotCapability.attackSpeedMultiplier(
                this.getPilotSynchronization());
    }

    private int ordinaryAttackVisualTicks(int stage)
    {
        return Math.max(1, Mth.ceil(this.ordinaryAttackDurationTicks(stage)));
    }

    private int ordinaryAttackContactTicks(int stage)
    {
        if(EvaGameplayMotionR32.ready(this))return Math.max(1,Math.round(ordinaryAttackDurationTicks(stage)
                *EvaGameplayMotionR32.contactPhase(this,EvaGameplayMotionR32.ordinary(stage))));
        int logicalStage = stage == 3 ? 0 : stage;
        int safeStage = Mth.clamp(logicalStage, 0,
                ORDINARY_ATTACK_CONTACT_FRAMES.length - 1);
        float authoredTicks = ORDINARY_ATTACK_CONTACT_FRAMES[safeStage]
                * 20.0F / ORDINARY_ATTACK_SOURCE_FPS
                / ORDINARY_ATTACK_PLAYBACK_SPEED;
        float synchronizedTicks = authoredTicks
                / EvaPilotCapability.attackSpeedMultiplier(
                        this.getPilotSynchronization());
        return Math.max(1, Math.round(synchronizedTicks / MELEE_RATE_R43));
    }

    public float getCockpitSmashAnim(float partialTick)
    {
        if (this.isHeavyMotionActive()) return Math.max(.0001F, this.liveActionProgress(partialTick));
        float elapsed = this.tickCount - this.clientSmashStartTick + partialTick;
        return elapsed >= 0.0F && elapsed < 18.0F ? elapsed / 18.0F : 0.0F;
    }

    /** -1 none, 0 approved forward-grip LMB, 1 approved reverse-grip RMB. */
    public int getKnifeMotionType(float partialTick)
    {
        if (this.getWeapon() != WEAPON_KNIFE || ((this.isPilotProne()
                || this.isPilotCrouching()) && !EvaGameplayMotionR32.lowAttackReadyR44(this)) || this.entityData.get(DATA_KNIFE_TYPE) < 0)
        {
            return -1;
        }
        return this.entityData.get(DATA_KNIFE_TYPE);
    }

    public float getKnifeMotionProgress(int type, float partialTick)
    {
        return this.liveActionProgress(partialTick);
    }

    public boolean hasLiveActionForRender(float partialTick)
    {
        return EvaSwordActionsR45.active(this) || EvaFieldActionsR45.active(this) || this.isHeavyMotionActive() || this.getOrdinaryAttackStage() >= 0
                || this.isKickMotionActive(partialTick)
                || this.getKnifeMotionType(partialTick) >= 0;
    }
    public boolean hasLegacyStrikeForRender()
    {
        if(!this.level().isClientSide||this.hasLiveActionForRender(0)||!this.isPoweredOn())return false;
        // A legacy takeoff/landing trigger must not veto the physics-timed
        // whole-body jump. Otherwise updated jump assets are never rendered.
        if(EvaGameplayMotionR32.sharedJumpActive(this,0))return false;
        var controller=this.geoCache.getManagerForId(this.getId()).getAnimationControllers().get("strike");
        return controller!=null&&controller.isPlayingTriggeredAnimation();
    }

    public String poseTransitionKey(float partialTick)
    {
        // The directed clip owns its own airborne/landing/contact changes.
        // Blend once at its entry and exit, not again at each gait-key change.
        if(this.isFirstBattleActive())return "firstbattle";
        String pose;
        if (this.getOrdinaryAttackStage() >= 0)
            pose = "ordinary:" + this.clientMeleeStartTick;
        else if (this.isKickMotionActive(partialTick))
            pose = "kick:" + this.clientKickStartTick;
        else if (this.getKnifeMotionType(partialTick) >= 0)
            pose = "knife:" + this.getKnifeMotionType(partialTick) + ":"
                    + (this.getKnifeMotionType(partialTick) == 1
                    ? this.clientSmashStartTick : this.clientMeleeStartTick);
        else if (this.getCockpitSmashAnim(partialTick) > 0.0F)
            pose = "smash:" + this.clientSmashStartTick;
        else if (this.getCockpitAttackAnim(partialTick) > 0.0F)
            pose = "melee:" + this.clientMeleeStartTick;
        else if (this.isPilotProne())
            pose = "prone:" + this.isVisuallyMovingForRender();
        else if (this.isPilotCrouching())
            pose = "crouch:" + this.isVisuallyMovingForRender();
        else if (this.isVisuallyAirborneForRender())
            pose = "airborne";
        else
            pose = this.isVisuallyMovingForRender()
                    ? this.isVisualRunRequested() ? "run" : "walk" : "idle";
        return this.getWeapon() + ":" + pose;
    }

    private float knifeDurationTicks(boolean reverse)
    {
        int intervals = reverse ? KNIFE_REVERSE_FRAME_INTERVALS
                : KNIFE_FORWARD_FRAME_INTERVALS;
        float authoredTicks = intervals * 20.0F / KNIFE_SOURCE_FPS;
        return authoredTicks / EvaPilotCapability.attackSpeedMultiplier(
                this.getPilotSynchronization()) / MELEE_RATE_R43;
    }

    private int knifeVisualTicks(boolean reverse)
    {
        return Math.max(1, Mth.ceil(this.knifeDurationTicks(reverse)));
    }

    // ----- pilot commands (validated by the packet handler) -----

    public void cycleWeapon(ServerPlayer pilot)
    {
        EvaSwordActionsR45.cancelByPilotR45(this,pilot);
        if (this.isPilotControlLocked())
        {
            return;
        }
        int next = this.getWeapon();
        for (int offset = 1; offset <= LAST_WEAPON_R45 + 1; offset++)
        {
            int candidate = Math.floorMod(this.getWeapon() + offset,
                    LAST_WEAPON_R45 + 1);
            if (this.armamentAvailable(candidate))
            {
                next = candidate;
                break;
            }
        }
        if(!EvaWeaponHandlingR45.request(this,next))this.selectWeapon(next);
        pilot.displayClientMessage(Component.translatable(this.getWeaponTranslationKey()), true);
        EvaMovementSounds.play(this,this.getPilotCameraSeatPosition(pilot),ModSounds.EVA_COCKPIT_CONFIRM.get(),.4F,1);
    }

    public String getWeaponTranslationKey()
    {
        return switch (this.getWeapon())
        {
            case WEAPON_KNIFE -> "msg.projectseele.weapon_knife";
            case WEAPON_CANNON -> "msg.projectseele.weapon_cannon";
            case WEAPON_LANCE -> this.getUnitVariant() == UNIT_02
                    ? "msg.projectseele.weapon_unit02_special"
                    : "msg.projectseele.weapon_lance";
            case WEAPON_RIFLE -> "msg.projectseele.weapon_rifle";
            case WEAPON_N2 -> "msg.projectseele.weapon_n2";
            case WEAPON_SWORD_R45 -> "msg.projectseele.weapon_sword";
            case WEAPON_SHIELD_R45 -> "msg.projectseele.weapon_shield";
            default -> "msg.projectseele.weapon_fists";
        };
    }

    public void toggleAtField(ServerPlayer pilot)
    {
        if (this.isPilotControlLocked())
        {
            return;
        }
        if (!this.isAtFieldOn() && this.getAtFieldEnergy() < AT_FIELD_MIN_TO_RAISE)
        {
            pilot.displayClientMessage(Component.translatable("msg.projectseele.at_field_low"), true);
            return;
        }
        boolean on = !this.isAtFieldOn();
        this.entityData.set(DATA_AT_ON, on);
        pilot.displayClientMessage(Component.translatable(
                on ? "msg.projectseele.at_field_on" : "msg.projectseele.at_field_off"), true);
        this.playSound(ModSounds.CRYSTAL_HIT.get(), 2.0F, on ? 0.8F : 0.5F);
        if (on && this.level() instanceof ServerLevel serverLevel)
        {
            Vec3 front = this.position().add(this.getForward().scale(Math.max(7.5D,this.getBbWidth()))).add(0.0D,this.getBbHeight()*.55D,0.0D);
            AtFieldFX.ripple(serverLevel,front,this.getForward(),Math.max(10.5F,this.getBbHeight()*.58F));
        }
    }

    public void setChargingHeld(boolean held)
    {
        this.chargingHeld = held && !this.isPilotControlLocked();
    }

    /** Left-click from the plug: Tiger-reviewed strikes and weapon clips. */
    public void meleeAttack(ServerPlayer pilot)
    { meleeAttack((LivingEntity)pilot); }

    private void meleeAttack(LivingEntity pilot)
    {
        if(this.getWeapon()==WEAPON_SWORD_R45){EvaSwordActionsR45.request(this,pilot,false);return;}
        if(CombatFeelR31.restrained(this)){EvaCombatIntentR32.offer(this,pilot,0);return;}
        if(EvaCombatR31.attack(this,false))return;
        if (this.isPilotControlLocked() || !this.isMeleeWeapon())
        {
            return;
        }
        if (this.isHeavyMotionActive())
        {
            this.queuedMeleeAfterHeavy = true;
            return;
        }
        boolean prone = this.isPilotProne();
        boolean crouching = this.isPilotCrouching();
        boolean liveOrdinaryAttack = this.getWeapon() == WEAPON_FISTS
                && ((!prone && !crouching) || EvaGameplayMotionR32.lowAttackReadyR44(this));
        if(liveOrdinaryAttack&&!prone&&!crouching&&this.getOrdinaryAttackStage()<0&&pilot instanceof ServerPlayer player&&this.needsClosingStepR32(player))return;
        if (this.getWeapon() == WEAPON_KNIFE && ((!prone && !crouching) || EvaGameplayMotionR32.lowAttackReadyR44(this))
                && this.knifeVisualTicks > 0)
        {
            // Holding LMB cannot overwrite an explicitly buffered RMB.
            if (this.queuedKnifeInput != 1) this.queuedKnifeInput = 0;
            return;
        }
        if (liveOrdinaryAttack && this.kickVisualTicks > 0)
        {
            this.ordinaryAfterKickBufferTicks = CROSS_ACTION_BUFFER_TICKS;
            return;
        }
        if (this.meleeCooldown > 0)
        {
            this.meleeInputBufferTicks = MELEE_INPUT_BUFFER_TICKS;
            if (this.getTags().contains("seele_motion_lab"))
            {
                ProjectSeele.LOGGER.info(
                        "EVA motion-lab melee buffered: eva={} weapon={} cooldown={}",
                        this.getStringUUID(), this.getWeapon(),
                        this.meleeCooldown);
            }
            return;
        }
        this.meleeInputBufferTicks = 0;
        if (liveOrdinaryAttack)
        {
            this.beginOrdinaryGroupCAttack();
            return;
        }
        boolean lance = this.getWeapon() == WEAPON_LANCE;
        boolean knife = this.getWeapon() == WEAPON_KNIFE;
        boolean liveKnife = knife && ((!prone && !crouching) || EvaGameplayMotionR32.lowAttackReadyR44(this));
        this.meleeCooldown = liveKnife ? this.knifeVisualTicks(false)
                : this.fastMeleeCooldownR43(MELEE_COOLDOWN_TICKS);
        boolean fixedRightHandWeapon = lance || knife;
        this.cancelOrdinaryGroupCAttack();
        this.cancelSideKick();
        this.cancelKnifeMotion();
        this.leftSwing = fixedRightHandWeapon ? false : !this.leftSwing;
        this.entityData.set(DATA_MELEE_LEFT, this.leftSwing);
        this.entityData.set(DATA_MELEE_SEQUENCE,
                (this.entityData.get(DATA_MELEE_SEQUENCE) + 1) & Integer.MAX_VALUE);
        if (liveKnife)
        {
            this.beginKnifeMotion(false);
        }
        this.swing(this.leftSwing ? InteractionHand.OFF_HAND : InteractionHand.MAIN_HAND, true);
        String animation = prone
                ? lance ? "prone_lance_thrust"
                    : knife ? "prone_knife"
                    : (this.leftSwing ? "prone_melee_left" : "prone_melee")
                : crouching
                    ? lance ? "crouch_lance_thrust"
                        : knife ? "crouch_knife"
                        : (this.leftSwing ? "crouch_melee_left" : "crouch_melee")
                : lance ? "lance_thrust"
                    : knife ? "knife"
                    : (this.leftSwing ? "melee_left" : "melee");
        if (!liveKnife) this.triggerAnim("strike", animation);
        if (this.getTags().contains("seele_motion_lab"))
        {
            ProjectSeele.LOGGER.info(
                    "EVA motion-lab melee accepted: eva={} weapon={} animation={}",
                    this.getStringUUID(), this.getWeapon(), animation);
        }
        if (liveKnife) return;
        float baseDamage = lance ? MELEE_LANCE_DAMAGE : knife ? MELEE_KNIFE_DAMAGE : MELEE_FIST_DAMAGE;
        float damage = baseDamage * this.getMeleeMultiplier();
        Vec3 forward = this.getForward().multiply(1.0D, 0.0D, 1.0D).normalize();
        double strikeHeight = prone ? 3.2D : this.isPilotCrouching() ? 8.0D : 14.0D;
        double verticalRadius = prone ? 3.2D : this.isPilotCrouching() ? 6.0D : 10.0D;
        Vec3 center = this.position().add(forward.scale(MELEE_REACH))
                .add(0.0D, strikeHeight, 0.0D);
        AABB zone = new AABB(center, center).inflate(MELEE_RADIUS, verticalRadius, MELEE_RADIUS);
        this.strikeZone(pilot, zone, damage, 1.1D, center);
    }

    public boolean isKickMotionActive(float partialTick)
    {
        return this.entityData.get(DATA_KICK_ACTIVE)
                && this.getWeapon() == WEAPON_FISTS
                && !this.isPilotProne() && !this.isPilotCrouching();
    }

    public float getKickAttackProgress(float partialTick)
    {
        return this.liveActionProgress(partialTick);
    }

    private float kickDurationTicks()
    {
        float authoredTicks = KICK_FRAME_INTERVALS * 20.0F
                / KICK_SOURCE_FPS / KICK_PLAYBACK_SPEED;
        return authoredTicks / EvaPilotCapability.attackSpeedMultiplier(
                this.getPilotSynchronization()) / MELEE_RATE_R43;
    }

    private int kickVisualTicks()
    {
        return Math.max(1, Mth.ceil(this.kickDurationTicks()));
    }

    private int kickContactTicks()
    {
        if(EvaGameplayMotionR32.kickReady(this))
            return Math.max(1,Math.round(this.kickDurationTicks()*EvaGameplayMotionR32.contactPhase(this,"kick")));
        float authoredTicks = KICK_CONTACT_FRAME * 20.0F
                / KICK_SOURCE_FPS / KICK_PLAYBACK_SPEED;
        float synchronizedTicks = authoredTicks
                / EvaPilotCapability.attackSpeedMultiplier(
                        this.getPilotSynchronization());
        return Math.max(1, Math.round(synchronizedTicks / MELEE_RATE_R43));
    }

    private void beginOrdinaryGroupCAttack()
    {
        com.projectseele.world.CombatCommandBriefR47.attackCommitted(this,"punch");
        EvaGameplayMotionR32.beginAction(this);
        if(EvaGameplayMotionR32.phrases(this))CombatFoleyR36.load(this);
        this.gameplayOrdinaryContactR32=false;
        if(EvaGameplayMotionR32.ready(this)&&!EvaGameplayMotionR32.directed(this))EvaMovementSounds.swing(this,.8F);
        boolean continuing = this.ordinaryAttackComboGraceTicks > 0;
        boolean selectedThreeStage=EvaGameplayMotionR32.selectedThreeStageR45(this);
        int stage = continuing
                ? Math.floorMod(this.ordinaryAttackComboStage + 1,
                        selectedThreeStage?3:EvaGameplayMotionR32.phrases(this)?2:ORDINARY_ATTACK_FRAME_INTERVALS.length)
                : 0;
        int visualStage = (!EvaGameplayMotionR32.phrases(this)||selectedThreeStage)&&continuing&&stage==0?3:stage;
        int visualTicks = this.ordinaryAttackVisualTicks(visualStage);
        this.ordinaryAttackComboStage = stage;
        this.ordinaryAttackComboGraceTicks = Math.max(
                MELEE_INPUT_BUFFER_TICKS, visualTicks + 14);
        this.ordinaryAttackVisualTicks = visualTicks;
        this.entityData.set(DATA_LIVE_ACTION_PHASE, 0.0F);
        this.ordinaryAttackElapsedTicks = 0;
        this.ordinaryAttackDurationAtStart =
                this.ordinaryAttackDurationTicks(visualStage);
        this.ordinaryAttackRootStage = visualStage;
        this.liveCombatRootPrevious = EvaGameplayMotionR32.ready(this)?EvaGameplayMotionR32.root(this,EvaGameplayMotionR32.ordinary(visualStage),0):EvaLiveCombatMotion.ordinary(visualStage,0);
        this.pendingOrdinaryContactTicks =
                this.ordinaryAttackContactTicks(visualStage);
        this.pendingOrdinaryContactStage = stage;
        this.ordinaryAfterKickBufferTicks = 0;
        this.meleeCooldown = visualTicks;
        this.leftSwing = EvaGameplayMotionR32.ready(this)?EvaGameplayMotionR32.side(this,EvaGameplayMotionR32.ordinary(visualStage)).equals("l"):stage==1;
        this.entityData.set(DATA_MELEE_LEFT, this.leftSwing);
        this.entityData.set(DATA_ORDINARY_ATTACK_STAGE, visualStage);
        this.entityData.set(DATA_MELEE_SEQUENCE,
                (this.entityData.get(DATA_MELEE_SEQUENCE) + 1)
                        & Integer.MAX_VALUE);
        this.ordinaryAcceptedTargetsR45.begin(this.entityData.get(DATA_MELEE_SEQUENCE),this.level().getGameTime());
        this.swing(this.leftSwing ? InteractionHand.OFF_HAND
                : InteractionHand.MAIN_HAND, true);
        if (this.getTags().contains("seele_motion_lab"))
        {
            ProjectSeele.LOGGER.info(
                    "EVA motion-lab group-C melee accepted: eva={} stage={} "
                            + "visualTicks={} contactTicks={} speed={}x",
                    this.getStringUUID(), stage, visualTicks,
                    this.pendingOrdinaryContactTicks,
                    ORDINARY_ATTACK_PLAYBACK_SPEED);
        }
    }

    private void resolveOrdinaryGroupCContact(LivingEntity pilot, int stage)
    {
        if(EvaGameplayMotionR32.ready(this))
        {
            String clip=EvaGameplayMotionR32.ordinary(Math.max(0,stage));
            Vec3 point=EvaGameplayMotionR32.hand(this,EvaGameplayMotionR32.side(this,clip),1);
            this.strikeSweepR32(pilot,EvaGameplayMotionR32.previousContact(this,point),point,3.2F,MELEE_FIST_DAMAGE*this.getMeleeMultiplier(),1.1D);return;
        }
        float damage = MELEE_FIST_DAMAGE * this.getMeleeMultiplier();
        Vec3 forward = this.getForward().multiply(1.0D, 0.0D, 1.0D)
                .normalize();
        Vec3 hand=EvaLiveCombatMotion.ordinaryContact(Math.max(0,this.getOrdinaryAttackStage()),this.liveActionProgress(1));
        Vec3 lateral=new Vec3(forward.z,0,-forward.x);
        Vec3 center=this.position().add(lateral.scale(hand.x)).add(0,hand.y,0).add(forward.scale(hand.z));
        if ("r10-firstbattle".equals(System.getProperty("projectseele.regionalBuild","")))
            ProjectSeele.LOGGER.info("R10 CONTACT stage={} phase={} center={} forward={}",stage,this.liveActionProgress(1),center,forward);
        Vec3 previous=EvaLiveCombatMotion.ordinaryContact(Math.max(0,stage),Math.max(0,this.liveActionProgress(1)-2F/this.ordinaryAttackDurationTicks(stage)));
        Vec3 from=this.position().add(lateral.scale(previous.x)).add(0,previous.y,0).add(forward.scale(previous.z));
        this.strikeSweepR32(pilot,from,center,3.2,damage,1.1D);
        if (this.getTags().contains("seele_motion_lab"))
        {
            ProjectSeele.LOGGER.info(
                    "EVA motion-lab group-C melee contact: eva={} stage={}",
                    this.getStringUUID(), stage);
        }
    }

    private void cancelOrdinaryGroupCAttack()
    {
        this.ordinaryAcceptedTargetsR45.end();
        this.ordinaryAttackVisualTicks = 0;
        this.ordinaryAttackComboStage = -1;
        this.ordinaryAttackComboGraceTicks = 0;
        this.pendingOrdinaryContactTicks = 0;
        this.pendingOrdinaryContactStage = -1;
        this.ordinaryAttackElapsedTicks = 0;
        this.ordinaryAttackDurationAtStart = 0.0F;
        this.entityData.set(DATA_ORDINARY_ATTACK_STAGE, -1);
    }

    /** Crouch + attack: a slow two-handed slam that flattens the area ahead. */
    public void smashAttack(ServerPlayer pilot)
    { smashAttack((LivingEntity)pilot); }

    private void smashAttack(LivingEntity pilot)
    {
        if(this.getWeapon()==WEAPON_SWORD_R45){EvaSwordActionsR45.request(this,pilot,true);return;}
        if(CombatFeelR31.restrained(this)){EvaCombatIntentR32.offer(this,pilot,1);return;}
        if(EvaCombatR31.attack(this,true))return;
        if(this.heavyTicks>0){this.queuedHeavy=true;return;}
        if (this.getWeapon() == WEAPON_FISTS && ((!this.isPilotProne() && !this.isPilotCrouching()) || EvaGameplayMotionR32.lowAttackReadyR44(this))
                && !this.isPilotControlLocked() && this.smashCooldown == 0
                && (this.ordinaryAttackVisualTicks > 0 || this.kickVisualTicks > 0))
        {
            this.queuedHeavy = true;
            return;
        }
        if (!this.isPilotControlLocked() && this.getWeapon() == WEAPON_KNIFE
                && ((!this.isPilotCrouching() && !this.isPilotProne()) || EvaGameplayMotionR32.lowAttackReadyR44(this))
                && this.knifeVisualTicks > 0)
        {
            this.queuedKnifeInput = 1;
            return;
        }
        if (this.isPilotControlLocked() || this.smashCooldown > 0
                || !this.isMeleeWeapon() || this.kickVisualTicks > 0)
        {
            return;
        }
        EvaGameplayMotionR32.beginAction(this);
        this.cancelOrdinaryGroupCAttack();
        this.cancelSideKick();
        this.cancelKnifeMotion();
        this.smashCooldown = this.getWeapon()==WEAPON_KNIFE
                ?this.fastMeleeCooldownR43(SMASH_COOLDOWN_TICKS):this.synchronizedCooldown(SMASH_COOLDOWN_TICKS);
        this.entityData.set(DATA_SMASH_SEQUENCE,
                (this.entityData.get(DATA_SMASH_SEQUENCE) + 1) & Integer.MAX_VALUE);
        com.projectseele.world.CombatCommandBriefR47.attackCommitted(this,this.getWeapon()==WEAPON_KNIFE?"knife":"smash");

        boolean knife = this.getWeapon() == WEAPON_KNIFE;
        boolean lance = this.getWeapon() == WEAPON_LANCE;
        boolean liveKnife = knife && ((!this.isPilotProne() && !this.isPilotCrouching()) || EvaGameplayMotionR32.lowAttackReadyR44(this));
        if (this.getWeapon() == WEAPON_FISTS && ((!this.isPilotProne() && !this.isPilotCrouching()) || EvaGameplayMotionR32.lowAttackReadyR44(this)))
        {
            if(EvaGameplayMotionR32.ready(this)&&!EvaGameplayMotionR32.directed(this))EvaMovementSounds.swing(this,1.1F);
            int authoredHeavy=EvaGameplayMotionR32.authoredHeavyTicksR45(this);
            this.heavyDuration = authoredHeavy>0?this.fastMeleeCooldownR43(authoredHeavy)
                    :this.synchronizedCooldown(EvaCombatSupportR33.ready(this)?34:24);
            this.heavyTicks = this.heavyDuration;
            this.heavyElapsed = 0;
            this.heavyContact = false;
            this.queuedHeavy = false;
            this.liveCombatRootPrevious = EvaGameplayMotionR32.ready(this)
                    ?EvaGameplayMotionR32.root(this,"heavy",0):EvaLiveCombatMotion.heavy(0);
            this.entityData.set(DATA_LIVE_ACTION_PHASE, 0F);
            this.entityData.set(DATA_HEAVY_ACTIVE, true);
            if (this.getTags().contains("seele_motion_lab")) ProjectSeele.LOGGER.info("EVA heavy begin tick={} duration={}", this.tickCount, this.heavyDuration);
            return;
        }
        if (liveKnife)
        {
            this.beginKnifeMotion(true);
        }
        String animation = knife
                ? this.isPilotProne() ? "prone_knife_heavy"
                    : this.isPilotCrouching() ? "crouch_knife_heavy" : "knife_heavy"
                : lance
                    ? this.isPilotProne() ? "prone_lance_thrust"
                        : this.isPilotCrouching() ? "crouch_lance_thrust" : "lance_thrust"
                    : this.isPilotProne() ? "prone_smash"
                        : this.isPilotCrouching() ? "crouch_smash" : "smash";
        if (liveKnife) return;
        this.triggerAnim("strike", animation);
        this.resolveHeavyContact(pilot);
    }

    public boolean isHeavyMotionActive() { return this.entityData.get(DATA_HEAVY_ACTIVE); }
    public float heavyMotionProgress(float partial) { return this.liveActionProgress(partial); }
    private void cancelHeavyMotion()
    {
        this.heavyTicks = 0;
        this.queuedHeavy = false;
        this.queuedMeleeAfterHeavy = false;
        this.queuedKickAfterHeavy = false;
        this.entityData.set(DATA_HEAVY_ACTIVE, false);
    }
    private void resolveHeavyContact(LivingEntity pilot)
    {
        if(EvaGameplayMotionR32.ready(this)&&this.isHeavyMotionActive())
        {
            Vec3 point=EvaGameplayMotionR32.hand(this,EvaGameplayMotionR32.side(this,"heavy"),1);
            this.strikeSweepR32(pilot,EvaGameplayMotionR32.previousContact(this,point),point,4,SMASH_FIST_DAMAGE*this.getMeleeMultiplier(),2);return;
        }
        boolean knife = this.getWeapon() == WEAPON_KNIFE, lance = this.getWeapon() == WEAPON_LANCE;
        float baseDamage = lance ? SMASH_LANCE_DAMAGE : knife ? SMASH_KNIFE_DAMAGE : SMASH_FIST_DAMAGE;
        float damage = baseDamage * this.getMeleeMultiplier();
        Vec3 forward = this.getForward().multiply(1.0D, 0.0D, 1.0D).normalize();
        Vec3 center = this.position().add(forward.scale(
                MELEE_REACH + EvaScale.fromLegacy(1.0D)))
                .add(0.0D, EvaScale.fromLegacy(4.0D), 0.0D);
        if(this.isHeavyMotionActive())
        {
            Vec3 hand=EvaLiveCombatMotion.heavyContact(this.liveActionProgress(1));
            Vec3 lateral=new Vec3(forward.z,0,-forward.x);
            center=this.position().add(lateral.scale(hand.x)).add(0,hand.y,0).add(forward.scale(hand.z));
            if(this.getTags().contains("seele_motion_lab"))ProjectSeele.LOGGER.info("EVA heavy impact centre={} damage={}",center,damage);
            Vec3 previous=EvaLiveCombatMotion.heavyContact(Math.max(0,this.liveActionProgress(1)-2F/Math.max(1,this.heavyDuration)));
            Vec3 from=this.position().add(lateral.scale(previous.x)).add(0,previous.y,0).add(forward.scale(previous.z));
            this.strikeSweepR32(pilot,from,center,4,damage,2.0D);return;
        }
        AABB zone = new AABB(center, center).inflate(SMASH_RADIUS,
                EvaScale.fromLegacy(8.5D), SMASH_RADIUS);
        this.strikeZone(pilot, zone, damage, 2.0D, center);
    }

    /** B key: selected K1 side kick for standing fists, legacy stomp otherwise. */
    public void stompAttack(ServerPlayer pilot)
    { stompAttack((LivingEntity)pilot); }

    private void stompAttack(LivingEntity pilot)
    {
        if(CombatFeelR31.restrained(this)||EvaCombatR31.active(this))return;
        if (this.isHeavyMotionActive())
        {
            this.queuedKickAfterHeavy = true;
            return;
        }
        if (this.isPilotControlLocked() || this.isPilotProne()
                || !this.isMeleeWeapon())
        {
            return;
        }
        boolean liveSideKick = this.getWeapon() == WEAPON_FISTS
                && !this.isPilotCrouching();
        if (liveSideKick && this.ordinaryAttackVisualTicks > 0)
        {
            if (this.stompCooldown == 0)
            {
                this.kickAfterOrdinaryBufferTicks =
                        CROSS_ACTION_BUFFER_TICKS;
            }
            return;
        }
        if (this.stompCooldown > 0)
        {
            return;
        }
        if (liveSideKick)
        {
            this.beginSideKick();
            return;
        }
        this.cancelOrdinaryGroupCAttack();
        this.cancelSideKick();
        this.stompCooldown = this.fastMeleeCooldownR43(STOMP_COOLDOWN_TICKS);
        this.triggerAnim("strike", "stomp");

        this.resolveStompContact(pilot);
    }

    private void beginSideKick()
    {
        EvaGameplayMotionR32.beginAction(this);
        this.cancelOrdinaryGroupCAttack();
        this.cancelKnifeMotion();
        this.kickAfterOrdinaryBufferTicks = 0;
        this.meleeInputBufferTicks = 0;
        this.kickVisualTicks = this.kickVisualTicks();
        this.entityData.set(DATA_LIVE_ACTION_PHASE, 0.0F);
        this.entityData.set(DATA_KICK_ACTIVE, true);
        this.kickElapsedTicks = 0;
        this.kickDurationAtStart = this.kickDurationTicks();
        this.liveCombatRootPrevious = EvaGameplayMotionR32.kickReady(this)?EvaGameplayMotionR32.root(this,"kick",0):EvaLiveCombatMotion.kick(0.0F);
        this.pendingKickContactTicks = this.kickContactTicks();
        this.stompCooldown = this.fastMeleeCooldownR43(STOMP_COOLDOWN_TICKS);
        this.entityData.set(DATA_KICK_SEQUENCE,
                (this.entityData.get(DATA_KICK_SEQUENCE) + 1)
                        & Integer.MAX_VALUE);
        if (this.getTags().contains("seele_motion_lab"))
        {
            ProjectSeele.LOGGER.info(
                    "EVA motion-lab side kick accepted: eva={} "
                            + "visualTicks={} contactTicks={} speed={}x",
                    this.getStringUUID(), this.kickVisualTicks,
                    this.pendingKickContactTicks, KICK_PLAYBACK_SPEED);
        }
    }

    private void resolveSideKickContact(LivingEntity pilot)
    {
        if(EvaGameplayMotionR32.kickReady(this))
        {
            Vec3 point=EvaGameplayMotionR32.contact(this,"kick",1);
            this.strikeSweepR32(pilot,EvaGameplayMotionR32.previousContact(this,point),point,4,
                    STOMP_DAMAGE*this.getMeleeMultiplier(),2.4D);return;
        }
        Vec3 forward=this.getForward().multiply(1,0,1).normalize(),lateral=new Vec3(forward.z,0,-forward.x);
        Vec3 foot=EvaLiveCombatMotion.kickContact(this.liveActionProgress(1));
        Vec3 center=this.position().add(lateral.scale(foot.x)).add(0,foot.y,0).add(forward.scale(foot.z));
        this.strikeZone(pilot,new AABB(center,center).inflate(STOMP_RADIUS,EvaScale.fromLegacy(3.5D),STOMP_RADIUS),
                STOMP_DAMAGE*this.getMeleeMultiplier(),2.4D,center);
        if (this.getTags().contains("seele_motion_lab"))
        {
            ProjectSeele.LOGGER.info(
                    "EVA motion-lab side kick contact: eva={}",
                    this.getStringUUID());
        }
    }

    private void resolveStompContact(LivingEntity pilot)
    {
        Vec3 forward = this.getForward().multiply(1.0D, 0.0D, 1.0D).normalize();
        Vec3 center = this.position().add(forward.scale(2.8D)).add(0.0D, 1.0D, 0.0D);
        AABB zone = new AABB(center, center).inflate(STOMP_RADIUS,
                EvaScale.fromLegacy(3.5D), STOMP_RADIUS);
        this.strikeZone(pilot, zone, STOMP_DAMAGE * this.getMeleeMultiplier(), 2.4D, center);
        this.playSound(ModSounds.EVA_LAND.get(),1.5F,1.08F);
    }

    private void cancelSideKick()
    {
        this.entityData.set(DATA_KICK_ACTIVE, false);
        this.kickVisualTicks = 0;
        this.kickElapsedTicks = 0;
        this.kickDurationAtStart = 0.0F;
        this.pendingKickContactTicks = 0;
        this.ordinaryAfterKickBufferTicks = 0;
    }

    private void beginKnifeMotion(boolean reverse)
    {
        com.projectseele.world.CombatCommandBriefR47.attackCommitted(this,"knife");
        EvaGameplayMotionR32.beginAction(this);
        this.entityData.set(DATA_KNIFE_TYPE, reverse ? 1 : 0);
        this.entityData.set(DATA_LIVE_ACTION_PHASE, 0.0F);
        this.queuedKnifeInput = -1;
        this.knifeReverseMotion = reverse;
        this.knifeVisualTicks = this.knifeVisualTicks(reverse);
        this.knifeElapsedTicks = 0;
        this.knifeDurationAtStart = this.knifeDurationTicks(reverse);
        this.pendingKnifeContactTicks = Math.max(1, Math.round(
                (reverse ? KNIFE_REVERSE_CONTACT_FRAME : KNIFE_FORWARD_CONTACT_FRAME)
                        * 20.0F / KNIFE_SOURCE_FPS
                        / EvaPilotCapability.attackSpeedMultiplier(this.getPilotSynchronization()) / MELEE_RATE_R43));
        if(EvaGameplayMotionR32.knifeReady(this))
            this.pendingKnifeContactTicks=Math.max(1,Math.round(this.knifeDurationAtStart
                    *EvaGameplayMotionR32.contactPhase(this,reverse?"knife_reverse":"knife_forward")));
        this.liveCombatRootPrevious = EvaGameplayMotionR32.knifeReady(this)
                ?EvaGameplayMotionR32.root(this,reverse?"knife_reverse":"knife_forward",0):EvaLiveCombatMotion.knife(reverse,0);
    }

    private void cancelKnifeMotion()
    {
        this.entityData.set(DATA_KNIFE_TYPE, -1);
        this.pendingKnifeContactTicks = 0;
        this.queuedKnifeInput = -1;
        this.knifeVisualTicks = 0;
        this.knifeElapsedTicks = 0;
        this.knifeDurationAtStart = 0.0F;
    }

    private void resolveKnifeContact(LivingEntity pilot)
    {
        boolean reverse = this.knifeReverseMotion;
        if(EvaGameplayMotionR32.knifeReady(this))
        {
            Vec3 point=EvaGameplayMotionR32.contact(this,reverse?"knife_reverse":"knife_forward",1);
            this.strikeSweepR32(pilot,EvaGameplayMotionR32.previousContact(this,point),point,reverse?4:3.2,
                    (reverse?SMASH_KNIFE_DAMAGE:MELEE_KNIFE_DAMAGE)*this.getMeleeMultiplier(),reverse?2:1.1);
            return;
        }
        // Evaluated blade-tip model coordinates at frames 44 / 24. World X/Z
        // use the same 180-degree facing conversion as the rendered Tiger rig.
        Vec3 point = reverse ? new Vec3(42.8D, 167.2D, -68.5D)
                : new Vec3(6.6D, 149.6D, -57.4D);
        double scale = EvaScale.RENDER_SCALE / 16.0D;
        Vec3 forward = this.getForward().multiply(1.0D, 0.0D, 1.0D).normalize();
        Vec3 right = new Vec3(forward.z, 0.0D, -forward.x);
        Vec3 center = this.position().add(right.scale(-point.x * scale))
                .add(forward.scale(-point.z * scale)).add(0.0D, point.y * scale, 0.0D);
        double radius = reverse ? SMASH_RADIUS : MELEE_RADIUS;
        AABB zone = new AABB(center, center).inflate(radius,
                reverse ? EvaScale.fromLegacy(8.5D) : 10.0D, radius);
        this.strikeZone(pilot, zone,
                (reverse ? SMASH_KNIFE_DAMAGE : MELEE_KNIFE_DAMAGE) * this.getMeleeMultiplier(),
                reverse ? 2.0D : 1.1D, center);
        this.playSound(SoundEvents.PLAYER_ATTACK_SWEEP, reverse ? 3.0F : 2.5F,
                reverse ? 0.68F : 0.7F);
        ProjectSeele.LOGGER.debug("EVA knife contact: entity={} reverse={} elapsed={}",
                this.getId(), reverse, this.knifeElapsedTicks);
    }

    private void cancelLiveActionsForStanceChange()
    {
        this.cancelOrdinaryGroupCAttack();
        this.cancelHeavyMotion();
        this.cancelSideKick();
        this.cancelKnifeMotion();
        this.meleeInputBufferTicks = 0;
        this.kickAfterOrdinaryBufferTicks = 0;
    }

    public void interruptCombatR31()
    {cancelLiveActionsForStanceChange();cancelHeavyMotion();chargingHeld=false;}
    public void beginPhysicalControlR35(){interruptCombatR31();clearJumpRequestState();pilotMovementRequested=false;}
    public float combatPhaseR31(){return this.entityData.get(DATA_LIVE_ACTION_PHASE);}

    private void applyKnifeRootMotion()
    {
        if (this.knifeDurationAtStart <= 0.0F)
        {
            return;
        }
        this.knifeElapsedTicks++;
        this.entityData.set(DATA_LIVE_ACTION_PHASE, Mth.clamp(
                this.knifeElapsedTicks / this.knifeDurationAtStart, 0.0F, 1.0F));
        float phase=Mth.clamp(this.knifeElapsedTicks/this.knifeDurationAtStart,0,1);
        Vec3 authored=EvaGameplayMotionR32.knifeReady(this)
                ?EvaGameplayMotionR32.root(this,this.knifeReverseMotion?"knife_reverse":"knife_forward",phase)
                :EvaLiveCombatMotion.knife(this.knifeReverseMotion,phase);
        this.applyAuthoredRootDelta(authored);
    }

    private void applyLiveCombatRootMotion(boolean ordinary)
    {
        float duration = ordinary ? this.ordinaryAttackDurationAtStart
                : this.kickDurationAtStart;
        if (duration <= 0.0F)
        {
            return;
        }
        int elapsed;
        Vec3 authored;
        if (ordinary)
        {
            this.ordinaryAttackElapsedTicks++;
            elapsed = this.ordinaryAttackElapsedTicks;
            float swingPhase=EvaGameplayMotionR32.ready(this)?EvaGameplayMotionR32.swingSoundPhaseR45(this,EvaGameplayMotionR32.ordinary(this.ordinaryAttackRootStage)):.26F;
            if(EvaGameplayMotionR32.directed(this)&&elapsed>=duration*swingPhase&&elapsed-1<duration*swingPhase)EvaMovementSounds.swing(this,2.1F);
            authored = EvaGameplayMotionR32.ready(this)?EvaGameplayMotionR32.root(this,EvaGameplayMotionR32.ordinary(this.ordinaryAttackRootStage),Mth.clamp(elapsed/duration,0,1))
                    :EvaLiveCombatMotion.ordinary(this.ordinaryAttackRootStage,Mth.clamp(elapsed/duration,0,1));
        }
        else
        {
            this.kickElapsedTicks++;
            elapsed = this.kickElapsedTicks;
            authored = EvaGameplayMotionR32.kickReady(this)?EvaGameplayMotionR32.root(this,"kick",Mth.clamp(elapsed/duration,0,1))
                    :EvaLiveCombatMotion.kick(Mth.clamp(elapsed/duration,0,1));
        }
        this.entityData.set(DATA_LIVE_ACTION_PHASE, Mth.clamp(elapsed / duration, 0.0F, 1.0F));
        this.applyAuthoredRootDelta(authored);
    }

    private void applyAuthoredRootDelta(Vec3 authored)
    {
        Vec3 local = authored.subtract(this.liveCombatRootPrevious);
        this.liveCombatRootPrevious = authored;
        this.moveAuthoredRootDelta(local);
    }

    private void moveAuthoredRootDelta(Vec3 local)
    {
        if(this.pilotMovementRequested&&EvaGameplayMotionR32.movementMayComposeR45(this))return;
        double blocksPerMetre = 112.0D * EvaScale.RENDER_SCALE / 16.0D;
        Vec3 forward = this.getForward().multiply(1.0D, 0.0D, 1.0D);
        if (forward.lengthSqr() < 1.0e-8D)
        {
            return;
        }
        forward = forward.normalize();
        Vec3 right = new Vec3(forward.z, 0.0D, -forward.x);
        Vec3 movement = right.scale(local.x * blocksPerMetre)
                .add(forward.scale(-local.z * blocksPerMetre));
        if (Double.isFinite(movement.x) && Double.isFinite(movement.z))
        {
            if(this instanceof EvaPrototypeEntity&&movement.horizontalDistanceSqr()>36)return;
            int steps=Math.max(1,(int)Math.ceil(movement.horizontalDistance()/6));
            if(steps>64)return;
            boolean supported=this.onGround();
            Vec3 step=movement.scale(1D/steps);
            // Large captured steps must pass normal collision in bounded pieces.
            // Discarding an entire >6-block frame left the attack's legs playing
            // while its chassis remained behind, especially with a long sword.
            for(int i=0;i<steps;i++)this.move(MoverType.SELF,CombatSpacingR32.clipAuthoredAdvance(this,step));
            // A horizontal animation displacement is not a takeoff. Retain
            // floor contact only when the moved hull still has real support.
            if(supported)
            {
                AABB b=this.getBoundingBox();
                AABB sole=new AABB(b.minX+.1,b.minY-.10,b.minZ+.1,b.maxX-.1,b.minY+.01,b.maxZ-.1);
                if(this.level().getBlockCollisions(this,sole).iterator().hasNext())this.setOnGround(true);
            }
        }
    }
    void moveCombatRootR34(Vec3 delta){moveAuthoredRootDelta(delta);}
    float swordActionProgressR45(float partial){return this.liveActionProgress(partial);}
    void swordActionPhaseR45(float phase){this.entityData.set(DATA_LIVE_ACTION_PHASE,Mth.clamp(phase,0,1));}
    int swordSourceTicksR45(double seconds){return this.fastMeleeCooldownR43(Math.max(1,Mth.ceil(seconds*20)));}
    int swordInputBufferTicksR45(){return MELEE_INPUT_BUFFER_TICKS;}
    boolean swordHeavyAvailableR45(){return this.smashCooldown==0;}
    void swordBeginHeavyCooldownR45(){this.smashCooldown=this.fastMeleeCooldownR43(SMASH_COOLDOWN_TICKS);}
    float swordDamageR45(boolean heavy){return (heavy?SMASH_KNIFE_DAMAGE:MELEE_KNIFE_DAMAGE)*this.getMeleeMultiplier();}
    void swordContactSoundR45(Vec3 point){EvaMovementSounds.play(this,point,ModSounds.EVA_KNIFE_CUT.get(),3.8F,1);}
    float fieldActionProgressR45(float partial){return this.liveActionProgress(partial);}
    void fieldActionPhaseR45(float phase){this.entityData.set(DATA_LIVE_ACTION_PHASE,Mth.clamp(phase,0,1));}
    void finishCapturedActionEndpointR45()
    {
        if(this.level().isClientSide||!(this.getPilotEntity() instanceof ServerPlayer pilot))return;
        this.setDeltaMovement(Vec3.ZERO);
        // The ordinary vehicle teleport is ignored once the local pilot regains
        // movement authority. Publish the final source endpoint before clearing
        // the action owner, using the same explicit handoff as a shaft arrival.
        SeeleNetwork.CHANNEL.send(PacketDistributor.PLAYER.with(()->pilot),
                new ClientboundEvaArrivalSyncPacket(this.getId(),this.getX(),this.getY(),this.getZ(),this.getYRot(),this.getXRot()));
    }
    void moveFieldRootR45(Vec3 local)
    {
        double scale=112.0D*EvaScale.RENDER_SCALE/16.0D;
        Vec3 forward=this.getForward().multiply(1,0,1);if(forward.lengthSqr()<1e-8)return;
        forward=forward.normalize();Vec3 right=new Vec3(forward.z,0,-forward.x);
        Vec3 delta=right.scale(local.x*scale).add(forward.scale(-local.z*scale));
        if(!Double.isFinite(delta.x)||!Double.isFinite(delta.z))return;
        boolean supported=this.onGround();
        // Deliberate evasion uses the normal move/spacing path, which retains tangential motion.
        int steps=Math.max(1,(int)Math.ceil(delta.horizontalDistance()/6));
        if(steps>64)return;
        Vec3 step=delta.scale(1D/steps);
        for(int i=0;i<steps;i++)this.move(MoverType.SELF,step);
        if(supported)
        {
            var b=this.getBoundingBox();var sole=new AABB(b.minX+.1,b.minY-.10,b.minZ+.1,b.maxX-.1,b.minY+.01,b.maxZ-.1);
            if(this.level().getBlockCollisions(this,sole).iterator().hasNext())this.setOnGround(true);
        }
    }

    @Override public void move(MoverType type,Vec3 motion)
    {
        if(this.tickCount>0&&this.getPilotEntity()!=null&&!this.isNervLogisticsLocked()&&!this.isFirstBattleActive()
                &&!EvaShutdownR30.disabled(this)&&!CombatFeelR31.restrained(this)&&!EvaCombatR31.locksFacing(this))motion=CombatSpacingR32.clip(this,motion);
        super.move(type,motion);
    }

    private Vec3 actionRootSample(int family, float phase)
    {
        if(EvaGameplayMotionR32.ready(this)&&(family>=0&&family<4||family==7))return EvaGameplayMotionR32.root(this,family==7?"heavy":EvaGameplayMotionR32.ordinary(family),phase);
        if(family==4&&EvaGameplayMotionR32.kickReady(this))return EvaGameplayMotionR32.root(this,"kick",phase);
        if((family==5||family==6)&&EvaGameplayMotionR32.knifeReady(this))return EvaGameplayMotionR32.root(this,family==6?"knife_reverse":"knife_forward",phase);
        return family == 7 ? EvaLiveCombatMotion.heavy(phase) : family < 4 ? EvaLiveCombatMotion.ordinary(family, phase)
                : family == 4 ? EvaLiveCombatMotion.kick(phase)
                : EvaLiveCombatMotion.knife(family == 6, phase);
    }

    private void predictAuthoritativeActionRoot()
    {
        int stage = this.getOrdinaryAttackStage();
        int knife = this.getKnifeMotionType(0.0F);
        int family = this.isHeavyMotionActive() ? 7 : stage >= 0 ? stage : this.isKickMotionActive(0.0F) ? 4
                : knife >= 0 ? 5 + knife : -1;
        int sequence = family == 4 ? this.entityData.get(DATA_KICK_SEQUENCE)
                : family == 6 || family == 7 ? this.entityData.get(DATA_SMASH_SEQUENCE)
                : this.entityData.get(DATA_MELEE_SEQUENCE);
        float phase = this.entityData.get(DATA_LIVE_ACTION_PHASE);
        if (family < 0)
        {
            if (this.clientRootFamily >= 0)
            {
                // Consume the final synchronized sample, including a partial
                // sample when the server cancelled the attack before contact.
                Vec3 finalRoot = actionRootSample(this.clientRootFamily, phase);
                this.moveAuthoredRootDelta(finalRoot.subtract(this.clientRootPrevious));
                this.clientRootFamily = -1;
            }
            return;
        }
        if (family != this.clientRootFamily || sequence != this.clientRootSequence)
        {
            this.clientRootPrevious = actionRootSample(family, 0.0F);
            this.clientRootFamily = family;
            this.clientRootSequence = sequence;
        }
        Vec3 root = actionRootSample(family, phase);
        this.moveAuthoredRootDelta(root.subtract(this.clientRootPrevious));
        this.clientRootPrevious = root;
    }

    void replayCombatIntentR32(LivingEntity pilot,int action)
    {if(action==0)meleeAttack(pilot);else if(action==1)smashAttack(pilot);}

    private boolean needsClosingStepR32(ServerPlayer player)
    {
        if(player.zza<=.15F||this.isPilotProne()||this.isPilotCrouching())return false;
        var forward=this.getForward().multiply(1,0,1).normalize();
        var targets=this.level().getEntitiesOfClass(LivingEntity.class,this.getBoundingBox().inflate(64,32,64),
                e->e instanceof Angel&&e.isAlive()&&Math.abs(e.getY()-this.getY())<32
                    &&e.position().subtract(this.position()).multiply(1,0,1).normalize().dot(forward)>.65);
        var target=targets.stream().min(java.util.Comparator.comparingDouble(this::distanceToSqr)).orElse(null);
        if(target==null||target.position().subtract(this.position()).horizontalDistance()<=27)return false;
        return this.level().clip(new net.minecraft.world.level.ClipContext(this.position().add(0,35,0),
                target.position().add(0,target.getBbHeight()*.55,0),net.minecraft.world.level.ClipContext.Block.COLLIDER,
                net.minecraft.world.level.ClipContext.Fluid.NONE,this)).getType()==net.minecraft.world.phys.HitResult.Type.MISS;
    }

    private int contactReviewRowsR45;
    private void reviewContactGateR45(String gate,@Nullable Entity target,@Nullable Vec3 from,Vec3 to,
            @Nullable Vec3 contact,double radius,float requested,int invulnerableBefore,float healthBefore,boolean accepted)
    {
        if(!Boolean.getBoolean("projectseele.r45ContactTrace")||!com.projectseele.visual.CombatR31Review.ownsFixture(this)
                ||contactReviewRowsR45++>=4096)return;
        var row=new com.google.gson.JsonObject();row.addProperty("gate",gate);row.addProperty("server_tick",this.level().getGameTime());
        row.addProperty("review_stage",com.projectseele.visual.CombatR31Review.stageName);row.addProperty("review_tick",com.projectseele.visual.CombatR31Review.stageTicks);
        row.addProperty("ordinary_stage",this.getOrdinaryAttackStage());row.addProperty("action_sequence",this.entityData.get(DATA_MELEE_SEQUENCE));
        row.addProperty("heavy_sequence",this.entityData.get(DATA_SMASH_SEQUENCE));row.addProperty("heavy",this.isHeavyMotionActive());
        row.addProperty("ordinary_action_started_at_r45",this.ordinaryAcceptedTargetsR45.startedAt());row.addProperty("ordinary_accepted_targets_r45",this.ordinaryAcceptedTargetsR45.acceptedCount());
        row.addProperty("live_phase",this.liveActionProgress(1));row.addProperty("pilot_control_locked",this.isPilotControlLocked());
        row.addProperty("eva_uuid",this.getStringUUID());row.addProperty("target_uuid",target==null?"none":target.getStringUUID());
        row.addProperty("requested_damage",requested);row.addProperty("radius",radius);row.addProperty("accepted",accepted);
        row.addProperty("invulnerable_before",invulnerableBefore);row.addProperty("health_before",healthBefore);
        if(target instanceof LivingEntity living){row.addProperty("health_after",living.getHealth());row.addProperty("invulnerable_after",living.invulnerableTime);row.addProperty("target_bounds",living.getBoundingBox().toString());}
        if(target instanceof com.projectseele.entity.Angel angel)row.addProperty("field_after",angel.getAtField());
        row.addProperty("from",from==null?"zone":from.toString());row.addProperty("to",to.toString());row.addProperty("actual_contact",contact==null?"none":contact.toString());
        ProjectSeele.LOGGER.info("R45 ACTUAL CONTACT {}",row);
    }
    private void strikeZone(LivingEntity pilot, AABB zone, float damage, double knockback, Vec3 fxCenter)
    {strikeZoneR32(pilot,zone,damage,knockback,fxCenter,null,0);}

    private boolean strikeSweepR32(LivingEntity pilot,Vec3 from,Vec3 to,double radius,float damage,double knockback)
    {return strikeZoneR32(pilot,new AABB(from,to).inflate(radius),damage,knockback,to,from,radius,false);}
    private boolean gameplayContactR32(LivingEntity pilot,String clip,boolean heavy)
    {
        Vec3 point=EvaGameplayMotionR32.contact(this,clip,1),previous=EvaGameplayMotionR32.previousContact(this,point);
        double radius=heavy?4:3.2;return strikeZoneR32(pilot,new AABB(previous,point).inflate(radius),(heavy?SMASH_FIST_DAMAGE:MELEE_FIST_DAMAGE)*this.getMeleeMultiplier(),heavy?2:1.1,point,previous,radius,true);
    }

    private boolean strikeZoneR32(LivingEntity pilot,AABB zone,float damage,double knockback,Vec3 fxCenter,@Nullable Vec3 from,double radius)
    {return strikeZoneR32(pilot,zone,damage,knockback,fxCenter,from,radius,false);}
    private boolean strikeZoneR32(LivingEntity pilot,AABB zone,float damage,double knockback,Vec3 fxCenter,@Nullable Vec3 from,double radius,boolean quietMiss)
    {
        if (!(this.level() instanceof ServerLevel serverLevel))
        {
            return false;
        }
        boolean knife = this.getWeapon() == WEAPON_KNIFE;
        boolean lance = this.getWeapon() == WEAPON_LANCE;
        boolean anyHit = false;
        // Entity sections are indexed near their feet. A fist at Y+55 must
        // include the section holding a giant's feet, then test its real bounds.
        var actualCandidates=com.projectseele.physics.CombatDamageTargetsR44.candidates(serverLevel,zone,this,pilot);
        if(actualCandidates.isEmpty())reviewContactGateR45("no_candidate",null,from,fxCenter,null,radius,damage,-1,-1,false);
        for (Entity target : actualCandidates)
        {
            if(pilot instanceof TrainingPilotEntity&&(target instanceof EvaUnit01Entity||target instanceof TrainingPilotEntity||target instanceof NervStaffEntity))continue;
            if(from==null&&!com.projectseele.physics.CombatDamageTargetsR44.overlap(target,zone))continue;
            var bodyContact=from==null?java.util.Optional.of(fxCenter):com.projectseele.physics.CombatDamageTargetsR44.clip(target,from,fxCenter,radius);
            if(bodyContact.isEmpty())
            {reviewContactGateR45("body_clip_miss",target,from,fxCenter,null,radius,damage,target.invulnerableTime,target instanceof LivingEntity living?living.getHealth():-1,false);continue;}
            Vec3 wallOrigin=from==null?this.position().add(0,Math.max(2,fxCenter.y-this.getY()),0):from;
            if(this.level().clip(new net.minecraft.world.level.ClipContext(wallOrigin,fxCenter,net.minecraft.world.level.ClipContext.Block.COLLIDER,net.minecraft.world.level.ClipContext.Fluid.NONE,this)).getType()!=net.minecraft.world.phys.HitResult.Type.MISS)
            {reviewContactGateR45("wall_to_endpoint",target,from,fxCenter,bodyContact.get(),radius,damage,target.invulnerableTime,target instanceof LivingEntity living?living.getHealth():-1,false);continue;}
            if(from!=null&&this.level().clip(new net.minecraft.world.level.ClipContext(this.position().add(0,Math.max(2,from.y-this.getY()),0),from,net.minecraft.world.level.ClipContext.Block.COLLIDER,net.minecraft.world.level.ClipContext.Fluid.NONE,this)).getType()!=net.minecraft.world.phys.HitResult.Type.MISS)
            {reviewContactGateR45("wall_to_start",target,from,fxCenter,bodyContact.get(),radius,damage,target.invulnerableTime,target instanceof LivingEntity living?living.getHealth():-1,false);continue;}
            // Damage sourced directly from the Unit: Angel A.T. Fields
            // treat EVA contact as neutralized and let it through.
            boolean field=target instanceof Angel angel&&angel.getAtField()>0;
            Vec3 hitPoint=bodyContact.orElse(fxCenter);
            Vec3 away=target.position().subtract(this.position()).multiply(1,0,1).normalize();
            Vec3 impulse=from==null?away:away.scale(.65).add(fxCenter.subtract(from).multiply(1,.12,1).normalize().scale(.35)).normalize();
            // Independent ordinary punches can contact less than ten ticks apart.
            // Use a dedicated cooldown tag only after this actual body/LOS admission.
            boolean ordinary=!this.isExperimentalUnit()&&target instanceof LivingEntity&&this.getWeapon()==WEAPON_FISTS&&this.getOrdinaryAttackStage()>=0
                    &&!this.isHeavyMotionActive()&&!this.isKickMotionActive(0)&&this.getKnifeMotionType(0)<0
                    &&!EvaCombatR31.active(this)&&pilot!=null&&this.getPilotEntity()==pilot&&!this.isPilotControlLocked();
            float targetFieldBefore=ordinary&&target instanceof EvaUnit01Entity defender?defender.getAtFieldEnergy():Float.NaN;
            int actualSequence=this.entityData.get(DATA_MELEE_SEQUENCE);
            var admission=ordinary?this.ordinaryAcceptedTargetsR45.admit(actualSequence,target.getUUID()):com.projectseele.combat.EvaContactHitsR45.Admission.FIRST;
            if(!admission.allowsDamage())
            {reviewContactGateR45(admission.countsAsAcceptedContact()?"same_action_target_already_accepted":"ordinary_attempt_pending_closed_or_stale",target,from,fxCenter,hitPoint,radius,damage,target.invulnerableTime,target instanceof LivingEntity living?living.getHealth():-1,false);anyHit|=admission.countsAsAcceptedContact();continue;}
            int reviewInvulnerable=target.invulnerableTime;float reviewHealth=target instanceof LivingEntity living?living.getHealth():-1;
            long actualStartedAt=this.ordinaryAcceptedTargetsR45.startedAt();boolean accepted=false,fieldAbsorbed=false;
            try
            {
                DamageSource contactSource=ordinary?com.projectseele.registry.ModDamageTypesR45.ordinaryContact(this):this.damageSources().mobAttack(this);
                accepted=com.projectseele.physics.CombatDamageTargetsR44.hurt(target,contactSource,damage,hitPoint,impulse,com.projectseele.physics.CombatDamageTargetsR44.Weapon.CONTACT);
            }
            finally
            {
                try
                {
                    if(ordinary&&target instanceof EvaUnit01Entity defender)
                        fieldAbsorbed=com.projectseele.combat.EvaContactHitsR45.settledContactR46(false,targetFieldBefore,defender.getAtFieldEnergy());
                }
                finally{if(ordinary)this.ordinaryAcceptedTargetsR45.finishAttempt(actualSequence,actualStartedAt,target.getUUID(),accepted||fieldAbsorbed);}
            }
            reviewContactGateR45(fieldAbsorbed?"actual_hurt_at_consumed":"actual_hurt",target,from,fxCenter,hitPoint,radius,damage,reviewInvulnerable,reviewHealth,accepted);
            if(!accepted&&!field&&!fieldAbsorbed)continue;
            if(!anyHit)
            {
                if(knife)EvaMovementSounds.play(this,hitPoint,ModSounds.EVA_KNIFE_CUT.get(),3.8F,1);
                else if(target instanceof LivingEntity living)CombatFoleyR36.impact(this,living,hitPoint,field||fieldAbsorbed,this.isHeavyMotionActive());
                else EvaMovementSounds.play(this,hitPoint,ModSounds.EVA_LAND.get(),1.5F,1.08F);
            }
            if(!accepted){anyHit=true;continue;}
            if(target instanceof LivingEntity living)living.knockback(knockback, this.getX() - target.getX(), this.getZ() - target.getZ());
            anyHit = true;
            // Impact burst on the body actually struck.
            if(field)com.projectseele.fx.AtFieldFX.ripple(serverLevel,fxCenter,this.getForward());
        }
        if(!anyHit&&quietMiss)return false;
        // The swing arc itself: a fan of sweep across the strike front.
        Vec3 side = this.getForward().yRot((float) Math.toRadians(90.0D));
        for (int i = -1; i <= 1; i++)
        {
            Vec3 p = fxCenter.add(side.scale(i * 1.6D));
            if(!anyHit)serverLevel.sendParticles(ParticleTypes.CLOUD,p.x,p.y,p.z,1,0,0,0,.02);
        }
        if (knife)
        {
            // High-vibration blade wake.
            serverLevel.sendParticles(ParticleTypes.ELECTRIC_SPARK,
                    fxCenter.x, fxCenter.y, fxCenter.z, 30, 2.0D, 1.4D, 2.0D, 0.35D);
        }
        if (lance)
        {
            serverLevel.sendParticles(ParticleTypes.END_ROD,
                    fxCenter.x, fxCenter.y, fxCenter.z, 44, 2.4D, 2.0D, 2.4D, 0.45D);
            serverLevel.sendParticles(ParticleTypes.ELECTRIC_SPARK,
                    fxCenter.x, fxCenter.y, fxCenter.z, 52, 2.8D, 2.2D, 2.8D, 0.55D);
        }
        if (!anyHit)
        {
            EvaMovementSounds.play(this,fxCenter,ModSounds.EVA_SWING.get(),1.1F,1);
            // Whiff: a little air displacement so empty swings still feel weighty.
            serverLevel.sendParticles(ParticleTypes.CLOUD, fxCenter.x, fxCenter.y, fxCenter.z,
                    6, 1.2D, 0.8D, 1.2D, 0.02D);
        }
        return anyHit;
    }

    private float getMeleeMultiplier()
    {
        return switch (this.getUnitVariant())
        {
            case UNIT_00 -> 0.85F;
            case UNIT_02 -> 1.20F;
            default -> 1.0F;
        };
    }

    private int fastMeleeCooldownR43(int baseTicks)
    {return Math.max(1,Mth.ceil(this.synchronizedCooldown(baseTicks)/MELEE_RATE_R43));}

    private int synchronizedCooldown(int baseTicks)
    {
        float speed = EvaPilotCapability.attackSpeedMultiplier(
                this.getPilotSynchronization());
        return Math.max(1, Mth.ceil(baseTicks / speed));
    }

    /** Use-key released: fire if fully charged, otherwise just power down. */
    public void releaseCannon(ServerPlayer pilot)
    {releaseCannon((LivingEntity)pilot);}

    public void releaseCannon(LivingEntity pilot)
    {
        if(pilot==null||this.getPilotEntity()!=pilot||this.level().isClientSide)return;
        this.chargingHeld = false;
        if (this.getWeapon() == WEAPON_N2)
        {
            this.entityData.set(DATA_N2_ARM_TICKS, 0);
            return;
        }
        boolean full = this.getCannonCharge() >= SeeleConfig.CANNON_CHARGE_TICKS.get();
        this.entityData.set(DATA_CANNON_CHARGE, 0);
        if(this.getPersistentData().getBoolean("TvMissionCannonAppliedR45")
                &&!com.projectseele.world.TvMissionEquipmentR45.operational(this))return;
        if (this.isPilotControlLocked() || !full || this.getWeapon() != WEAPON_CANNON
                || this.getCannonCooldown() > 0)
        {
            return;
        }
        this.entityData.set(DATA_CANNON_COOLDOWN, SeeleConfig.CANNON_COOLDOWN_TICKS.get());
        if (this.level() instanceof ServerLevel serverLevel)
        {
            this.fireCannon(serverLevel, pilot);
        }
    }

    public void setPilotCrouching(ServerPlayer pilot, boolean crouching)
    {
        if (this.getControllingPassenger() != pilot || this.isPilotControlLocked()
                || this.isPilotCrouching() == crouching)
        {
            return;
        }
        if ((!crouching||this.isPilotProne()) && !this.hasPoseRoom(crouching?CROUCH_HEIGHT:NORMAL_HEIGHT))
        {
            pilot.displayClientMessage(Component.translatable("msg.projectseele.cannot_stand"), true);
            return;
        }
        if (crouching)
        {
            this.entityData.set(DATA_PRONE, false);
        }
        if(this.getWeapon()==WEAPON_FISTS&&(this.getOrdinaryAttackStage()>=0||this.isHeavyMotionActive()))EvaGameplayMotionR32.releaseToMovement(this);
        this.cancelLiveActionsForStanceChange();
        this.entityData.set(DATA_CROUCHING, crouching);
        this.entityData.set(DATA_SPRINTING, false);
        this.updatePoseDimensions();
        ProjectSeele.LOGGER.info(
                "EVA pilot stance changed: eva={} crouching={} prone={}",
                this.getStringUUID(), this.isPilotCrouching(),
                this.isPilotProne());
    }

    public void toggleProne(ServerPlayer pilot)
    {
        if (this.getControllingPassenger() != pilot || this.isPilotControlLocked())
        {
            return;
        }
        boolean prone = !this.isPilotProne();
        if (!prone && !this.hasStandingRoom())
        {
            pilot.displayClientMessage(Component.translatable("msg.projectseele.cannot_stand"), true);
            return;
        }
        if(this.getWeapon()==WEAPON_FISTS&&(this.getOrdinaryAttackStage()>=0||this.isHeavyMotionActive()))EvaGameplayMotionR32.releaseToMovement(this);
        this.cancelLiveActionsForStanceChange();
        this.entityData.set(DATA_PRONE, prone);
        this.entityData.set(DATA_CROUCHING, false);
        this.entityData.set(DATA_SPRINTING, false);
        this.updatePoseDimensions();
        ProjectSeele.LOGGER.info(
                "EVA pilot stance changed: eva={} crouching={} prone={}",
                this.getStringUUID(), this.isPilotCrouching(),
                this.isPilotProne());
    }

    public void setPilotSprinting(ServerPlayer pilot, boolean sprinting)
    {
        if (this.getControllingPassenger() == pilot && !this.isPilotControlLocked())
        {
            this.entityData.set(DATA_SPRINTING, sprinting && !this.isPilotCrouching() && !this.isPilotProne()
                    && this.getCannonCharge() <= 0);
        }
    }

    public void pilotJump(ServerPlayer pilot)
    {
        if(CombatFeelR31.restrained(this)||EvaCombatR31.active(this))return;
        if (this.getControllingPassenger() != pilot || this.isPilotProne()
                ||this.rifleStanceLevel(0)>1.05F||EvaCapturedLocomotionR44.ownsMultiContactPoseR45(this))
        {
            this.jumpBufferTicks = 0;
            return;
        }

        this.jumpBufferTicks = JUMP_BUFFER_TICKS;
        this.tryConsumeBufferedJump(pilot);
    }

    public void pilotJump(ServerPlayer pilot, int requestId)
    {
        if(CombatFeelR31.restrained(this)||EvaCombatR31.active(this))return;
        if (requestId == this.lastJumpRequestId)
        {
            // A request that arrived during a transient false ground reading
            // used to expire after 20 ticks. Client retries kept the same ID,
            // so the server rejected them forever until Space was released.
            if (this.jumpBufferTicks <= 0 && !this.explicitJumpInProgress
                    && this.jumpCooldown <= 0)
            {
                this.jumpBufferTicks = JUMP_BUFFER_TICKS;
                this.tryConsumeBufferedJump(pilot);
            }
            return;
        }
        this.lastJumpRequestId = requestId;
        this.pilotJump(pilot);
    }

    private boolean tryConsumeBufferedJump(ServerPlayer pilot)
    {
        // Prone is a deliberate supported posture. Space must not silently
        // stand the airframe up or retain a jump for the next stance change.
        if (this.isPilotProne()||this.rifleStanceLevel(0)>1.05F
                ||EvaCapturedLocomotionR44.ownsMultiContactPoseR45(this))
        {
            this.jumpBufferTicks = 0;
            return false;
        }
        if (this.jumpBufferTicks <= 0 || this.getControllingPassenger() != pilot
                || this.isPilotControlLocked() || this.jumpCooldown > 0
                || this.getCannonCharge() > 0
                || !this.hasJumpSupport())
        {
            return false;
        }
        if ((this.isPilotCrouching() || this.isPilotProne())
                && !this.hasStandingRoom())
        {
            this.jumpBufferTicks = 0;
            pilot.displayClientMessage(Component.translatable(
                    "msg.projectseele.cannot_stand"), true);
            return false;
        }
        if (this.isPilotCrouching())
        {
            this.setPilotCrouching(pilot, false);
            if (this.isPilotCrouching())
            {
                return false;
            }
        }
        this.cancelLiveActionsForStanceChange();
        this.cancelHeavyMotion();
        if(!EvaGameplayMotionR32.prepareJump(this))return false;
        if(EvaGameplayMotionR32.serverMovement(this))
        {
            Vec3 motion=this.getDeltaMovement();this.setDeltaMovement(motion.x,JUMP_VELOCITY,motion.z);
            this.setOnGround(false);this.hasImpulse=true;
        }
        if (!EvaGameplayMotionR32.sharedJump(this)) this.triggerAnim("strike", "takeoff");
        // A ridden living entity is movement-authoritative on the pilot's
        // client. Setting velocity only on the logical server is overwritten
        // by the next ServerboundMoveVehiclePacket, which previously reduced
        // every configured EVA jump to a one-block hop. The monotonically
        // increasing sequence authorizes the same impulse on that client.
        this.entityData.set(DATA_JUMP_SEQUENCE,
                this.entityData.get(DATA_JUMP_SEQUENCE) + 1);
        this.explicitJumpInProgress = true;
        this.explicitJumpObservedAirborne = false;
        this.explicitJumpAuthorizationTicks = JUMP_BUFFER_TICKS;
        // Do not also send a vanilla velocity impulse. It can arrive one tick
        // before the sequence and add a second, clamped takeoff displacement.
        if (this.getVisualPose() == VISUAL_LIVE_JUMP)
        {
            ProjectSeele.LOGGER.info("Visual live jump accepted velocityY={}", JUMP_VELOCITY);
        }
        this.jumpCooldown = JUMP_COOLDOWN_TICKS;
        this.jumpBufferTicks = 0;
        this.groundedGraceTicks = 0;
        EvaMovementSounds.swing(this,1.0F);
        return true;
    }

    private boolean hasJumpSupport()
    {
        if (this.onGround() || this.groundedGraceTicks > 0)
        {
            return true;
        }
        if (Math.abs(this.getDeltaMovement().y) > 0.20D)
        {
            return false;
        }
        AABB body=this.getBoundingBox();
        AABB feet=new AABB(body.minX+.05D,body.minY-JUMP_SUPPORT_PROBE,body.minZ+.05D,
                body.maxX-.05D,body.minY+.01D,body.maxZ-.05D);
        return !this.level().noCollision(this,feet);
    }

    public void exitEva(ServerPlayer pilot)
    {
        if (this.getControllingPassenger() == pilot)
        {
            boolean inAssignedHangar = this.level() instanceof ServerLevel server
                    && this.isInsideActiveAssignedHangar(server);
            if (this.isLaunchSequenceActive() || this.isCrucified()
                    || (this.isNervLogisticsLocked() && !inAssignedHangar))
            {
                pilot.displayClientMessage(Component.translatable("message.projectseele.launch_interlock"), true);
                return;
            }
            // Eject the pilot inside the entry plug at the dorsal socket rather
            // than dropping them at the airframe's feet. They then sneak to
            // dismount and climb down from the plug.
            if (this.level() instanceof ServerLevel serverLevel
                    && this.isEntryPlugInserted()
                    && EntryPlugDirector.ejectPilotToPlug(
                            serverLevel, this.getUnitVariant(), this, pilot))
            {
                return;
            }
            pilot.stopRiding();
        }
    }

    /** Automatic EVA pallet SMG: hitscan damage and a brief tracer, never an explosion. */
    public void fireRifle(ServerPlayer pilot)
    { fireRifle((LivingEntity)pilot); }

    private boolean autonomousPilotR30(TrainingPilotEntity pilot)
    {
        return !this.level().isClientSide&&pilot!=null&&this.getPilotEntity()==pilot
                &&pilot.getAssignedVariant()==this.getUnitVariant()&&this.isPoweredOn()&&!this.isPilotControlLocked();
    }
    public boolean autonomousWeaponR30(TrainingPilotEntity pilot,int weapon)
    {
        if(!autonomousPilotR30(pilot)||weapon<WEAPON_FISTS||weapon>WEAPON_SHIELD_R45
                ||!this.armamentAvailable(weapon))return false;
        if(this.hasLiveActionForRender(0))return false;
        this.selectWeapon(weapon);return true;
    }
    public void autonomousDriveR30(TrainingPilotEntity pilot,Vec3 movement,Vec3 aim,boolean sprint)
    {
        if(!autonomousPilotR30(pilot)){this.xxa=this.zza=0;return;}
        Vec3 look=aim.subtract(this.position().add(0,45,0));
        float yaw=(float)Math.toDegrees(Math.atan2(-look.x,look.z));
        float pitch=(float)-Math.toDegrees(Math.atan2(look.y,Math.max(.01,look.horizontalDistance())));
        this.setYRot(Mth.approachDegrees(this.getYRot(),yaw,4));this.yBodyRot=this.getYRot();this.yHeadRot=this.getYRot();
        pilot.setYRot(yaw);pilot.setXRot(pitch);this.entityData.set(DATA_CANNON_AIM_PITCH,this.clampPilotWeaponPitch(pitch,1));
        this.entityData.set(DATA_CROUCHING,false);this.entityData.set(DATA_PRONE,false);this.entityData.set(DATA_SPRINTING,sprint);
        Vec3 local=new Vec3(movement.x,0,movement.z);if(local.lengthSqr()>1)local=local.normalize();local=local.yRot((float)Math.toRadians(this.getYRot()));
        this.pilotMovementRequested=local.lengthSqr()>.001;
        if(this.hasLiveActionForRender(0)&&!EvaGameplayMotionR32.movementMayComposeR45(this))local=Vec3.ZERO;
        this.autonomousInputR30=local;this.autonomousInputAtR30=this.level().getGameTime();
        this.xxa=(float)local.x;this.zza=(float)local.z;this.setSpeed(this.drivingSpeedR30());
    }
    public void autonomousAttackR30(TrainingPilotEntity pilot,int action)
    {
        if(!autonomousPilotR30(pilot))return;
        switch(action)
        {
            case 0->meleeAttack((LivingEntity)pilot);
            case 1->smashAttack((LivingEntity)pilot);
            case 2->stompAttack((LivingEntity)pilot);
            case 3->{setRifleSightHeldR45(pilot,true);if(this.isExperimentalUnit()||rifleSightBlendR45(1)>.85F)fireRifle((LivingEntity)pilot);}
            default->{}
        }
    }
    public void stopAutonomousR30(){if(!this.level().isClientSide){this.xxa=this.zza=0;this.autonomousInputR30=Vec3.ZERO;this.autonomousInputAtR30=this.level().getGameTime();this.pilotMovementRequested=false;this.entityData.set(DATA_SPRINTING,false);}}
    public void autonomousGuardR30(TrainingPilotEntity pilot){if(autonomousPilotR30(pilot))this.entityData.set(DATA_AT_ON,true);}
    public void settleAutonomousAttackR30(TrainingPilotEntity pilot)
    {
        if(!autonomousPilotR30(pilot))return;
        this.queuedKnifeInput=-1;this.queuedHeavy=false;this.queuedKickAfterHeavy=false;this.queuedMeleeAfterHeavy=false;
        this.meleeInputBufferTicks=0;this.ordinaryAfterKickBufferTicks=0;this.kickAfterOrdinaryBufferTicks=0;
    }

    private void fireRifle(LivingEntity pilot)
    {
        if(CombatFeelR31.restrained(this)||EvaCombatR31.active(this))return;
        if (this.isPilotControlLocked() || this.getWeapon() != WEAPON_RIFLE
                || this.rifleCooldown > 0 || this.getControllingPassenger() != pilot
                || this.rifleReadyBlend(1)<RIFLE_READY_FOR_FIRE_R45
                || !(this.level() instanceof ServerLevel level))
        {
            return;
        }
        this.rifleCooldown = this.synchronizedCooldown(SeeleConfig.EVA_RIFLE_INTERVAL_TICKS.get());
        com.projectseele.world.CombatCommandBriefR47.attackCommitted(this,"rifle");
        if("r29-factory".equals(System.getProperty("projectseele.regionalBuild","")))com.projectseele.visual.FieldR28Review.rifleTicks.add(level.getGameTime());
        Vec3 look = this.pilotAimDirection(pilot);
        EvaRifleKinematics.Frame rifle = EvaRifleKinematics.sample(this,1,look);
        Vec3 muzzle = rifle.muzzle();
        this.entityData.set(DATA_RIFLE_RECOIL,1F);
        double range = SeeleConfig.EVA_RIFLE_RANGE.get();

        // Kinematics already resolves the crosshair and the barrel's ground
        // limit. Ballistics must leave that same barrel along its actual axis.
        Vec3 shotDirection = rifle.forward();
        Vec3 farEnd = muzzle.add(shotDirection.scale(range));
        BlockHitResult blockHit = level.clip(
                new ClipContext(muzzle, farEnd, ClipContext.Block.COLLIDER,
                        ClipContext.Fluid.NONE, this));
        Vec3 end = blockHit.getLocation();
        EntityHitResult entityHit = com.projectseele.physics.CombatDamageTargetsR44.ray(level,muzzle,end,.3,this,pilot);
        if (entityHit != null)
        {
            end = entityHit.getLocation();
            com.projectseele.physics.CombatDamageTargetsR44.hurt(entityHit.getEntity(),pilot instanceof Player human?this.damageSources().playerAttack(human):this.damageSources().mobAttack(pilot),
                    SeeleConfig.EVA_RIFLE_DAMAGE.get().floatValue(),end,shotDirection,com.projectseele.physics.CombatDamageTargetsR44.Weapon.PROJECTILE);
        }

        SeeleNetwork.CHANNEL.send(PacketDistributor.TRACKING_ENTITY_AND_SELF.with(() -> this),
                new ClientboundRifleTracerPacket(this.getId(), muzzle.x,
                        muzzle.y, muzzle.z, end.x, end.y, end.z));
        if (entityHit == null
                && blockHit.getType() != net.minecraft.world.phys.HitResult.Type.MISS)
        {
            BlockState impactState = level.getBlockState(blockHit.getBlockPos());
            if (!impactState.isAir())
            {
                Vec3 normal = Vec3.atLowerCornerOf(
                        blockHit.getDirection().getNormal()).scale(0.18D);
                Vec3 dust = end.add(normal);
                level.sendParticles(new BlockParticleOption(
                                ParticleTypes.BLOCK, impactState),
                        dust.x, dust.y, dust.z, 26,
                        0.72D, 0.72D, 0.72D, 0.24D);
                level.sendParticles(ParticleTypes.POOF,
                        dust.x, dust.y, dust.z, 42,
                        1.6D, 1.6D, 1.6D, 0.18D);
                level.sendParticles(ParticleTypes.LARGE_SMOKE,
                        dust.x, dust.y, dust.z, 30, 1.2D, 1.8D, 1.2D, 0.10D);
                level.sendParticles(ParticleTypes.CAMPFIRE_COSY_SMOKE,
                        dust.x, dust.y, dust.z, 12, 1.6D, .7D, 1.6D, .05D);
            }
        }
        else
        {
            level.sendParticles(ParticleTypes.CRIT, end.x, end.y, end.z,
                    9, 0.35D, 0.35D, 0.35D, 0.18D);
            if(entityHit!=null)level.sendParticles(ParticleTypes.LARGE_SMOKE,
                    end.x,end.y,end.z,24,1.2D,1.6D,1.2D,.12D);
        }
        level.sendParticles(ParticleTypes.SMOKE,
                muzzle.x, muzzle.y, muzzle.z, 3,
                0.12D, 0.12D, 0.12D, 0.025D);
        if(entityHit!=null||blockHit.getType()!=net.minecraft.world.phys.HitResult.Type.MISS)
        {
            // Vanilla's ordinary particle packets stop at 32 metres, shorter
            // than an EVA engagement. Deliver distant impact smoke to the
            // pilot and nearby observers without doubling the close effect.
            for(ServerPlayer observer:level.players())
                if(observer.distanceToSqr(end)>32*32 && (observer==pilot||observer.distanceToSqr(this)<256*256))
                {
                    level.sendParticles(observer,ParticleTypes.LARGE_SMOKE,true,end.x,end.y,end.z,30,1.2D,1.8D,1.2D,.10D);
                    level.sendParticles(observer,ParticleTypes.POOF,true,end.x,end.y,end.z,42,1.6D,1.6D,1.6D,.18D);
                }
        }
        // Superb's gun sounds are data-driven sound definitions, not static
        // registry entries. A direct sound event works like /playsound and
        // resolves its existing client resource without copying the audio.
        var rifleSound=net.minecraftforge.fml.ModList.get().isLoaded("superbwarfare")
                ? net.minecraft.sounds.SoundEvent.createFixedRangeEvent(new net.minecraft.resources.ResourceLocation("superbwarfare","ntw_20_fire_3p"),512F)
                : net.minecraft.sounds.SoundEvent.createFixedRangeEvent(ModSounds.EVA_RIFLE_FIRE.get().getLocation(),512F);
        level.playSound(null, muzzle.x, muzzle.y, muzzle.z, rifleSound,
                SoundSource.PLAYERS, 12F,
                0.93F + this.random.nextFloat() * 0.08F);
    }

    private Vec3 rifleMuzzlePosition(Vec3 aimDirection)
    {
        return EvaRifleKinematics.sample(this,1,aimDirection).muzzle();
    }

    private Vec3 cannonMuzzlePosition(Vec3 aimDirection)
    {
        if(EvaCannonFrameR45.enabled(this))
            return EvaCannonFrameR45.sample(this,1,aimDirection).muzzle();
        Vec3 horizontal = aimDirection.multiply(1.0D, 0.0D, 1.0D).normalize();
        Vec3 right = new Vec3(horizontal.z, 0.0D, -horizontal.x);
        double horizontalLength = Math.sqrt(aimDirection.x * aimDirection.x
                + aimDirection.z * aimDirection.z);
        Vec3 pitchedUp = horizontal.scale(-aimDirection.y)
                .add(0.0D, horizontalLength, 0.0D).normalize();
        boolean prone = this.isPilotProne();
        double pivotHeight = prone ? CANNON_PRONE_PIVOT_HEIGHT
                : CANNON_STANDING_PIVOT_HEIGHT;
        double pivotForward = prone ? CANNON_PRONE_PIVOT_FORWARD
                : CANNON_STANDING_PIVOT_FORWARD;
        double muzzleForward = prone ? CANNON_PRONE_MUZZLE_FORWARD
                : CANNON_STANDING_MUZZLE_FORWARD;
        double muzzleUp = prone ? CANNON_PRONE_MUZZLE_UP
                : CANNON_STANDING_MUZZLE_UP;
        double muzzleRight = prone ? CANNON_PRONE_MUZZLE_RIGHT
                : CANNON_STANDING_MUZZLE_RIGHT;
        Vec3 pivot = this.position().add(0.0D, pivotHeight, 0.0D)
                .add(horizontal.scale(pivotForward));
        return pivot.add(aimDirection.scale(muzzleForward + MUZZLE_SURFACE_CLEARANCE))
                .add(pitchedUp.scale(muzzleUp)).add(right.scale(muzzleRight));
    }

    private void detonateN2(ServerLevel level, ServerPlayer pilot)
    {
        this.chargingHeld = false;
        this.entityData.set(DATA_N2_ARM_TICKS, 0);
        Vec3 groundZero = this.position();
        Vec3 flash = groundZero.add(0.0D, 5.0D, 0.0D);
        StrategicExplosionDirector.startN2(level, groundZero, this);
        SeeleNetwork.CHANNEL.send(PacketDistributor.NEAR.with(() -> new PacketDistributor.TargetPoint(
                        flash.x, flash.y, flash.z, 1024.0D, level.dimension())),
                new ClientboundNukeFxPacket(flash.x, flash.y, flash.z, 10.8F, false));
        level.sendParticles(ParticleTypes.EXPLOSION_EMITTER,
                flash.x, flash.y, flash.z, 24, 12.0D, 7.0D, 12.0D, 0.0D);
        level.playSound(null, flash.x, flash.y, flash.z, SoundEvents.GENERIC_EXPLODE,
                SoundSource.PLAYERS, 12.0F, 0.38F);
        pilot.stopRiding();
        pilot.hurt(level.damageSources().genericKill(), Float.MAX_VALUE);
        this.hurt(level.damageSources().genericKill(), Float.MAX_VALUE);
    }

    public void disconnectForAirliftR32()
    {
        if(level().isClientSide)return;
        this.setUmbilicalAnchor(null);
        // This is a deliberate unplug, not cable damage. Reconnection is allowed after handoff.
        this.powerCheckCooldown=20;
    }

    private void tickPowerSystem()
    {
        if (!(this.level() instanceof ServerLevel server))
        {
            return;
        }
        // Transport owns the captured inert pose. It neither consumes the
        // onboard reserve nor reconnects a cable while the load is restrained.
        if(EvaAirTransportR31.active(this))return;
        if (this.isExperimentalUnit())
        {
            this.setUmbilicalAnchor(null);
            this.entityData.set(DATA_POWER_TICKS, this.getPowerCapacityTicks());
            this.entityData.set(DATA_UMBILICAL_SEVERED, false);
            this.batterySessionArmed = this.isEntryPlugInserted() && this.getPilotEntity() != null;
            return;
        }
        if(EvaAirTransportR31.active(this))
        {
            this.setUmbilicalAnchor(null);
            if(this.isEntryPlugInserted()&&this.getPilotEntity()!=null&&this.getPowerTicks()>0)
                this.entityData.set(DATA_POWER_TICKS,this.getPowerTicks()-1);
            return;
        }
        if (this.isBerserk())
        {
            this.setUmbilicalAnchor(null);
            this.entityData.set(DATA_POWER_TICKS, 0);
            this.entityData.set(DATA_AT_ON, false);
            return;
        }

        boolean controlCircuitClosed = this.isEntryPlugInserted()
                && this.getPilotEntity() != null;
        if (!controlCircuitClosed)
        {
            this.batterySessionArmed = false;
            this.setUmbilicalAnchor(null);
            if (this.isInsideActiveAssignedHangar(server))
            {
                this.entityData.set(DATA_POWER_TICKS, 0);
                this.entityData.set(DATA_UMBILICAL_SEVERED, false);
            }
            return;
        }

        if (!this.batterySessionArmed)
        {
            this.entityData.set(DATA_POWER_TICKS, this.getPowerCapacityTicks());
            this.batterySessionArmed = true;
        }
        if(this.isCarrierPowerConnected())
        {
            // The travelling rack has its own collector and short rear lead.
            // It never masquerades as a fixed block pylon or drags a cable
            // through the full shaft during ascent.
            this.setUmbilicalAnchor(null);
            this.entityData.set(DATA_POWER_TICKS,Math.min(this.getPowerCapacityTicks(),
                    this.getPowerTicks()+Math.max(1,Mth.ceil(this.getPowerCapacityTicks()/100F))));
            this.entityData.set(DATA_UMBILICAL_SEVERED,false);
            this.powerCheckCooldown=0;return;
        }
        boolean surfacePower = this.getY() >= 64 && this.getLaunchPhase() != LAUNCH_ASCENT
                && (!this.isNervLogisticsLocked() || this.getY() >= 80);
        int range = SeeleConfig.COMMON_SPEC.isLoaded()
                ? SeeleConfig.UMBILICAL_RANGE.get() : 768;
        BlockPos anchor = this.getUmbilicalAnchor();
        if (!surfacePower || anchor != null && anchor.getY()<32) anchor=null;
        if (anchor != null && this.position().distanceToSqr(Vec3.atCenterOf(anchor)) <= (double) range * range)
            com.projectseele.world.EvaPowerLinkR25.retain(server, anchor);
        boolean anchorValid = anchor != null
                && server.hasChunkAt(anchor)
                && server.getBlockEntity(anchor) instanceof UmbilicalPylonBlockEntity
                && this.position().distanceToSqr(Vec3.atCenterOf(anchor))
                <= (double) range * range;
        boolean wasConnected = this.isUmbilicalConnected();
        if (!anchorValid)
        {
            anchor = null;
        }
        // The surface reel takes over after ascent. Keeping the wet-cage
        // anchor would draw a lead through the GeoFront roof and consume most
        // of its usable range before the airframe even walks off the launch pad.
        if(anchor!=null && anchor.getY()<32 && this.getY()>=64 && this.tickCount%10==0)
        {
            BlockPos surface=UmbilicalPylonBlockEntity.findNearest(server,this.position(),Math.min(range,128),32);
            if(surface!=null)anchor=surface;
        }
        if (surfacePower && wasConnected && anchor == null
                && !this.isNervLogisticsLocked())
        {
            // A cable that was pulled past its limit or lost its socket does
            // not silently reconnect on the next one-second pylon scan.
            this.entityData.set(DATA_UMBILICAL_SEVERED, true);
        }
        if (surfacePower && anchor == null && !this.isUmbilicalSevered() && --this.powerCheckCooldown <= 0)
        {
            anchor = UmbilicalPylonBlockEntity.findNearest(
                    server, this.position(), range,32);
            this.powerCheckCooldown = 20;
        }

        int oldPower = this.getPowerTicks();
        this.setUmbilicalAnchor(anchor);
        if (anchor != null)
        {
            int capacity = this.getPowerCapacityTicks();
            int chargePerTick = Math.max(1, Mth.ceil(capacity / 100.0F));
            this.entityData.set(DATA_POWER_TICKS,
                    Math.min(capacity, oldPower + chargePerTick));
            if (this.tickCount % 20 == 0 && this.getHealth() < this.getMaxHealth())
            {
                double repair = SeeleConfig.COMMON_SPEC.isLoaded()
                        ? SeeleConfig.UMBILICAL_REPAIR_PER_SECOND.get() : 1.0D;
                if (repair > 0.0D)
                {
                    this.heal((float) repair);
                }
            }
            if (!wasConnected && this.getControllingPassenger() instanceof ServerPlayer pilot)
            {
                pilot.displayClientMessage(Component.translatable(
                        "msg.projectseele.power_connected"), true);
            }
            return;
        }

        if (wasConnected && this.getControllingPassenger() instanceof ServerPlayer pilot)
        {
            pilot.displayClientMessage(Component.translatable(
                    "msg.projectseele.power_disconnected"), true);
        }
        if (oldPower > 0)
        {
            int nextPower = oldPower - 1;
            this.entityData.set(DATA_POWER_TICKS, nextPower);
            if (nextPower == 0)
            {
                this.entityData.set(DATA_AT_ON, false);
                this.entityData.set(DATA_SPRINTING, false);
                this.entityData.set(DATA_CANNON_CHARGE, 0);
                this.entityData.set(DATA_N2_ARM_TICKS, 0);
                this.chargingHeld = false;
                this.setDeltaMovement(Vec3.ZERO);
                if (this.getControllingPassenger() instanceof ServerPlayer pilot)
                {
                    pilot.displayClientMessage(Component.translatable(
                            "msg.projectseele.power_depleted"), true);
                }
                this.playSound(SoundEvents.REDSTONE_TORCH_BURNOUT, 2.5F, 0.55F);
            }
        }
    }

    /**
     * Resolves the wet cage in the active facility coordinate frame. S19
     * worlds must never test a parked airframe against the retired GeoFront
     * origin, while legacy development worlds retain their original cage.
     */
    private boolean isInsideActiveAssignedHangar(ServerLevel level)
    {
        if(this.isExperimentalUnit())return false;
        int variant = this.getUnitVariant();
        if (FacilityV2EvaRuntime.ready(level, variant))
        {
            return FacilityV2EvaRuntime.isInsideAssignedCage(
                    level, this.position(), variant);
        }
        return EvaHangarBuilder.isInsideAssignedCage(
                level, this, variant);
    }

    private void tickPilotSynchronization()
    {
        if (!(this.getControllingPassenger() instanceof ServerPlayer pilot))
        {
            return;
        }
        if (this.getActivationTicks() <= 20 && !this.isLaunchSequenceActive()
                && !this.isPowerDepleted() && !this.isCrucified())
        {
            EvaPilotCapability.tickActiveDriving(pilot);
        }
        float synchronization = EvaPilotCapability.synchronization(pilot);
        if (Math.abs(this.getPilotSynchronization() - synchronization) > 0.001F)
        {
            this.entityData.set(DATA_PILOT_SYNCHRONIZATION, synchronization);
        }
    }

    private void tickBerserkState()
    {
        if(this.isBerserk()&&EvaShutdownR30.wreck(this))
        {
            this.finishBerserk();
            // Wreck recovery is owned by the complete bay repair cycle.
            this.berserkRecoveryTicks=0;
            return;
        }
        if (this.berserkRecoveryTicks > 0 && !this.isBerserk())
        {
            this.berserkRecoveryTicks--;
        }
        if (!this.isBerserk())
        {
            if (this.canEnterBerserk())
            {
                this.beginBerserk();
            }
            return;
        }
        if (!(this.level() instanceof ServerLevel server)
                || this.getUnitVariant() != UNIT_01 || this.isCrucified()
                || this.isLaunchSequenceActive())
        {
            this.finishBerserk();
            return;
        }

        int remaining = this.getBerserkTicks() - 1;
        this.entityData.set(DATA_BERSERK_TICKS, Math.max(0, remaining));
        if(com.projectseele.physics.CombatBodyDynamics.active(this))
        {EvaBerserkMotionR34.clear(this);this.getNavigation().stop();if(remaining<=0)this.finishBerserk();return;}
        EvaBerserkMotionR34.tick(this);
        if (this.berserkAttackCooldown > 0)
        {
            this.berserkAttackCooldown--;
        }
        if (this.berserkPounceVisualCooldown > 0)
        {
            this.berserkPounceVisualCooldown--;
        }
        if (--this.berserkTargetSearchCooldown <= 0
                || !(this.getTarget() instanceof Angel) || !this.getTarget().isAlive())
        {
            this.setTarget(this.findNearestBerserkTarget(server));
            this.berserkTargetSearchCooldown = 20;
        }

        LivingEntity target = this.getTarget();
        if(target==null&&!EvaBerserkMotionR34.active(this)&&!this.isFirstBattleActive())
        {this.finishBerserk();return;}
        if (target != null && target.isAlive()&&!EvaBerserkMotionR34.active(this))
        {
            this.getLookControl().setLookAt(target, 30.0F, 30.0F);
            double distance = this.distanceTo(target);
            boolean aligned=true;
            if(EvaGameplayMotionR32.directed(this))
            {
                this.getNavigation().stop();var to=target.position().subtract(this.position()).multiply(1,0,1);
                float wanted=(float)Math.toDegrees(Math.atan2(-to.x,to.z)),yaw=Mth.approachDegrees(this.getYRot(),wanted,7F);
                this.setYRot(yaw);this.yBodyRot=this.yHeadRot=yaw;float error=Math.abs(Mth.wrapDegrees(wanted-yaw));aligned=error<18;
                if(distance>27&&!CombatFeelR31.restrained(this))
                {
                    boolean ground=this.onGround();double speed=error<35?2.6:.35;this.move(MoverType.SELF,CombatSpacingR32.clip(this,this.getForward().multiply(speed,0,speed)));
                    if(ground&&this.level().getBlockCollisions(this,this.getBoundingBox().deflate(.1).move(0,-.15,0)).iterator().hasNext())this.setOnGround(true);
                }
                this.setDeltaMovement(0,this.getDeltaMovement().y,0);
            }
            else this.getNavigation().moveTo(target, 1.45D);
            if (!EvaGameplayMotionR32.directed(this)&&distance > 14.0D && distance <= 36.0D
                    && this.berserkPounceVisualCooldown <= 0)
            {
                this.triggerAnim("strike", "berserk_pounce");
                this.berserkPounceVisualCooldown = 60;
            }
            if (distance <= (EvaGameplayMotionR32.directed(this)?31.0D:14.0D) && Math.abs(target.getY() - this.getY()) <= 16.0D
                    && this.berserkAttackCooldown <= 0&&aligned&&!CombatFeelR31.restrained(this))
            {
                boolean finishing=target instanceof SachielEntity sachiel&&!sachiel.hasUsedFirstBattle()&&sachiel.getHealth()<=sachiel.getMaxHealth()*.32F;
                if(finishing)
                {
                    if(!BerserkFinaleApproachR38.tick(this,(SachielEntity)target))this.berserkClaw(target,server);
                }
                else this.berserkClaw(target, server);
            }
        }
        else
        {
            this.getNavigation().stop();
        }

        // Eye colour is attached to the real eye surface. The old particles
        // used a guessed upright head position and drifted away during motion.
        if (remaining <= 0)
        {
            this.finishBerserk();
        }
    }

    private boolean canEnterBerserk()
    {
        return canArmBerserkR37()&&getHealth()>0&&getHealth()<=50;
    }
    private boolean canArmBerserkR37()
    {
        return getUnitVariant()==UNIT_01&&!isExperimentalUnit()&&!isBerserk()&&berserkRecoveryTicks==0
                &&!EvaDorsalMechanism.dormantAfterBerserk(this)
                &&!isCrucified()&&!isLaunchSequenceActive()&&!isNervLogisticsLocked()&&!isFirstBattleActive()
                &&!EvaAirTransportR31.active(this)&&!EvaShutdownR30.wreck(this)&&!EvaBayRepairR33.active(this)&&getPilotEntity()!=null;
    }

    public void reviewBerserkR34()
    {
        if(!com.projectseele.visual.CombatR31Review.ownsFixture(this)||getUnitVariant()!=UNIT_01)throw new IllegalStateException("Berserk review requires the isolated original fixture");
        beginBerserk();
    }
    private void beginBerserk()
    {
        int duration = SeeleConfig.COMMON_SPEC.isLoaded()
                ? SeeleConfig.EVA_BERSERK_DURATION_TICKS.get() : 900;
        ServerPlayer pilot = this.getPilotEntity() instanceof ServerPlayer player
                ? player : null;
        this.interruptCombatR31();EvaShutdownR30.clear(this);CombatFeelR31.clear(this);
        this.setHealth(50);this.setUmbilicalAnchor(null);this.entityData.set(DATA_POWER_TICKS,0);
        this.entityData.set(DATA_BERSERK, true);
        this.entityData.set(DATA_BERSERK_TICKS, duration);
        this.entityData.set(DATA_AT_ON, false);
        this.entityData.set(DATA_WEAPON, WEAPON_FISTS);
        this.entityData.set(DATA_CROUCHING, false);
        this.entityData.set(DATA_PRONE, false);
        this.entityData.set(DATA_SPRINTING, false);
        this.entityData.set(DATA_CANNON_CHARGE, 0);
        this.entityData.set(DATA_N2_ARM_TICKS, 0);
        this.chargingHeld = false;
        this.updatePoseDimensions();
        this.setNoGravity(false);
        this.berserkAttackCooldown = 0;
        this.berserkTargetSearchCooldown = 0;
        this.berserkPounceVisualCooldown = 0;
        this.berserkPatternR37=0;
        BerserkFinaleApproachR38.clear(this);
        EvaBerserkMotionR34.clear(this);
        EvaBerserkMotionR34.begin(this,0,null);
        if (pilot != null)
        {
            pilot.displayClientMessage(Component.literal("律子：主电源切断。初号机停止活动。"), false);
        }
        ProjectSeele.LOGGER.warn(
                "EVA Unit-01 berserk: eva={} synchronization={} durationTicks={}",
                this.getStringUUID(), this.getPilotSynchronization(), duration);
    }

    @Nullable
    private LivingEntity findNearestBerserkTarget(ServerLevel server)
    {
        int range = SeeleConfig.COMMON_SPEC.isLoaded()
                ? SeeleConfig.EVA_BERSERK_TARGET_RANGE.get() : 128;
        LivingEntity nearest = null;
        double nearestDistance = Double.MAX_VALUE;
        for (LivingEntity candidate : server.getEntitiesOfClass(LivingEntity.class,
                this.getBoundingBox().inflate(range),
                entity -> entity instanceof Angel && entity.isAlive()))
        {
            double distance = this.distanceToSqr(candidate);
            if (distance < nearestDistance)
            {
                nearest = candidate;
                nearestDistance = distance;
            }
        }
        return nearest;
    }

    private void berserkClaw(LivingEntity target, ServerLevel server)
    {
        if(EvaGameplayMotionR32.directed(this))
        {
            boolean low=com.projectseele.physics.CombatBodyDynamics.active(target)&&target.getBoundingBox().getYsize()<32;
            int kind=low?6:new int[]{2,3,4,3,5,2}[this.berserkPatternR37++%6];
            EvaBerserkMotionR34.begin(this,kind,target);this.berserkAttackCooldown=EvaBerserkMotionR34.duration(this)+2;return;
        }
        this.cancelOrdinaryGroupCAttack();
        this.cancelSideKick();
        this.leftSwing = !this.leftSwing;
        this.entityData.set(DATA_MELEE_LEFT, this.leftSwing);
        this.entityData.set(DATA_MELEE_SEQUENCE,
                (this.entityData.get(DATA_MELEE_SEQUENCE) + 1) & Integer.MAX_VALUE);
        this.triggerAnim("strike", this.leftSwing
                ? "berserk_claw_l" : "berserk_claw_r");
        this.swing(this.leftSwing ? InteractionHand.OFF_HAND : InteractionHand.MAIN_HAND, true);
        float multiplier = SeeleConfig.COMMON_SPEC.isLoaded()
                ? SeeleConfig.EVA_BERSERK_DAMAGE_MULTIPLIER.get().floatValue() : 2.5F;
        float damage = MELEE_FIST_DAMAGE * multiplier;
        if (target.hurt(this.damageSources().mobAttack(this), damage))
        {
            Vec3 away = target.position().subtract(this.position())
                    .multiply(1.0D, 0.0D, 1.0D).normalize();
            target.push(away.x * 1.7D, 0.55D, away.z * 1.7D);
            server.sendParticles(ParticleTypes.SWEEP_ATTACK,
                    target.getX(), target.getY() + target.getBbHeight() * 0.55D,
                    target.getZ(), 4, 1.8D, 1.8D, 1.8D, 0.0D);
        }
        this.berserkAttackCooldown = 10;
        this.playSound(SoundEvents.RAVAGER_ATTACK, 3.5F, 0.72F);
    }

    private void emitBerserkEyes(ServerLevel server)
    {
        Vec3 forward = this.getForward().multiply(1.0D, 0.0D, 1.0D).normalize();
        Vec3 right = new Vec3(forward.z, 0.0D, -forward.x);
        Vec3 eye = this.position().add(0.0D, this.getBbHeight() * 0.88D, 0.0D)
                .add(forward.scale(2.2D));
        for (double side : new double[] {-0.42D, 0.42D})
        {
            Vec3 point = eye.add(right.scale(side));
            server.sendParticles(DustParticleOptions.REDSTONE,
                    point.x, point.y, point.z, 2, 0.05D, 0.05D, 0.05D, 0.0D);
        }
    }

    private void finishBerserk()
    {
        if (!this.isBerserk())
        {
            return;
        }
        this.entityData.set(DATA_BERSERK, false);
        this.entityData.set(DATA_BERSERK_TICKS, 0);
        EvaBerserkMotionR34.clear(this);
        EvaDorsalMechanism.afterBerserk(this);
        this.berserkRecoveryTicks = SeeleConfig.COMMON_SPEC.isLoaded()
                ? SeeleConfig.EVA_BERSERK_RECOVERY_TICKS.get() : 6000;
        this.getNavigation().stop();
        this.setTarget(null);
        this.setDeltaMovement(Vec3.ZERO);
        this.entityData.set(DATA_WEAPON, WEAPON_FISTS);
        this.playSound(SoundEvents.REDSTONE_TORCH_BURNOUT, 3.0F, 0.42F);
        ProjectSeele.LOGGER.warn(
                "EVA Unit-01 berserk ended: eva={} recoveryTicks={}",
                this.getStringUUID(), this.berserkRecoveryTicks);
    }

    private void setUmbilicalAnchor(@Nullable BlockPos anchor)
    {
        boolean connected = anchor != null;
        this.entityData.set(DATA_POWER_CONNECTED, connected);
        if (connected)
        {
            this.entityData.set(DATA_POWER_ANCHOR_X, anchor.getX());
            this.entityData.set(DATA_POWER_ANCHOR_Y, anchor.getY());
            this.entityData.set(DATA_POWER_ANCHOR_Z, anchor.getZ());
        }
    }

    protected boolean isPilotControlLocked()
    {
        if(EvaSwordActionsR45.active(this)||EvaFieldActionsR45.active(this))return true;
        if(EvaWeaponHandlingR45.active(this))return true;
        if(com.projectseele.physics.CombatBodyDynamics.active(this))return true;
        if(EvaShutdownR30.disabled(this)||EvaBayRepairR33.active(this))return true;
        return EvaDorsalMechanism.bow(this) > .001F || EvaDorsalMechanism.open(this) > .001F || this.isFirstBattleActive() || this.isNervLogisticsLocked() || this.getActivationTicks() > 20
                || this.isLaunchSequenceActive()
                || this.isPowerDepleted() || this.isBerserk()
                || this.berserkRecoveryTicks > 0;
    }

    private boolean hasStandingRoom()
    {
        return this.hasPoseRoom(NORMAL_HEIGHT);
    }

    private boolean hasPoseRoom(double height)
    {
        double halfWidth = bodyCollisionWidthR30() * 0.5D;
        AABB standing = new AABB(this.getX() - halfWidth, this.getY(), this.getZ() - halfWidth,
                this.getX() + halfWidth, this.getY() + height, this.getZ() + halfWidth);
        return this.level().noCollision(this, standing);
    }

    private void fireCannon(ServerLevel level, LivingEntity pilot)
    {
        com.projectseele.world.CombatCommandBriefR47.attackCommitted(this,"cannon");
        this.triggerAnim("strike", this.isPilotProne()
                ? "prone_cannon_fire" : "cannon_fire");
        // Sample the authoritative pilot rotation at the release packet, not
        // the previous entity-data frame. This removes the last one-tick yaw
        // or pitch discrepancy between the optical reticle and impact point.
        Vec3 dir = this.pilotAimDirection(pilot);
        // Match the reviewed hand/receiver pivots of the authored standing and
        // prone cannon stances. A fixed standing-height muzzle would otherwise
        // fire more than sixteen blocks above the visible prone weapon.
        Vec3 muzzle = this.cannonMuzzlePosition(dir);
        Vec3 from = muzzle;
        double range = this.effectiveCannonRangeR45();
        Vec3 farEnd = from.add(dir.scale(range));
        BlockHitResult blockHit = level.clip(
                new ClipContext(from, farEnd, ClipContext.Block.COLLIDER, ClipContext.Fluid.NONE, this));
        Vec3 end = blockHit.getLocation();

        EntityHitResult entityHit = com.projectseele.physics.CombatDamageTargetsR44.ray(level,from,end,.3,this,pilot);

        if (entityHit != null)
        {
            end = entityHit.getLocation();
            if (entityHit.getEntity() instanceof RamielEntity ramiel && ramiel.isCoreShot(from, dir))
            {
                // The Yashima shot: two clean core hits end the Angel.
                ramiel.hurt((pilot instanceof ServerPlayer player?this.damageSources().playerAttack(player):this.damageSources().mobAttack(pilot)),
                        SeeleConfig.CANNON_CORE_DAMAGE.get().floatValue());
            }
            else
            {
                com.projectseele.physics.CombatDamageTargetsR44.hurt(entityHit.getEntity(),(pilot instanceof ServerPlayer player?this.damageSources().playerAttack(player):this.damageSources().mobAttack(pilot)),
                        SeeleConfig.CANNON_MOB_DAMAGE.get().floatValue(),end,dir,com.projectseele.physics.CombatDamageTargetsR44.Weapon.PROJECTILE);
            }
        }

        // The shot itself detonates: damage is immediate, while the mountain-
        // scale crater is carved across later server ticks so one frame never
        // attempts millions of block updates.
        com.projectseele.visual.StanceContactR41Review.actualCannonShotR45(this,pilot,muzzle,dir,end,entityHit==null?null:entityHit.getEntity());
        StrategicExplosionDirector.startCannon(level, end, this);
        final Vec3 impact = end;

        SeeleNetwork.CHANNEL.send(PacketDistributor.TRACKING_ENTITY_AND_SELF.with(() -> this),
                new ClientboundCannonBeamPacket(muzzle.x, muzzle.y, muzzle.z, end.x, end.y, end.z));
        SeeleNetwork.CHANNEL.send(PacketDistributor.NEAR.with(() -> new PacketDistributor.TargetPoint(
                        impact.x, impact.y, impact.z, 320.0D, level.dimension())),
                new ClientboundNukeFxPacket(impact.x, impact.y, impact.z, 3.6F, false));
        level.sendParticles(ParticleTypes.END_ROD, impact.x, impact.y, impact.z, 54, 1.4D, 1.4D, 1.4D, 0.24D);
        level.sendParticles(ParticleTypes.EXPLOSION_EMITTER,
                impact.x, impact.y + 1.5D, impact.z, 6, 3.5D, 1.8D, 3.5D, 0.0D);
        for (int i = 2; i <= 24; i += 3)
        {
            level.sendParticles(ParticleTypes.LARGE_SMOKE,
                    impact.x, impact.y + i, impact.z, 8, 1.7D, 1.0D, 1.7D, 0.015D);
        }
        level.sendParticles(ParticleTypes.CAMPFIRE_COSY_SMOKE,
                impact.x, impact.y + 25.0D, impact.z, 70, 9.5D, 2.5D, 9.5D, 0.02D);
        com.projectseele.world.PositronAudioR45.fire(level, this, pilot instanceof ServerPlayer player?player:null, muzzle);
    }

    @Override public double effectiveCannonRangeR45()
    {return SeeleConfig.CANNON_RANGE.get();}

    /** NPCs use the real barrel ray, real charge and real pilot damage source. */
    @Override public boolean missionCannonInputR45(TrainingPilotEntity pilot,Vec3 actualAim,boolean hold,boolean release)
    {
        if(this.level().isClientSide||pilot==null||this.getPilotEntity()!=pilot)return false;
        if(!hold&&!release)
        {this.chargingHeld=false;this.entityData.set(DATA_CANNON_CHARGE,0);return true;}
        if(!this.autonomousPilotR30(pilot)||!com.projectseele.world.TvMissionEquipmentR45.cannonAuthorized(this)
                ||!com.projectseele.world.TvMissionEquipmentR45.operational(this)
                ||actualAim==null||!Double.isFinite(actualAim.x)||!Double.isFinite(actualAim.y)||!Double.isFinite(actualAim.z))
        {this.chargingHeld=false;this.entityData.set(DATA_CANNON_CHARGE,0);return false;}
        if(!this.autonomousWeaponR30(pilot,WEAPON_CANNON))return false;
        Vec3 direction=actualAim.subtract(this.position().add(0,CANNON_STANDING_PIVOT_HEIGHT,0)).normalize();
        // Solve against the measured muzzle, not the old head-height approximation.
        for(int iteration=0;iteration<6;iteration++)direction=actualAim.subtract(this.cannonMuzzlePosition(direction)).normalize();
        float yaw=(float)Math.toDegrees(Math.atan2(-direction.x,direction.z));
        float pitch=(float)-Math.toDegrees(Math.atan2(direction.y,Math.max(.001,direction.horizontalDistance())));
        pilot.setYRot(yaw);pilot.setXRot(pitch);
        Vec3 actualDirection=this.pilotAimDirection(pilot);
        Vec3 muzzle=this.cannonMuzzlePosition(actualDirection);
        if(release)
        {
            if(!(this.level() instanceof ServerLevel level))return false;
            var mission=com.projectseele.world.TvCampaignSavedData.get(level);
            if(mission.angel==null||!(level.getEntity(mission.angel) instanceof RamielEntity ramiel)||!ramiel.isCoreShot(muzzle,actualDirection))return false;
            this.releaseCannon((LivingEntity)pilot);
        }
        else this.setChargingHeld(hold);
        return true;
    }

    /** Exact optical/fire ray shared by cannon and pallet SMG. */
    private Vec3 pilotAimDirection(LivingEntity pilot)
    {
        float pitch = this.clampPilotWeaponPitch(pilot.getXRot(),1);
        this.entityData.set(DATA_CANNON_AIM_PITCH, pitch);
        return Vec3.directionFromRotation(pitch, this.clampPilotWeaponYaw(pilot.getYRot(),1)).normalize();
    }

    // ----- per-tick combat state -----

    @Override protected void playStepSound(BlockPos position,net.minecraft.world.level.block.state.BlockState state)
    {
        // Human-sized vanilla step intervals do not match this rig's stride.
        // EvaMovementSounds emits the measured left/right contact events.
    }

    @Override
    public void aiStep()
    {
        this.refreshTvPersonnelClockHoldR44();
        com.projectseele.visual.RuntimeR44ServerProbe.firstActorTick(this,"first_before_ai_step");
        EvaBayRepairR33.tick(this);
        EvaShutdownR30.tick(this);
        EvaFieldActionsR45.tick(this);
        EvaSwordActionsR45.tick(this);
        EvaWeaponHandlingR45.tick(this);
        EvaGameplayMotionR32.tick(this);
        if(!this.level().isClientSide&&this.getPilotEntity() instanceof ServerPlayer player
                &&(player.zza<-.15F||Math.abs(player.xxa)>.15F)
                &&this.entityData.get(DATA_LIVE_ACTION_PHASE)>=.72F
                &&(this.getOrdinaryAttackStage()>=0||this.isHeavyMotionActive())
                &&!CombatFeelR31.hitPaused(this)&&!this.isPilotControlLocked())
        {
            // Preserve wind-up/contact. A deliberate retreat can leave the recovery
            // rather than committing the player to another buffered stationary combo.
            EvaGameplayMotionR32.releaseToMovement(this);
            this.cancelLiveActionsForStanceChange();
            this.cancelHeavyMotion();
        }
        EvaCombatIntentR32.tick(this);
        EvaCombatR31.tick(this);
        this.oldCarrierRiseR26=this.entityData.get(DATA_CARRIER_RISE_R26);
        FIRST_BATTLE.clientPhysics(this);
        if(this.isFirstBattleActive())
        {
            EvaCombatSupportR33.release(this);
            FirstBattleClip.applyKinematics(this);this.syncPassengerAssembly();return;
        }
        if(!EvaShutdownR30.retainsPoseR45(this))this.updateRiflePoseSignals();
        // Contact ownership and the position/phase pair must see the phase
        // belonging to this position, not the previous tick's gait.
        EvaCombatSupportR33.tick(this);
        boolean preserveUnpilotedFacing = this.getPilotEntity() == null
                && !this.isBerserk()
                && !this.isNervLogisticsLocked()
                && !this.isLaunchSequenceActive()
                && !this.hasActiveCarrierMotion();
        float preservedYaw = this.getYRot();
        float preservedPitch = this.getXRot();
        super.aiStep();
        EvaTerrainSupport.tick(this);
        if (this.isNervLogisticsLocked())
        {
            // Vanilla body/head control also runs for nested entry-plug
            // passengers. Keep the mechanical frame authoritative on both
            // sides; mouse look belongs to the pilot camera, not the rack.
            float railYaw = this.entityData.get(DATA_NERV_LOGISTICS_YAW);
            this.setRot(railYaw, 0.0F);
            this.yRotO = this.yBodyRot = this.yBodyRotO = railYaw;
            this.yHeadRot = this.yHeadRotO = railYaw;
            this.xRotO = 0.0F;
        }
        if (preserveUnpilotedFacing)
        {
            // BodyRotationControl runs inside super.aiStep(). Restore the
            // chassis frame after vanilla collision/head tracking, including
            // interpolation history, so touching a parked or lab EVA cannot
            // rotate it for one render frame before the server correction.
            this.setRot(preservedYaw, preservedPitch);
            this.yRotO = preservedYaw;
            this.yBodyRot = preservedYaw;
            this.yBodyRotO = preservedYaw;
            this.yHeadRot = preservedYaw;
            this.yHeadRotO = preservedYaw;
        }
        if (this.level().isClientSide)
        {
            this.updateClientAnimationSignals();
            this.syncClientCarrierFrameR35();
            return;
        }
        this.refreshTvMissionEquipmentR45();
        // The pilot is sealed inside the entry plug within the airframe; keep
        // the body hidden so it is never seen perched on the giant frame.
        if (this.getControllingPassenger() instanceof ServerPlayer sealedPilot)
        {
            sealedPilot.setInvisible(true);
        }
        if(!CombatFeelR31.hitPaused(this))
        {
        if (this.ordinaryAttackComboGraceTicks > 0)
        {
            this.ordinaryAttackComboGraceTicks--;
        }
        if (this.ordinaryAfterKickBufferTicks > 0)
        {
            this.ordinaryAfterKickBufferTicks--;
        }
        if (this.kickAfterOrdinaryBufferTicks > 0)
        {
            this.kickAfterOrdinaryBufferTicks--;
        }
        if (this.ordinaryAttackVisualTicks > 0)
        {
            this.applyLiveCombatRootMotion(true);
        }
        else if (this.kickVisualTicks > 0)
        {
            this.applyLiveCombatRootMotion(false);
        }
        else if (this.knifeVisualTicks > 0
                && this.getWeapon() == WEAPON_KNIFE)
        {
            this.applyKnifeRootMotion();
        }
        LivingEntity combatPilot=this.getPilotEntity();
        if(!(combatPilot instanceof ServerPlayer)&&!(combatPilot instanceof TrainingPilotEntity))combatPilot=null;
        if(EvaGameplayMotionR32.ready(this)&&this.getOrdinaryAttackStage()>=0)
        {
            this.pendingOrdinaryContactTicks=0;
            float phase=this.entityData.get(DATA_LIVE_ACTION_PHASE);
            if(!gameplayOrdinaryContactR32&&EvaGameplayMotionR32.inContactWindowR45(this,EvaGameplayMotionR32.ordinary(this.getOrdinaryAttackStage()),phase)&&combatPilot!=null&&!this.isPilotControlLocked())
                gameplayOrdinaryContactR32=this.gameplayContactR32(combatPilot,EvaGameplayMotionR32.ordinary(this.getOrdinaryAttackStage()),false);
        }
        else if (this.pendingOrdinaryContactTicks > 0)
        {
            this.pendingOrdinaryContactTicks--;
            if (this.pendingOrdinaryContactTicks == 0)
            {
                int contactStage = this.pendingOrdinaryContactStage;
                this.pendingOrdinaryContactStage = -1;
                if (combatPilot != null
                        && !this.isPilotControlLocked())
                {
                    this.resolveOrdinaryGroupCContact(combatPilot, contactStage);
                }
            }
        }
        if (this.pendingKickContactTicks > 0)
        {
            this.pendingKickContactTicks--;
            if (this.pendingKickContactTicks == 0
                    && combatPilot != null
                    && !this.isPilotControlLocked())
            {
                this.resolveSideKickContact(combatPilot);
            }
        }
        boolean ordinaryEnded = false;
        boolean heavyEnded = false;
        if (this.isPilotControlLocked() || !(combatPilot != null))
            this.cancelHeavyMotion();
        if (this.heavyTicks > 0)
        {
            if (this.getWeapon() != WEAPON_FISTS || ((this.isPilotProne() || this.isPilotCrouching()) && !EvaGameplayMotionR32.lowAttackReadyR44(this)) || this.isPilotControlLocked())
                this.cancelHeavyMotion();
            else
            {
                float phase = Mth.clamp(++this.heavyElapsed / (float)this.heavyDuration, 0, 1);
                float swingPhase=EvaGameplayMotionR32.ready(this)?EvaGameplayMotionR32.swingSoundPhaseR45(this,"heavy"):.40F;
                if(EvaGameplayMotionR32.directed(this)&&heavyElapsed>=heavyDuration*swingPhase&&heavyElapsed-1<heavyDuration*swingPhase)EvaMovementSounds.swing(this,2.8F);
                this.entityData.set(DATA_LIVE_ACTION_PHASE, phase);
                this.applyAuthoredRootDelta(EvaGameplayMotionR32.ready(this)?EvaGameplayMotionR32.root(this,"heavy",phase):EvaLiveCombatMotion.heavy(phase));
                if(EvaGameplayMotionR32.ready(this))
                {
                    if(!this.heavyContact&&EvaGameplayMotionR32.inContactWindowR45(this,"heavy",phase)&&combatPilot!=null)this.heavyContact=this.gameplayContactR32(combatPilot,"heavy",true);
                }
                else if (!this.heavyContact && phase >= .45F && combatPilot != null)
                {
                    this.heavyContact = true;
                    if (this.getTags().contains("seele_motion_lab")) ProjectSeele.LOGGER.info("EVA heavy contact tick={} phase={}", this.tickCount, phase);
                    this.resolveHeavyContact(combatPilot);
                }
                heavyEnded = --this.heavyTicks == 0;
                if (heavyEnded)
                {
                    if(EvaGameplayMotionR32.naturalRecovery(this))EvaGameplayMotionR32.releaseToMovement(this);
                    this.entityData.set(DATA_HEAVY_ACTIVE, false);
                }
            }
        }
        if (this.pendingKnifeContactTicks > 0 && --this.pendingKnifeContactTicks == 0
                && this.getWeapon() == WEAPON_KNIFE && this.knifeVisualTicks > 0
                && ((!this.isPilotCrouching() && !this.isPilotProne()) || EvaGameplayMotionR32.lowAttackReadyR44(this))
                && !this.isPilotControlLocked()
                && combatPilot != null)
        {
            this.resolveKnifeContact(combatPilot);
        }
        if (this.ordinaryAttackVisualTicks > 0)
        {
            // Buffered follow-ups leave from the braking pose. Waiting for the
            // full neutral release made every attack restart the whole body.
            if(EvaGameplayMotionR32.phrases(this)&&this.entityData.get(DATA_LIVE_ACTION_PHASE)>=EvaGameplayMotionR32.releasePhase(this)
                    &&this.meleeInputBufferTicks>0&&!this.queuedHeavy&&this.kickAfterOrdinaryBufferTicks==0
                    &&combatPilot!=null&&!this.isPilotControlLocked())
            {
                this.meleeInputBufferTicks=0;
                this.beginOrdinaryGroupCAttack();
            }
            this.ordinaryAttackVisualTicks--;
            if (this.ordinaryAttackVisualTicks == 0)
            {
                if(EvaGameplayMotionR32.naturalRecovery(this))EvaGameplayMotionR32.releaseToMovement(this);
                this.entityData.set(DATA_ORDINARY_ATTACK_STAGE, -1);
                ordinaryEnded = true;
            }
        }
        boolean kickEnded = false;
        if (this.kickVisualTicks > 0)
        {
            this.kickVisualTicks--;
            kickEnded = this.kickVisualTicks == 0;
            if (kickEnded)
            {
                if(EvaGameplayMotionR32.kickReady(this))EvaGameplayMotionR32.releaseToMovement(this);
                this.entityData.set(DATA_KICK_ACTIVE, false);
            }
        }
        if (this.knifeVisualTicks > 0)
        {
            this.knifeVisualTicks--;
            if (this.knifeVisualTicks == 0)
            {
                if(EvaGameplayMotionR32.knifeReady(this))EvaGameplayMotionR32.releaseToMovement(this);
                this.entityData.set(DATA_KNIFE_TYPE, -1);
            }
        }
        if (this.meleeCooldown > 0)
        {
            this.meleeCooldown--;
        }
        if (this.meleeInputBufferTicks > 0)
        {
            this.meleeInputBufferTicks--;
        }
        if (this.smashCooldown > 0)
        {
            this.smashCooldown--;
        }
        if (this.stompCooldown > 0)
        {
            this.stompCooldown--;
        }
        if (combatPilot != null
                && !this.isPilotControlLocked() && this.isMeleeWeapon())
        {
            if (this.queuedHeavy && this.ordinaryAttackVisualTicks == 0 && this.kickVisualTicks == 0 && !this.isHeavyMotionActive())
            {
                this.queuedHeavy = false;
                this.smashAttack(combatPilot);
            }
            else if (heavyEnded && this.queuedKickAfterHeavy)
            {
                this.queuedKickAfterHeavy = false;
                this.queuedMeleeAfterHeavy = false;
                this.stompAttack(combatPilot);
            }
            else if (heavyEnded && this.queuedMeleeAfterHeavy)
            {
                this.queuedMeleeAfterHeavy = false;
                this.meleeAttack(combatPilot);
            }
            else if (this.queuedKnifeInput >= 0 && this.knifeVisualTicks == 0
                    && this.getWeapon() == WEAPON_KNIFE
                    && (this.queuedKnifeInput == 1 ? this.smashCooldown == 0 : this.meleeCooldown == 0))
            {
                int queued = this.queuedKnifeInput;
                this.queuedKnifeInput = -1;
                if (queued == 1) this.smashAttack(combatPilot);
                else this.meleeAttack(combatPilot);
            }
            else if (ordinaryEnded && this.kickAfterOrdinaryBufferTicks > 0)
            {
                this.stompAttack(combatPilot);
            }
            else if (kickEnded && this.ordinaryAfterKickBufferTicks > 0)
            {
                this.meleeAttack(combatPilot);
            }
            else if (this.meleeInputBufferTicks > 0
                    && this.meleeCooldown == 0)
            {
                this.meleeAttack(combatPilot);
            }
        }
        if (this.rifleCooldown > 0)
        {
            this.rifleCooldown--;
        }
        }
        if (this.jumpCooldown > 0)
        {
            this.jumpCooldown--;
        }
        if (this.onGround())
        {
            this.groundedGraceTicks = JUMP_COYOTE_TICKS;
        }
        if (this.jumpBufferTicks > 0)
        {
            boolean consumed = this.getControllingPassenger() instanceof ServerPlayer pilot
                    && this.tryConsumeBufferedJump(pilot);
            if (!consumed)
            {
                this.jumpBufferTicks--;
            }
        }
        if (!this.onGround() && this.groundedGraceTicks > 0)
        {
            // Consume after the buffered attempt so the first three airborne
            // ticks all retain their intended coyote-time opportunity.
            this.groundedGraceTicks--;
        }
        if (this.getControllingPassenger() != null && !this.isEntryPlugInserted())
        {
            // Covers passenger restoration and development commands that use
            // startRiding directly instead of the normal plug interaction.
            this.entityData.set(DATA_ENTRY_PLUG_INSERTED, true);
        }
        if (this.getActivationTicks() > 0 && !this.refreshTvPersonnelClockHoldR44())
        {
            this.entityData.set(DATA_ACTIVATION_TICKS, this.getActivationTicks() - 1);
        }
        this.tickPilotSynchronization();
        this.tickPowerSystem();
        com.projectseele.visual.RuntimeR44ServerProbe.firstActorTick(this,"first_after_power_tick");
        this.tickBerserkState();
        this.tickSortieParkingLock();
        this.tickLaunchSequence();
        this.entityData.set(DATA_POWERED_VISUAL_R46, this.isPoweredOn());
        if (!this.onGround())
        {
            this.serverAirborneTicks++;
            if (this.explicitJumpInProgress)
            {
                this.explicitJumpObservedAirborne = true;
                this.wasAirborne = true;
            }
            else
            {
                double verticalSpeed = this.getDeltaMovement().y * 20.0D;
                boolean confirmedFall = this.serverAirborneTicks
                        >= PASSIVE_FALL_CONFIRM_TICKS
                        && (this.fallDistance >= PASSIVE_FALL_MIN_DROP
                        || this.serverAirborneTicks
                                >= PASSIVE_FALL_SPEED_CONFIRM_TICKS
                        && verticalSpeed <= PASSIVE_FALL_MIN_SPEED);
                if (confirmedFall)
                {
                    this.wasAirborne = true;
                }
            }
        }
        else
        {
            this.serverAirborneTicks = 0;
            if (this.explicitJumpInProgress
                    && !this.explicitJumpObservedAirborne)
            {
                if (this.explicitJumpAuthorizationTicks > 0)
                {
                    this.explicitJumpAuthorizationTicks--;
                }
                else
                {
                    this.explicitJumpInProgress = false;
                }
            }
            if (this.wasAirborne)
            {
                this.wasAirborne = false;
                this.explicitJumpInProgress = false;
                this.explicitJumpObservedAirborne = false;
                this.explicitJumpAuthorizationTicks = 0;
                boolean movingThroughLanding =
                        this.getDeltaMovement().horizontalDistanceSqr() > 0.01D
                        || this.isPilotSprinting()
                        || this.pilotMovementRequested;
                if (!movingThroughLanding && !EvaGameplayMotionR32.sharedJump(this))
                {
                    this.triggerAnim("strike", "land");
                }
                if (this.level() instanceof ServerLevel serverLevel)
                {
                    serverLevel.sendParticles(ParticleTypes.CLOUD, this.getX(),
                            this.getY() + 0.4D, this.getZ(), 22, 3.2D, 0.25D,
                            3.2D, 0.04D);
                }
                this.playSound(ModSounds.EVA_LAND.get(),1.9F,1);
            }
        }
        int cooldown = this.getCannonCooldown();
        if (cooldown > 0)
        {
            this.entityData.set(DATA_CANNON_COOLDOWN, cooldown - 1);
        }

        int charge = this.getCannonCharge();
        boolean canCharge = !this.isPilotControlLocked()
                && this.chargingHeld && this.getWeapon() == WEAPON_CANNON
                && this.getCannonCooldown() <= 0 && this.getControllingPassenger() != null;
        if (canCharge)
        {
            if (charge < SeeleConfig.CANNON_CHARGE_TICKS.get())
            {
                this.entityData.set(DATA_CANNON_CHARGE, charge + 1);
            }
        }
        else if (charge > 0 && !this.chargingHeld)
        {
            this.entityData.set(DATA_CANNON_CHARGE, 0);
        }

        int n2Arm = this.getN2ArmTicks();
        boolean canArmN2 = !this.isPilotControlLocked()
                && this.chargingHeld && this.getWeapon() == WEAPON_N2
                && this.getControllingPassenger() instanceof ServerPlayer;
        if (canArmN2)
        {
            int next = Math.min(SeeleConfig.N2_ARM_TICKS.get(), n2Arm + 1);
            this.entityData.set(DATA_N2_ARM_TICKS, next);
            if (next >= SeeleConfig.N2_ARM_TICKS.get()
                    && this.getControllingPassenger() instanceof ServerPlayer pilot)
            {
                this.detonateN2((ServerLevel) this.level(), pilot);
            }
        }
        else if (n2Arm > 0)
        {
            this.entityData.set(DATA_N2_ARM_TICKS, 0);
        }

        if (this.atRegenDelay > 0)
        {
            this.atRegenDelay--;
        }
        else if (this.getAtFieldEnergy() < this.getAtFieldCapacity())
        {
            this.entityData.set(DATA_AT_ENERGY,
                    Math.min(this.getAtFieldCapacity(), this.getAtFieldEnergy() + AT_FIELD_REGEN));
        }
        if (this.isAtFieldOn() && this.getAtFieldEnergy() <= 0.0F)
        {
            this.entityData.set(DATA_AT_ON, false);
            this.playSound(ModSounds.CRYSTAL_BREAK.get(), 2.0F, 1.2F);
        }
        if (this.getControllingPassenger() == null
                && !this.getTags().contains("seele_motion_lab"))
        {
            this.pilotMovementRequested = false;
            this.clearJumpRequestState();
            this.clearPilotMotion();
        }
    }

    private void armLaunchBed(BlockPos bed)
    {
        this.launchBedPos = bed.immutable();
        this.launchLockedYaw = this.getYRot();
        this.entityData.set(DATA_LAUNCH_PHASE, LAUNCH_LOCKED);
        this.entityData.set(DATA_LAUNCH_TICKS, this.getActivationTicks());
        this.launchCarrierY = bed.getY();
        this.launchContinuousRoute = this.isContinuousSortie();
        this.launchCommandReleased = false;
        this.launchRecoveryPending = false;
        this.launchPassengerRestoreGraceTicks = 0;
        this.entityData.set(DATA_CROUCHING, false);
        this.entityData.set(DATA_PRONE, false);
        this.entityData.set(DATA_SPRINTING, false);
        this.updatePoseDimensions();
        this.setNoGravity(true);
        this.enforceLaunchLock();
        ProjectSeele.LOGGER.info("NERV launch locked: eva={} bed={} targetY={}",
                this.getStringUUID(), bed.toShortString(), this.launchTargetY());
    }

    /**
     * A same-dimension destination lodestone is the real surface carrier.
     * Legacy external launch complexes retain their original 32-block travel,
     * while an integrated NERV shaft derives its complete height from the two
     * physical station markers.
     */
    private boolean isContinuousSortie()
    {
        boolean logicalSurfaceDestination =
                this.level() instanceof ServerLevel serverLevel
                && this.sortieDestinationBed != null
                && IntegratedNervMapBuilder.isSurfaceStation(
                        serverLevel, this.sortieDestinationBed);
        return this.launchBedPos != null
                && this.sortieDestinationDimension != null
                && this.sortieDestinationDimension.equals(this.level().dimension())
                && this.sortieDestinationBed != null
                && this.sortieDestinationBed.getY() > this.launchBedPos.getY()
                && this.sortieDestinationBed.getX() == this.launchBedPos.getX()
                && this.sortieDestinationBed.getZ() == this.launchBedPos.getZ()
                && (logicalSurfaceDestination
                    || this.level().getBlockState(this.sortieDestinationBed)
                            .is(Blocks.LODESTONE));
    }

    private double launchTargetY()
    {
        if (this.launchContinuousRoute && this.sortieDestinationBed != null)
        {
            // The Tokyo-3 hatch itself occupies destination Y+1.  The old
            // route stopped on a second 29x29 slab at destination Y, leaving
            // a redundant visible lid beneath all three animated doors.
            // Arrive one block higher so the closed physical hatch is the
            // only surface support plane.
            return this.sortieDestinationBed.getY() + 2.0D;
        }
        return this.launchBedPos == null ? this.getY()
                : this.launchBedPos.getY() + LAUNCH_TARGET_ABOVE_BED;
    }

    private int launchDeckY()
    {
        if (this.launchContinuousRoute && this.sortieDestinationBed != null)
        {
            return this.sortieDestinationBed.getY() + 1;
        }
        return this.launchBedPos == null ? Mth.floor(this.getY()) - 1
                : this.launchBedPos.getY() + (int) LAUNCH_TARGET_ABOVE_BED - 1;
    }

    private int launchAscentTicks()
    {
        if (this.launchBedPos == null)
        {
            return LAUNCH_ASCENT_TICKS;
        }
        double distance = Math.max(0.0D,
                this.launchTargetY() - (this.launchBedPos.getY() + 1.0D));
        int originalTicks=Math.max(LAUNCH_ASCENT_TICKS,
                Mth.ceil(distance / CONTINUOUS_ASCENT_BLOCKS_PER_TICK));
        // The speed impression belongs to the first rail segment. Compressing
        // the entire 491 m route to 33 ticks erased the climb between launch
        // and arrival. Both sides sample the same staged curve above.
        return originalTicks;
    }

    private void tickSortieParkingLock()
    {
        if (this.sortieParkingBed == null || !this.hasSortieDestination()
                || this.isLaunchSequenceActive() || this.getControllingPassenger() != null)
        {
            return;
        }
        if (!this.level().getBlockState(this.sortieParkingBed).is(Blocks.LODESTONE))
        {
            ProjectSeele.LOGGER.error(
                    "NERV sortie parking lock lost its bed: eva={} bed={}",
                    this.getStringUUID(), this.sortieParkingBed.toShortString());
            this.clearSortieDestination();
            this.setNoGravity(false);
            return;
        }
        this.getNavigation().stop();
        this.setTarget(null);
        this.setPos(this.sortieParkingBed.getX() + 0.5D,
                this.sortieParkingBed.getY() + 1.0D,
                this.sortieParkingBed.getZ() + 0.5D);
        this.setDeltaMovement(Vec3.ZERO);
        this.setRot(SILO_BAY_YAW, 0.0F);
        this.yRotO = this.yBodyRot = this.yHeadRot = SILO_BAY_YAW;
        this.fallDistance = 0.0F;
        this.setNoGravity(true);
        this.hasImpulse = true;
    }

    /** Hold the complete airframe on its audited bed until catapult release. */
    private void enforceLaunchLock()
    {
        if (this.launchBedPos == null)
        {
            return;
        }
        this.getNavigation().stop();
        this.setTarget(null);
        this.setPos(this.launchBedPos.getX() + 0.5D, this.launchBedPos.getY() + 1.0D,
                this.launchBedPos.getZ() + 0.5D);
        this.setDeltaMovement(Vec3.ZERO);
        this.setRot(this.launchLockedYaw, 0.0F);
        this.yRotO = this.yBodyRot = this.yHeadRot = this.launchLockedYaw;
        this.fallDistance = 0.0F;
        this.hasImpulse = true;
        this.syncPassengerAssembly();
    }

    private void beginLaunchAscent()
    {
        if (this.launchBedPos == null || !this.level().getBlockState(this.launchBedPos).is(Blocks.LODESTONE))
        {
            this.resetLaunchSequence();
            return;
        }
        ServerLevel serverLevel = this.level() instanceof ServerLevel activeLevel
                ? activeLevel : null;
        if (this.launchContinuousRoute
                && (serverLevel == null
                    || !this.isContinuousSortie()
                    || !isContinuousSortieRouteClear(serverLevel,
                            this.launchBedPos, this.sortieDestinationBed)))
        {
            if (this.getControllingPassenger() instanceof ServerPlayer pilot)
            {
                pilot.displayClientMessage(Component.literal(
                        "NERV launch inhibited: the physical shaft or surface exit is obstructed."),
                        true);
            }
            ProjectSeele.LOGGER.error(
                    "NERV continuous sortie preflight failed: eva={} lower={} upper={} obstruction={}",
                    this.getStringUUID(), this.launchBedPos.toShortString(),
                    this.sortieDestinationBed == null ? "missing"
                            : this.sortieDestinationBed.toShortString(),
                    serverLevel == null || this.sortieDestinationBed == null ? "missing"
                            : describeContinuousSortieObstruction(
                            serverLevel, this.launchBedPos,
                            this.sortieDestinationBed));
            this.resetLaunchSequence();
            return;
        }
        int ascentTicks = this.launchAscentTicks();
        Vec3 launchFrom = new Vec3(
                this.launchBedPos.getX() + 0.5D,
                this.launchBedPos.getY() + 1.0D,
                this.launchBedPos.getZ() + 0.5D);
        Vec3 launchTo = new Vec3(
                launchFrom.x, this.launchTargetY(), launchFrom.z);
        this.entityData.set(DATA_LAUNCH_PHASE, LAUNCH_ASCENT);
        this.entityData.set(DATA_LAUNCH_TICKS, ascentTicks);
        this.setSurfaceCarrier(false);
        this.setNoGravity(true);
        this.setPos(launchFrom.x, launchFrom.y, launchFrom.z);
        this.beginCarrierMotion(launchFrom, launchTo, ascentTicks);
        this.setDeltaMovement(Vec3.ZERO);
        ProjectSeele.LOGGER.info("NERV launch ascent: eva={} ticks={}",
                this.getStringUUID(), ascentTicks);
        this.level().playSound(null,this.getX(),this.getY()+2,this.getZ(),net.minecraft.sounds.SoundEvent.createFixedRangeEvent(ModSounds.FACILITY.get("facility_hydraulic_launch").get().getLocation(),256F),SoundSource.BLOCKS,3.2F,1);
        if (serverLevel != null)
        {
            com.projectseele.world.LaunchSteamEffects.emit(serverLevel,this.launchBedPos,0);
            serverLevel.sendParticles(ParticleTypes.CLOUD, this.getX(), this.getY() + 0.4D, this.getZ(),
                    72, 4.2D, 0.7D, 4.2D, 0.16D);
            serverLevel.sendParticles(ParticleTypes.ELECTRIC_SPARK, this.getX(), this.getY() + 2.0D, this.getZ(),
                    36, 4.0D, 2.5D, 4.0D, 0.08D);
        }
    }

    /**
     * Advances a launch whose entity section stopped ticking while no human
     * player rides the airframe. EvaLogisticsDirector calls this only after
     * observing an unchanged entity tick counter, so ordinary launches are
     * never double-ticked.
     */
    public boolean tickDormantNervLaunch()
    {
        if (this.level().isClientSide || !this.isLaunchSequenceActive())
        {
            return false;
        }
        this.tickLaunchSequence();
        return true;
    }

    private void tickLaunchSequence()
    {
        if(this.refreshTvPersonnelClockHoldR44())return;
        int phase = this.getLaunchPhase();
        if (phase == LAUNCH_IDLE)
        {
            return;
        }
        if (phase == LAUNCH_LOCKED)
        {
            if (!this.hasLaunchPassenger())
            {
                if (this.launchPassengerRestoreGraceTicks > 0)
                {
                    this.launchPassengerRestoreGraceTicks--;
                    this.enforceLaunchLock();
                    return;
                }
                this.resetLaunchSequence();
                return;
            }
            this.launchPassengerRestoreGraceTicks = 0;
            this.enforceLaunchLock();
            if (!this.launchCommandReleased)
            {
                // Activation may finish while the airframe is transported.
                // Hold above the release threshold until operations explicitly
                // authorizes the carrier; never infer permission from time.
                int interlockTicks = Math.max(21, this.getActivationTicks());
                this.entityData.set(DATA_ACTIVATION_TICKS, interlockTicks);
                this.entityData.set(DATA_LAUNCH_TICKS, interlockTicks);
                return;
            }
            if (this.getActivationTicks() <= 20)
            {
                this.beginLaunchAscent();
                return;
            }
            this.entityData.set(DATA_LAUNCH_TICKS, this.getActivationTicks());
            return;
        }
        if (phase == LAUNCH_ASCENT)
        {
            if (this.launchBedPos == null)
            {
                this.resetLaunchSequence();
                return;
            }
            if (this.launchRecoveryPending && !this.recoverMovingCarrier())
            {
                return;
            }
            if (!this.hasLaunchPassenger())
            {
                if (this.launchPassengerRestoreGraceTicks > 0)
                {
                    this.launchPassengerRestoreGraceTicks--;
                    this.setDeltaMovement(Vec3.ZERO);
                    return;
                }
                this.resetLaunchSequence();
                return;
            }
            this.launchPassengerRestoreGraceTicks = 0;
            double targetY = this.launchTargetY();
            int ascentTicks = this.launchAscentTicks();
            int remainingTicks = Math.max(0, this.getLaunchTicks() - 1);
            if(this.level() instanceof ServerLevel steamLevel)
                com.projectseele.world.LaunchSteamEffects.emit(steamLevel,this.launchBedPos,ascentTicks-remainingTicks);
            Vec3 sampled = this.sampleCarrierMotion(0.0F);
            this.setPos(sampled.x, sampled.y, sampled.z);
            this.setDeltaMovement(Vec3.ZERO);
            this.setRot(this.launchLockedYaw, 0.0F);
            this.yRotO = this.yBodyRot = this.yHeadRot = this.launchLockedYaw;
            this.fallDistance = 0.0F;
            this.hasImpulse = true;
            this.syncPassengerAssembly();
            if (!this.updateMovingCarrier())
            {
                if (this.getControllingPassenger() instanceof ServerPlayer pilot)
                {
                    pilot.displayClientMessage(Component.literal(
                            "NERV emergency stop: an obstruction entered the launch shaft."),
                            true);
                }
                ProjectSeele.LOGGER.error(
                        "NERV carrier obstruction during ascent: eva={} y={}",
                        this.getStringUUID(), Mth.floor(this.getY()) - 1);
                this.resetLaunchSequence();
                return;
            }
            this.entityData.set(DATA_LAUNCH_TICKS, remainingTicks);
            if (remainingTicks <= 0)
            {
                this.setPos(this.launchBedPos.getX() + 0.5D, targetY,
                        this.launchBedPos.getZ() + 0.5D);
                this.endCarrierMotion();
                this.clearMovingCarrierBelowSurface();
                boolean continuousRoute = this.launchContinuousRoute;
                if (this.completeLinkedSortie())
                {
                    return;
                }
                if (continuousRoute)
                {
                    this.resetLaunchSequence();
                    return;
                }
                this.launchCarrierY = this.launchDeckY();
                this.setPos(this.launchBedPos.getX() + 0.5D, targetY, this.launchBedPos.getZ() + 0.5D);
                this.syncPassengerAssembly();
                // Close only after the complete EVA/passenger assembly has
                // cleared the deck plane; otherwise a timeout could build
                // 121 solid blocks through a still-rising body.
                this.setSurfaceCarrier(true);
                this.setDeltaMovement(0.0D, 0.12D, 0.0D);
                this.setNoGravity(false);
                this.entityData.set(DATA_LAUNCH_PHASE, LAUNCH_CLEAR);
                this.entityData.set(DATA_LAUNCH_TICKS, LAUNCH_CLEAR_TICKS);
                ProjectSeele.LOGGER.info("NERV launch surface clear: eva={} y={}",
                        this.getStringUUID(), targetY);
                if (this.getControllingPassenger() instanceof ServerPlayer pilot)
                {
                    pilot.displayClientMessage(Component.translatable(
                            "message.projectseele.launch_surface_clear"), true);
                }
                this.playSound(SoundEvents.PISTON_CONTRACT, 2.8F, 0.72F);
                if (this.level() instanceof ServerLevel serverLevel)
                {
                    serverLevel.sendParticles(ParticleTypes.CLOUD, this.getX(), this.getY(), this.getZ(),
                            54, 5.0D, 0.4D, 5.0D, 0.09D);
                }
                return;
            }
            return;
        }
        if (phase == LAUNCH_CLEAR && this.launchContinuousRoute
                && this.sortieDestinationBed != null)
        {
            this.enforceContinuousSurfaceArrival();
            int remainingTicks = this.getLaunchTicks() - 1;
            if (remainingTicks <= 0)
            {
                // The R16 telescopic leaves take longer than the arrival sync
                // timer. Releasing human control on that timer alone restores
                // gravity over an open shaft; dummy standby hid the failure.
                this.entityData.set(DATA_LAUNCH_TICKS, 0);
                if (this.level() instanceof ServerLevel serverLevel
                        && NervSiloDoorEntity.hasClosedSurfaceSupport(
                                serverLevel, this.sortieDestinationBed))
                {
                    this.finishTransferredSortie(this.launchLockedYaw);
                }
            }
            else
            {
                this.entityData.set(DATA_LAUNCH_TICKS, remainingTicks);
            }
            return;
        }
        int remainingTicks = this.getLaunchTicks() - 1;
        if (remainingTicks <= 0)
        {
            this.resetLaunchSequence();
        }
        else
        {
            this.entityData.set(DATA_LAUNCH_TICKS, remainingTicks);
            this.fallDistance = 0.0F;
        }
    }

    /** Move one ephemeral visual deck below the EVA without repainting blocks. */
    private boolean updateMovingCarrier()
    {
        if (this.launchBedPos == null
                || !(this.level() instanceof ServerLevel serverLevel))
        {
            return false;
        }
        int bedY = this.launchBedPos.getY();
        int deckY = this.launchDeckY();
        int desiredY = Mth.clamp(Mth.floor(this.getY()) - 1, bedY, deckY);
        double visualY = Mth.clamp(this.getY() - 1.0D,
                (double) bedY, (double) deckY);
        if (desiredY > bedY && desiredY < deckY
                && !this.canPlaceMovingCarrierLayer(desiredY))
        {
            return false;
        }
        // Remove a layer left by an older build exactly once. New builds use
        // one no-save renderer entity and never modify the shaft every tick.
        if (this.launchCarrierY > bedY && this.launchCarrierY < deckY
                && this.hasMovingCarrierSignature(this.launchCarrierY))
        {
            this.setMovingCarrierLayer(this.launchCarrierY, false);
        }
        if (desiredY > bedY)
        {
            NervCarrierVisuals.update(serverLevel, this,
                    this.launchBedPos.getX() + 0.5D, visualY,
                    this.launchBedPos.getZ() + 0.5D);
        }
        else
        {
            NervCarrierVisuals.remove(serverLevel, this);
        }
        boolean changed = desiredY != this.launchCarrierY;
        this.launchCarrierY = desiredY;
        int travelled = desiredY - bedY;
        if (changed && (travelled == 1 || travelled == 16
                || desiredY == deckY - 1))
        {
            ProjectSeele.LOGGER.info(
                    "NERV carrier progress: eva={} carrierY={} travelled={}/{}",
                    this.getStringUUID(), desiredY, travelled, deckY - bedY);
        }
        return true;
    }

    private void clearMovingCarrierBelowSurface()
    {
        if (this.launchBedPos == null
                || !(this.level() instanceof ServerLevel serverLevel))
        {
            return;
        }
        NervCarrierVisuals.remove(serverLevel, this);
        int bedY = this.launchBedPos.getY();
        int deckY = this.launchDeckY();
        if (this.launchCarrierY > bedY && this.launchCarrierY < deckY
                && this.hasMovingCarrierSignature(this.launchCarrierY))
        {
            this.setMovingCarrierLayer(this.launchCarrierY, false);
        }
    }

    private boolean recoverMovingCarrier()
    {
        this.launchRecoveryPending = false;
        if (this.launchBedPos == null
                || !this.level().getBlockState(this.launchBedPos).is(Blocks.LODESTONE))
        {
            this.resetLaunchSequence();
            return false;
        }
        int bedY = this.launchBedPos.getY();
        int deckY = this.launchDeckY();
        int inferredY = Mth.clamp(Mth.floor(this.getY()) - 1, bedY, deckY);
        int savedY = this.launchCarrierY;
        // Entity and chunk saves are not atomic, so either the stored layer or
        // the layer immediately around the restored feet may survive. Only an
        // exact 29x29 carrier signature is eligible for removal; never sweep
        // an entire shaft merely because player blocks share its materials.
        for (int candidateY : new int[] {
                savedY, savedY - 1, savedY + 1,
                inferredY, inferredY - 1, inferredY + 1})
        {
            if (candidateY > bedY && candidateY < deckY
                    && this.hasMovingCarrierSignature(candidateY))
            {
                this.setMovingCarrierLayer(candidateY, false);
            }
        }
        this.launchCarrierY = NO_LAUNCH_CARRIER;
        if (!this.updateMovingCarrier())
        {
            this.resetLaunchSequence();
            return false;
        }
        ProjectSeele.LOGGER.info("NERV carrier recovered: eva={} bed={} carrierY={}",
                this.getStringUUID(), this.launchBedPos.toShortString(), this.launchCarrierY);
        return true;
    }

    private boolean hasMovingCarrierSignature(int y)
    {
        if (this.launchBedPos == null || !(this.level() instanceof ServerLevel serverLevel))
        {
            return false;
        }
        for (int x = -LAUNCH_CARRIER_HALF; x <= LAUNCH_CARRIER_HALF; x++)
        {
            for (int z = -LAUNCH_CARRIER_HALF; z <= LAUNCH_CARRIER_HALF; z++)
            {
                BlockPos block = new BlockPos(this.launchBedPos.getX() + x, y,
                        this.launchBedPos.getZ() + z);
                boolean rim = Math.abs(x) == LAUNCH_CARRIER_HALF
                        || Math.abs(z) == LAUNCH_CARRIER_HALF;
                if (rim ? !serverLevel.getBlockState(block).is(Blocks.IRON_BLOCK)
                        : !serverLevel.getBlockState(block).is(Blocks.LIGHT_GRAY_CONCRETE))
                {
                    return false;
                }
            }
        }
        return true;
    }

    private boolean canPlaceMovingCarrierLayer(int y)
    {
        if (this.launchBedPos == null || !(this.level() instanceof ServerLevel serverLevel))
        {
            return false;
        }
        for (int x = -LAUNCH_CARRIER_HALF; x <= LAUNCH_CARRIER_HALF; x++)
        {
            for (int z = -LAUNCH_CARRIER_HALF; z <= LAUNCH_CARRIER_HALF; z++)
            {
                if (!withinLaunchShaftClearance(x, z))
                {
                    continue;
                }
                BlockPos block = new BlockPos(this.launchBedPos.getX() + x, y,
                        this.launchBedPos.getZ() + z);
                if (!serverLevel.getBlockState(block).isAir())
                {
                    return false;
                }
            }
        }
        return true;
    }

    private void setMovingCarrierLayer(int y, boolean present)
    {
        if (this.launchBedPos == null || !(this.level() instanceof ServerLevel serverLevel))
        {
            return;
        }
        for (int x = -LAUNCH_CARRIER_HALF; x <= LAUNCH_CARRIER_HALF; x++)
        {
            for (int z = -LAUNCH_CARRIER_HALF; z <= LAUNCH_CARRIER_HALF; z++)
            {
                BlockPos block = new BlockPos(this.launchBedPos.getX() + x, y,
                        this.launchBedPos.getZ() + z);
                boolean rim = Math.abs(x) == LAUNCH_CARRIER_HALF
                        || Math.abs(z) == LAUNCH_CARRIER_HALF;
                if (present)
                {
                    var desired = rim ? Blocks.IRON_BLOCK.defaultBlockState()
                            : Blocks.LIGHT_GRAY_CONCRETE.defaultBlockState();
                    if (!serverLevel.getBlockState(block).equals(desired))
                    {
                        serverLevel.setBlock(block, desired, 2);
                        PerformanceCounters.recordWorldBlockWrites(1);
                    }
                }
                else if (serverLevel.getBlockState(block).is(Blocks.IRON_BLOCK)
                        || serverLevel.getBlockState(block).is(Blocks.LIGHT_GRAY_CONCRETE))
                {
                    serverLevel.setBlock(block, Blocks.AIR.defaultBlockState(), 2);
                    PerformanceCounters.recordWorldBlockWrites(1);
                }
            }
        }
    }

    /** Opens/closes the split surface carrier without touching unrelated player blocks. */
    private void setSurfaceCarrier(boolean closed)
    {
        if (this.launchBedPos == null || !(this.level() instanceof ServerLevel serverLevel))
        {
            return;
        }
        // A continuous Tokyo-3 sortie uses NervSiloDoorEntity at Y+1 as its
        // only surface hatch.  Never recreate the retired Y=79 carrier lid.
        if (this.launchContinuousRoute)
        {
            return;
        }
        setSurfaceCarrierAt(serverLevel, this.launchBedPos,
                this.launchDeckY(), closed);
    }

    private static void setSurfaceCarrierAt(ServerLevel level, BlockPos bed,
                                            int deckY, boolean closed)
    {
        boolean flushTokyo3Door =
                IntegratedNervMapBuilder.isSurfaceStation(level, bed);
        for (int x = -LAUNCH_CARRIER_HALF; x <= LAUNCH_CARRIER_HALF; x++)
        {
            for (int z = -LAUNCH_CARRIER_HALF; z <= LAUNCH_CARRIER_HALF; z++)
            {
                BlockPos deck = new BlockPos(bed.getX() + x, deckY, bed.getZ() + z);
                if (closed)
                {
                    var desired = x == 0 && z == 0
                            && level.getBlockState(deck).is(Blocks.LODESTONE)
                            ? Blocks.LODESTONE.defaultBlockState()
                            : flushTokyo3Door
                            ? Blocks.SMOOTH_STONE.defaultBlockState()
                            : (Math.abs(x) == LAUNCH_CARRIER_HALF
                                    || Math.abs(z) == LAUNCH_CARRIER_HALF)
                            ? Blocks.IRON_BLOCK.defaultBlockState()
                            : Blocks.LIGHT_GRAY_CONCRETE.defaultBlockState();
                    if (!level.getBlockState(deck).equals(desired))
                    {
                        level.setBlock(deck, desired, 2);
                        PerformanceCounters.recordWorldBlockWrites(1);
                    }
                }
                else if (level.getBlockState(deck).is(Blocks.IRON_BLOCK)
                        || level.getBlockState(deck).is(Blocks.LIGHT_GRAY_CONCRETE))
                {
                    level.setBlock(deck, Blocks.AIR.defaultBlockState(), 2);
                    PerformanceCounters.recordWorldBlockWrites(1);
                }
            }
        }
    }

    /** Completes a linked launch; integrated maps keep the same entity and dimension. */
    private boolean completeLinkedSortie()
    {
        if (this.sortieDestinationDimension == null || this.sortieDestinationBed == null
                || !(this.level() instanceof ServerLevel sourceLevel)
                || !this.hasLaunchPassenger())
        {
            return false;
        }
        ServerPlayer pilot = this.getControllingPassenger() instanceof ServerPlayer player
                ? player : null;
        ServerLevel destination = sourceLevel.getServer().getLevel(
                this.sortieDestinationDimension);
        BlockPos destinationBed = this.sortieDestinationBed;
        boolean logicalSurfaceStation = destination != null
                && destination == sourceLevel
                && IntegratedNervMapBuilder.isSurfaceStation(
                        destination, destinationBed);
        if (destination == null
                || !logicalSurfaceStation
                && !destination.getBlockState(destinationBed)
                        .is(Blocks.LODESTONE))
        {
            if (pilot != null)
            {
                pilot.displayClientMessage(Component.literal(
                        "NERV sortie link unavailable; completing launch inside GeoFront."), true);
            }
            ProjectSeele.LOGGER.error(
                    "NERV cross-dimension sortie refused: eva={} dimension={} bed={}",
                    this.getStringUUID(), this.sortieDestinationDimension.location(),
                    destinationBed.toShortString());
            return false;
        }

        if (destination == sourceLevel)
        {
            /*
             * The complete route was checked before motion and every moving
             * carrier layer was checked again during ascent.  At this point
             * the EVA is already above the surface plane; rechecking the
             * entire shaft races the owned Y+1 weather seal as it begins to
             * close and can falsely abort a successful sortie.
             */
            if (this.launchBedPos == null)
            {
                if (pilot != null)
                {
                    pilot.displayClientMessage(Component.literal(
                            "NERV launch origin was lost during surface hand-off."),
                            true);
                }
                ProjectSeele.LOGGER.error(
                    "NERV continuous sortie origin lost: eva={} lower={} upper={}",
                    this.getStringUUID(),
                    "missing",
                    destinationBed.toShortString());
                return false;
            }

            BlockPos lowerBed = this.launchBedPos;
            int rise = destinationBed.getY() - lowerBed.getY();
            float arrivalYaw = this.launchLockedYaw;
            Vec3 arrival = new Vec3(destinationBed.getX() + 0.5D,
                    destinationBed.getY() + 2.0D,
                    destinationBed.getZ() + 0.5D);
            this.setPos(arrival.x, arrival.y, arrival.z);
            this.syncPassengerAssembly();
            this.beginContinuousSurfaceArrival(arrivalYaw);
            if (pilot != null)
            {
                pilot.displayClientMessage(Component.literal(
                        "TOKYO-3 SURFACE CLEAR - physical shaft sortie complete"), true);
            }
            sourceLevel.sendParticles(ParticleTypes.CLOUD,
                    arrival.x, arrival.y, arrival.z,
                    90, 5.0D, 0.8D, 5.0D, 0.14D);
            sourceLevel.sendParticles(ParticleTypes.ELECTRIC_SPARK,
                    arrival.x, arrival.y + 3.0D, arrival.z,
                    48, 4.0D, 4.0D, 4.0D, 0.08D);
            ProjectSeele.LOGGER.info(
                    "NERV continuous sortie complete: eva={} dimension={} lower={} upper={} rise={}",
                    this.getStringUUID(), sourceLevel.dimension().location(),
                    lowerBed.toShortString(), destinationBed.toShortString(), rise);
            return true;
        }

        // The integrated GeoFront/Tokyo-3 map always uses one continuous
        // dimension, so a synthetic training pilot never has to cross a
        // dimension boundary. Keep this legacy transfer path player-only:
        // moving an arbitrary passenger separately would break vehicle UUID
        // ownership and the one-airframe fleet contract.
        if (pilot == null)
        {
            ProjectSeele.LOGGER.error(
                    "NERV legacy cross-dimension sortie requires a human pilot: eva={} destination={}",
                    this.getStringUUID(), destination.dimension().location());
            return false;
        }

        if (!isSortieShaftClear(destination, destinationBed))
        {
            pilot.displayClientMessage(Component.literal(
                    "Legacy destination shaft is obstructed; using the local emergency deck."), true);
            return false;
        }

        destination.getChunkAt(destinationBed);
        Vec3 arrival = new Vec3(destinationBed.getX() + 0.5D,
                destinationBed.getY() + LAUNCH_TARGET_ABOVE_BED,
                destinationBed.getZ() + 0.5D);
        float arrivalYaw = this.launchLockedYaw;
        pilot.stopRiding();
        Entity moved = this.changeDimension(destination,
                directTeleporter(arrival, new Vec3(0.0D, 0.12D, 0.0D),
                        arrivalYaw, 0.0F));
        if (!(moved instanceof EvaUnit01Entity relocated))
        {
            if (!this.isRemoved())
            {
                pilot.startRiding(this, true);
            }
            ProjectSeele.LOGGER.error(
                    "NERV cross-dimension sortie transfer failed: eva={} destination={}",
                    this.getStringUUID(), destination.dimension().location());
            return false;
        }

        relocated.finishTransferredSortie(arrivalYaw);
        setSurfaceCarrierAt(destination, destinationBed,
                destinationBed.getY() + (int) LAUNCH_TARGET_ABOVE_BED - 1, true);
        pilot.teleportTo(destination, arrival.x, arrival.y + 1.0D, arrival.z,
                arrivalYaw, 0.0F);
        if (!pilot.startRiding(relocated, true))
        {
            ProjectSeele.LOGGER.error(
                    "NERV sortie arrived but pilot remount failed: eva={} pilot={}",
                    relocated.getStringUUID(), pilot.getGameProfile().getName());
        }
        pilot.displayClientMessage(Component.literal(
                "TOKYO-3 SURFACE CLEAR — EVA sortie complete"), true);
        destination.sendParticles(ParticleTypes.CLOUD, arrival.x, arrival.y, arrival.z,
                90, 5.0D, 0.8D, 5.0D, 0.14D);
        destination.sendParticles(ParticleTypes.ELECTRIC_SPARK,
                arrival.x, arrival.y + 3.0D, arrival.z,
                48, 4.0D, 4.0D, 4.0D, 0.08D);
        ProjectSeele.LOGGER.info(
                "NERV cross-dimension sortie complete: eva={} source={} destination={} bed={}",
                relocated.getStringUUID(), sourceLevel.dimension().location(),
                destination.dimension().location(), destinationBed.toShortString());
        return true;
    }

    private void finishTransferredSortie(float yaw)
    {
        this.setCarrierRiseProgress(0);
        this.entityData.set(DATA_LAUNCH_PHASE, LAUNCH_IDLE);
        this.entityData.set(DATA_LAUNCH_TICKS, 0);
        // A completed or aborted launch is a hard boundary for the cockpit
        // activation film.  Keeping the old activation counter here let the
        // 100% SYNCHRONIZATION panel survive after the carrier had already
        // released the EVA, even though no activation sequence remained.
        this.entityData.set(DATA_ACTIVATION_TICKS, 0);
        this.launchBedPos = null;
        this.launchCarrierY = NO_LAUNCH_CARRIER;
        this.launchContinuousRoute = false;
        this.launchCommandReleased = false;
        this.launchRecoveryPending = false;
        this.launchPassengerRestoreGraceTicks = 0;
        this.launchLockedYaw = yaw;
        this.clearSortieDestination();
        this.setNoGravity(false);
        this.setDeltaMovement(Vec3.ZERO);
        this.setOnGround(true);
        this.fallDistance = 0.0F;
        this.setRot(yaw, 0.0F);
        this.yRotO = this.yBodyRot = this.yHeadRot = yaw;
    }

    private void beginContinuousSurfaceArrival(float yaw)
    {
        this.entityData.set(DATA_LAUNCH_PHASE, LAUNCH_CLEAR);
        this.entityData.set(DATA_LAUNCH_TICKS, CONTINUOUS_SURFACE_SYNC_TICKS);
        this.entityData.set(DATA_ACTIVATION_TICKS, 0);
        this.launchCarrierY = NO_LAUNCH_CARRIER;
        this.launchRecoveryPending = false;
        this.launchPassengerRestoreGraceTicks = 0;
        this.launchLockedYaw = yaw;
        this.setNoGravity(true);
        this.enforceContinuousSurfaceArrival();
    }

    private void enforceContinuousSurfaceArrival()
    {
        if (this.sortieDestinationBed == null)
        {
            return;
        }
        BlockPos bed = this.sortieDestinationBed;
        this.setPos(bed.getX() + 0.5D, bed.getY() + 2.0D,
                bed.getZ() + 0.5D);
        this.setDeltaMovement(Vec3.ZERO);
        this.setRot(this.launchLockedYaw, 0.0F);
        this.yRotO = this.yBodyRot = this.yHeadRot = this.launchLockedYaw;
        this.fallDistance = 0.0F;
        this.hasImpulse = true;
        this.syncPassengerAssembly();
        if (this.level() instanceof ServerLevel serverLevel
                && this.getLaunchTicks() > 0)
        {
            serverLevel.getChunkSource().broadcastAndSend(this,
                    new ClientboundTeleportEntityPacket(this));
            if (this.getControllingPassenger() instanceof ServerPlayer pilot)
            {
                SeeleNetwork.CHANNEL.send(PacketDistributor.PLAYER.with(() -> pilot),
                        new ClientboundEvaArrivalSyncPacket(this.getId(),
                                this.getX(), this.getY(), this.getZ(),
                                this.launchLockedYaw, 0.0F));
            }
        }
    }

    /**
     * Applies the server's physical shaft-exit position on the locally driven
     * vehicle. The normal teleport packet is ignored for local vehicle
     * authority, which otherwise leaves the pilot visually inside the shaft.
     */
    public void applyClientArrivalSync(double x, double y, double z,
            float yaw, float pitch)
    {
        if (!this.level().isClientSide)
        {
            return;
        }
        this.syncPacketPositionCodec(x, y, z);
        // Clear inherited interpolation before returning local vehicle authority.
        super.lerpTo(x,y,z,yaw,pitch,0,true);
        this.setPos(x, y, z);
        this.xo = x;
        this.yo = y;
        this.zo = z;
        this.setDeltaMovement(Vec3.ZERO);
        this.setRot(yaw, pitch);
        this.yRotO = yaw;
        this.xRotO = pitch;
        this.yBodyRot = yaw;
        this.yBodyRotO = yaw;
        this.yHeadRot = yaw;
        this.yHeadRotO = yaw;
        this.fallDistance = 0.0F;
        this.setOnGround(true);
        this.hasImpulse = true;
        this.clientJumpImpulsePending = false;
        for (Entity passenger : this.getPassengers())
        {
            this.positionRider(passenger, (entity, riderX, riderY, riderZ) ->
            {
                entity.setPos(riderX, riderY, riderZ);
                entity.xo = riderX;
                entity.yo = riderY;
                entity.zo = riderZ;
                entity.setDeltaMovement(Vec3.ZERO);
                entity.fallDistance = 0.0F;
            });
            if (passenger instanceof EntryPlugCarrierEntity plug)
            {
                plug.syncPilotPositionNow();
            }
        }
    }

    private static boolean isSortieShaftClear(ServerLevel level, BlockPos bed)
    {
        for (int y = 1; y <= (int) LAUNCH_TARGET_ABOVE_BED - 1; y++)
        {
            for (int x = -LAUNCH_CARRIER_HALF;
                 x <= LAUNCH_CARRIER_HALF; x++)
            {
                for (int z = -LAUNCH_CARRIER_HALF;
                     z <= LAUNCH_CARRIER_HALF; z++)
                {
                    if (!withinLaunchShaftClearance(x, z))
                    {
                        continue;
                    }
                    if (!level.getBlockState(bed.offset(x, y, z)).isAir())
                    {
                        return false;
                    }
                }
            }
        }
        return true;
    }

    /** Circular carrier-clearance audit between the two station markers. */
    private static boolean isContinuousSortieShaftClear(ServerLevel level,
                                                         BlockPos lowerBed,
                                                         BlockPos upperBed)
    {
        if (lowerBed.getX() != upperBed.getX()
                || lowerBed.getZ() != upperBed.getZ()
                || upperBed.getY() <= lowerBed.getY())
        {
            return false;
        }
        for (int y = lowerBed.getY() + 1; y < upperBed.getY(); y++)
        {
            for (int x = -LAUNCH_CARRIER_HALF;
                 x <= LAUNCH_CARRIER_HALF; x++)
            {
                for (int z = -LAUNCH_CARRIER_HALF;
                     z <= LAUNCH_CARRIER_HALF; z++)
                {
                    if (!withinLaunchShaftClearance(x, z))
                    {
                        continue;
                    }
                    BlockPos position = new BlockPos(lowerBed.getX() + x, y,
                            lowerBed.getZ() + z);
                    if (!isSortieClearance(level, position))
                    {
                        return false;
                    }
                }
            }
        }
        return true;
    }

    private static boolean isContinuousSortieRouteClear(ServerLevel level,
                                                         BlockPos lowerBed,
                                                         BlockPos upperBed)
    {
        return findContinuousSortieObstruction(level, lowerBed, upperBed)
                == null;
    }

    private static String describeContinuousSortieObstruction(
            ServerLevel level, BlockPos lowerBed, BlockPos upperBed)
    {
        BlockPos obstruction = findContinuousSortieObstruction(
                level, lowerBed, upperBed);
        return obstruction == null ? "none"
                : obstruction.toShortString() + "="
                + level.getBlockState(obstruction);
    }

    private static BlockPos findContinuousSortieObstruction(
            ServerLevel level, BlockPos lowerBed, BlockPos upperBed)
    {
        if (lowerBed.getX() != upperBed.getX()
                || lowerBed.getZ() != upperBed.getZ()
                || upperBed.getY() <= lowerBed.getY())
        {
            return lowerBed;
        }
        for (int y = lowerBed.getY() + 1; y < upperBed.getY(); y++)
        {
            for (int x = -LAUNCH_CARRIER_HALF;
                 x <= LAUNCH_CARRIER_HALF; x++)
            {
                for (int z = -LAUNCH_CARRIER_HALF;
                     z <= LAUNCH_CARRIER_HALF; z++)
                {
                    if (!withinLaunchShaftClearance(x, z))
                    {
                        continue;
                    }
                    BlockPos position = new BlockPos(lowerBed.getX() + x, y,
                            lowerBed.getZ() + z);
                    if (!isSortieClearance(level, position))
                    {
                        return position;
                    }
                }
            }
        }
        for (int y = upperBed.getY() + 1;
             y <= upperBed.getY() + CONTINUOUS_EXIT_HEADROOM; y++)
        {
            for (int x = -LAUNCH_CARRIER_HALF;
                 x <= LAUNCH_CARRIER_HALF; x++)
            {
                for (int z = -LAUNCH_CARRIER_HALF;
                     z <= LAUNCH_CARRIER_HALF; z++)
                {
                    if (!withinLaunchShaftClearance(x, z))
                    {
                        continue;
                    }
                    BlockPos position = new BlockPos(upperBed.getX() + x,
                            y, upperBed.getZ() + z);
                    if (!isSortieClearance(level, position))
                    {
                        return position;
                    }
                }
            }
        }
        return null;
    }

    private static boolean withinLaunchShaftClearance(int x, int z)
    {
        return x * x + z * z
                <= LAUNCH_CARRIER_HALF * LAUNCH_CARRIER_HALF;
    }

    private static boolean isSortieClearance(ServerLevel level,
                                              BlockPos position)
    {
        var state = level.getBlockState(position);
        return state.isAir() || state.canBeReplaced();
    }

    private static ITeleporter directTeleporter(Vec3 position, Vec3 velocity,
                                                 float yaw, float pitch)
    {
        return new ITeleporter()
        {
            @Override
            public PortalInfo getPortalInfo(Entity entity, ServerLevel destination,
                                            Function<ServerLevel, PortalInfo> defaultPortalInfo)
            {
                return new PortalInfo(position, velocity, yaw, pitch);
            }
        };
    }

    private void resetLaunchSequence()
    {
        this.endCarrierMotion();
        boolean abandoned = !this.hasLaunchPassenger();
        if (this.getLaunchPhase() == LAUNCH_ASCENT)
        {
            this.clearMovingCarrierBelowSurface();
            if (this.launchBedPos != null)
            {
                this.setPos(this.launchBedPos.getX() + 0.5D, this.launchBedPos.getY() + 1.0D,
                        this.launchBedPos.getZ() + 0.5D);
                this.syncPassengerAssembly();
                this.setSurfaceCarrier(true);
            }
        }
        this.entityData.set(DATA_LAUNCH_PHASE, LAUNCH_IDLE);
        this.entityData.set(DATA_LAUNCH_TICKS, 0);
        // Every completion and abort path converges here.  The cockpit
        // activation film must end with the launch state instead of remaining
        // pinned at its final 100% frame after the carrier releases the EVA.
        this.entityData.set(DATA_ACTIVATION_TICKS, 0);
        this.launchBedPos = null;
        this.launchCarrierY = NO_LAUNCH_CARRIER;
        this.launchContinuousRoute = false;
        this.launchCommandReleased = false;
        this.launchRecoveryPending = false;
        this.launchPassengerRestoreGraceTicks = 0;
        this.launchLockedYaw = this.getYRot();
        if (abandoned)
        {
            // A timed-out passenger restore is a real aborted insertion. Do
            // not leave the seated plug or activation overlay latched forever.
            this.entityData.set(DATA_ENTRY_PLUG_INSERTED, false);
        }
        if (!this.isCrucified())
        {
            this.setNoGravity(false);
        }
    }

    @Override
    public void die(DamageSource source)
    {
        if(!source.is(DamageTypes.GENERIC_KILL)){EvaShutdownR30.fail(this);return;}
        EvaShutdownR30.clear(this);
        // /kill or lethal combat during ascent must not strand a carrier
        // layer inside the shaft or leave the surface aperture open.
        if (this.isLaunchSequenceActive())
        {
            this.resetLaunchSequence();
        }
        super.die(source);
    }

    @Override public boolean isAlive(){return EvaShutdownR30.wreck(this)?!isRemoved():super.isAlive();}
    @Override public boolean isDeadOrDying(){return EvaShutdownR30.wreck(this)?false:super.isDeadOrDying();}
    @Override public void kill()
    {
        if(EvaShutdownR30.wreck(this)){remove(RemovalReason.KILLED);return;}
        super.kill();
    }

    @Override
    public void remove(RemovalReason reason)
    {
        this.clearJumpRequestState();
        if (reason == RemovalReason.DISCARDED && this.isLaunchSequenceActive())
        {
            this.resetLaunchSequence();
        }
        super.remove(reason);
    }

    /**
     * The EVA A.T. Field: while raised it nullifies ordinary damage outright;
     * Angel attacks tear chunks out of the field energy instead, spilling
     * into hull damage only once the pool runs dry.
     */
    @Override
    public boolean hurt(DamageSource source, float amount)
    {
        if(this.isBerserk()&&!source.is(DamageTypeTags.BYPASSES_INVULNERABILITY))return false;
        if(EvaShutdownR30.wreck(this)&&source.is(DamageTypes.GENERIC_KILL)){remove(RemovalReason.KILLED);return true;}
        if(EvaShutdownR30.wreck(this)&&!source.is(DamageTypes.GENERIC_KILL))return false;
        if(this.isFirstBattleActive()&&!source.is(DamageTypeTags.BYPASSES_INVULNERABILITY))return false;
        if (source.is(DamageTypeTags.IS_FALL))
        {
            return false;
        }
        if ((this.isNervLogisticsLocked() || this.isLaunchSequenceActive())
                && source.is(DamageTypes.IN_WALL))
        {
            return false;
        }
        if (source.is(DamageTypeTags.BYPASSES_INVULNERABILITY))
        {
            return this.applyHullDamage(source, amount);
        }
        if (AtFieldRules.bypassesAtField(source))
        {
            return this.applyHullDamage(source, amount);
        }
        if (this.isAtFieldOn() && amount > 0.0F)
        {
            this.atRegenDelay = AT_FIELD_REGEN_DELAY;
            boolean evaMelee = source.getEntity() instanceof EvaUnit01Entity attacker
                    && attacker.isMeleeWeapon() && !source.is(DamageTypeTags.IS_EXPLOSION);
            if (source.getEntity() instanceof Angel || evaMelee)
            {
                float energy = this.getAtFieldEnergy();
                // Unit-00 can physically interpose itself in Ramiel's ray.
                // Kneeling behind the shield doubles its already superior
                // field efficiency, making the Yashima cover role practical.
                float costMultiplier = this.getUnitVariant() == UNIT_00
                        ? (this.isShieldBraced() ? 0.30F : 0.60F) : 1.0F;
                float fieldCost = amount * costMultiplier;
                float absorbed = Math.min(energy, fieldCost);
                this.entityData.set(DATA_AT_ENERGY, energy - absorbed);
                this.rippleAt(source);
                float leftover = (fieldCost - absorbed) / costMultiplier;
                return leftover > 0.0F && this.applyHullDamage(source, leftover);
            }
            // Conventional weapons cannot even scratch the field.
            this.rippleAt(source);
            return false;
        }
        return this.applyHullDamage(source, amount);
    }

    private boolean applyHullDamage(DamageSource source, float amount)
    {
        float healthBefore = this.getHealth();
        if(canArmBerserkR37()&&!source.is(DamageTypeTags.BYPASSES_INVULNERABILITY))amount=Math.min(amount,Math.max(0,healthBefore-1));
        boolean accepted = super.hurt(source, amount);
        if(accepted&&canEnterBerserk())this.beginBerserk();
        float actualHullDamage = Math.max(0.0F, healthBefore - this.getHealth());
        if (accepted && actualHullDamage > 0.0F && !this.isNervLogisticsLocked()
                && this.isUmbilicalConnected())
        {
            this.severUmbilicalFromDamage();
        }
        // Hull damage affects the airframe. Synchronization no longer copies
        // that damage into the protected cockpit occupant's vanilla health.
        return accepted;
    }

    private void severUmbilicalFromDamage()
    {
        this.entityData.set(DATA_UMBILICAL_SEVERED, true);
        this.setUmbilicalAnchor(null);
        if (this.getControllingPassenger() instanceof ServerPlayer pilot)
        {
            pilot.displayClientMessage(Component.translatable(
                    "msg.projectseele.power_cable_severed"), true);
        }
        this.playSound(SoundEvents.LIGHTNING_BOLT_IMPACT, 2.8F, 1.35F);
        if (this.level() instanceof ServerLevel server)
        {
            Vec3 cableSocket = this.getUmbilicalSocketPosition();
            server.sendParticles(ParticleTypes.ELECTRIC_SPARK,
                    cableSocket.x, cableSocket.y, cableSocket.z, 28,
                    1.2D, 1.4D, 1.2D, 0.16D);
        }
    }

    private void rippleAt(DamageSource source)
    {
        if (!(this.level() instanceof ServerLevel serverLevel))
        {
            return;
        }
        Vec3 origin = source.getSourcePosition();
        Vec3 center = this.position().add(0.0D, this.getBbHeight() * 0.55D, 0.0D);
        Vec3 dir = origin != null && origin.distanceToSqr(center) > 1.0E-4D
                ? origin.subtract(center).normalize()
                : this.getForward();
        AtFieldFX.ripple(serverLevel,center.add(dir.scale(Math.max(8.0D,this.getBbWidth()))),dir,Math.max(10.5F,this.getBbHeight()*.55F));
    }

    // ----- piloting -----

    @Override
    public InteractionResult mobInteract(Player player, InteractionHand hand)
    {
        if (!this.isVehicle() && !player.isSecondaryUseActive())
        {
            return this.level().isClientSide
                    ? InteractionResult.SUCCESS : this.tryEnterFromPlug(player, false);
        }
        return super.mobInteract(player, hand);
    }

    /**
     * Server-authoritative boarding entry used by the extended plug ray.
     * Vanilla entity interaction has already performed a hit test and calls
     * the overload that skips only the redundant narrow aim-cone check.
     */
    public InteractionResult tryEnterFromPlug(Player player)
    {
        return this.tryEnterFromPlug(player, true);
    }

    /** Command helpers may skip only the look cone after placing the pilot on an audited gantry. */
    public InteractionResult tryEnterFromPlug(Player player, boolean requireAim)
    {
        if(!this.level().isClientSide&&com.projectseele.visual.StanceContactR41Review.shutdownEntryTraceAllowedR45(player,this))com.projectseele.visual.StanceContactR41Review.shutdownEntryTraceR45(player,this,"server_try_enter_begin",requireAim,this.hasClearEntryPlugPath(player));
        if (this.level().isClientSide)
        {
            return InteractionResult.SUCCESS;
        }
        if (this.isVehicle() || player.isPassenger())
        {
            return InteractionResult.FAIL;
        }
        if (this.isNervLogisticsLocked())
        {
            // A canonical wet-cage EVA may only receive its pilot through the
            // suspended physical capsule. Allowing the compatibility socket
            // here skipped black standby, LCL fill and the visible insertion.
            player.displayClientMessage(Component.translatable(
                    "message.projectseele.board_external_entry_plug"), true);
            return InteractionResult.CONSUME;
        }
        if (this.isLaunchSequenceActive())
        {
            player.displayClientMessage(
                    Component.translatable("message.projectseele.launch_interlock"), true);
            return InteractionResult.CONSUME;
        }
        if (this.isBerserk() || this.berserkRecoveryTicks > 0)
        {
            player.displayClientMessage(Component.translatable(
                    this.isBerserk() ? "msg.projectseele.berserk_active"
                            : "msg.projectseele.berserk_recovery",
                    Math.max(0, (this.isBerserk() ? this.getBerserkTicks() : this.berserkRecoveryTicks) / 20)), true);
            return InteractionResult.CONSUME;
        }

        BlockPos launchBed = this.findLaunchBed();
        if (launchBed != null)
        {
            if (this.launchBedClaimedByAnother(launchBed))
            {
                player.displayClientMessage(
                        Component.translatable("message.projectseele.launch_bed_occupied"), true);
                return InteractionResult.CONSUME;
            }
        }

        // Everything below through line-of-sight is evaluated against the
        // transform the player can currently see. A rejected interaction must
        // never snap or rotate an EVA as a side effect.
        double relativeHeight = player.getY() - this.getY();
        Vec3 horizontal = new Vec3(player.getX() - this.getX(), 0.0D,
                player.getZ() - this.getZ());
        double distance = horizontal.length();
        Vec3 rear = this.getForward().multiply(-1.0D, 0.0D, -1.0D).normalize();
        double rearDot = distance > 1.0E-4D
                ? horizontal.scale(1.0D / distance).dot(rear) : -1.0D;
        if (relativeHeight < SILO_ENTRY_MIN_HEIGHT || relativeHeight > SILO_ENTRY_MAX_HEIGHT
                || distance < SILO_ENTRY_MIN_DISTANCE || distance > SILO_ENTRY_MAX_DISTANCE
                || rearDot < SILO_ENTRY_MIN_REAR_DOT)
        {
            player.displayClientMessage(
                    Component.translatable("message.projectseele.use_entry_gantry"), true);
            return InteractionResult.CONSUME;
        }
        if ((requireAim && !this.isEntryPlugTargeted(player)) || !this.hasClearEntryPlugPath(player))
        {
            player.displayClientMessage(
                    Component.translatable("message.projectseele.aim_entry_plug"), true);
            return InteractionResult.CONSUME;
        }

        if (launchBed != null)
        {
            // Authorization succeeded. Only now may the launch fixture pull a
            // slightly displaced caged airframe onto its audited bed/yaw.
            this.alignForSiloBoarding(launchBed);
        }
        this.entityData.set(DATA_ACTIVATION_TICKS, 120);
        this.entityData.set(DATA_ENTRY_PLUG_INSERTED, true);
        if (!player.startRiding(this, true))
        {
            this.entityData.set(DATA_ACTIVATION_TICKS, 0);
            this.entityData.set(DATA_ENTRY_PLUG_INSERTED, false);
            return InteractionResult.FAIL;
        }
        com.projectseele.visual.StanceContactR41Review.shutdownEntryTraceR45(player,this,"server_actual_start_riding_accepted",requireAim,null);
        if (EvaShutdownR30.mode(this) == EvaShutdownR30.EMPTY
                && !com.projectseele.physics.CombatBodyDynamics.active(this))
        {
            EvaShutdownR30.clear(this);
        }
        if (launchBed != null)
        {
            this.armLaunchBed(launchBed);
            player.displayClientMessage(Component.translatable("message.projectseele.launch_locked"), true);
        }
        return InteractionResult.CONSUME;
    }

    /** Installs the visible automated pilot through the same entry-plug state. */
    public boolean boardTrainingPilot(TrainingPilotEntity pilot)
    {
        if (this.level().isClientSide || this.isVehicle()
                || pilot.isPassenger() || this.isLaunchSequenceActive())
        {
            return false;
        }
        this.entityData.set(DATA_ACTIVATION_TICKS, 120);
        this.entityData.set(DATA_ENTRY_PLUG_INSERTED, true);
        if (!pilot.startRiding(this, true))
        {
            this.entityData.set(DATA_ACTIVATION_TICKS, 0);
            this.entityData.set(DATA_ENTRY_PLUG_INSERTED, false);
            return false;
        }
        return true;
    }

    public boolean boardFromExternalPlug(Entity passenger)
    {
        return this.boardFromExternalPlug(passenger,
                EntryPlugCarrierEntity.CABIN_TRANSFER_PERCENT);
    }

    /**
     * Transfers the pilot without restarting the cockpit sequence. The
     * external capsule owns dark/LCL/A10 progress up to the dorsal socket; the
     * airframe continues from that exact percentage while its optical feed
     * clears.
     */
    public boolean boardFromExternalPlug(Entity passenger,
                                         int completedPercent)
    {
        if (EvaBayRepairR33.active(this) || EvaShutdownR30.wreck(this) || this.level().isClientSide || this.isVehicle()
                || passenger.isPassenger() || this.isLaunchSequenceActive()
                || !(passenger instanceof Player
                    || passenger instanceof TrainingPilotEntity))
        {
            return false;
        }
        int safeProgress = Mth.clamp(completedPercent, 0, 100);
        int remainingTicks = Mth.clamp(
                Mth.ceil(120.0F * (100 - safeProgress) / 100.0F), 1, 120);
        this.entityData.set(DATA_ACTIVATION_TICKS, remainingTicks);
        this.entityData.set(DATA_ENTRY_PLUG_INSERTED, true);
        if (!passenger.startRiding(this, true))
        {
            this.entityData.set(DATA_ACTIVATION_TICKS, 0);
            this.entityData.set(DATA_ENTRY_PLUG_INSERTED, false);
            return false;
        }
        if (EvaShutdownR30.mode(this) == EvaShutdownR30.EMPTY)
        {
            EvaShutdownR30.clear(this);
        }
        return true;
    }

    public boolean isTrainingPilotActive()
    {
        return this.getPilotEntity() instanceof TrainingPilotEntity;
    }

    private void alignForSiloBoarding(BlockPos bed)
    {
        this.setPos(bed.getX() + 0.5D, bed.getY() + 1.0D, bed.getZ() + 0.5D);
        this.setDeltaMovement(Vec3.ZERO);
        this.setRot(SILO_BAY_YAW, 0.0F);
        this.yRotO = this.yBodyRot = this.yHeadRot = SILO_BAY_YAW;
        this.fallDistance = 0.0F;
    }

    private boolean hasClearEntryPlugPath(Player player)
    {
        Vec3 eye = player.getEyePosition();
        Vec3 socket = this.getEntryPlugSocketPosition();
        BlockHitResult hit = this.level().clip(new ClipContext(
                eye, socket, ClipContext.Block.COLLIDER, ClipContext.Fluid.NONE, player));
        return hit.getType() == net.minecraft.world.phys.HitResult.Type.MISS
                || hit.getLocation().distanceToSqr(socket)
                        <= EvaScale.fromLegacy(0.75D)
                        * EvaScale.fromLegacy(0.75D);
    }

    @Nullable
    @Override
    public LivingEntity getControllingPassenger()
    {
        LivingEntity pilot = this.getPilotEntity();
        return pilot != null ? pilot : super.getControllingPassenger();
    }

    /**
     * Carrier rails and launch machinery own the chassis transform while their
     * locks are active. Leaving local vehicle authority enabled made the pilot
     * send a competing move packet for every rendered frame; the server then
     * rejected and logged tens of thousands of "moved wrongly" packets during
     * one sortie. Remote entity tracking still keeps the pilot's client on the
     * server-authored carrier path.
     */
    @Override
    public boolean isControlledByLocalInstance()
    {
        if(EvaSwordActionsR45.active(this)||EvaFieldActionsR45.active(this))return !this.level().isClientSide;
        if(this.isBerserk()||com.projectseele.physics.CombatBodyDynamics.active(this)||com.projectseele.physics.CombatBodyDynamics.ownsGroundAction(this))return !this.level().isClientSide;
        if(!this.level().isClientSide&&!this.isNervLogisticsLocked()&&!this.isLaunchSequenceActive()&&!this.isFirstBattleActive()
                &&(this.getPilotEntity() instanceof TrainingPilotEntity||EvaShutdownR30.displayed(this)&&this.getPilotEntity()==null))return true;
        return !this.isFirstBattleActive() && !this.isNervLogisticsLocked()
                && !this.isLaunchSequenceActive()
                && super.isControlledByLocalInstance();
    }

    @Override
    protected void tickRidden(Player player, Vec3 input)
    {
        if(this.level().isClientSide&&com.projectseele.physics.CombatBodyDynamics.ownsGroundAction(this))return;
        if (!this.level().isClientSide)
        {
            float aimPitch = !this.isCrucified()
                    && !this.isPilotControlLocked()
                    && (this.getWeapon() == WEAPON_CANNON || this.getWeapon() == WEAPON_RIFLE)
                    ? this.clampPilotWeaponPitch(player.getXRot(),1)
                    : 0.0F;
            if (Math.abs(this.getCannonAimPitch() - aimPitch) > 0.01F)
            {
                this.entityData.set(DATA_CANNON_AIM_PITCH, aimPitch);
            }
        }
        if (this.isCrucified() || this.isPilotControlLocked())
        {
            // Activation interlocks, launch rails and ritual restraints all
            // own the chassis transform. Pilot view input must not rotate it.
            this.setDeltaMovement(EvaShutdownR30.displayed(this)||this.isBerserk()?new Vec3(0,this.getDeltaMovement().y,0):Vec3.ZERO);
            return;
        }
        float previousBodyYaw = this.getYRot();
        super.tickRidden(player, input);
        boolean moving = Math.abs(input.x) + Math.abs(input.z) > 0.01D;
        float deadZone = moving ? PILOT_BODY_MOVING_DEAD_ZONE
                : PILOT_BODY_IDLE_DEAD_ZONE;
        boolean longHull=this.rifleStanceInitialized && this.entityData.get(DATA_RIFLE_STANCE)>1.05F;
        if(longHull)deadZone=0;
        float maxTurn = moving ? PILOT_BODY_MOVING_TURN_PER_TICK
                : PILOT_BODY_IDLE_TURN_PER_TICK;
        if(EvaGameplayMotionR32.directed(this)&&EvaCombatSupportR33.strike(this))
        {
            float phase=isHeavyMotionActive()?heavyMotionProgress(0):getOrdinaryAttackProgress(0);
            maxTurn=Math.min(maxTurn,phase<.30F?4:phase<.68F?1.5F:6);
        }
        float delta = Mth.wrapDegrees(player.getYRot() - previousBodyYaw);
        float remaining = Math.max(0.0F, Math.abs(delta) - deadZone);
        float turn = Math.copySign(Math.min(remaining, maxTurn), delta);
        float bodyYaw = previousBodyYaw + turn;
        if(longHull)
        {
            // A long capsule can translate through a passage yet cannot rotate
            // through its side wall. Keep mouse look free and limit only the hull.
            if(!hasHullTurningRoom(bodyYaw))
            {
                float low=0,high=1;
                for(int i=0;i<9;i++)
                {
                    float mid=(low+high)*.5F;
                    if(hasHullTurningRoom(previousBodyYaw+turn*mid))low=mid;else high=mid;
                }
                bodyYaw=previousBodyYaw+turn*low;
            }
        }
        // Preserve the previous tick for render interpolation. Assigning both
        // values to the camera yaw made the sixty-block chassis teleport under
        // the pilot whenever the mouse moved.
        if(EvaCombatR31.locksFacing(this))bodyYaw=Mth.approachDegrees(previousBodyYaw,EvaCombatR31.facing(this),6);
        this.setRot(bodyYaw, 0.0F);
        if(longHull)this.setBoundingBox(stanceBounds(bodyYaw));
        this.yRotO = previousBodyYaw;
        this.yBodyRotO = previousBodyYaw;
        this.yHeadRotO = previousBodyYaw;
        this.yBodyRot = bodyYaw;
        this.yHeadRot = bodyYaw;
        // The player renderer is cancelled client-side while mounted. Do not
        // leave the pilot invisibility flag set after an older cockpit pass.
        if (player.isInvisible())
        {
            player.setInvisible(false);
        }
    }

    @Override
    protected void addPassenger(Entity passenger)
    {
        passengerAuthorityTraceR44(passenger,"before_add_passenger");
        super.addPassenger(passenger);
        passengerAuthorityTraceR44(passenger,"after_add_passenger");
    }

    @Override
    protected void removePassenger(Entity passenger)
    {
        passengerAuthorityTraceR44(passenger,"before_remove_passenger");
        super.removePassenger(passenger);
        passengerAuthorityTraceR44(passenger,"after_vanilla_remove_passenger");
        // Vanilla rebuilds the client passenger list by removing and then
        // re-adding even an unchanged passenger. This is not a server ejection.
        // Clearing unchanged synced fields here leaves them false indefinitely
        // because the server has no new metadata value to transmit.
        if(this.level().isClientSide&&!com.projectseele.client.visual.RuntimeR44ClientProbe.passengerCleanupBefore(this))
        {
            passengerAuthorityTraceR44(passenger,"after_client_graph_only");return;
        }
        if (passenger instanceof EntryPlugCarrierEntity plug)
        {
            this.clearEntryPlugLink(plug);
        }
        if (passenger instanceof ServerPlayer leavingPilot)
        {
            leavingPilot.setInvisible(false);
        }
        this.clearJumpRequestState();
        this.meleeInputBufferTicks = 0;
        this.cancelOrdinaryGroupCAttack();
        this.cancelSideKick();
        this.chargingHeld = false;
        this.entityData.set(DATA_CANNON_CHARGE, 0);
        this.entityData.set(DATA_N2_ARM_TICKS, 0);
        this.entityData.set(DATA_CANNON_AIM_PITCH, 0.0F);
        this.entityData.set(DATA_ACTIVATION_TICKS, 0);
        this.entityData.set(DATA_ENTRY_PLUG_INSERTED, false);
        if (this.isLaunchSequenceActive())
        {
            this.resetLaunchSequence();
        }
        this.clearPilotMotion();
        passengerAuthorityTraceR44(passenger,"after_authoritative_remove_cleanup");
    }

    private void passengerAuthorityTraceR44(Entity passenger,String stage)
    {
        if(!com.projectseele.visual.PassengerAuthorityWitnessR44.enabled())return;
        var fields=EvaGameplayMotionR32.ownerDiagnosticR44(this,0);
        fields.addProperty("locked_plug_uuid",this.lockedEntryPlugUuid==null?"":this.lockedEntryPlugUuid.toString());
        fields.addProperty("link_fault_logged",this.entryPlugLinkFaultLogged);fields.addProperty("launch_phase",this.getLaunchPhase());
        fields.addProperty("cannon_charge",this.entityData.get(DATA_CANNON_CHARGE));fields.addProperty("n2_arm_ticks",this.entityData.get(DATA_N2_ARM_TICKS));
        fields.addProperty("cannon_aim_pitch",this.entityData.get(DATA_CANNON_AIM_PITCH));fields.addProperty("ordinary_stage",this.getOrdinaryAttackStage());
        fields.addProperty("heavy_active",this.isHeavyMotionActive());fields.addProperty("kick_active",this.isKickMotionActive(0));
        fields.addProperty("client_explicit_jump",this.clientExplicitJumpInProgress);fields.addProperty("client_jump_pending",this.clientJumpImpulsePending);
        com.projectseele.visual.PassengerAuthorityWitnessR44.capture(this,passenger,stage,fields);
    }

    private void setPilotMovementState(boolean crouching, boolean sprinting)
    {
        this.entityData.set(DATA_CROUCHING, crouching);
        this.entityData.set(DATA_SPRINTING, sprinting);
        this.entityData.set(DATA_PRONE, false);
        this.updatePoseDimensions();
    }

    /** Stop input-driven motion without making a prone Unit pop upright. */
    private void clearPilotMotion()
    {
        this.cancelLiveActionsForStanceChange();
        this.entityData.set(DATA_CROUCHING, false);
        this.entityData.set(DATA_SPRINTING, false);
        this.updatePoseDimensions();
    }

    private void clearJumpRequestState()
    {
        this.jumpBufferTicks = 0;
        this.groundedGraceTicks = 0;
        this.lastJumpRequestId = Integer.MIN_VALUE;
        this.clientJumpImpulsePending = false;
        this.explicitJumpInProgress = false;
        this.explicitJumpObservedAirborne = false;
        this.explicitJumpAuthorizationTicks = 0;
        this.serverAirborneTicks = 0;
        this.clientExplicitJumpInProgress = false;
        this.clientExplicitJumpObservedAirborne = false;
        this.clientExplicitJumpAuthorizationTicks = 0;
        this.clientVisualAirborne = false;
        this.clientVisualAscending = false;
        this.clientVisualAirTicks = 0;
    }

    private void updatePoseDimensions()
    {
        boolean crouching = this.isPilotCrouching();
        boolean prone = this.isPilotProne();
        if (this.crouchingDimensions != crouching || this.proneDimensions != prone)
        {
            this.crouchingDimensions = crouching;
            this.proneDimensions = prone;
            this.refreshDimensions();
        }
        else if(this.rifleStanceInitialized&&this.isExperimentalUnit()&&Math.abs(this.getDimensions(this.getPose()).width-this.getBbWidth())>.001F)
        {
            this.refreshDimensions();
        }
    }

    @Override
    public boolean isImmobile()
    {
        return super.isImmobile() || this.isCrucified() || (!this.isBerserk() && this.isPilotControlLocked());
    }

    @Override
    public boolean isPushable()
    {
        // A sixty-block airframe is not a vanilla shoulder-to-shoulder mob.
        // Allowing ordinary entity push made an on-foot player impart a tiny
        // displacement; PathfinderMob then turned the complete render body to
        // face that collision vector. EVA movement remains authoritative via
        // pilot input, berserk AI, carrier rails and launch machinery.
        return false;
    }

    @Override
    public void lerpMotion(double x, double y, double z)
    {
        // The rider simulates a sequence-authorized jump. The server's living-
        // vehicle velocity is zeroed by vanilla, and motion packets also clamp
        // speeds to 3.9; applying either midway through flight truncates jumps.
        if (this.level().isClientSide && this.isControlledByLocalInstance()
                && !this.isPilotControlLocked()
                && (this.clientJumpImpulsePending || this.clientExplicitJumpInProgress))
        {
            return;
        }
        super.lerpMotion(x, y, z);
    }

    @Override
    public void travel(Vec3 input)
    {
        if(CombatFeelR31.travel(this))return;
        if(EvaCombatR31.locksInput(this))input=Vec3.ZERO;
        if(!this.level().isClientSide&&this.getPilotEntity() instanceof TrainingPilotEntity
                &&com.projectseele.world.NervPilotCombatR30.controls(this)&&this.autonomousInputAtR30!=Long.MIN_VALUE&&this.level().getGameTime()-this.autonomousInputAtR30<=2)
        {
            // Mob MoveControl's WAIT state clears zza after the controller's
            // server-start tick. Apply the owned intent at the physics boundary.
            input=this.hasLiveActionForRender(0)&&!EvaGameplayMotionR32.movementMayComposeR45(this)?Vec3.ZERO:this.autonomousInputR30;this.setSpeed(this.drivingSpeedR30());
        }
        if(EvaShutdownR30.displayed(this))
        {
            var resting=EvaShutdownR30.restBounds(this);
            if(resting!=null&&this.getDeltaMovement().lengthSqr()<.01)
            {
                var sole=new AABB(resting.minX+.05,resting.minY-.15,resting.minZ+.05,resting.maxX-.05,resting.minY+.01,resting.maxZ-.05);
                if(this.level().getBlockCollisions(this,sole).iterator().hasNext()){this.setDeltaMovement(Vec3.ZERO);this.setOnGround(true);return;}
            }
            // Frozen joints are not an antigravity lock. Only the movement
            // authority integrates the disabled hull, using native collisions.
            if(this.isControlledByLocalInstance())
            {
                Vec3 velocity=this.getDeltaMovement();this.move(MoverType.SELF,velocity);
                double gravity=this.isNoGravity()?0:this.getAttributeValue(net.minecraftforge.common.ForgeMod.ENTITY_GRAVITY.get());
                this.setDeltaMovement(this.onGround()?Vec3.ZERO:new Vec3(velocity.x*.91,(this.verticalCollision?0:velocity.y-gravity)*.98,velocity.z*.91));
                this.resetFallDistance();
            }
            return;
        }
        if (this.isCrucified() || (!this.isBerserk() && this.isPilotControlLocked()))
        {
            this.setDeltaMovement(Vec3.ZERO);
            return;
        }
        super.travel(input);
        EvaCombatR31.approach(this);
        if (this.level().isClientSide)
        {
            if (this.isControlledByLocalInstance())
            {
                // Ridden vehicles report their local position to the server.
                // Predict only the server-authorized action phase, otherwise
                // vanilla reports a stationary vehicle over the server root.
                this.predictAuthoritativeActionRoot();
            }
            else
            {
                this.clientRootFamily = -1;
            }
        }
        // LivingEntity calls this only after it has selected the local pilot
        // as vehicle authority. Applying the synchronized impulse here avoids
        // both the pre-travel friction pass and the non-authoritative branch
        // that zeros remote ridden entities.
        if (this.level().isClientSide && this.clientJumpImpulsePending
                && this.isControlledByLocalInstance())
        {
            Vec3 motion = this.getDeltaMovement();
            this.setDeltaMovement(motion.x, JUMP_VELOCITY, motion.z);
            this.hasImpulse = true;
            this.clientJumpImpulsePending = false;
            if (this.getVisualPose() == VISUAL_LIVE_JUMP)
            {
                ProjectSeele.LOGGER.info(
                        "Visual live jump client travel impulse applied velocityY={} localAuthority={}",
                        this.getDeltaMovement().y, this.isControlledByLocalInstance());
            }
        }
    }

    @Override
    protected Vec3 getRiddenInput(Player player, Vec3 input)
    {
        if(this.isBerserk()){this.pilotMovementRequested=false;return Vec3.ZERO;}
        if(com.projectseele.physics.CombatBodyDynamics.active(this)){this.pilotMovementRequested=false;return Vec3.ZERO;}
        if(CombatFeelR31.restrained(this)||EvaCombatR31.locksInput(this))return Vec3.ZERO;
        if(EvaShutdownR30.disabled(this)){this.pilotMovementRequested=false;return Vec3.ZERO;}
        if (this.getActivationTicks() > 20 || this.isLaunchSequenceActive())
        {
            this.pilotMovementRequested = false;
            return Vec3.ZERO;
        }
        this.pilotMovementRequested = Math.abs(player.xxa) > 0.01F
                || Math.abs(player.zza) > 0.01F;
        if (this.hasLiveActionForRender(0.0F)&&!EvaGameplayMotionR32.movementMayComposeR45(this))
        {
            // Captured planted feet travel with the authoritative action root.
            // Held movement resumes when the action finishes; it is not added
            // on top of the capture as a second, sliding trajectory.
            return Vec3.ZERO;
        }
        double strafe = this.isPilotProne() ? 0.28D
                : this.isPilotCrouching() ? 0.45D : 0.7D;
        return new Vec3(player.xxa * strafe, 0.0D,
                player.zza >= 0.0F ? player.zza : player.zza * 0.6D);
    }

    @Override
    protected float getRiddenSpeed(Player player)
    {return drivingSpeedR30();}
    private float drivingSpeedR30()
    {
        if (this.getActivationTicks() > 20 || this.isLaunchSequenceActive())
        {
            return 0.0F;
        }
        // Sniper stance: charging the cannon roots the Unit.
        if (this.getCannonCharge() > 0 || this.getN2ArmTicks() > 0)
        {
            return 0.02F;
        }
        float synchronizationSpeed = EvaPilotCapability.mobilityMultiplier(
                this.getPilotSynchronization());
        float variantSpeed = switch (this.getUnitVariant())
        {
            case UNIT_00 -> this.isPilotSprinting() ? 0.65F : 0.36F;
            case UNIT_02 -> this.isPilotSprinting() ? 0.90F : 0.48F;
            default -> this.isPilotSprinting() ? SPRINT_SPEED : WALK_SPEED;
        };
        float stance=this.rifleStanceInitialized?this.entityData.get(DATA_RIFLE_STANCE):this.isPilotProne()?3:this.isPilotCrouching()?1:0;
        float speed=stance<=1?Mth.lerp(stance,variantSpeed,CROUCH_SPEED):Mth.lerp(Mth.clamp((stance-1)/2,0,1),CROUCH_SPEED,PRONE_SPEED);
        return speed * synchronizationSpeed;
    }

    @Override
    public EntityDimensions getDimensions(Pose pose)
    {
        EntityDimensions dimensions = super.getDimensions(pose);
        float width=bodyCollisionWidthR30();
        if(this.rifleStanceInitialized&&this.getVisualPose()==VISUAL_NORMAL&&!this.isFirstBattleActive())
        {
            float stance=this.entityData.get(DATA_RIFLE_STANCE);
            float low=Mth.clamp((stance-1)/2,0,1);
            float height=stance<=1?Mth.lerp(stance,NORMAL_HEIGHT,CROUCH_HEIGHT):Mth.lerp(low,CROUCH_HEIGHT,PRONE_HEIGHT);
            return EntityDimensions.scalable(Mth.lerp(low,width,Math.max(28F,width)),height);
        }
        if (this.proneDimensions)
        {
            return EntityDimensions.scalable(PRONE_WIDTH, PRONE_HEIGHT);
        }
        return this.crouchingDimensions ? EntityDimensions.scalable(width, CROUCH_HEIGHT) : width>NORMAL_WIDTH?EntityDimensions.scalable(width,dimensions.height):dimensions;
    }
    private float bodyCollisionWidthR30()
    {
        return this.rifleStanceInitialized&&this instanceof EvaPrototypeEntity un&&EvaBodyPose.hasOwnUnRig(this)?un.getUNSerial()==1?28F:22F:NORMAL_WIDTH;
    }

    @Override
    protected AABB makeBoundingBox()
    {
        AABB physical=com.projectseele.physics.CombatBodyDynamics.bounds(this);if(physical!=null)return physical;
        AABB resting=EvaShutdownR30.restBounds(this);if(resting!=null)return resting;
        return stanceBounds(this.getYRot());
    }

    @Override
    public void updateFluidHeightAndDoFluidPushing(java.util.function.Predicate<net.minecraft.world.level.material.FluidState> predicate)
    {
        if(this.isNervLogisticsLocked()||this.isLaunchSequenceActive()||this.hasActiveCarrierMotion()||this.isFirstBattleActive())
        {
            // Rails and restraints own this transform. Vanilla's human-scale
            // fluid scan traversed every voxel of three 60-metre wet airframes
            // each tick even though its current impulse was immediately erased.
            this.forgeFluidTypeHeight.clear();this.fluidHeight.clear();return;
        }
        super.updateFluidHeightAndDoFluidPushing(predicate);
    }

    private AABB stanceBounds(float bodyYaw)
    {
        AABB normal=super.makeBoundingBox();
        if(!this.rifleStanceInitialized||this.getVisualPose()!=VISUAL_NORMAL||this.isFirstBattleActive()||this.isNervLogisticsLocked()||this.isLaunchSequenceActive())return normal;
        float low=Mth.clamp((this.entityData.get(DATA_RIFLE_STANCE)-1)/2,0,1);
        if(low<=.001F)return normal;
        // Actual terminal stance spans about 26 x 60 blocks. A square 48-block
        // footprint blocked walls beside the body and did not describe its length.
        float width=bodyCollisionWidthR30();double halfWidth=Mth.lerp(low,width,Math.max(28F,width))/2D,halfLength=Mth.lerp(low,width,62)/2D;
        double yaw=Math.toRadians(bodyYaw),c=Math.abs(Math.cos(yaw)),s=Math.abs(Math.sin(yaw));
        double x=c*halfWidth+s*halfLength,z=s*halfWidth+c*halfLength;
        return new AABB(this.getX()-x,normal.minY,this.getZ()-z,this.getX()+x,normal.maxY,this.getZ()+z);
    }

    private boolean hasHullTurningRoom(float yaw)
    {
        AABB b=stanceBounds(yaw);
        // Leave lateral clearance for the next movement tick. Deflating the
        // sides admitted a thin wall overlap and vanilla then blocked sliding.
        return this.level().noCollision(this,new AABB(b.minX-.08,b.minY+.02,b.minZ-.08,b.maxX+.08,b.maxY-.02,b.maxZ+.08));
    }

    @Override
    public void onSyncedDataUpdated(EntityDataAccessor<?> key)
    {
        super.onSyncedDataUpdated(key);
        if(this.level().isClientSide&&key==DATA_RIFLE_SIGHT_R45&&rifleSightClockR45!=null)
            rifleSightClockR45.accept(this.entityData.get(DATA_RIFLE_SIGHT_R45),false,false);
        if(this.level().isClientSide&&(key==DATA_TV_PERSONNEL_CLOCK_HELD_R44||key==DATA_TV_PERSONNEL_FROZEN_R44))this.clientCarrierFramePendingR35=true;
        if(this.tickCount>0&&EvaShutdownR30.updatesBounds(key))this.refreshDimensions();
        if(this.level().isClientSide&&this.entityData.get(DATA_CARRIER_MOTION_START)!=0
                &&(key==DATA_CARRIER_MOTION_ACTIVE||key==DATA_CARRIER_MOTION_START||key==DATA_CARRIER_FROM_X||key==DATA_CARRIER_FROM_Y||key==DATA_CARRIER_FROM_Z||key==DATA_CARRIER_TO_X||key==DATA_CARRIER_TO_Y||key==DATA_CARRIER_TO_Z))this.clientCarrierFramePendingR35=true;
        if(DATA_RIFLE_STANCE.equals(key)&&rifleSignalTicks!=null)
        {
            this.rifleStanceInitialized=true;this.refreshDimensions();
        }
        if(this.level().isClientSide&&rifleSignalTicks!=null)
        {
            java.util.List<EntityDataAccessor<Float>> keys=java.util.List.of(DATA_RIFLE_CROUCH,DATA_RIFLE_PRONE,DATA_RIFLE_READY,DATA_RIFLE_RECOIL,DATA_RIFLE_GAIT,DATA_RIFLE_MOVE,DATA_RIFLE_RUN,DATA_RIFLE_STANCE);
            int index=keys.indexOf(key);
            if(index>=0){float value=this.entityData.get(keys.get(index));rifleSignalPrevious[index]=this.tickCount<2?value:rifleSignalCurrent[index];rifleSignalCurrent[index]=value;rifleSignalTicks[index]=this.tickCount;if(poseSignalClocks!=null)poseSignalClocks[index].accept(value,index==4,false);}
        }
        if (DATA_LIVE_ACTION_PHASE.equals(key))
        {
            float phase = this.entityData.get(DATA_LIVE_ACTION_PHASE);
            this.clientActionPhasePrevious = phase < this.clientActionPhase
                    ? phase : this.clientActionPhase;
            this.clientActionPhase = phase;
            this.clientActionPhaseTick = this.tickCount;
            if(this.level().isClientSide&&actionSignalClock!=null)actionSignalClock.accept(phase,false,true);
        }
        if (DATA_CROUCHING.equals(key) || DATA_PRONE.equals(key))
        {
            this.updatePoseDimensions();
            this.clientMeleeStartTick = -1000;
            this.clientSmashStartTick = -1000;
            this.clientKickStartTick = -1000;
        }
        if (DATA_KNIFE_TYPE.equals(key) && this.entityData.get(DATA_KNIFE_TYPE) < 0
                && this.getWeapon() == WEAPON_KNIFE)
        {
            this.clientMeleeStartTick = -1000;
            this.clientSmashStartTick = -1000;
        }
        if (DATA_MELEE_SEQUENCE.equals(key))
        {
            int sequence = this.entityData.get(DATA_MELEE_SEQUENCE);
            if (sequence != this.clientMeleeSequence)
            {
                this.clientMeleeSequence = sequence;
                this.clientMeleeWeapon = this.getWeapon();
                this.clientMeleeLeft = this.entityData.get(DATA_MELEE_LEFT);
                this.clientOrdinaryAttackStage =
                        this.entityData.get(DATA_ORDINARY_ATTACK_STAGE);
                this.clientMeleeStartTick = this.tickCount;
            }
        }
        if (DATA_ORDINARY_ATTACK_STAGE.equals(key))
        {
            // Synched-data callbacks arrive in accessor-id order. The melee
            // sequence precedes this field, so reading the stage only from the
            // sequence callback always lagged one click and dropped the first.
            this.clientOrdinaryAttackStage =
                    this.entityData.get(DATA_ORDINARY_ATTACK_STAGE);
        }
        if (DATA_SMASH_SEQUENCE.equals(key))
        {
            int sequence = this.entityData.get(DATA_SMASH_SEQUENCE);
            if (sequence != this.clientSmashSequence)
            {
                this.clientSmashSequence = sequence;
                this.clientSmashWeapon = this.getWeapon();
                this.clientSmashStartTick = this.tickCount;
            }
        }
        if (DATA_KICK_SEQUENCE.equals(key))
        {
            int sequence = this.entityData.get(DATA_KICK_SEQUENCE);
            if (sequence != this.clientKickSequence)
            {
                this.clientKickSequence = sequence;
                this.clientKickStartTick = this.tickCount;
            }
        }
        if (DATA_JUMP_SEQUENCE.equals(key) && this.level().isClientSide)
        {
            int sequence = this.entityData.get(DATA_JUMP_SEQUENCE);
            if (sequence != this.clientJumpSequence)
            {
                this.clientJumpSequence = sequence;
                this.clientJumpImpulsePending = this.isControlledByLocalInstance();
                this.clientExplicitJumpInProgress = true;
                this.clientExplicitJumpObservedAirborne = false;
                this.clientExplicitJumpAuthorizationTicks =
                        JUMP_BUFFER_TICKS;
                this.clientVisualAirborne = true;
                this.clientVisualAscending = true;
                if (this.getVisualPose() == VISUAL_LIVE_JUMP)
                {
                    ProjectSeele.LOGGER.info("Visual live jump client sequence received sequence={}",
                            sequence);
                }
            }
        }
    }

    @Override
    protected void positionRider(Entity passenger, Entity.MoveFunction move)
    {
        if (!this.hasPassenger(passenger))
        {
            return;
        }
        if (passenger instanceof EntryPlugCarrierEntity plug
                && plug.isLockedToEva())
        {
            Vec3 seated = EntryPlugKinematics.lockedTransform(this).translation();
            move.accept(passenger, seated.x, seated.y, seated.z);
            return;
        }
        Vec3 seat = this.getPilotCameraSeatPosition(passenger);
        move.accept(passenger, seat.x, seat.y, seat.z);
    }

    /**
     * Camera socket shared by direct legacy riders and the pilot nested inside
     * the persistent entry plug.
     */
    public Vec3 getPilotCameraSeatPosition(Entity passenger)
    {
        return this.getPilotCameraSeatPosition(passenger,1F);
    }

    public Vec3 getPilotCameraSeatPosition(Entity passenger,float partial)
    {
        var reaction=CombatFeelR31.beat(this);
        if(EvaAirTransportR31.active(this)||EvaShutdownR30.displayed(this)||reaction!=null&&(reaction.kind()==CombatFeelR31.DOWN||reaction.kind()==CombatFeelR31.THROWN))
            return EvaBodyPose.opticalEye(this,partial).subtract(0,passenger.getEyeHeight(),0);
        if(this.isFirstBattleActive()&&FirstBattleClip.ready())
            return FirstBattleClip.point(FIRST_BATTLE.spec(this),true,"eye_blocks",FIRST_BATTLE.time(this,partial)).subtract(0,passenger.getEyeHeight(),0);
        if(this.isNervLogisticsLocked()||this.hasActiveCarrierMotion())
        {
            // The transport fixture owns this pose. A walking/rifle optical
            // socket must not introduce motion into a mechanically held EVA.
            Vec3 root=this.hasActiveCarrierMotion()?this.carrierRenderPosition(partial):this.getPosition(partial);
            double yaw=Math.toRadians(this.getYRot()),forward=EvaScale.fromLegacy(1);
            return root.add(-Math.sin(yaw)*forward,EvaScale.fromLegacy(24.63)-passenger.getEyeHeight(),Math.cos(yaw)*forward);
        }
        if(this instanceof EvaPrototypeEntity un&&un.isEyeLaserActive())return EvaUNOptics.eye(un,partial).subtract(0,passenger.getEyeHeight(),0);
        if(this.getWeapon()==WEAPON_RIFLE&&this.isPoweredOn()&&this.getVisualPose()==VISUAL_NORMAL
                &&(!this.isVisuallyAirborneForRender()||EvaGameplayMotionR32.sharedJumpActive(this,partial))&&EvaBodyPose.hasSupportedStances())
            return EvaRifleKinematics.sample(this,partial,this.getAimDirectionForPoseCapture(partial)).eye()
                    .subtract(0,passenger.getEyeHeight(),0);
        // The full-body owner also owns the head during strikes and jumps.
        // Falling back to a fixed standing socket here made first person
        // jump several metres away from the actual rendered optical point.
        if(!(this instanceof EvaPrototypeEntity)&&EvaGameplayMotionR32.sharedBody(this,partial)
                &&EvaGameplayMotionR32.sharedWeapon(this))
            return EvaBodyPose.opticalEye(this,partial).subtract(0,passenger.getEyeHeight(),0);
        if((this.getWeapon()==WEAPON_FISTS||this.getWeapon()==WEAPON_KNIFE)&&this.isPoweredOn()&&this.getVisualPose()==VISUAL_NORMAL&&!this.isVisuallyAirborneForRender()&&!this.hasLiveActionForRender(partial)&&EvaBodyPose.hasTerrainStances())
            return EvaBodyPose.opticalEye(this,partial).subtract(0,passenger.getEyeHeight(),0);
        // The pilot rides at the animated rig's head socket. First person sees
        // the same world entity and the same evaluated bones as third person.
        float rad = (float) Math.toRadians(Mth.rotLerp(partial,this.yBodyRotO,this.yBodyRot));
        // All three reviewed Tiger bodies share the same 192-pixel height and
        // semantic rig contract. Keep one eye-socket calculation so Unit-00
        // and Unit-02 cannot fall back to the former SmOd seat coordinates.
        boolean proneView = this.isPilotProne() || this.getVisualPose() == VISUAL_PRONE
                || this.getVisualPose() == VISUAL_CRAWL
                || this.getVisualPose() == VISUAL_PRONE_CANNON
                || this.getVisualPose() == VISUAL_PRONE_KNIFE_CONTACT
                || this.getVisualPose() == VISUAL_PRONE_LANCE_CONTACT
                || this.getVisualPose() == VISUAL_PRONE_RIFLE;
        boolean crouchView = this.isPilotCrouching() || this.getVisualPose() == VISUAL_CROUCH
                || this.getVisualPose() == VISUAL_CROUCH_WALK
                || this.getVisualPose() == VISUAL_CROUCH_KNIFE_CONTACT
                || this.getVisualPose() == VISUAL_CROUCH_LANCE_CONTACT
                || this.getVisualPose() == VISUAL_CROUCH_RIFLE_CONTACT;
        // These coordinates place the camera on the visible face plane rather
        // than at the neck pivot inside the chest shell. Tiger/SmOd's local
        // -Z face direction is entity-forward after rendering, so every stance
        // uses the same positive forward socket convention. Express Y as the
        // desired eye position because Camera adds the player's own eye height
        // after positionRider.
        float crouch=this.getVisualPose()==VISUAL_NORMAL?this.rifleCrouchBlend(partial):crouchView?1:0;
        float prone=this.getVisualPose()==VISUAL_NORMAL?this.rifleProneBlend(partial):proneView?1:0;
        double targetEyeHeight=EvaScale.fromLegacy(Mth.lerp(prone,Mth.lerp(crouch,24.63D,19.70D),7.00D));
        double forward=EvaScale.fromLegacy(Mth.lerp(prone,Mth.lerp(crouch,1D,.8D),12D));
        // A right-shouldered rifle puts its receiver immediately beside the
        // EVA's face. Offset the optical eye toward the left eye by less than
        // one block so the stock sits at the screen edge like a human sight
        // picture instead of covering half the display. This moves only the
        // rider socket; weapon and arms remain the shared world skeleton.
        double lateral = this.getWeapon() == WEAPON_RIFLE
                ? EvaScale.fromLegacy(0.90D) : 0.0D;
        double seatHeight = targetEyeHeight - passenger.getEyeHeight();
        return new Vec3(
                Mth.lerp(partial,this.xo,this.getX()) - Math.sin(rad) * forward + Math.cos(rad) * lateral,
                Mth.lerp(partial,this.yo,this.getY()) + seatHeight,
                Mth.lerp(partial,this.zo,this.getZ()) + Math.cos(rad) * forward + Math.sin(rad) * lateral);
    }

    @Override
    public Vec3 getDismountLocationForPassenger(LivingEntity passenger)
    {
        // Step out at the Unit's feet instead of dropping from plug height.
        float rad = (float) Math.toRadians(this.yBodyRot);
        double dismount = EvaScale.fromLegacy(5.5D);
        return new Vec3(this.getX() + Math.sin(rad) * dismount, this.getY(),
                this.getZ() - Math.cos(rad) * dismount);
    }

    // ----- durability -----

    @Override
    public boolean causeFallDamage(float distance, float multiplier, DamageSource source)
    {
        return false;
    }

    @Override
    public boolean fireImmune()
    {
        return true;
    }

    @Override
    public boolean removeWhenFarAway(double distance)
    {
        return false;
    }

    @Override
    protected SoundEvent getHurtSound(DamageSource source)
    {
        return SoundEvents.IRON_GOLEM_DAMAGE;
    }

    @Override
    protected SoundEvent getDeathSound()
    {
        return SoundEvents.IRON_GOLEM_DEATH;
    }

    @Override
    protected float getSoundVolume()
    {
        return 2.5F;
    }

    private void updateClientAnimationSignals()
    {
        if (this.hasActiveCarrierMotion() || this.isNervLogisticsLocked())
        {
            this.clientVisualHorizontalSpeed *= 0.55D;
            this.clientVisualVerticalSpeed *= 0.55D;
            this.clientVisualMoving = false;
            this.clientVisualAirborne = false;
            this.clientVisualAscending = false;
            this.clientVisualRunning = false;
            this.clientVisualRunReleaseTicks = 0;
            this.clientVisualGroundTicks = 2;
            this.clientVisualAirTicks = 0;
            this.clientExplicitJumpInProgress = false;
            this.clientExplicitJumpObservedAirborne = false;
            this.clientExplicitJumpAuthorizationTicks = 0;
            return;
        }
        double dx = this.getX() - this.xo;
        double dy = this.getY() - this.yo;
        double dz = this.getZ() - this.zo;
        double horizontal = Math.sqrt(dx * dx + dz * dz) * 20.0D;
        double vertical = dy * 20.0D;
        if (!Double.isFinite(horizontal) || horizontal > 160.0D)
        {
            horizontal = 0.0D;
        }
        if (!Double.isFinite(vertical) || Math.abs(vertical) > 160.0D)
        {
            vertical = 0.0D;
        }
        double speedGain = horizontal > this.clientVisualHorizontalSpeed
                ? 0.48D : 0.22D;
        this.clientVisualHorizontalSpeed = Mth.lerp(speedGain,
                this.clientVisualHorizontalSpeed, horizontal);
        this.clientVisualVerticalSpeed = Mth.lerp(0.38D,
                this.clientVisualVerticalSpeed, vertical);

        /*
         * Run/walk is a gait, not a one-packet animation trigger.  Keep the
         * chosen run gait authoritative across brief input/data latency and
         * while the chassis still carries run-speed momentum.  The old direct
         * boolean branch could alternate RUN/WALK on consecutive client ticks;
         * GeckoLib then restarted the 0.8 s loop before the second footfall.
         */
        if (this.hasVisualRunIntent())
        {
            this.clientVisualRunning = true;
            this.clientVisualRunReleaseTicks = 6;
        }
        else if (this.clientVisualRunning)
        {
            if (this.clientVisualHorizontalSpeed >= 10.25D)
            {
                this.clientVisualRunReleaseTicks = 6;
            }
            else if (this.clientVisualRunReleaseTicks > 0)
            {
                this.clientVisualRunReleaseTicks--;
            }
            else
            {
                this.clientVisualRunning = false;
            }
        }

        // Hysteresis prevents stair edges and one late position packet from
        // toggling idle/walk every other client tick.
        if (this.clientVisualMoving)
        {
            if (this.clientVisualHorizontalSpeed < 0.16D)
            {
                this.clientVisualMoving = false;
            }
        }
        else if (this.clientVisualHorizontalSpeed > 0.42D)
        {
            this.clientVisualMoving = true;
        }

        if (this.onGround())
        {
            this.clientVisualGroundTicks++;
            this.clientVisualAirTicks = 0;
            if (this.clientExplicitJumpInProgress
                    && this.clientExplicitJumpObservedAirborne
                    && this.clientVisualGroundTicks
                            >= (this.clientVisualMoving ? 1 : 2))
            {
                this.clientExplicitJumpInProgress = false;
                this.clientExplicitJumpObservedAirborne = false;
                this.clientExplicitJumpAuthorizationTicks = 0;
                this.clientVisualAirborne = false;
                this.clientVisualAscending = false;
            }
            else if (this.clientExplicitJumpInProgress)
            {
                this.clientVisualAirborne = true;
                if (!this.clientExplicitJumpObservedAirborne
                        && this.clientExplicitJumpAuthorizationTicks > 0)
                {
                    this.clientExplicitJumpAuthorizationTicks--;
                }
                if (!this.clientExplicitJumpObservedAirborne
                        && this.clientExplicitJumpAuthorizationTicks <= 0)
                {
                    this.clientExplicitJumpInProgress = false;
                    this.clientVisualAirborne = false;
                    this.clientVisualAscending = false;
                }
            }
            else
            {
                this.clientVisualAirborne = false;
                this.clientVisualAscending = false;
            }
        }
        else
        {
            if (this.clientVisualAirTicks == 0)
            {
                this.clientAirborneStartY = this.getY();
            }
            this.clientVisualAirTicks++;
            this.clientVisualGroundTicks = 0;
            if (this.clientExplicitJumpInProgress)
            {
                this.clientExplicitJumpObservedAirborne = true;
                this.clientVisualAirborne = true;
                if (this.clientVisualAscending
                        && this.clientVisualVerticalSpeed < -0.15D)
                {
                    // A jump has one apex. Interpolation may wobble around
                    // zero, but FALL must never flip back into JUMP.
                    this.clientVisualAscending = false;
                }
            }
            else
            {
                double drop = this.clientAirborneStartY - this.getY();
                boolean confirmedFall = this.clientVisualAirTicks
                        >= PASSIVE_FALL_CONFIRM_TICKS
                        && (drop >= PASSIVE_FALL_MIN_DROP
                        || this.clientVisualAirTicks
                                >= PASSIVE_FALL_SPEED_CONFIRM_TICKS
                        && this.clientVisualVerticalSpeed
                                <= PASSIVE_FALL_MIN_SPEED);
                this.clientVisualAirborne = confirmedFall;
                this.clientVisualAscending = false;
            }
        }
    }

    private boolean visuallyMoving(AnimationState<EvaUnit01Entity> state)
    {
        return this.level().isClientSide
                ? this.clientVisualMoving : state.isMoving();
    }

    public boolean isVisuallyMovingForRender()
    {
        return this.level().isClientSide
                ? this.clientVisualMoving
                : this.getDeltaMovement().horizontalDistanceSqr() > 0.0004D;
    }

    public double visualHorizontalSpeedForRender()
    {
        return this.level().isClientSide
                ? this.clientVisualHorizontalSpeed
                : this.getDeltaMovement().horizontalDistance() * 20.0D;
    }

    public double visualVerticalSpeedForRender()
    {
        return this.visualVerticalSpeed();
    }

    public boolean isVisuallyAirborneForRender()
    {
        return this.visuallyAirborne();
    }

    private boolean visuallyAirborne()
    {
        return this.level().isClientSide
                ? this.clientVisualAirborne
                : this.explicitJumpInProgress || this.wasAirborne;
    }

    private double visualVerticalSpeed()
    {
        return this.level().isClientSide
                ? this.clientVisualVerticalSpeed
                : this.getDeltaMovement().y * 20.0D;
    }

    // ----- GeckoLib -----

    private double locomotionAnimationSpeed()
    {
        if (this.getVisualPose() != VISUAL_NORMAL || this.getActivationTicks() > 0
                || this.isCrucified() || this.visuallyAirborne())
        {
            return 1.0D;
        }
        Vec3 motion = this.getDeltaMovement();
        double blocksPerSecond = this.level().isClientSide
                ? this.clientVisualHorizontalSpeed
                : Math.sqrt(motion.x * motion.x + motion.z * motion.z) * 20.0D;
        if (blocksPerSecond < 0.05D)
        {
            return 1.0D;
        }
        double speed;
        if (this.isPilotProne())
        {
            speed = blocksPerSecond * CRAWL_CYCLE_SECONDS / CRAWL_STRIDE_BLOCKS;
        }
        else if (this.isPilotCrouching())
        {
            speed = blocksPerSecond * CROUCH_CYCLE_SECONDS / CROUCH_STRIDE_BLOCKS;
        }
        else if (this.isVisualRunRequested())
        {
            speed = blocksPerSecond * RUN_CYCLE_SECONDS / RUN_STRIDE_BLOCKS
                    * RUN_CADENCE_GAIN;
        }
        else
        {
            speed = blocksPerSecond * WALK_CYCLE_SECONDS / WALK_STRIDE_BLOCKS
                    * WALK_CADENCE_GAIN;
        }
        return Mth.clamp(speed, 0.45D, 1.35D);
    }

    private RawAnimation groundedLocomotionAnimation()
    {
        if (this.isVisualRunRequested())
        {
            return ANIM_RUN;
        }
        return ANIM_WALK;
    }

    private PlayState continueBaseAnimation(
            AnimationState<EvaUnit01Entity> state, RawAnimation animation,
            int selection)
    {
        if (this.level().isClientSide
                && selection != this.clientBaseAnimationSelection)
        {
            this.clientBaseAnimationSelection = selection;
            ProjectSeele.LOGGER.info(
                    "EVA base animation selection: eva={} selection={} sprint={} moving={} airborne={} speed={} pose={}",
                    this.getId(), selection, this.isVisualRunRequested(),
                    this.clientVisualMoving, this.clientVisualAirborne,
                    this.clientVisualHorizontalSpeed, this.getVisualPose());
        }
        return state.isCurrentAnimation(animation)
                ? PlayState.CONTINUE : state.setAndContinue(animation);
    }

    @Override
    public void registerControllers(AnimatableManager.ControllerRegistrar controllers)
    {
        controllers.add(new AnimationController<>(this, "base", 2, state ->
        {
            if (this.isCrucified())
            {
                return state.setAndContinue(ANIM_CRUCIFIED);
            }
            // Cage restraint, plug insertion, carrier transfer and launch
            // ascent all keep one inert airframe silhouette.  The pilot may
            // see the activation sequence in the capsule, but the full body
            // cannot jump to a combat/aim pose before surface release.
            if (this.isNervLogisticsLocked())
            {
                return state.setAndContinue(ANIM_DORMANT);
            }
            if (this.isBerserk())
            {
                return state.setAndContinue(this.visuallyMoving(state)
                        ? ANIM_BERSERK_RUN : ANIM_IDLE);
            }
            switch (this.getVisualPose())
            {
                case VISUAL_IDLE -> { return state.setAndContinue(ANIM_VISUAL_IDLE); }
                case VISUAL_WALK_CONTACT -> { return state.setAndContinue(ANIM_VISUAL_WALK); }
                case VISUAL_RUN_CONTACT -> { return state.setAndContinue(ANIM_VISUAL_RUN); }
                case VISUAL_JUMP -> { return state.setAndContinue(ANIM_VISUAL_JUMP); }
                case VISUAL_FALL -> { return state.setAndContinue(ANIM_VISUAL_FALL); }
                case VISUAL_CROUCH_WALK -> { return state.setAndContinue(ANIM_VISUAL_CROUCH_WALK); }
                case VISUAL_CRAWL -> { return state.setAndContinue(ANIM_VISUAL_CRAWL); }
                case VISUAL_KNIFE_READY -> { return state.setAndContinue(ANIM_VISUAL_KNIFE_READY); }
                case VISUAL_LANCE_READY -> { return state.setAndContinue(ANIM_VISUAL_LANCE_READY); }
                case VISUAL_KNIFE_WINDUP -> { return state.setAndContinue(ANIM_VISUAL_KNIFE_WINDUP); }
                case VISUAL_KNIFE_CONTACT -> { return state.setAndContinue(ANIM_VISUAL_KNIFE_CONTACT); }
                case VISUAL_KNIFE_RECOVERY -> { return state.setAndContinue(ANIM_VISUAL_KNIFE_RECOVERY); }
                case VISUAL_CROUCH -> { return state.setAndContinue(ANIM_CROUCH); }
                case VISUAL_PRONE -> { return state.setAndContinue(ANIM_PRONE); }
                case VISUAL_LANCE_WINDUP -> { return state.setAndContinue(ANIM_VISUAL_LANCE_WINDUP); }
                case VISUAL_LANCE_CONTACT -> { return state.setAndContinue(ANIM_VISUAL_LANCE_CONTACT); }
                case VISUAL_LANCE_RECOVERY -> { return state.setAndContinue(ANIM_VISUAL_LANCE_RECOVERY); }
                case VISUAL_CANNON -> { return state.setAndContinue(ANIM_VISUAL_CANNON); }
                case VISUAL_PRONE_CANNON -> { return state.setAndContinue(ANIM_PRONE); }
                case VISUAL_RIFLE -> { return state.setAndContinue(ANIM_VISUAL_RIFLE); }
                case VISUAL_CROUCH_KNIFE_CONTACT -> { return state.setAndContinue(ANIM_VISUAL_CROUCH_KNIFE_CONTACT); }
                case VISUAL_PRONE_KNIFE_CONTACT -> { return state.setAndContinue(ANIM_VISUAL_PRONE_KNIFE_CONTACT); }
                case VISUAL_CROUCH_LANCE_CONTACT -> { return state.setAndContinue(ANIM_VISUAL_CROUCH_LANCE_CONTACT); }
                case VISUAL_PRONE_LANCE_CONTACT -> { return state.setAndContinue(ANIM_VISUAL_PRONE_LANCE_CONTACT); }
                case VISUAL_N2_READY -> { return state.setAndContinue(ANIM_VISUAL_N2_READY); }
                case VISUAL_RIFLE_WALK_CONTACT -> { return state.setAndContinue(ANIM_VISUAL_RIFLE_WALK_CONTACT); }
                case VISUAL_CROUCH_RIFLE_CONTACT -> { return state.setAndContinue(ANIM_VISUAL_CROUCH_RIFLE_CONTACT); }
                case VISUAL_PRONE_RIFLE -> { return state.setAndContinue(ANIM_VISUAL_PRONE_RIFLE); }
                case VISUAL_LIVE_MELEE -> { return state.setAndContinue(ANIM_VISUAL_IDLE); }
                case VISUAL_LIVE_KNIFE -> { return state.setAndContinue(ANIM_VISUAL_KNIFE_READY); }
                case VISUAL_LIVE_LANCE -> { return state.setAndContinue(ANIM_VISUAL_LANCE_READY); }
                case VISUAL_LIVE_RIFLE -> { return state.setAndContinue(ANIM_VISUAL_RIFLE); }
                case VISUAL_LIVE_KNIFE_HEAVY -> { return state.setAndContinue(ANIM_VISUAL_KNIFE_READY); }
                case VISUAL_LIVE_JUMP -> { return state.setAndContinue(ANIM_JUMP); }
                default -> { }
            }
            if (!this.isPoweredOn())
            {
                return this.continueBaseAnimation(state, ANIM_DORMANT, 1);
            }
            if (this.getActivationTicks() > 0)
            {
                return this.continueBaseAnimation(state, ANIM_ACTIVATION, 2);
            }
            // Stance changes resize the hitbox and can leave the Unit one
            // frame off the ground. Keep the requested pose authoritative so
            // PRONE never flashes back to an upright jump/fall animation.
            if (this.isPilotProne())
            {
                return state.setAndContinue(this.visuallyMoving(state)
                        ? ANIM_CRAWL : ANIM_PRONE);
            }
            if (this.isPilotCrouching())
            {
                return state.setAndContinue(this.visuallyMoving(state)
                        ? ANIM_CROUCH_WALK : ANIM_CROUCH);
            }
            if (this.visuallyAirborne())
            {
                boolean ascending = this.level().isClientSide
                        ? this.clientVisualAscending
                        : this.visualVerticalSpeed() > 0.35D;
                return this.continueBaseAnimation(state,
                        ascending ? ANIM_JUMP : ANIM_FALL,
                        ascending ? 3 : 4);
            }
            if (this.visuallyMoving(state))
            {
                boolean running = this.isVisualRunRequested();
                return this.continueBaseAnimation(state,
                        running ? ANIM_RUN : ANIM_WALK,
                        running ? 5 : 6);
            }
            return this.continueBaseAnimation(state, ANIM_IDLE, 7);
        }).setAnimationSpeedHandler(entity -> entity.locomotionAnimationSpeed()));
        controllers.add(new AnimationController<>(this, "arms", 3, state ->
        {
            if (this.isCrucified() || this.isBerserk()
                    || this.isNervLogisticsLocked()
                    || !this.isPoweredOn())
            {
                return PlayState.STOP;
            }
            if (this.isShieldBraced())
            {
                return state.setAndContinue(ANIM_SHIELD_BRACE);
            }
            if (this.getWeapon() == WEAPON_N2
                    && !this.isPilotProne()
                    && this.getVisualPose() == VISUAL_NORMAL)
            {
                return state.setAndContinue(ANIM_N2_READY);
            }
            if (this.getWeapon() == WEAPON_KNIFE
                    && this.getVisualPose() == VISUAL_NORMAL)
            {
                return state.setAndContinue(this.isPilotProne()
                        ? ANIM_PRONE_KNIFE_READY : ANIM_KNIFE_READY);
            }
            if ((this.getWeapon() == WEAPON_CANNON || this.getWeapon() == WEAPON_RIFLE)
                    && (this.isPilotProne() || this.getVisualPose() == VISUAL_PRONE_CANNON))
            {
                return state.setAndContinue(this.getWeapon() == WEAPON_RIFLE
                        ? ANIM_PRONE_RIFLE_AIM : ANIM_PRONE_AIM);
            }
            if (this.getWeapon() == WEAPON_LANCE
                    && this.getVisualPose() == VISUAL_NORMAL)
            {
                return state.setAndContinue(this.isPilotProne()
                        ? ANIM_PRONE_LANCE_READY : ANIM_LANCE_CARRY);
            }
            if ((this.getWeapon() == WEAPON_CANNON || this.getWeapon() == WEAPON_RIFLE)
                    && !this.isPilotProne()
                    && this.getVisualPose() == VISUAL_NORMAL)
            {
                return state.setAndContinue(this.getWeapon() == WEAPON_RIFLE
                        ? ANIM_RIFLE_AIM : ANIM_AIM);
            }
            return PlayState.STOP;
        }));
        controllers.add(new AnimationController<>(this, "strike", 3, state ->
        {
            var trigger=state.getController().getTriggeredAnimation();
            boolean fast=trigger!=null&&java.util.List.of(ANIM_MELEE,ANIM_MELEE_LEFT,ANIM_KNIFE,ANIM_KNIFE_LEFT,
                    ANIM_KNIFE_HEAVY,ANIM_LANCE_THRUST,ANIM_PRONE_MELEE,ANIM_PRONE_MELEE_LEFT,ANIM_PRONE_KNIFE,
                    ANIM_PRONE_KNIFE_HEAVY,ANIM_PRONE_LANCE_THRUST,ANIM_CROUCH_MELEE,ANIM_CROUCH_MELEE_LEFT,
                    ANIM_CROUCH_KNIFE,ANIM_CROUCH_KNIFE_HEAVY,ANIM_CROUCH_LANCE_THRUST,ANIM_STOMP).contains(trigger);
            state.getController().setAnimationSpeed(fast?MELEE_RATE_R43:1);
            if (this.isCrucified() || this.isNervLogisticsLocked()
                    || !this.isPoweredOn())
            {
                state.getController().stop();
                return PlayState.STOP;
            }
            if (ANIM_LAND.equals(
                    state.getController().getTriggeredAnimation())
                    && this.isVisuallyMovingForRender())
            {
                state.getController().stop();
                return PlayState.STOP;
            }
            // receiveTriggeredAnimations asks GeckoLib to consult this
            // predicate during a trigger. Returning STOP unconditionally
            // cancelled every melee/knife/lance clip on its first frame.
            return state.getController().isPlayingTriggeredAnimation()
                    ? PlayState.CONTINUE : PlayState.STOP;
        })
                .triggerableAnim("melee", ANIM_MELEE)
                .triggerableAnim("melee_left", ANIM_MELEE_LEFT)
                .triggerableAnim("knife", ANIM_KNIFE)
                .triggerableAnim("knife_left", ANIM_KNIFE_LEFT)
                .triggerableAnim("knife_heavy", ANIM_KNIFE_HEAVY)
                .triggerableAnim("lance_thrust", ANIM_LANCE_THRUST)
                .triggerableAnim("prone_melee", ANIM_PRONE_MELEE)
                .triggerableAnim("prone_melee_left", ANIM_PRONE_MELEE_LEFT)
                .triggerableAnim("prone_knife", ANIM_PRONE_KNIFE)
                .triggerableAnim("prone_knife_heavy", ANIM_PRONE_KNIFE_HEAVY)
                .triggerableAnim("prone_lance_thrust", ANIM_PRONE_LANCE_THRUST)
                .triggerableAnim("prone_smash", ANIM_PRONE_SMASH)
                .triggerableAnim("crouch_melee", ANIM_CROUCH_MELEE)
                .triggerableAnim("crouch_melee_left", ANIM_CROUCH_MELEE_LEFT)
                .triggerableAnim("crouch_knife", ANIM_CROUCH_KNIFE)
                .triggerableAnim("crouch_knife_heavy", ANIM_CROUCH_KNIFE_HEAVY)
                .triggerableAnim("crouch_lance_thrust", ANIM_CROUCH_LANCE_THRUST)
                .triggerableAnim("crouch_smash", ANIM_CROUCH_SMASH)
                .triggerableAnim("smash", ANIM_SMASH)
                .triggerableAnim("cannon_fire", ANIM_CANNON_FIRE)
                .triggerableAnim("prone_cannon_fire", ANIM_PRONE_CANNON_FIRE)
                .triggerableAnim("rifle_fire", ANIM_RIFLE_FIRE)
                .triggerableAnim("prone_rifle_fire", ANIM_PRONE_RIFLE_FIRE)
                .triggerableAnim("takeoff", ANIM_TAKEOFF)
                .triggerableAnim("land", ANIM_LAND)
                .triggerableAnim("stomp", ANIM_STOMP)
                .triggerableAnim("berserk_roar", ANIM_BERSERK_ROAR)
                .triggerableAnim("berserk_claw_r", ANIM_BERSERK_CLAW_R)
                .triggerableAnim("berserk_claw_l", ANIM_BERSERK_CLAW_L)
                .triggerableAnim("berserk_pounce", ANIM_BERSERK_POUNCE)
                .receiveTriggeredAnimations());
    }

    @Override
    public AnimatableInstanceCache getAnimatableInstanceCache()
    {
        return this.geoCache;
    }

    /** Client helper for smooth HUD/FOV: 0..1 charge with partial ticks. */
    public float chargeProgress()
    {
        return Mth.clamp(this.getCannonCharge() / (float) SeeleConfig.CANNON_CHARGE_TICKS.get(), 0.0F, 1.0F);
    }
}
