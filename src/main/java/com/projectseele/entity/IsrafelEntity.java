package com.projectseele.entity;

import java.util.UUID;

import com.projectseele.ProjectSeele;
import com.projectseele.config.SeeleConfig;
import com.projectseele.fx.AtFieldFX;
import com.projectseele.fx.CrossExplosionFX;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.syncher.EntityDataAccessor;
import net.minecraft.network.syncher.EntityDataSerializers;
import net.minecraft.network.syncher.SynchedEntityData;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.entity.ai.attributes.AttributeSupplier;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.entity.ai.goal.MeleeAttackGoal;
import net.minecraft.world.entity.ai.goal.target.NearestAttackableTargetGoal;
import net.minecraft.world.entity.monster.Monster;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.Vec3;
import software.bernie.geckolib.animatable.GeoEntity;
import software.bernie.geckolib.core.animatable.instance.AnimatableInstanceCache;
import software.bernie.geckolib.core.animation.AnimatableManager;
import software.bernie.geckolib.util.GeckoLibUtil;

/**
 * Seventh Angel (episode 9): cut down once, it divides into two halves; a half brought down alone waits for its
 * partner for the sync window and then rises again, mended by the other. Only both halves falling inside the window
 * kill it. The window, health and field are in SeeleConfig ("israfel").
 * <p>
 * R66: the halves are numbered (1 and 2, for their colours and for which unit takes which half), each fights a
 * different unit when there are two, and a half carries the mission tags and owner of the original so the operation
 * owns both.
 */
public class IsrafelEntity extends Monster implements Angel, GeoEntity
{
    public static final String MISSION_TAG = "seele_tv_israfel_r66";
    /** 0: whole; 1 and 2: the two halves. */
    private static final EntityDataAccessor<Integer> HALF = SynchedEntityData.defineId(IsrafelEntity.class, EntityDataSerializers.INT);
    private static final EntityDataAccessor<Boolean> DOWNED = SynchedEntityData.defineId(IsrafelEntity.class, EntityDataSerializers.BOOLEAN);
    private final AnimatableInstanceCache geoCache = GeckoLibUtil.createInstanceCache(this);
    private float atField = 850.0F;
    @Override public float getAtField(){return atField;}
    private boolean split;
    private boolean resolved;
    private boolean configured;
    private boolean heldByMission;
    private int downedTicks;
    private UUID twinId;

    public IsrafelEntity(EntityType<? extends IsrafelEntity> type, Level level)
    {
        super(type, level);
        this.setMaxUpStep(2.2F);
    }

    public static AttributeSupplier.Builder createAttributes()
    {
        return Mob.createMobAttributes()
                .add(Attributes.MAX_HEALTH, 720.0D)
                .add(Attributes.ARMOR, 9.0D)
                .add(Attributes.ATTACK_DAMAGE, 38.0D)
                .add(Attributes.MOVEMENT_SPEED, 0.31D)
                .add(Attributes.FOLLOW_RANGE, 96.0D)
                .add(Attributes.KNOCKBACK_RESISTANCE, 1.0D);
    }

    @Override
    protected void defineSynchedData()
    {
        super.defineSynchedData();
        this.entityData.define(HALF, 0);
        this.entityData.define(DOWNED, false);
    }

    @Override
    protected void registerGoals()
    {
        this.goalSelector.addGoal(2, new MeleeAttackGoal(this, 1.0D, true));
        this.targetSelector.addGoal(1, new NearestAttackableTargetGoal<>(this, EvaUnit01Entity.class, true));
        this.targetSelector.addGoal(2, new NearestAttackableTargetGoal<>(this, Player.class, true));
    }

    public int halfR66(){return this.entityData.get(HALF);}
    public boolean downedR66(){return this.entityData.get(DOWNED);}
    public boolean splitR66(){return this.split;}
    /** The half a unit of the given rank (0, 1, ...) among the sortie should take; the whole Angel before the split. */
    public IsrafelEntity pairTargetR66(int rank)
    {
        IsrafelEntity twin = getTwin();
        if (!this.split || twin == null || !twin.isAlive()) return this;
        int wanted = 1 + Math.floorMod(rank, 2);
        return this.halfR66() == wanted ? this : twin;
    }
    public IsrafelEntity twinR66(){return getTwin();}

    private void configureR66()
    {
        if (this.configured) return;
        this.configured = true;
        var health = this.getAttribute(Attributes.MAX_HEALTH);
        double max = SeeleConfig.ISRAFEL_MAX_HEALTH.get();
        if (health != null && Math.abs(health.getBaseValue() - max) > 1e-3)
        {
            float share = this.getHealth() / this.getMaxHealth();
            health.setBaseValue(max);
            this.setHealth((float) (max * share));
        }
        if (!this.split && this.tickCount < 5 && this.atField == 850.0F) this.atField = (float) (double) SeeleConfig.ISRAFEL_AT_FIELD.get();
    }

