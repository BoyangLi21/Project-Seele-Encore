package com.projectseele.entity;

import java.util.UUID;

import com.projectseele.fx.CrossExplosionFX;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.syncher.EntityDataAccessor;
import net.minecraft.network.syncher.EntityDataSerializers;
import net.minecraft.network.syncher.SynchedEntityData;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.util.Mth;
import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.entity.ai.attributes.AttributeSupplier;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.entity.ai.goal.target.NearestAttackableTargetGoal;
import net.minecraft.world.entity.monster.Monster;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.Vec3;
import software.bernie.geckolib.animatable.GeoEntity;
import software.bernie.geckolib.core.animatable.instance.AnimatableInstanceCache;
import software.bernie.geckolib.core.animation.AnimatableManager;
import software.bernie.geckolib.core.animation.AnimationController;
import software.bernie.geckolib.core.animation.RawAnimation;
import software.bernie.geckolib.core.object.PlayState;
import software.bernie.geckolib.util.GeckoLibUtil;
import org.jetbrains.annotations.Nullable;

/** White SEELE mass-production unit. It revives until an EVA knife destroys its exposed core. */
public class MassProductionEvaEntity extends Monster implements GeoEntity
{
    public static final int VISUAL_NORMAL = 0;
    public static final int VISUAL_IDLE = 1;
    public static final int VISUAL_MOVE = 2;
    public static final int VISUAL_ATTACK = 3;
    public static final int VISUAL_REVIVE = 4;
    public static final int VISUAL_RITUAL = 5;

    private static final EntityDataAccessor<Integer> DATA_VISUAL_POSE =
            SynchedEntityData.defineId(MassProductionEvaEntity.class, EntityDataSerializers.INT);
    private static final EntityDataAccessor<Integer> DATA_REVIVE_TICKS =
            SynchedEntityData.defineId(MassProductionEvaEntity.class, EntityDataSerializers.INT);
    private static final RawAnimation ANIM_IDLE = RawAnimation.begin().thenLoop("animation.entity_mp.idle_1");
    private static final RawAnimation ANIM_WALK = RawAnimation.begin().thenLoop("animation.entity_mp.move");
    private static final RawAnimation ANIM_RITUAL = RawAnimation.begin().thenLoop("animation.entity_mp.ritual");
    private static final RawAnimation ANIM_REVIVE = RawAnimation.begin().thenLoop("animation.entity_mp.revive");
    private static final RawAnimation ANIM_VISUAL_ATTACK =
            RawAnimation.begin().thenLoop("animation.entity_mp.visual_attack");
    private static final RawAnimation ANIM_ATTACK = RawAnimation.begin().thenPlay("animation.entity_mp.attack");
    private final AnimatableInstanceCache geoCache = GeckoLibUtil.createInstanceCache(this);
    private boolean coreBroken;
    private int attackCooldown;
    @Nullable
    private UUID ritualImpactId;
    private int ritualNode = -1;
    private boolean ritualPreview;

    public MassProductionEvaEntity(EntityType<? extends MassProductionEvaEntity> type, Level level)
    {
        super(type, level);
        this.setNoGravity(true);
        this.setMaxUpStep(2.5F);
    }

    public static AttributeSupplier.Builder createAttributes()
    {
        return Mob.createMobAttributes()
                .add(Attributes.MAX_HEALTH, 420.0D)
                .add(Attributes.ARMOR, 12.0D)
                .add(Attributes.ATTACK_DAMAGE, 34.0D)
                .add(Attributes.MOVEMENT_SPEED, 0.32D)
                .add(Attributes.FLYING_SPEED, 0.40D)
                .add(Attributes.KNOCKBACK_RESISTANCE, 1.0D)
                .add(Attributes.FOLLOW_RANGE, 128.0D);
    }

    @Override
    protected void defineSynchedData()
    {
        super.defineSynchedData();
        this.entityData.define(DATA_VISUAL_POSE, VISUAL_NORMAL);
        this.entityData.define(DATA_REVIVE_TICKS, 0);
    }

    @Override
    public void addAdditionalSaveData(CompoundTag tag)
    {
        super.addAdditionalSaveData(tag);
        tag.putInt("VisualPose", this.getVisualPose());
        tag.putInt("ReviveTicks", this.getReviveTicks());
        tag.putBoolean("CoreBroken", this.coreBroken);
        if (this.ritualImpactId != null)
        {
            tag.putUUID("SeeleImpactId", this.ritualImpactId);
            tag.putInt("SeeleImpactNode", this.ritualNode);
            tag.putBoolean("SeeleImpactPreview", this.ritualPreview);
        }
    }

    @Override
    public void readAdditionalSaveData(CompoundTag tag)
    {
        super.readAdditionalSaveData(tag);
        this.setVisualPose(tag.getInt("VisualPose"));
        this.setReviveTicks(tag.getInt("ReviveTicks"));
        this.coreBroken = tag.getBoolean("CoreBroken");
        this.ritualImpactId = tag.hasUUID("SeeleImpactId")
                ? tag.getUUID("SeeleImpactId") : null;
        this.ritualNode = this.ritualImpactId == null ? -1
                : Mth.clamp(tag.getInt("SeeleImpactNode"), 0, 9);
        this.ritualPreview = this.ritualImpactId != null
                && tag.getBoolean("SeeleImpactPreview");
    }

