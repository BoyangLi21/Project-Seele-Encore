package com.projectseele.entity;

import java.util.EnumSet;
import java.util.Optional;

import java.util.HashSet;
import java.util.Set;
import java.util.UUID;

import com.projectseele.alarm.AngelAlarmSystem;
import com.projectseele.config.SeeleConfig;
import com.projectseele.fx.AtFieldFX;
import com.projectseele.fx.CrossExplosionFX;
import com.projectseele.network.ClientboundNukeFxPacket;
import com.projectseele.network.SeeleNetwork;
import com.projectseele.registry.ModSounds;
import net.minecraft.core.BlockPos;
import net.minecraft.core.particles.DustParticleOptions;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.network.chat.Component;
import net.minecraft.network.syncher.EntityDataAccessor;
import net.minecraft.network.syncher.EntityDataSerializers;
import net.minecraft.network.syncher.SynchedEntityData;
import net.minecraft.server.level.ServerBossEvent;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.sounds.SoundEvent;
import net.minecraft.tags.DamageTypeTags;
import net.minecraft.util.Mth;
import net.minecraft.world.BossEvent;
import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.DifficultyInstance;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.FlyingMob;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.entity.MobSpawnType;
import net.minecraft.world.entity.SpawnGroupData;
import net.minecraft.world.entity.ai.attributes.AttributeSupplier;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.entity.ai.control.MoveControl;
import net.minecraft.world.entity.ai.goal.Goal;
import net.minecraft.world.entity.ai.goal.target.NearestAttackableTargetGoal;
import net.minecraft.world.entity.monster.Enemy;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.entity.projectile.ProjectileUtil;
import net.minecraft.world.level.ClipContext;
import net.minecraft.world.level.GameRules;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.ServerLevelAccessor;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraftforge.network.PacketDistributor;
import org.jetbrains.annotations.Nullable;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraft.world.phys.EntityHitResult;
import net.minecraft.world.phys.Vec3;
import org.joml.Vector3f;

/**
 * Ramiel, the Fifth Angel: a hovering crystalline octahedron that snipes its
 * target with a devastating energy beam after a telegraphed charge-up.
 */
public class RamielEntity extends FlyingMob implements Enemy, Angel, com.projectseele.world.TvEncounterRulesR45.BeamRangeSource
{
    private static final EntityDataAccessor<Float> DATA_MODEL_SCALE_R52=SynchedEntityData.defineId(RamielEntity.class,EntityDataSerializers.FLOAT);
    private float modelScaleR52=1;
    public static final float MODEL_SIZE_MULTIPLIER_R53=4;
    public float modelScaleR52(){return (modelScaleR52>0?modelScaleR52:1)*MODEL_SIZE_MULTIPLIER_R53;}
    public void configureScaleR52(float scale)
    {if(this.level().isClientSide||!Float.isFinite(scale)||scale<1||scale>16)throw new IllegalArgumentException("Measured Ramiel scale required");this.entityData.set(DATA_MODEL_SCALE_R52,scale);}
    @Override public net.minecraft.world.entity.EntityDimensions getDimensions(net.minecraft.world.entity.Pose pose)
    {return super.getDimensions(pose).scale(modelScaleR52());}
    @Override public void onSyncedDataUpdated(EntityDataAccessor<?> key)
    {super.onSyncedDataUpdated(key);if(key==DATA_MODEL_SCALE_R52){modelScaleR52=this.entityData.get(DATA_MODEL_SCALE_R52);this.refreshDimensions();}}
    private static final EntityDataAccessor<Boolean> DATA_CHARGING =
            SynchedEntityData.defineId(RamielEntity.class, EntityDataSerializers.BOOLEAN);
    // Beam presentation state, synced so every client renders the same shot.
    private static final EntityDataAccessor<Integer> DATA_BEAM_TICKS =
            SynchedEntityData.defineId(RamielEntity.class, EntityDataSerializers.INT);
    private static final EntityDataAccessor<Integer> DATA_BEAM_DURATION_R54 =
            SynchedEntityData.defineId(RamielEntity.class, EntityDataSerializers.INT);
    private static final EntityDataAccessor<Vector3f> DATA_BEAM_END =
            SynchedEntityData.defineId(RamielEntity.class, EntityDataSerializers.VECTOR3);
    private static final EntityDataAccessor<Boolean> DATA_DRILLING =
            SynchedEntityData.defineId(RamielEntity.class, EntityDataSerializers.BOOLEAN);
    private static final EntityDataAccessor<Float> DATA_DRILL_DEPTH =
            SynchedEntityData.defineId(RamielEntity.class, EntityDataSerializers.FLOAT);
    // Shell presentation mirrors the actual beam's sniping window.
    private static final EntityDataAccessor<Boolean> DATA_EXPOSED =
            SynchedEntityData.defineId(RamielEntity.class, EntityDataSerializers.BOOLEAN);
    private static final EntityDataAccessor<Float> DATA_AT_ENERGY =
            SynchedEntityData.defineId(RamielEntity.class, EntityDataSerializers.FLOAT);
    /**
     * R63: the last blow the crystal answered. Where it came from, seen from the core, times how hard it was (0 to
     * 1.5), and a count that moves with every blow so two alike are still two.
     */
    private static final EntityDataAccessor<Vector3f> DATA_STRUCK_R63 =
            SynchedEntityData.defineId(RamielEntity.class, EntityDataSerializers.VECTOR3);
    private static final EntityDataAccessor<Integer> DATA_STRUCK_COUNT_R63 =
            SynchedEntityData.defineId(RamielEntity.class, EntityDataSerializers.INT);
    /** How hard the crystal answers a deflected shot, a Unit's blow on the field, and the field breaking. */
    public static final float STRUCK_SHOT_R63=.2F,STRUCK_BLOW_R63=.45F,STRUCK_BREAK_R63=1.1F;
    /**
     * The answer itself, for strength 1: the crystal gives this far away from the blow (blocks) and tips this far
     * over (degrees), swinging back and forth with this period and dying out over this time (ticks); it flashes
     * white for this long.
     */
    public static final float RECOIL_R63=1.6F,TILT_R63=7F,SWING_R63=11F,DECAY_R63=7F,FLASH_R63=3F;
    /**
     * R63: the crystal's answer to a Unit that keeps striking its field. BURST_BLOWS blows inside BURST_WINDOW ticks
     * and the field throws the Unit off: it staggers back as from a blow of BURST_FORCE (no damage is done), and
     * the field does not do it again for BURST_REST ticks.
     */
    public static final int BURST_BLOWS_R63=3,BURST_WINDOW_R63=60,BURST_REST_R63=100;
    public static final float BURST_FORCE_R63=14F;
    private int fieldBlowsR63;
    /**
     * Long ago, and still a time the game's clock can be taken from: from Long.MIN_VALUE the difference wrapped
     * round to a negative number, the rest after a burst never ended and no first burst ever came.
     */
    private static final long NEVER_R63=Long.MIN_VALUE/2;
    private long fieldBlowAtR63=NEVER_R63,burstAtR63=NEVER_R63;
    private int struckSeenR63;
    private float struckAgeR63=1000,struckAgeOR63=1000;
    private Vector3f struckR63=new Vector3f();

    // Balance values (damage, ranges, cooldowns) live in SeeleConfig; the
    // constants left here are presentation/geometry, not tuning knobs.
    /** Total client-visible beam lifetime: solid flash then afterglow fade-out. */
    public static final int BEAM_RENDER_TICKS = 16;
    public static final int YASHIMA_BEAM_TICKS_R54 = 60;
    public static final int BEAM_SOLID_TICKS = 6;