    @Override
    public void tick()
    {
        super.tick();
        if (this.level().isClientSide) return;
        configureR66();
        if (this.downedTicks > 0 && --this.downedTicks == 0 && !this.resolved)
        {
            // the window passed alone: the other half makes this one whole again
            this.setNoAi(false);
            this.entityData.set(DOWNED, false);
            this.setHealth(this.getMaxHealth() * SeeleConfig.ISRAFEL_REVIVE_FRACTION.get().floatValue());
            this.atField = (float) (double) SeeleConfig.ISRAFEL_REVIVE_FIELD.get();
            ProjectSeele.LOGGER.info("R66 ISRAFEL half {} rose again: health {} field {}", halfR66(), this.getHealth(), this.atField);
        }
        IsrafelEntity twin = getTwin();
        if (this.heldByMission && twin != null && !twin.isNoAi() && twin.downedTicks == 0 && this.downedTicks == 0)
        {
            this.heldByMission = false;
            this.setNoAi(false);
        }
        // the halves fight different units when there are two to fight
        if (this.split && twin != null && twin.isAlive() && this.tickCount % 20 == 0 && this.getTarget() != null
                && this.getTarget() == twin.getTarget() && this.halfR66() == 2)
        {
            LivingEntity shared = this.getTarget();
            var other = this.level().getEntitiesOfClass(EvaUnit01Entity.class, this.getBoundingBox().inflate(96),
                    e -> e.isAlive() && e != shared && e.getPilotEntity() != null)
                    .stream().min(java.util.Comparator.comparingDouble(this::distanceToSqr)).orElse(null);
            if (other != null) this.setTarget(other);
        }
    }

    @Override
    public boolean doHurtTarget(Entity target)
    {
        boolean accepted = super.doHurtTarget(target);
        CombatFoleyR36.angelSwing(this,target.position().add(0.0D,target.getBbHeight()*.5D,0.0D),1.6F,.72F);
        if(accepted&&target instanceof net.minecraft.world.entity.LivingEntity victim)
            CombatFoleyR36.impact(this,victim,victim.getBoundingBox().getCenter(),false,false);
        return accepted;
    }

    @Override
    public boolean hurt(DamageSource source, float amount)
    {
        if (this.level().isClientSide) return super.hurt(source, amount);
        if (this.downedTicks > 0 || this.resolved)
        {
            return this.resolved && super.hurt(source, amount);
        }
        if (this.atField > 0.0F && !com.projectseele.combat.AtFieldRules.bypassesAtField(source))
        {
            if (source.getEntity() instanceof EvaUnit01Entity eva && eva.isMeleeWeapon())
            {
                float fieldBefore=this.atField;
                this.atField = Math.max(0.0F, this.atField - amount);
                CombatFoleyR36.fieldBroken(this,fieldBefore,this.atField);
                if (this.level() instanceof ServerLevel server)
                {
                    AtFieldFX.ripple(server, this.getBoundingBox().getCenter(), eva.getForward());
                }
                return true;
            }
            if (amount > 0.0F && this.level() instanceof ServerLevel server)
            {
                AtFieldFX.blocked(server, this, source);
            }
            return false;
        }
        if (!this.split && (amount >= this.getHealth()
                || this.getHealth() - amount <= this.getMaxHealth() * 0.5F))
        {
            splitIntoTwins();
            return true;
        }
        if (this.split && amount >= this.getHealth())
        {
            IsrafelEntity twin = getTwin();
            if (twin != null && twin.isAlive())
            {
                if (twin.downedTicks > 0)
                {
                    int window = SeeleConfig.ISRAFEL_SYNC_WINDOW_TICKS.get();
                    ProjectSeele.LOGGER.info("R66 ISRAFEL sync kill: half {} fell {} ticks after half {}", halfR66(), window - twin.downedTicks, twin.halfR66());
                    this.resolved = true;
                    twin.resolved = true;
                    twin.setNoAi(false);
                    twin.hurt(source, Float.MAX_VALUE);
                    return super.hurt(source, Float.MAX_VALUE);
                }
                this.setHealth(1.0F);
                this.downedTicks = SeeleConfig.ISRAFEL_SYNC_WINDOW_TICKS.get();
                this.entityData.set(DOWNED, true);
                this.playSound(com.projectseele.registry.ModSounds.EVA_LAND.get(),3.0F,.8F);
                this.setNoAi(true);
                this.setDeltaMovement(Vec3.ZERO);
                ProjectSeele.LOGGER.info("R66 ISRAFEL half {} down; window {} ticks for half {}", halfR66(), this.downedTicks, twin.halfR66());
                return true;
            }
        }
        return super.hurt(source, amount);
    }

