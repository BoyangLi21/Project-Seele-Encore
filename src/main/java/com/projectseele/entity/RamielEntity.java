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
    private static final EntityDataAccessor<Boolean> DATA_CHARGING =
            SynchedEntityData.defineId(RamielEntity.class, EntityDataSerializers.BOOLEAN);
    // Beam presentation state, synced so every client renders the same shot.
    private static final EntityDataAccessor<Integer> DATA_BEAM_TICKS =
            SynchedEntityData.defineId(RamielEntity.class, EntityDataSerializers.INT);
    private static final EntityDataAccessor<Vector3f> DATA_BEAM_END =
            SynchedEntityData.defineId(RamielEntity.class, EntityDataSerializers.VECTOR3);
    private static final EntityDataAccessor<Boolean> DATA_DRILLING =
            SynchedEntityData.defineId(RamielEntity.class, EntityDataSerializers.BOOLEAN);
    private static final EntityDataAccessor<Float> DATA_DRILL_DEPTH =
            SynchedEntityData.defineId(RamielEntity.class, EntityDataSerializers.FLOAT);
    // Core exposure: the only window in which Ramiel can be damaged at all.
    private static final EntityDataAccessor<Boolean> DATA_EXPOSED =
            SynchedEntityData.defineId(RamielEntity.class, EntityDataSerializers.BOOLEAN);
    private static final EntityDataAccessor<Float> DATA_AT_ENERGY =
            SynchedEntityData.defineId(RamielEntity.class, EntityDataSerializers.FLOAT);

    // Balance values (damage, ranges, cooldowns) live in SeeleConfig; the
    // constants left here are presentation/geometry, not tuning knobs.
    /** Total client-visible beam lifetime: solid flash then afterglow fade-out. */
    public static final int BEAM_RENDER_TICKS = 16;
    public static final int BEAM_SOLID_TICKS = 6;

    // Operation-Yashima rules: the shell opens for the final stretch of the
    // charge and stays open briefly after firing — snipe the core or nothing.
    // Geometry enlarged again after playtest: the Angel should dominate half a city block.
    // Aim tolerance matches the rendered core octahedron (~3.2 blocks).
    public static final float CORE_RADIUS = 4.25F;
    private static final int EXPOSE_CHARGE_WINDOW = 20;
    private static final int EXPOSED_AFTER_FIRE_TICKS = 60;
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
    private int exposedTimer;
    private int rippleCooldown;

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
        tag.putFloat("AtFieldEnergy", this.getAtFieldEnergy());
    }

    @Override
    public void readAdditionalSaveData(CompoundTag tag)
    {
        super.readAdditionalSaveData(tag);
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
        this.entityData.define(DATA_CHARGING, false);
        this.entityData.define(DATA_BEAM_TICKS, 0);
        this.entityData.define(DATA_BEAM_END, new Vector3f());
        this.entityData.define(DATA_DRILLING, false);
        this.entityData.define(DATA_DRILL_DEPTH, 0.0F);
        this.entityData.define(DATA_EXPOSED, false);
        this.entityData.define(DATA_AT_ENERGY, 1750.0F);
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
        return missSqr <= CORE_RADIUS * CORE_RADIUS;
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
        return this.entityData.get(DATA_BEAM_TICKS);
    }

    public Vec3 getBeamEnd()
    {
        Vector3f end = this.entityData.get(DATA_BEAM_END);
        return new Vec3(end.x(), end.y(), end.z());
    }

    public boolean isCharging()
    {
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
    public void tick()
    {
        super.tick();
        if (this.level().isClientSide)
        {
            this.spinO = this.spin;
            this.spin += this.isCharging() || this.isDrilling() ? 6.0F : 0.75F;
            this.exposeProgressO = this.exposeProgress;
            float target = this.isExposed() ? 1.0F : 0.0F;
            this.exposeProgress += (target - this.exposeProgress) * 0.16F;
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
                this.deflect(source);
                if (evaMelee)
                {
                    float remaining = Math.max(0.0F, this.getAtFieldEnergy() - amount);
                    this.entityData.set(DATA_AT_ENERGY, remaining);
                    if (remaining <= 0.0F)
                    {
                        this.playSound(ModSounds.CRYSTAL_BREAK.get(), 3.0F, 0.65F);
                    }
                }
            }
            return false;
        }
        return super.hurt(source, amount);
    }

    private void deflect(DamageSource source)
    {
        if (this.rippleCooldown > 0)
        {
            return;
        }
        this.rippleCooldown = 3;
        Vec3 origin = source.getSourcePosition() != null ? source.getSourcePosition() : null;
        Vec3 core = this.beamOrigin();
        Vec3 dir = origin != null && origin.distanceToSqr(core) > 1.0E-4D
                ? origin.subtract(core).normalize()
                : new Vec3(this.random.nextDouble() - 0.5D, this.random.nextDouble() - 0.5D,
                        this.random.nextDouble() - 0.5D).normalize();
        this.spawnAtFieldRipple(core.add(dir.scale(SHELL_SURFACE_RADIUS)), dir);
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
        if (this.exposedTimer > 0 && --this.exposedTimer == 0 && !this.isCharging())
        {
            this.setExposed(false);
        }
        int beamTicks = this.entityData.get(DATA_BEAM_TICKS);
        if (beamTicks > 0)
        {
            this.entityData.set(DATA_BEAM_TICKS, beamTicks - 1);
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
        return this.level().clip(new ClipContext(this.beamOrigin(),target.getEyePosition(),ClipContext.Block.COLLIDER,ClipContext.Fluid.NONE,this))
                .getType()==net.minecraft.world.phys.HitResult.Type.MISS;
    }

    private void fireBeam(LivingEntity target)
    {
        if(com.projectseele.world.TvEncounterRulesR45.missionRamielAnchor(this)!=null
                &&!com.projectseele.world.TvEncounterRulesR45.missionBeamAllowed(this))return;
        Vec3 from = this.beamOrigin();
        Vec3 dir = target.getEyePosition().subtract(from).normalize();
        Vec3 farEnd = from.add(dir.scale(this.effectiveBeamRangeR45()));
        BlockHitResult blockHit = this.level().clip(
                new ClipContext(from, farEnd, ClipContext.Block.COLLIDER, ClipContext.Fluid.NONE, this));
        Vec3 end = blockHit.getLocation();

        // The beam detonates on the first body it meets (an EVA blocks it
        // with its bulk) instead of lancing through to the far terrain.
        EntityHitResult bodyHit = com.projectseele.physics.CombatEntityQueryR44.ray(this.level(),from,end,.3,
                e -> e != this && e.isAlive()
                        && !(e instanceof Angel)
                        && !(e.getVehicle() instanceof EvaUnit01Entity));
        if (bodyHit != null)
        {
            end = bodyHit.getLocation();
        }
        // Clip against the same measured physical shield used by the mission gate.
        // Missing geometry never creates an imaginary shield or alters ordinary beams.
        var shieldHit=com.projectseele.world.TvEncounterRulesR45.missionShieldContactR45(this,from,end);
        if(shieldHit.isPresent())end=shieldHit.get();
        final Vec3 impact = end;

        for (LivingEntity victim : com.projectseele.physics.CombatEntityQueryR44.candidates(this.level(),
                new AABB(from, end).inflate(1.0D), e -> e != this && e.isAlive()))
        {
            // The entry plug shields the pilot; the Unit takes the hit instead.
            if (victim.isPassenger()&&victim.getRootVehicle() instanceof EvaUnit01Entity)
            {
                continue;
            }
            Optional<Vec3> hit = com.projectseele.physics.CombatBodyContacts.clip(victim,from,end,.3);
            if (hit.isPresent())
            {
                victim.hurt(this.damageSources().mobAttack(this),
                        SeeleConfig.BEAM_DAMAGE.get().floatValue());
            }
        }

        this.level().explode(this, end.x, end.y, end.z,
                SeeleConfig.BEAM_EXPLOSION_RADIUS.get().floatValue(), Level.ExplosionInteraction.MOB);
        // The shell stays open after the shot — this is the sniping window.
        this.exposedTimer = EXPOSED_AFTER_FIRE_TICKS;
        this.setExposed(true);

        // The beam itself is rendered client-side from this synced state; the
        // impact gets the full nuke treatment: flash + fireball + cross light
        // client-side, mushroom column via server particles.
        this.entityData.set(DATA_BEAM_END, new Vector3f((float) end.x, (float) end.y, (float) end.z));
        this.entityData.set(DATA_BEAM_TICKS, BEAM_RENDER_TICKS);
        if (this.level() instanceof ServerLevel serverLevel)
        {
            SeeleNetwork.CHANNEL.send(
                    PacketDistributor.NEAR.with(() -> new PacketDistributor.TargetPoint(
                            impact.x, impact.y, impact.z, 256.0D, serverLevel.dimension())),
                    new ClientboundNukeFxPacket(impact.x, impact.y, impact.z, 2.6F, true));
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
    }

    // ----- boss bar -----

    @Override
    public void startSeenByPlayer(ServerPlayer player)
    {
        super.startSeenByPlayer(player);
        this.bossEvent.addPlayer(player);
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
            return this.ramiel.beamCooldown <= 0
                    && !this.ramiel.isDrilling()
                    && target != null && target.isAlive()
                    && this.ramiel.distanceToSqr(target) < range * range
                    && this.ramiel.beamLineOfSightR45(target);
        }

        @Override
        public boolean canContinueToUse()
        {
            LivingEntity target = this.ramiel.getTarget();
            return this.chargeTicks > 0 && target != null && target.isAlive();
        }

        @Override
        public boolean requiresUpdateEveryTick()
        {
            return true;
        }

        @Override
        public void start()
        {
            this.chargeTicks = this.ramiel.isEnraged()
                    ? SeeleConfig.BEAM_CHARGE_TICKS_ENRAGED.get()
                    : SeeleConfig.BEAM_CHARGE_TICKS.get();
            this.ramiel.setCharging(true);
            this.ramiel.playSound(ModSounds.BEAM_CHARGE.get(), 3.0F,
                    this.ramiel.isEnraged() ? 1.35F : 1.0F);
        }

        @Override
        public void stop()
        {
            this.ramiel.setCharging(false);
            this.ramiel.beamCooldown = SeeleConfig.BEAM_COOLDOWN_TICKS.get();
            // Interrupted before firing: seal the shell again immediately.
            if (this.ramiel.exposedTimer <= 0)
            {
                this.ramiel.setExposed(false);
            }
        }

        @Override
        public void tick()
        {
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

            if (--this.chargeTicks <= 0)
            {
                this.ramiel.fireBeam(target);
            }
            else if (this.chargeTicks == EXPOSE_CHARGE_WINDOW)
            {
                // The shell parts for the final stretch of the charge.
                this.ramiel.setExposed(true);
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
            if (this.drillTicks % 20 == 1)
            {
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
}