    // Operation-Yashima sniping is accepted only while the actual three-second
    // beam is active, and only when the shot threads the core.
    // Geometry enlarged again after playtest: the Angel should dominate half a city block.
    // Aim tolerance matches the rendered core octahedron (~3.2 blocks).
    public static final float CORE_RADIUS = 4.25F;
    private static final double AT_FIELD_PUSH_RANGE = 17.5D;
    private static final float SHELL_SURFACE_RADIUS = 8.5F;

    // Phase two (below 40% health): faster charge plus the drill descent.
    private static final float ENRAGE_HEALTH_FRACTION = 0.4F;
    private static final int DRILL_APPROACH_TIMEOUT = 140;
    private static final int DRILL_DURATION_TICKS = 80;
    private static final int DRILL_HIT_INTERVAL = 10;
    private static final double DRILL_RADIUS = 2.6D;
    private static final float DRILL_DESCENT_PER_TICK = 0.5F;
    private static final float DRILL_MAX_DEPTH = 32.0F;
    private static final float DRILL_UNBREAKABLE_RESISTANCE = 1200.0F;

    private static final DustParticleOptions CHARGE_DUST =
            new DustParticleOptions(new Vector3f(1.0F, 0.35F, 0.45F), 2.0F);

    private final ServerBossEvent bossEvent = new ServerBossEvent(
            this.getDisplayName(), BossEvent.BossBarColor.BLUE, BossEvent.BossBarOverlay.PROGRESS);

    private int beamCooldown = 60;
    private long beamCooldownReadyAtR54;
    private long beamEndsAtR54;
    private int rippleCooldown;

    private static int pacedRemainingR54(int ticks,long readyAt)
    {
        // A burst of catch-up ticks must not consume the spoken warning or
        // recovery interval. Simulation ticks also keep these paused in menus.
        long remaining=readyAt==0?0:Math.max(0,readyAt-System.nanoTime());
        return Math.max(ticks,(int)((remaining+49_999_999L)/50_000_000L));
    }

    /** The mission armour controller is the only writer of the accepted drilling front. */
    public void missionDrillR50(boolean active,float depth)
    {
        if(this.level().isClientSide)return;
        this.entityData.set(DATA_DRILLING,active);
        this.entityData.set(DATA_DRILL_DEPTH,active&&Float.isFinite(depth)?Math.max(0,depth):0F);
    }

    // Players this Angel ever managed to hurt — the flawless-kill bonus
    // (hidden advancement) goes to a slayer who is not on this list.
    private final Set<UUID> hurtPlayers = new HashSet<>();

    // Client-side rotation state, interpolated by the renderer.
    private float spin;
    private float spinO;
    // Client-side shell-separation animation, eased toward the synced flag.
    private float exposeProgress;
    private float exposeProgressO;

    public RamielEntity(EntityType<? extends RamielEntity> type, Level level)
    {
        super(type, level);
        this.moveControl = new RamielMoveControl(this);
        this.xpReward = 500;
    }

    @Override
    protected boolean updateInWaterStateAndDoFluidPushing()
    {
        if (fluidSectionsEmpty())
        {
            this.fluidHeight.clear();
            this.forgeFluidTypeHeight.clear();
            this.wasTouchingWater = false;
            return false;
        }
        return super.updateInWaterStateAndDoFluidPushing();
    }

    @Override
    public boolean isInWall()
    {
        if (this.noPhysics || this.isSleeping()) return false;
        // Match Entity.isInWall's float width and exact thin eye volume.
        // Only the three vanilla air blocks can bypass its position-sensitive
        // suffocation/shape predicate. Client missing chunks read VOID_AIR;
        // unavailable server chunks retain super's path.
        float width = this.getBbWidth() * .8F;
        AABB eye = AABB.ofSize(this.getEyePosition(), width, 1e-6D, width);
        if (com.projectseele.physics.GiantMoveBlockQueryR53.noPaletteMatch(this.level(), eye,
                state -> !state.is(net.minecraft.world.level.block.Blocks.AIR)
                        && !state.is(net.minecraft.world.level.block.Blocks.CAVE_AIR)
                        && !state.is(net.minecraft.world.level.block.Blocks.VOID_AIR))) return false;
        return super.isInWall();
    }

    private boolean fluidSectionsEmpty()
    {
        // A scaled airframe spans millions of voxels. Palette rejection is
        // conservative: any fluid (including waterlogged blocks) keeps the
        // original fluid calculation, and missing chunks are never generated.
        AABB bounds = this.getBoundingBox();
        int firstSection = Math.max(0, this.level().getSectionIndex(Mth.floor(bounds.minY)));
        int lastSection = Math.min(this.level().getSectionsCount() - 1,
                this.level().getSectionIndex(Mth.ceil(bounds.maxY) - 1));
        for (int x = Mth.floor(bounds.minX) >> 4; x <= (Mth.ceil(bounds.maxX) - 1) >> 4; x++)
        {
            for (int z = Mth.floor(bounds.minZ) >> 4; z <= (Mth.ceil(bounds.maxZ) - 1) >> 4; z++)
            {
                var chunk = this.level().getChunkSource().getChunk(x, z,
                        net.minecraft.world.level.chunk.ChunkStatus.FULL, false);
                if (chunk == null)
                {
                    // Client missing chunks have Fluids.EMPTY, as returned by
                    // vanilla EmptyLevelChunk; never generate a server chunk.
                    if (this.level().isClientSide) continue;
                    return false;
                }
                var sections = chunk.getSections();
                for (int index = firstSection; index <= lastSection; index++)
                {
                    if (!sections[index].hasOnlyAir()
                            && sections[index].maybeHas(state -> !state.getFluidState().isEmpty()))
                        return false;
                }
            }
        }
        return true;
    }

    public static AttributeSupplier.Builder createAttributes()
    {
        return Mob.createMobAttributes()
                .add(Attributes.MAX_HEALTH, 350.0D)
                .add(Attributes.ARMOR, 6.0D)
                .add(Attributes.KNOCKBACK_RESISTANCE, 1.0D)
                .add(Attributes.ATTACK_DAMAGE, 20.0D)
                .add(Attributes.FOLLOW_RANGE, 100.0D);
    }

    @Override
    public SpawnGroupData finalizeSpawn(ServerLevelAccessor level, DifficultyInstance difficulty,
                                        MobSpawnType reason, @Nullable SpawnGroupData spawnData,
                                        @Nullable CompoundTag dataTag)
    {
        // Attribute registration happens before configs are guaranteed loaded,
        // so the config values are applied per-spawn instead.
        if (SeeleConfig.COMMON_SPEC.isLoaded())
        {
            this.getAttribute(Attributes.MAX_HEALTH).setBaseValue(SeeleConfig.RAMIEL_MAX_HEALTH.get());
            this.getAttribute(Attributes.ARMOR).setBaseValue(SeeleConfig.RAMIEL_ARMOR.get());
            this.setHealth(this.getMaxHealth());
        }
        this.entityData.set(DATA_AT_ENERGY, this.getAtFieldMax());
        return super.finalizeSpawn(level, difficulty, reason, spawnData, dataTag);
    }

    @Override
    public void addAdditionalSaveData(CompoundTag tag)
    {
        super.addAdditionalSaveData(tag);
        // Save the authored base scale; loading must not multiply it again.
        tag.putFloat("AtFieldEnergy", this.getAtFieldEnergy());tag.putFloat("ModelScaleR52",this.entityData.get(DATA_MODEL_SCALE_R52));
        tag.putInt("BeamCooldownR54",pacedRemainingR54(this.beamCooldown,this.beamCooldownReadyAtR54));
    }