    private void splitIntoTwins()
    {
        if (!(this.level() instanceof ServerLevel server))
        {
            return;
        }
        this.split = true;
        this.setHealth(this.getMaxHealth() * 0.5F);
        IsrafelEntity twin = com.projectseele.registry.ModEntities.ISRAFEL.get().create(server);
        if (twin == null)
        {
            return;
        }
        twin.configured = true;
        var twinHealth = twin.getAttribute(Attributes.MAX_HEALTH);
        if (twinHealth != null) twinHealth.setBaseValue(this.getMaxHealth());
        twin.split = true;
        twin.setHealth(twin.getMaxHealth() * 0.5F);
        // the field broken on the whole stays broken on both halves
        twin.atField = this.atField;
        this.entityData.set(HALF, 1);
        twin.entityData.set(HALF, 2);
        // the halves step apart sideways from the cut
        Vec3 side = Vec3.directionFromRotation(0, this.getYRot() + 90).scale(9);
        this.move(net.minecraft.world.entity.MoverType.SELF, side.scale(-.5));
        twin.moveTo(this.getX() + side.x, this.getY(), this.getZ() + side.z, this.getYRot() + 12.0F, 0.0F);
        for (String tag : this.getTags()) twin.addTag(tag);
        twin.getPersistentData().merge(this.getPersistentData().copy());
        this.playSound(com.projectseele.registry.ModSounds.EVA_AT_TEAR.get(),3.0F,.8F);
        this.twinId = twin.getUUID();
        twin.twinId = this.getUUID();
        twin.setPersistenceRequired();
        twin.setTarget(this.getTarget());
        server.addFreshEntity(twin);
        ProjectSeele.LOGGER.info("R66 ISRAFEL split: halves {} and {} with {} health each, field {}", this.getUUID(), twin.getUUID(), this.getHealth(), this.atField);
    }

    private IsrafelEntity getTwin()
    {
        if (this.twinId == null || !(this.level() instanceof ServerLevel server))
        {
            return null;
        }
        Entity entity = server.getEntity(this.twinId);
        return entity instanceof IsrafelEntity twin ? twin : null;
    }

    /** The operation is paused (failure): the other half stops too until the first moves again. */
    public void holdTwinR66()
    {
        IsrafelEntity twin = getTwin();
        if (twin == null) return;
        twin.heldByMission = true;
        twin.setNoAi(true);
        twin.setTarget(null);
        twin.getNavigation().stop();
    }

    /** The operation is called off: the half the mission did not spawn goes with the one it did. */
    public void discardTwinR66()
    {
        IsrafelEntity twin = getTwin();
        if (twin != null) twin.discard();
    }

    @Override
    public void die(DamageSource source)
    {
        if (this.level() instanceof ServerLevel server)
        {
            CrossExplosionFX.spawn(server, this.position(), 1.15F);
        }
        super.die(source);
    }

    @Override
    public void addAdditionalSaveData(CompoundTag tag)
    {
        super.addAdditionalSaveData(tag);
        tag.putBoolean("IsrafelSplit", this.split);
        tag.putBoolean("IsrafelResolved", this.resolved);
        tag.putInt("IsrafelDowned", this.downedTicks);
        tag.putFloat("IsrafelAtField", this.atField);
        tag.putInt("IsrafelHalfR66", this.halfR66());
        tag.putBoolean("IsrafelHeldR66", this.heldByMission);
        if (this.twinId != null)
        {
            tag.putUUID("IsrafelTwin", this.twinId);
        }
    }

    @Override
    public void readAdditionalSaveData(CompoundTag tag)
    {
        super.readAdditionalSaveData(tag);
        this.split = tag.getBoolean("IsrafelSplit");
        this.resolved = tag.getBoolean("IsrafelResolved");
        this.downedTicks = tag.getInt("IsrafelDowned");
        this.atField = tag.contains("IsrafelAtField") ? tag.getFloat("IsrafelAtField") : 850.0F;
        this.entityData.set(HALF, tag.getInt("IsrafelHalfR66"));
        this.entityData.set(DOWNED, this.downedTicks > 0);
        this.heldByMission = tag.getBoolean("IsrafelHeldR66");
        this.twinId = tag.hasUUID("IsrafelTwin") ? tag.getUUID("IsrafelTwin") : null;
        // a saved Angel keeps the field it had
        this.configured = tag.contains("IsrafelAtField");
    }

    @Override
    public void registerControllers(AnimatableManager.ControllerRegistrar controllers) {}

    @Override
    public AnimatableInstanceCache getAnimatableInstanceCache()
    {
        return this.geoCache;
    }
}