    @Override
    protected void registerGoals()
    {
        this.targetSelector.addGoal(1, new NearestAttackableTargetGoal<>(this, EvaUnit01Entity.class, true));
    }

    @Override
    public void tick()
    {
        super.tick();
        this.setNoGravity(true);
        int reviveTicks = this.getReviveTicks();
        if (reviveTicks > 0)
        {
            this.setDeltaMovement(Vec3.ZERO);
            if (!this.level().isClientSide && reviveTicks == 1)
            {
                this.setReviveTicks(0);
                this.setHealth(this.getMaxHealth());
                if (this.level() instanceof ServerLevel server)
                {
                    CrossExplosionFX.spawn(server, this.position(), 0.22F);
                }
            }
            else if (!this.level().isClientSide)
            {
                this.setReviveTicks(reviveTicks - 1);
            }
            return;
        }
        LivingEntity target = this.getTarget();
        if (target == null || !target.isAlive())
        {
            return;
        }
        Vec3 delta = target.getBoundingBox().getCenter().subtract(this.position().add(0.0D, 9.0D, 0.0D));
        double distance = delta.length();
        if (distance > 7.0D)
        {
            this.setDeltaMovement(this.getDeltaMovement().scale(0.72D)
                    .add(delta.normalize().scale(distance > 30.0D ? 0.12D : 0.07D)));
        }
        if (distance < 12.0D && --this.attackCooldown <= 0)
        {
            this.attackCooldown = 24;
            this.swing(InteractionHand.MAIN_HAND, true);
            this.triggerAnim("strike", "attack");
            target.hurt(this.damageSources().mobAttack(this), 34.0F);
            target.push(delta.x * 0.05D, 0.3D, delta.z * 0.05D);
        }
    }

    @Override
    public boolean hurt(DamageSource source, float amount)
    {
        if (this.isReviving())
        {
            return false;
        }
        if (source.getEntity() instanceof EvaUnit01Entity eva
                && (eva.getWeapon() == EvaUnit01Entity.WEAPON_KNIFE
                    || eva.getWeapon() == EvaUnit01Entity.WEAPON_LANCE)
                && this.getHealth() <= this.getMaxHealth() * 0.28F)
        {
            this.coreBroken = true;
        }
        if (!this.coreBroken && amount >= this.getHealth())
        {
            this.setHealth(1.0F);
            this.setReviveTicks(120);
            return true;
        }
        return super.hurt(source, amount);
    }

    public boolean isReviving()
    {
        return this.getReviveTicks() > 0;
    }

    public int getVisualPose()
    {
        return this.entityData.get(DATA_VISUAL_POSE);
    }

    /** Development/ritual pose replicated to every tracking client. */
    public void setVisualPose(int pose)
    {
        this.entityData.set(DATA_VISUAL_POSE,
                Mth.clamp(pose, VISUAL_NORMAL, VISUAL_RITUAL));
    }


    private int getReviveTicks()
    {
        return this.entityData.get(DATA_REVIVE_TICKS);
    }

    private void setReviveTicks(int ticks)
    {
        this.entityData.set(DATA_REVIVE_TICKS, Math.max(0, ticks));
    }

    /** Inert vessels parked on the Sephirot during the Third Impact tableau. */
    public boolean isRitualFormation()
    {
        return this.getVisualPose() == VISUAL_RITUAL;
    }

    /** Persistent ownership makes Third-Impact recovery adopt instead of clone vessels. */
    public void assignRitualOwner(UUID impactId, int node, boolean preview)
    {
        this.ritualImpactId = impactId;
        this.ritualNode = Mth.clamp(node, 0, 9);
        this.ritualPreview = preview;
    }

    public boolean isRitualOwnedBy(UUID impactId, int node)
    {
        return impactId.equals(this.ritualImpactId) && this.ritualNode == node;
    }

    public boolean isRitualOwnedBy(UUID impactId)
    {
        return impactId.equals(this.ritualImpactId);
    }

    public boolean isRitualPreview()
    {
        return this.ritualPreview;
    }

    public boolean hasRitualOwner()
    {
        return this.ritualImpactId != null;
    }

    @Override
    public void registerControllers(AnimatableManager.ControllerRegistrar controllers)
    {
        controllers.add(new AnimationController<>(this, "base", 6, state ->
        {
            switch (this.getVisualPose())
            {
                case VISUAL_IDLE:
                    return state.setAndContinue(ANIM_IDLE);
                case VISUAL_MOVE:
                    return state.setAndContinue(ANIM_WALK);
                case VISUAL_ATTACK:
                    return state.setAndContinue(ANIM_VISUAL_ATTACK);
                case VISUAL_REVIVE:
                    return state.setAndContinue(ANIM_REVIVE);
                case VISUAL_RITUAL:
                    return state.setAndContinue(ANIM_RITUAL);
                default:
                    break;
            }
            if (this.isReviving())
            {
                return state.setAndContinue(ANIM_REVIVE);
            }
            return state.setAndContinue(state.isMoving() ? ANIM_WALK : ANIM_IDLE);
        }));
        controllers.add(new AnimationController<>(this, "strike", 2, state -> PlayState.STOP)
                .triggerableAnim("attack", ANIM_ATTACK));
    }

    @Override
    public AnimatableInstanceCache getAnimatableInstanceCache()
    {
        return this.geoCache;
    }
}