    @Override
    public void readAdditionalSaveData(CompoundTag tag)
    {
        super.readAdditionalSaveData(tag);
        if(tag.contains("BeamCooldownR54"))
        {
            this.beamCooldown=Mth.clamp(tag.getInt("BeamCooldownR54"),0,2400);
            this.beamCooldownReadyAtR54=System.nanoTime()+this.beamCooldown*50_000_000L;
        }
        this.entityData.set(DATA_MODEL_SCALE_R52,tag.contains("ModelScaleR52")?net.minecraft.util.Mth.clamp(tag.getFloat("ModelScaleR52"),1,16):1F);
        this.entityData.set(DATA_AT_ENERGY,
                tag.contains("AtFieldEnergy") ? tag.getFloat("AtFieldEnergy") : this.getAtFieldMax());
    }

    @Override
    protected void registerGoals()
    {
        this.goalSelector.addGoal(0, new DrillAttackGoal(this));
        this.goalSelector.addGoal(1, new BeamAttackGoal(this));
        this.goalSelector.addGoal(2, new HoverGoal(this));
        // The EVA is the bigger threat; stray humans are an afterthought.
        this.targetSelector.addGoal(1, new NearestAttackableTargetGoal<>(this, EvaUnit01Entity.class, false)
        {
            @Override public boolean canUse()
            {return com.projectseele.world.TvEncounterRulesR45.missionRamielAnchor(RamielEntity.this)==null&&super.canUse();}
            @Override public boolean canContinueToUse()
            {return com.projectseele.world.TvEncounterRulesR45.missionRamielAnchor(RamielEntity.this)==null&&super.canContinueToUse();}
        });
        this.targetSelector.addGoal(2, new NearestAttackableTargetGoal<>(this, Player.class, false)
        {
            @Override public boolean canUse()
            {return com.projectseele.world.TvEncounterRulesR45.missionRamielAnchor(RamielEntity.this)==null&&super.canUse();}
            @Override public boolean canContinueToUse()
            {return com.projectseele.world.TvEncounterRulesR45.missionRamielAnchor(RamielEntity.this)==null&&super.canContinueToUse();}
        });
    }

    @Override
    protected void defineSynchedData()
    {
        super.defineSynchedData();
        this.entityData.define(DATA_MODEL_SCALE_R52,1F);
        this.entityData.define(DATA_CHARGING, false);
        this.entityData.define(DATA_BEAM_TICKS, 0);
        this.entityData.define(DATA_BEAM_DURATION_R54, BEAM_RENDER_TICKS);
        this.entityData.define(DATA_BEAM_END, new Vector3f());
        this.entityData.define(DATA_DRILLING, false);
        this.entityData.define(DATA_DRILL_DEPTH, 0.0F);
        this.entityData.define(DATA_EXPOSED, false);
        this.entityData.define(DATA_AT_ENERGY, 1750.0F);
        this.entityData.define(DATA_STRUCK_R63, new Vector3f());
        this.entityData.define(DATA_STRUCK_COUNT_R63, 0);
    }

    /** True while the field stands closed round the crystal: a blow lands on it, not on nothing. */
    public boolean fieldSealedR63()
    {
        return !this.isExposed() && this.hasAtField();
    }

    /** -Dprojectseele.poseDiag=true: every blow on the field and every burst goes to the log. */
    private static final boolean TOLD_R63 = Boolean.getBoolean("projectseele.poseDiag");
    /** Server: a Unit's blow has landed on the standing field. A run of them throws the Unit off. */
    private void fieldBlowR63(EvaUnit01Entity striker)
    {
        long now = this.level().getGameTime();
        this.fieldBlowsR63 = now - this.fieldBlowAtR63 > BURST_WINDOW_R63 ? 1 : this.fieldBlowsR63 + 1;
        this.fieldBlowAtR63 = now;
        if (TOLD_R63) com.projectseele.ProjectSeele.LOGGER.info("R63RAMIELBLOW at {} blows {} since the last burst {}", now, this.fieldBlowsR63, now - this.burstAtR63);
        if (this.fieldBlowsR63 < BURST_BLOWS_R63 || now - this.burstAtR63 < BURST_REST_R63) return;
        this.fieldBlowsR63 = 0;
        this.burstAtR63 = now;
        Vec3 away = striker.position().subtract(this.position()).multiply(1, 0, 1);
        away = away.lengthSqr() < 1.0E-4D ? new Vec3(1, 0, 0) : away.normalize();
        // The beat alone: the Unit is driven back and loses its footing for a moment, its hull is not touched.
        CombatFeelR31.acceptedHit(striker, this, BURST_FORCE_R63, away, false);
        // A stagger taken in the middle of a punch is read down to a flinch, and the burst that answers a run of
        // punches finds the Unit in one: it is sent again as what it is. A berserk Unit in its strike is left with
        // the flinch: nothing staggers it there.
        var given = CombatFeelR31.beat(striker);
        boolean raised = given != null && given.kind() == CombatFeelR31.FLINCH && !EvaBerserkMotionR34.striking(striker);
        if (raised) CombatFeelR31.send(striker, CombatFeelR31.STAGGER, away, given.strength(), 16, 1);
        this.spawnAtFieldRipple(this.beamOrigin().add(away.scale(SHELL_SURFACE_RADIUS * this.modelScaleR52())), away);
        this.playSound(ModSounds.CRYSTAL_HIT.get(), 3.0F, 0.4F);
        if (TOLD_R63)
        {
            var beat = CombatFeelR31.beat(striker);
            com.projectseele.ProjectSeele.LOGGER.info("R63RAMIELBLOW burst: the Unit's beat is now {}, raised from a flinch {} (attack stage {} phase {})", beat == null ? "none" : beat.kind(),
                    raised, striker.getOrdinaryAttackStage(), striker.getOrdinaryAttackProgress(0));
        }
    }

    /** Server: the crystal answers a blow that came from there. */
    private void struckR63(Vec3 from, float strength)
    {
        Vec3 core = this.beamOrigin();
        Vec3 dir = from != null && from.distanceToSqr(core) > 1.0E-4D ? from.subtract(core).normalize() : new Vec3(0, 1, 0);
        float s = Mth.clamp(strength, 0, 1.5F);
        this.entityData.set(DATA_STRUCK_R63, new Vector3f((float) dir.x * s, (float) dir.y * s, (float) dir.z * s));
        this.entityData.set(DATA_STRUCK_COUNT_R63, this.entityData.get(DATA_STRUCK_COUNT_R63) + 1);
    }

    /** How far the crystal's answer has died out, 1 to 0, and where in its swing it is (radians). */
    private float struckEnvelopeR63(float partialTick)
    {
        float age = Mth.lerp(partialTick, this.struckAgeOR63, this.struckAgeR63);
        return age > DECAY_R63 * 6 ? 0 : (float) Math.exp(-age / DECAY_R63);
    }

    /** Client: where the crystal is drawn from its place, in blocks: away from the blow and back. */
    public Vec3 struckOffsetR63(float partialTick)
    {
        float envelope = this.struckEnvelopeR63(partialTick);
        if (envelope <= 0) return Vec3.ZERO;
        float age = Mth.lerp(partialTick, this.struckAgeOR63, this.struckAgeR63);
        // Starts at rest, is farthest a quarter of a swing later.
        float give = -RECOIL_R63 * envelope * Mth.sin(age * Mth.TWO_PI / SWING_R63);
        return new Vec3(this.struckR63.x() * give, this.struckR63.y() * give, this.struckR63.z() * give);
    }

