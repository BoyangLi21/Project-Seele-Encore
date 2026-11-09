package com.projectseele.entity;

import java.util.UUID;

import com.projectseele.fx.AtFieldFX;
import com.projectseele.fx.CrossExplosionFX;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EntityType;
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
import software.bernie.geckolib.core.animation.AnimationController;
import software.bernie.geckolib.core.animation.RawAnimation;
import software.bernie.geckolib.util.GeckoLibUtil;

/** Seventh Angel: divides into two bodies that must be downed in the same five-second window. */
public class IsrafelEntity extends Monster implements Angel, GeoEntity
{
    private static final RawAnimation ANIM_IDLE = RawAnimation.begin().thenLoop("animation.entity_israfel.idle_1");
    private static final RawAnimation ANIM_WALK = RawAnimation.begin().thenLoop("animation.entity_israfel.move");
    private final AnimatableInstanceCache geoCache = GeckoLibUtil.createInstanceCache(this);
    private float atField = 850.0F;
    @Override public float getAtField(){return atField;}
    private boolean split;
    private boolean resolved;
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
    protected void registerGoals()
    {
        this.goalSelector.addGoal(2, new MeleeAttackGoal(this, 1.0D, true));
        this.targetSelector.addGoal(1, new NearestAttackableTargetGoal<>(this, EvaUnit01Entity.class, true));
        this.targetSelector.addGoal(2, new NearestAttackableTargetGoal<>(this, Player.class, true));
    }

    @Override
    public void tick()
    {
        super.tick();
        if (this.downedTicks > 0 && --this.downedTicks == 0 && !this.resolved)
        {
            this.setNoAi(false);
            this.setHealth(this.getMaxHealth() * 0.45F);
            this.atField = 240.0F;
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
                    this.resolved = true;
                    twin.resolved = true;
                    twin.setNoAi(false);
                    twin.hurt(source, Float.MAX_VALUE);
                    return super.hurt(source, Float.MAX_VALUE);
                }
                this.setHealth(1.0F);
                this.downedTicks = 100;
                this.playSound(com.projectseele.registry.ModSounds.EVA_LAND.get(),3.0F,.8F);
                this.setNoAi(true);
                this.setDeltaMovement(Vec3.ZERO);
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
        twin.split = true;
        twin.setHealth(twin.getMaxHealth() * 0.5F);
        twin.moveTo(this.getX() + 8.0D, this.getY(), this.getZ(), this.getYRot() + 12.0F, 0.0F);
        this.playSound(com.projectseele.registry.ModSounds.EVA_AT_TEAR.get(),3.0F,.8F);
        this.twinId = twin.getUUID();
        twin.twinId = this.getUUID();
        twin.setPersistenceRequired();
        server.addFreshEntity(twin);
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
        this.twinId = tag.hasUUID("IsrafelTwin") ? tag.getUUID("IsrafelTwin") : null;
    }

    @Override
    public void registerControllers(AnimatableManager.ControllerRegistrar controllers)
    {
        controllers.add(new AnimationController<>(this, "base", 6, state ->
                state.setAndContinue(state.isMoving() ? ANIM_WALK : ANIM_IDLE)));
    }

    @Override
    public AnimatableInstanceCache getAnimatableInstanceCache()
    {
        return this.geoCache;
    }
}