    /** Client: the axis the crystal tips about (level, across the blow) and by how much (degrees); null when it stands still. */
    public org.joml.Vector4f struckTiltR63(float partialTick)
    {
        float envelope = this.struckEnvelopeR63(partialTick);
        float strength = this.struckR63.length();
        if (envelope <= 0 || strength < 1.0E-4F) return null;
        float age = Mth.lerp(partialTick, this.struckAgeOR63, this.struckAgeR63);
        // The tip follows the give by a quarter of a swing: the top goes last.
        float angle = TILT_R63 * strength * envelope * Mth.sin((age - SWING_R63 / 4) * Mth.TWO_PI / SWING_R63);
        float x = -this.struckR63.z(), z = this.struckR63.x(), flat = Mth.sqrt(x * x + z * z);
        if (flat < 1.0E-4F) return null;
        return new org.joml.Vector4f(x / flat, 0, z / flat, angle);
    }

    /** Client: how white the crystal is drawn, 0 to 1. */
    public float struckFlashR63(float partialTick)
    {
        float age = Mth.lerp(partialTick, this.struckAgeOR63, this.struckAgeR63);
        return age > FLASH_R63 * 4 ? 0 : Math.min(1, this.struckR63.length()) * (float) Math.exp(-age / FLASH_R63);
    }

    public boolean isExposed()
    {
        return this.entityData.get(DATA_EXPOSED);
    }

    private void setExposed(boolean exposed)
    {
        this.entityData.set(DATA_EXPOSED, exposed);
    }

    public float getAtFieldEnergy()
    {
        return this.entityData.get(DATA_AT_ENERGY);
    }

    public float getAtFieldMax()
    {
        double multiplier = SeeleConfig.COMMON_SPEC.isLoaded()
                ? SeeleConfig.RAMIEL_AT_FIELD_MULTIPLIER.get() : 5.0D;
        return (float) (this.getMaxHealth() * multiplier);
    }

    public boolean hasAtField()
    {
        return this.getAtFieldEnergy() > 0.0F;
    }

    /**
     * Whether an aim ray threads the exposed core (kill shot). Judged on the
     * ray itself, not the hitbox intersection point — the box surface sits
     * six blocks out, so a surface test could never reach the core.
     */
    public boolean isCoreShot(Vec3 from, Vec3 direction)
    {
        if (!this.isExposed())
        {
            return false;
        }
        Vec3 toCore = this.beamOrigin().subtract(from);
        double along = toCore.dot(direction.normalize());
        if (along <= 0.0D)
        {
            return false;
        }
        double missSqr = toCore.lengthSqr() - along * along;
        return missSqr <= CORE_RADIUS * CORE_RADIUS * this.modelScaleR52() * this.modelScaleR52();
    }

    /** Eased 0..1 shell separation for the renderer. */
    public float getExposeProgress(float partialTick)
    {
        return Mth.lerp(partialTick, this.exposeProgressO, this.exposeProgress);
    }

    public boolean isDrilling()
    {
        return this.entityData.get(DATA_DRILLING);
    }

    public float getDrillDepth()
    {
        return this.entityData.get(DATA_DRILL_DEPTH);
    }

    /** Phase two: wounded Ramiel charges faster and hunts from directly above. */
    public boolean isEnraged()
    {
        return this.getHealth() < this.getMaxHealth() * ENRAGE_HEALTH_FRACTION;
    }

    public int getBeamTicks()
    {
        if (ReviewR58.EXPOSE_CYCLE && this.level().isClientSide) return this.isAlive() ? ReviewR58.beamTicks(this.tickCount) : 0;
        return this.entityData.get(DATA_BEAM_TICKS);
    }
    public int getBeamDurationR54()
    {
        if (ReviewR58.EXPOSE_CYCLE && this.level().isClientSide) return ReviewR58.BEAM;
        return this.entityData.get(DATA_BEAM_DURATION_R54);
    }

    public Vec3 getBeamEnd()
    {
        if (ReviewR58.EXPOSE_CYCLE && this.level().isClientSide) return ReviewR58.target(this);
        Vector3f end = this.entityData.get(DATA_BEAM_END);
        return new Vec3(end.x(), end.y(), end.z());
    }

    public boolean isCharging()
    {
        if (ReviewR58.EXPOSE_CYCLE && this.level().isClientSide) return ReviewR58.charging(this.tickCount);
        return this.entityData.get(DATA_CHARGING);
    }

    private void setCharging(boolean charging)
    {
        this.entityData.set(DATA_CHARGING, charging);
    }

    /** Interpolated body rotation in degrees; spins faster while charging. */
    public float getSpin(float partialTick)
    {
        return Mth.lerp(partialTick, this.spinO, this.spin);
    }

    @Override
    public void travel(Vec3 input)
    {
        Vec3 anchor=com.projectseele.world.TvEncounterRulesR45.missionRamielAnchor(this);
        if(anchor!=null)
        {
            // The commissioned drilling target hovers at its original anchor.
            // Its oversized vanilla hull must not push that anchor away.
            this.setPos(anchor);this.setDeltaMovement(Vec3.ZERO);return;
        }
        super.travel(input);
    }

    @Override
    public void tick()
    {
        if (!this.level().isClientSide)
        {
            // Decrement before AI can fire. A new shot keeps its full window,
            // and the synced beam clock also controls the exposed model.
            int previous=this.getBeamTicks();
            int remaining = previous>0?pacedRemainingR54(Math.max(0,previous-1),this.beamEndsAtR54):0;
            this.entityData.set(DATA_BEAM_TICKS, remaining);
            int chargeRemaining=com.projectseele.world.TvYashimaCombatCommsR54.chargeRemainingR54(this);
            this.setExposed(remaining > 0 || this.isCharging() && chargeRemaining > 0 && chargeRemaining <= 20);
            if(previous>0&&remaining==0)com.projectseele.world.TvYashimaCombatCommsR54.onBeamEnded(this,
                    pacedRemainingR54(this.beamCooldown,this.beamCooldownReadyAtR54));
        }
        super.tick();
        if (this.level().isClientSide)
        {
            int struck = this.entityData.get(DATA_STRUCK_COUNT_R63);
            this.struckAgeOR63 = this.struckAgeR63;
            if (struck != this.struckSeenR63)
            {
                this.struckSeenR63 = struck;
                this.struckR63 = new Vector3f(this.entityData.get(DATA_STRUCK_R63));
                this.struckAgeR63 = this.struckAgeOR63 = 0;
            }
            else if (this.struckAgeR63 < 1000) this.struckAgeR63++;
            this.spinO = this.spin;
            this.spin += this.isCharging() || this.isDrilling() ? 6.0F : 0.75F;
            this.exposeProgressO = this.exposeProgress;
            float target = this.isExposed() ? 1.0F : 0.0F;
            if (ReviewR58.EXPOSE_CYCLE) target = ReviewR58.expose(this.tickCount);
            // Opens over ~15 ticks and folds back over ~20: the shell closing
            // used to snap shut in a single frame.
            this.exposeProgress += (target - this.exposeProgress) * (target > this.exposeProgress ? 0.16F : 0.12F);
            if (target == 0 && this.exposeProgress < .002F) this.exposeProgress = 0;
        }
    }

    /**
     * The A.T. Field is a real durability pool. While the core is sealed,
     * only direct EVA melee can drain it; all ranged damage is reflected.
     * Core shots during exposure bypass the pool and hit real health.
     */
    @Override
    public boolean hurt(DamageSource source, float amount)
    {
        // The cannon's direct ray owns Angel damage. Its huge cinematic
        // blast must not double-dip and turn the tuned two-core-hit fight
        // into an accidental one-shot.
        if (source.is(DamageTypeTags.IS_EXPLOSION) && source.getEntity() instanceof EvaUnit01Entity)
        {
            return false;
        }
        if (!this.isExposed() && this.hasAtField()
                && !source.is(DamageTypeTags.BYPASSES_INVULNERABILITY)
                && !com.projectseele.combat.AtFieldRules.bypassesAtField(source))
        {
            boolean evaMelee = source.getDirectEntity() instanceof EvaUnit01Entity eva
                    && eva.isMeleeWeapon() && !source.is(DamageTypeTags.IS_EXPLOSION);
            if (!this.level().isClientSide)
            {
                this.deflect(source, evaMelee ? STRUCK_BLOW_R63 : STRUCK_SHOT_R63);
                if (evaMelee)
                {
                    float remaining = Math.max(0.0F, this.getAtFieldEnergy() - amount);
                    this.entityData.set(DATA_AT_ENERGY, remaining);
                    if (remaining <= 0.0F)
                    {
                        this.playSound(ModSounds.CRYSTAL_BREAK.get(), 3.0F, 0.65F);
                        this.struckR63(source.getSourcePosition(), STRUCK_BREAK_R63);
                    }
                    else if (source.getDirectEntity() instanceof EvaUnit01Entity striker) this.fieldBlowR63(striker);
                }
            }
            return false;
        }
        boolean hurt = super.hurt(source, amount);
        // A hit that reaches the crystal itself: by how much of its health it took.
        if (hurt && !this.level().isClientSide)
            this.struckR63(source.getSourcePosition(), .5F + 3 * amount / Math.max(1, this.getMaxHealth()));
        return hurt;
    }

    private void deflect(DamageSource source, float strength)
    {
        if (this.rippleCooldown > 0)
        {
            return;
        }
        this.rippleCooldown = 3;
        this.struckR63(source.getSourcePosition(), strength);
        Vec3 origin = source.getSourcePosition() != null ? source.getSourcePosition() : null;
        Vec3 core = this.beamOrigin();
        Vec3 dir = origin != null && origin.distanceToSqr(core) > 1.0E-4D
                ? origin.subtract(core).normalize()
                : new Vec3(this.random.nextDouble() - 0.5D, this.random.nextDouble() - 0.5D,
                        this.random.nextDouble() - 0.5D).normalize();
        this.spawnAtFieldRipple(core.add(dir.scale(SHELL_SURFACE_RADIUS*this.modelScaleR52())), dir);
        this.playSound(ModSounds.CRYSTAL_HIT.get(), 2.0F, 0.55F);
    }

    /** Broadcasts a hexagon ripple to everyone near this Angel. */
    public void spawnAtFieldRipple(Vec3 point, Vec3 normal)
    {
        if (this.level() instanceof ServerLevel serverLevel)
        {
            AtFieldFX.ripple(serverLevel, point, normal);
        }
    }

    @Override
    protected void customServerAiStep()
    {
        super.customServerAiStep();
        if (this.beamCooldown > 0)
        {
            this.beamCooldown--;
        }
        if (this.rippleCooldown > 0)
        {
            this.rippleCooldown--;
        }
        if (this.hasAtField() && this.tickCount % 5 == 0)
        {
            this.pushWithAtField();
        }
        boolean fieldBar = this.hasAtField() && !this.isExposed();
        this.bossEvent.setProgress(fieldBar
                ? this.getAtFieldEnergy() / Math.max(1.0F, this.getAtFieldMax())
                : this.getHealth() / this.getMaxHealth());
        this.bossEvent.setName(fieldBar
                ? Component.translatable("boss.projectseele.ramiel_at_field") : this.getDisplayName());
        this.bossEvent.setColor(fieldBar ? BossEvent.BossBarColor.BLUE
                : this.isEnraged() ? BossEvent.BossBarColor.RED : BossEvent.BossBarColor.PURPLE);
    }

    /** Anything that walks up to the Angel gets shoved back by the field. */
    private void pushWithAtField()
    {
        Vec3 core = this.position();
        AABB range = new AABB(core, core).inflate(AT_FIELD_PUSH_RANGE);
        for (LivingEntity target : com.projectseele.physics.CombatEntityQueryR44.candidates(this.level(),range,
                e -> e != this && !(e instanceof Angel) && e.isAlive() && !e.isSpectator()))
        {
            Vec3 away = com.projectseele.physics.CombatBodyContacts.nearestSurfacePoint(target,core).subtract(core);
            double distance = away.length();
            if (distance > AT_FIELD_PUSH_RANGE || distance < 1.0E-3D)
            {
                continue;
            }
            double resist = target.getAttributeValue(Attributes.KNOCKBACK_RESISTANCE);
            double strength = 0.14D * (1.0D - distance / AT_FIELD_PUSH_RANGE) * (1.0D - resist);
            if (strength <= 0.0D)
            {
                continue;
            }
            Vec3 push = away.normalize().scale(strength);
            target.push(push.x, push.y * 0.4D + 0.02D, push.z);
            if (this.rippleCooldown <= 0 && distance < AT_FIELD_PUSH_RANGE * 0.6D)
            {
                this.rippleCooldown = 4;
                Vec3 mid = core.add(away.scale(0.55D)).add(0.0D, this.getBbHeight() * 0.35D, 0.0D);
                this.spawnAtFieldRipple(mid, away.normalize());
            }
        }
    }

    public void markPlayerHurt(UUID playerId)
    {
        this.hurtPlayers.add(playerId);
    }

    @Override
    public void die(DamageSource source)
    {
        super.die(source);
        if (this.level() instanceof ServerLevel serverLevel)
        {
            CrossExplosionFX.spawn(serverLevel, this.position(), 2.8F);
            if (source.getEntity() instanceof ServerPlayer slayer
                    && !this.hurtPlayers.contains(slayer.getUUID()))
            {
                AngelAlarmSystem.award(slayer, "yashima_untouched");
            }
        }
    }

    private Vec3 beamOrigin()
    {
        return this.position().add(0.0D, this.getBbHeight() * 0.5D, 0.0D);
    }

    @Override public double effectiveBeamRangeR45()
    {return com.projectseele.world.TvEncounterRulesR45.missionAttackRange(this,SeeleConfig.BEAM_RANGE.get());}

    private boolean beamLineOfSightR45(LivingEntity target)
    {
        if(com.projectseele.world.TvEncounterRulesR45.missionRamielAnchor(this)==null)return this.hasLineOfSight(target);
        return com.projectseele.world.TvYashimaFirelineR53.clip((ServerLevel)this.level(),new ClipContext(this.beamOrigin(),target.getEyePosition(),ClipContext.Block.COLLIDER,ClipContext.Fluid.NONE,this)).hit()
                .getType()==net.minecraft.world.phys.HitResult.Type.MISS;
    }

    private void fireBeam(LivingEntity target)
    {
        if(com.projectseele.world.TvEncounterRulesR45.missionRamielAnchor(this)!=null
                &&!com.projectseele.world.ShieldCoverR48.missionBeamAllowed(this))return;
        Vec3 from = this.beamOrigin();
        boolean yashima = com.projectseele.world.ShieldCoverR48.yashima(this);
        Vec3 targetPoint=target.getEyePosition();
        if(yashima&&target instanceof EvaUnit01Entity defender&&com.projectseele.world.ShieldCoverR48.authorized(defender))
        {
            var plate=EvaShieldRigR47.guardPlaneR54(defender);
            if(plate!=null)targetPoint=plate.centre();
        }
        Vec3 dir = targetPoint.subtract(from).normalize();
        Vec3 farEnd = from.add(dir.scale(this.effectiveBeamRangeR45()));
        var terrain = com.projectseele.world.TvYashimaFirelineR53.clip((ServerLevel)this.level(),
                new ClipContext(from, farEnd, ClipContext.Block.COLLIDER, ClipContext.Fluid.NONE, this));
        BlockHitResult blockHit = terrain.hit();
        Vec3 end = blockHit.getLocation();

        // Compare the same complete terrain-clipped segment for shield and
        // body contacts. The closest actual surface owns this one shot.
        var shieldHit = this.level() instanceof ServerLevel shieldLevel
                ? com.projectseele.world.ShieldCoverR48.nearest(shieldLevel, from, end, this)
                : java.util.Optional.<com.projectseele.world.ShieldCoverR48.Contact>empty();
        EntityHitResult bodyHit = com.projectseele.physics.CombatEntityQueryR44.ray(this.level(),from,end,.3,
                e -> e != this && e.isAlive()
                        && !(e instanceof Angel)
                        && !(e.getVehicle() instanceof EvaUnit01Entity));
        boolean stoppedByShield = shieldHit.isPresent() && (bodyHit == null
                || from.distanceToSqr(shieldHit.get().point()) <= from.distanceToSqr(bodyHit.getLocation()) + 1e-8);
        if (stoppedByShield) end = shieldHit.get().point();
        else if (bodyHit != null) end = bodyHit.getLocation();
        final Vec3 impact = end;
        var source = this.damageSources().mobAttack(this);
        if (stoppedByShield)
        {
            if (yashima) com.projectseele.world.ShieldCoverR48.receiveYashima(shieldHit.get(), this,
                    java.util.UUID.randomUUID(), source);
        }
        else if (bodyHit != null && bodyHit.getEntity() instanceof LivingEntity victim)
        {
            com.projectseele.world.ShieldCoverR48.hurtDirect(victim, source,
                    SeeleConfig.BEAM_DAMAGE.get().floatValue(), from, impact, () ->
            {
                if (yashima && victim instanceof EvaUnit01Entity eva)
                {
                    return eva.receiveUnshieldedYashimaBeamR48(source);
                }
                return victim.hurt(source, yashima ? Float.MAX_VALUE : SeeleConfig.BEAM_DAMAGE.get().floatValue());
            });
        }

        // A stopped ray has no damaging explosion on the rear of the shield.
        // Yashima applies its explicit chassis hit only, never blast damage to
        // the protected plug/pilot. Ordinary unshielded beams retain their blast.
        if (!stoppedByShield && !yashima && (terrain.complete()||bodyHit!=null||blockHit.getType()==net.minecraft.world.phys.HitResult.Type.BLOCK)) this.level().explode(this, end.x, end.y, end.z,
                SeeleConfig.BEAM_EXPLOSION_RADIUS.get().floatValue(), Level.ExplosionInteraction.MOB);
        // Yashima sustains a visible cutting beam; a nuclear flash and hundreds
        // of smoke particles would hide its sniping window and shield contact.
        this.entityData.set(DATA_BEAM_END, new Vector3f((float) end.x, (float) end.y, (float) end.z));
        int duration=yashima?YASHIMA_BEAM_TICKS_R54:BEAM_RENDER_TICKS;
        this.entityData.set(DATA_BEAM_DURATION_R54,duration);
        this.entityData.set(DATA_BEAM_TICKS,duration);
        this.beamEndsAtR54=yashima?System.nanoTime()+duration*50_000_000L:0;
        this.setExposed(true);
        com.projectseele.world.TvYashimaCombatCommsR54.onFire(this);
        if (this.level() instanceof ServerLevel serverLevel && !yashima
                && (terrain.complete() || bodyHit != null || blockHit.getType() == net.minecraft.world.phys.HitResult.Type.BLOCK))
        {
            SeeleNetwork.CHANNEL.send(
                    PacketDistributor.DIMENSION.with(serverLevel::dimension),
                    new ClientboundNukeFxPacket(impact.x, impact.y, impact.z, 2.6F, true));
            com.projectseele.world.MissionAudioR64.echo(serverLevel, impact, ModSounds.CROSS_EXPLOSION.get(),
                    net.minecraft.sounds.SoundSource.HOSTILE);
            serverLevel.sendParticles(ParticleTypes.END_ROD, impact.x, impact.y, impact.z, 64, 2.0D, 2.0D, 2.0D, 0.22D);
            serverLevel.sendParticles(ParticleTypes.EXPLOSION_EMITTER, impact.x, impact.y + 2.0D, impact.z, 9, 5.0D, 2.5D, 5.0D, 0.0D);
            // Mushroom stem and cap.
            for (int i = 2; i <= 36; i += 2)
            {
                serverLevel.sendParticles(ParticleTypes.LARGE_SMOKE,
                        impact.x, impact.y + i, impact.z, 12, 2.2D, 1.3D, 2.2D, 0.015D);
            }
            serverLevel.sendParticles(ParticleTypes.CAMPFIRE_COSY_SMOKE,
                    impact.x, impact.y + 37.0D, impact.z, 110, 14.0D, 3.5D, 14.0D, 0.025D);
            serverLevel.sendParticles(ParticleTypes.FLAME,
                    impact.x, impact.y + 1.0D, impact.z, 70, 4.5D, 1.6D, 4.5D, 0.09D);
        }
        this.playSound(ModSounds.BEAM_FIRE.get(), 5.0F, 1.0F);
        // R64: the shot echoes across the city at night for everyone within 1,500 blocks.
        if (this.level() instanceof ServerLevel echoLevel)
            com.projectseele.world.MissionAudioR64.echo(echoLevel, this.position(), ModSounds.BEAM_FIRE.get(), this.getSoundSource());
    }

    // ----- boss bar -----

    // Far tracking outlives the battle area; the bar keeps the old combat radius.
    public void updateBossBarAudienceR61(net.minecraft.server.level.ServerLevel level)
    {
        double range = Math.min(32 * 16, level.getServer().getPlayerList().getViewDistance() * 16);
        for (var player : level.players())
        {
            double dx = player.getX() - this.getX(), dz = player.getZ() - this.getZ();
            boolean near = dx * dx + dz * dz <= range * range;
            boolean listed = this.bossEvent.getPlayers().contains(player);
            if (near && !listed) this.bossEvent.addPlayer(player);
            else if (!near && listed) this.bossEvent.removePlayer(player);
        }
    }

    @Override
    public void stopSeenByPlayer(ServerPlayer player)
    {
        super.stopSeenByPlayer(player);
        this.bossEvent.removePlayer(player);
    }

    // ----- durability & presentation -----

    @Override
    public AABB getBoundingBoxForCulling()
    {
        // While the beam afterglow is alive the renderer draws far beyond the
        // body, so widen the culling volume to keep it visible off-screen.
        AABB box = super.getBoundingBoxForCulling();
        if (this.getBeamTicks() > 0)
        {
            box = box.minmax(new AABB(this.getBeamEnd(), this.getBeamEnd()).inflate(2.0D));
        }
        if (this.isDrilling())
        {
            box = box.expandTowards(0.0D, -this.getDrillDepth(), 0.0D);
        }
        return box;
    }

    @Override
    public boolean removeWhenFarAway(double distance)
    {
        return false;
    }

    @Override
    public boolean isPushable()
    {
        return false;
    }

    @Override
    protected SoundEvent getAmbientSound()
    {
        return ModSounds.RAMIEL_HUM.get();
    }

    @Override
    protected SoundEvent getHurtSound(DamageSource source)
    {
        return ModSounds.CRYSTAL_HIT.get();
    }

    @Override
    protected SoundEvent getDeathSound()
    {
        return ModSounds.CRYSTAL_BREAK.get();
    }

    @Override
    protected float getSoundVolume()
    {
        return 4.0F;
    }

    // =====================================================================
    // AI
    // =====================================================================

    /** Ghast-style drift toward the wanted position; no pathfinding needed. */
    static class RamielMoveControl extends MoveControl
    {
        private final RamielEntity ramiel;
        private int recalcDelay;

        RamielMoveControl(RamielEntity ramiel)
        {
            super(ramiel);
            this.ramiel = ramiel;
        }

        @Override
        public void tick()
        {
            if (this.operation != Operation.MOVE_TO)
            {
                return;
            }
            if (this.recalcDelay-- > 0)
            {
                return;
            }
            this.recalcDelay = this.ramiel.getRandom().nextInt(5) + 2;
            Vec3 toWanted = new Vec3(this.wantedX - this.ramiel.getX(),
                    this.wantedY - this.ramiel.getY(),
                    this.wantedZ - this.ramiel.getZ());
            double distance = toWanted.length();
            if (distance < 2.0D)
            {
                this.ramiel.setDeltaMovement(this.ramiel.getDeltaMovement().scale(0.7D));
                this.operation = Operation.WAIT;
            }
            else
            {
                this.ramiel.setDeltaMovement(this.ramiel.getDeltaMovement()
                        .add(toWanted.scale(0.03D / distance)));
            }
        }
    }

    /** Keeps a high-altitude standoff position near the target, or bobs idly. */
    static class HoverGoal extends Goal
    {
        private final RamielEntity ramiel;

        HoverGoal(RamielEntity ramiel)
        {
            this.ramiel = ramiel;
            this.setFlags(EnumSet.of(Goal.Flag.MOVE));
        }

        @Override
        public boolean canUse()
        {
            return true;
        }

        @Override
        public boolean requiresUpdateEveryTick()
        {
            return true;
        }

        @Override
        public void tick()
        {
            LivingEntity target = this.ramiel.getTarget();
            MoveControl control = this.ramiel.getMoveControl();
            Vec3 missionAnchor=com.projectseele.world.TvEncounterRulesR45.missionRamielAnchor(this.ramiel);
            if(missionAnchor!=null)
            {control.setWantedPosition(missionAnchor.x,missionAnchor.y,missionAnchor.z,1.0D);return;}
            if (target != null && target.isAlive())
            {
                Vec3 away = this.ramiel.position().subtract(target.position());
                Vec3 flatAway = new Vec3(away.x, 0.0D, away.z);
                if (flatAway.lengthSqr() < 1.0E-4D)
                {
                    flatAway = new Vec3(1.0D, 0.0D, 0.0D);
                }
                Vec3 wanted = target.position()
                        .add(flatAway.normalize().scale(30.0D))
                        .add(0.0D, 20.0D, 0.0D);
                control.setWantedPosition(wanted.x, wanted.y, wanted.z, 1.0D);
            }
            else if (this.ramiel.getRandom().nextInt(60) == 0)
            {
                Vec3 pos = this.ramiel.position();
                control.setWantedPosition(
                        pos.x + (this.ramiel.getRandom().nextDouble() - 0.5D) * 10.0D,
                        pos.y + (this.ramiel.getRandom().nextDouble() - 0.5D) * 4.0D,
                        pos.z + (this.ramiel.getRandom().nextDouble() - 0.5D) * 10.0D,
                        1.0D);
            }
        }
    }

    /** Telegraphed charge-up followed by a hitscan beam and explosion. */
    static class BeamAttackGoal extends Goal
    {
        private final RamielEntity ramiel;
        private int chargeTicks;
        private long chargeReadyAtR54;

        BeamAttackGoal(RamielEntity ramiel)
        {
            this.ramiel = ramiel;
            this.setFlags(EnumSet.of(Goal.Flag.LOOK));
        }

        @Override
        public boolean canUse()
        {
            LivingEntity target = this.ramiel.getTarget();
            double range = this.ramiel.effectiveBeamRangeR45();
            return pacedRemainingR54(this.ramiel.beamCooldown,this.ramiel.beamCooldownReadyAtR54) <= 0
                    && com.projectseele.world.TvYashimaDirectorR50.fireAiAllowedR50(this.ramiel)
                    && (!this.ramiel.isDrilling()||com.projectseele.world.TvEncounterRulesR45.missionRamielAnchor(this.ramiel)!=null)
                    && target != null && target.isAlive()
                    && this.ramiel.distanceToSqr(target) < range * range
                    && this.ramiel.beamLineOfSightR45(target);
        }

        @Override
        public boolean canContinueToUse()
        {
            LivingEntity target = this.ramiel.getTarget();
            return this.chargeTicks > 0 && target != null && target.isAlive()
                    && com.projectseele.world.TvYashimaDirectorR50.fireAiAllowedR50(this.ramiel);
        }

        @Override
        public boolean requiresUpdateEveryTick()
        {
            return true;
        }

        @Override
        public void start()
        {
            boolean yashima=com.projectseele.world.ShieldCoverR48.yashima(this.ramiel);
            this.chargeTicks = yashima?SeeleConfig.YASHIMA_BEAM_CHARGE_TICKS.get():this.ramiel.isEnraged()
                    ? SeeleConfig.BEAM_CHARGE_TICKS_ENRAGED.get()
                    : SeeleConfig.BEAM_CHARGE_TICKS.get();
            this.chargeReadyAtR54=yashima?System.nanoTime()+this.chargeTicks*50_000_000L:0;
            this.ramiel.setCharging(true);
            com.projectseele.world.TvYashimaCombatCommsR54.onCharge(this.ramiel,this.chargeTicks);
            this.ramiel.playSound(ModSounds.BEAM_CHARGE.get(), 3.0F,
                    this.ramiel.isEnraged() ? 1.35F : 1.0F);
        }

        @Override
        public void stop()
        {
            this.ramiel.setCharging(false);
            boolean yashima=com.projectseele.world.ShieldCoverR48.yashima(this.ramiel);
            this.ramiel.beamCooldown = yashima?SeeleConfig.YASHIMA_BEAM_COOLDOWN_TICKS.get()+this.ramiel.getBeamTicks():SeeleConfig.BEAM_COOLDOWN_TICKS.get();
            this.ramiel.beamCooldownReadyAtR54=yashima?System.nanoTime()+this.ramiel.beamCooldown*50_000_000L:0;
            this.chargeReadyAtR54=0;
            com.projectseele.world.TvYashimaCombatCommsR54.onChargeCancelled(this.ramiel);
            // Cancelling charge cannot create or extend a firing window.
            this.ramiel.setExposed(this.ramiel.getBeamTicks() > 0);
        }

        @Override
        public void tick()
        {
            if (this.chargeTicks <= 0) return;
            LivingEntity target = this.ramiel.getTarget();
            if (target == null)
            {
                return;
            }
            this.ramiel.getLookControl().setLookAt(target, 30.0F, 30.0F);

            if (this.ramiel.level() instanceof ServerLevel serverLevel)
            {
                Vec3 core = this.ramiel.beamOrigin();
                serverLevel.sendParticles(CHARGE_DUST, core.x, core.y, core.z, 4, 1.6D, 1.6D, 1.6D, 0.0D);
            }

            this.chargeTicks=pacedRemainingR54(Math.max(0,this.chargeTicks-1),this.chargeReadyAtR54);
            if(com.projectseele.world.ShieldCoverR48.yashima(this.ramiel)&&this.chargeTicks>0&&this.chargeTicks<=20)
                this.ramiel.setExposed(true);
            com.projectseele.world.TvYashimaCombatCommsR54.onChargeTick(this.ramiel,this.chargeTicks);
            if (this.chargeTicks <= 0)
            {
                this.ramiel.fireBeam(target);
            }
        }
    }

    /**
     * Phase-two attack: park directly above the target, then bore straight
     * down with a sustained damage column that chews through terrain (the
     * Rebuild drill, inverted — Ramiel brings the drill to you).
     */
    static class DrillAttackGoal extends Goal
    {
        private final RamielEntity ramiel;
        private int cooldown = 300;
        private int approachTicks;
        private int drillTicks;
        private boolean drilling;
        private Vec3 anchor = Vec3.ZERO;

        DrillAttackGoal(RamielEntity ramiel)
        {
            this.ramiel = ramiel;
            this.setFlags(EnumSet.of(Goal.Flag.MOVE, Goal.Flag.LOOK));
        }

        @Override
        public boolean canUse()
        {
            if(com.projectseele.world.TvEncounterRulesR45.missionRamielAnchor(this.ramiel)!=null)return false;
            if (this.cooldown > 0)
            {
                this.cooldown--;
                return false;
            }
            LivingEntity target = this.ramiel.getTarget();
            return this.ramiel.isEnraged() && target != null && target.isAlive();
        }

        @Override
        public boolean canContinueToUse()
        {
            LivingEntity target = this.ramiel.getTarget();
            if (target == null || !target.isAlive())
            {
                return false;
            }
            if (this.drilling)
            {
                return this.drillTicks < DRILL_DURATION_TICKS;
            }
            return this.approachTicks < DRILL_APPROACH_TIMEOUT;
        }

        @Override
        public boolean requiresUpdateEveryTick()
        {
            return true;
        }

        @Override
        public void start()
        {
            this.approachTicks = 0;
            this.drillTicks = 0;
            this.drilling = false;
        }

        @Override
        public void stop()
        {
            this.cooldown = SeeleConfig.DRILL_COOLDOWN_TICKS.get();
            if (this.drilling && this.drillTicks < DRILL_DURATION_TICKS && this.ramiel.level() instanceof ServerLevel server)
            {
                // The take runs the full four seconds; cut it when the attack ends early.
                var halt = new net.minecraft.network.protocol.game.ClientboundStopSoundPacket(ModSounds.DRILL.getId(), this.ramiel.getSoundSource());
                for (var player : server.players())
                {
                    if (player.distanceToSqr(this.ramiel) < 160 * 160) player.connection.send(halt);
                }
            }
            this.drilling = false;
            this.ramiel.entityData.set(DATA_DRILLING, false);
            this.ramiel.entityData.set(DATA_DRILL_DEPTH, 0.0F);
        }

        @Override
        public void tick()
        {
            LivingEntity target = this.ramiel.getTarget();
            if (target == null)
            {
                return;
            }
            if (!this.drilling)
            {
                this.approachTicks++;
                Vec3 wanted = target.position().add(0.0D, 24.0D, 0.0D);
                this.ramiel.getMoveControl().setWantedPosition(wanted.x, wanted.y, wanted.z, 1.0D);
                double horizontalSqr = this.ramiel.position().subtract(target.position())
                        .multiply(1.0D, 0.0D, 1.0D).lengthSqr();
                if (horizontalSqr < 4.0D * 4.0D && this.ramiel.getY() > target.getY() + 12.0D)
                {
                    this.drilling = true;
                    this.anchor = this.ramiel.position();
                    this.ramiel.entityData.set(DATA_DRILLING, true);
                }
                return;
            }

            this.drillTicks++;
            // Hold the anchor: the column stays put, giving the target a way out.
            this.ramiel.getMoveControl().setWantedPosition(this.anchor.x, this.anchor.y, this.anchor.z, 1.0D);
            this.ramiel.setDeltaMovement(this.ramiel.getDeltaMovement().scale(0.6D));
            if (this.drillTicks == 1)
            {
                // One continuous take covers the whole drill (DRILL_DURATION_TICKS, four seconds).
                this.ramiel.playSound(ModSounds.DRILL.get(), 3.0F, 1.0F);
            }

            float depth = Math.min(this.drillTicks * DRILL_DESCENT_PER_TICK, DRILL_MAX_DEPTH);
            this.ramiel.entityData.set(DATA_DRILL_DEPTH, depth);

            if (!(this.ramiel.level() instanceof ServerLevel serverLevel))
            {
                return;
            }

            double coreY = this.ramiel.getY() + this.ramiel.getBbHeight() * 0.5D;
            double floorY = coreY - depth;

            if (this.drillTicks % DRILL_HIT_INTERVAL == 0)
            {
                AABB column = new AABB(
                        this.ramiel.getX() - DRILL_RADIUS, floorY, this.ramiel.getZ() - DRILL_RADIUS,
                        this.ramiel.getX() + DRILL_RADIUS, coreY, this.ramiel.getZ() + DRILL_RADIUS);
                for (LivingEntity victim : com.projectseele.physics.CombatEntityQueryR44.overlap(serverLevel,column,
                        e -> e != this.ramiel && e.isAlive()))
                {
                    victim.hurt(this.ramiel.damageSources().mobAttack(this.ramiel),
                            SeeleConfig.DRILL_DAMAGE.get().floatValue());
                }
            }

            if (serverLevel.getGameRules().getBoolean(GameRules.RULE_MOBGRIEFING))
            {
                this.carveLayer(serverLevel, floorY);
            }

            if (this.drillTicks % 8 == 0)
            {
                serverLevel.sendParticles(ParticleTypes.CRIT,
                        this.ramiel.getX(), floorY, this.ramiel.getZ(), 14, 1.2D, 0.4D, 1.2D, 0.15D);
            }
        }

        /** Breaks one disc of blocks at the drill front, respecting a per-tick budget. */
        private void carveLayer(ServerLevel level, double floorY)
        {
            int broken = 0;
            BlockPos center = BlockPos.containing(this.ramiel.getX(), floorY, this.ramiel.getZ());
            int radius = (int) Math.ceil(DRILL_RADIUS);
            for (int dx = -radius; dx <= radius && broken < 40; dx++)
            {
                for (int dz = -radius; dz <= radius && broken < 40; dz++)
                {
                    if (dx * dx + dz * dz > DRILL_RADIUS * DRILL_RADIUS)
                    {
                        continue;
                    }
                    BlockPos pos = center.offset(dx, 0, dz);
                    BlockState state = level.getBlockState(pos);
                    if (state.isAir()
                            || state.getBlock().getExplosionResistance() >= DRILL_UNBREAKABLE_RESISTANCE
                            || state.getDestroySpeed(level, pos) < 0.0F)
                    {
                        continue;
                    }
                    level.destroyBlock(pos, false, this.ramiel);
                    broken++;
                }
            }
        }
    }

    /**
     * Development review only (-Dprojectseele.ramielReviewR58, client side):
     * a 200-tick cycle of charge, opening, a 50-tick beam onto the nearest
     * raised shield (or the ground ahead) and closing, with no AI or damage.
     */
    static final class ReviewR58
    {
        static final boolean EXPOSE_CYCLE = Boolean.getBoolean("projectseele.ramielReviewR58");
        static final int CYCLE = 200, OPEN = 30, FIRE = 80, BEAM = 50, CLOSE = 150;
        static float expose(int tick) { int c = tick % CYCLE; return c >= OPEN && c < CLOSE ? 1 : 0; }
        static boolean charging(int tick) { int c = tick % CYCLE; return c >= 10 && c < FIRE; }
        static int beamTicks(int tick) { int c = tick % CYCLE; return c >= FIRE && c < FIRE + BEAM ? FIRE + BEAM - c : 0; }
        static Vec3 target(RamielEntity ramiel)
        {
            Vec3 best = null; double distance = Double.MAX_VALUE;
            for (var eva : ramiel.level().getEntitiesOfClass(EvaUnit01Entity.class, ramiel.getBoundingBox().inflate(400)))
            {
                var plate = EvaShieldRigR47.guardPlaneR54(eva);
                if (plate == null) continue;
                double d = plate.centre().distanceToSqr(ramiel.position());
                if (d < distance) { distance = d; best = plate.centre(); }
            }
            return best != null ? best : ramiel.position().add(ramiel.getForward().scale(120)).add(0, -40, 0);
        }
    }
}
