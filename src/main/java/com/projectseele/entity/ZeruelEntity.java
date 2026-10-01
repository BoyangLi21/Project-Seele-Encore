package com.projectseele.entity;

import com.projectseele.fx.AtFieldFX;
import com.projectseele.fx.CrossExplosionFX;
import com.projectseele.network.ClientboundCannonBeamPacket;
import com.projectseele.network.ClientboundNukeFxPacket;
import com.projectseele.network.SeeleNetwork;
import net.minecraft.core.BlockPos;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.entity.ai.attributes.AttributeSupplier;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.entity.ai.goal.target.NearestAttackableTargetGoal;
import net.minecraft.world.entity.monster.Monster;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.Level.ExplosionInteraction;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.network.PacketDistributor;

/** Fourteenth Angel: extreme A.T. Field, paper-arm cleaves and twin-eye annihilation beam. */
public class ZeruelEntity extends Monster implements Angel, SiegeAnchorAware, software.bernie.geckolib.animatable.GeoEntity
{
    private final software.bernie.geckolib.core.animatable.instance.AnimatableInstanceCache geoCache=software.bernie.geckolib.util.GeckoLibUtil.createInstanceCache(this);
    @Override public software.bernie.geckolib.core.animatable.instance.AnimatableInstanceCache getAnimatableInstanceCache(){return geoCache;}
    @Override public void registerControllers(software.bernie.geckolib.core.animation.AnimatableManager.ControllerRegistrar controllers)
    {
        controllers.add(new software.bernie.geckolib.core.animation.AnimationController<>(this,"base",6,state->state.setAndContinue(
                software.bernie.geckolib.core.animation.RawAnimation.begin().thenLoop(state.isMoving()?"animation.Zeruel.move":"animation.Zeruel.idle"))));
    }
    private float atField = 2400.0F;
    @Override public float getAtField(){return atField;}
    private int armCooldown = 28;
    private int beamCooldown = 90;
    private BlockPos siegeBeacon;

    public ZeruelEntity(EntityType<? extends ZeruelEntity> type, Level level)
    {
        super(type, level);
        this.setMaxUpStep(3.0F);
    }

    public static AttributeSupplier.Builder createAttributes()
    {
        return Mob.createMobAttributes()
                .add(Attributes.MAX_HEALTH, 1500.0D)
                .add(Attributes.ARMOR, 16.0D)
                .add(Attributes.ATTACK_DAMAGE, 65.0D)
                .add(Attributes.MOVEMENT_SPEED, 0.22D)
                .add(Attributes.FOLLOW_RANGE, 128.0D)
                .add(Attributes.KNOCKBACK_RESISTANCE, 1.0D);
    }

    @Override
    protected void registerGoals()
    {
        this.targetSelector.addGoal(1, new NearestAttackableTargetGoal<>(this, EvaUnit01Entity.class, true));
        this.targetSelector.addGoal(2, new NearestAttackableTargetGoal<>(this, Player.class, true));
    }

    @Override
    public void tick()
    {
        super.tick();
        LivingEntity target = this.getTarget();
        if (target == null || !target.isAlive())
        {
            if (this.siegeBeacon != null)
            {
                Vec3 anchor = Vec3.atCenterOf(this.siegeBeacon)
                        .subtract(this.position().add(0.0D, 12.0D, 0.0D));
                Vec3 horizontal = new Vec3(anchor.x, 0.0D, anchor.z);
                if (horizontal.lengthSqr() > 100.0D)
                {
                    this.setDeltaMovement(this.getDeltaMovement().scale(0.70D)
                            .add(horizontal.normalize().scale(0.075D)));
                }
            }
            return;
        }
        Vec3 delta = target.getBoundingBox().getCenter().subtract(this.position().add(0.0D, 12.0D, 0.0D));
        double distance = delta.length();
        if (distance > 16.0D)
        {
            Vec3 horizontal = new Vec3(delta.x, 0.0D, delta.z).normalize();
            this.setDeltaMovement(this.getDeltaMovement().scale(0.70D).add(horizontal.scale(0.075D)));
        }
        if (this.level().isClientSide)
        {
            return;
        }
        if (--this.armCooldown <= 0 && distance < 35.0D)
        {
            this.armCooldown = 42;
            paperArmSweep(target, delta);
        }
        if (--this.beamCooldown <= 0 && distance >= 28.0D && distance < 110.0D && this.hasLineOfSight(target))
        {
            this.beamCooldown = 120;
            eyeBeam(target);
        }
    }

    private void paperArmSweep(LivingEntity target, Vec3 toward)
    {
        Vec3 forward = toward.normalize();
        Vec3 center = this.position().add(0.0D, 12.0D, 0.0D).add(forward.scale(15.0D));
        AABB zone = new AABB(center, center).inflate(18.0D, 10.0D, 18.0D);
        for (LivingEntity victim : com.projectseele.physics.CombatEntityQueryR44.overlap(this.level(),zone,
                e -> e != this && (e instanceof EvaUnit01Entity || e instanceof Player)))
        {
            Vec3 contact=com.projectseele.physics.CombatBodyContacts.nearestSurfacePoint(victim,center);
            if(this.level().clip(new net.minecraft.world.level.ClipContext(this.position().add(0,12,0),contact,
                    net.minecraft.world.level.ClipContext.Block.COLLIDER,net.minecraft.world.level.ClipContext.Fluid.NONE,this)).getType()!=net.minecraft.world.phys.HitResult.Type.MISS)continue;
            victim.hurt(this.damageSources().mobAttack(this), 72.0F);
            Vec3 push = victim.position().subtract(this.position()).normalize().scale(2.2D);
            victim.push(push.x, 0.8D, push.z);
        }
    }

    private void eyeBeam(LivingEntity target)
    {
        if (!(this.level() instanceof ServerLevel server))
        {
            return;
        }
        Vec3 from = this.position().add(0.0D, 22.0D, 0.0D);
        Vec3 far=target.getBoundingBox().getCenter();
        var wall=server.clip(new net.minecraft.world.level.ClipContext(from,far,net.minecraft.world.level.ClipContext.Block.COLLIDER,net.minecraft.world.level.ClipContext.Fluid.NONE,this));
        Vec3 impact=wall.getLocation();
        var hit=com.projectseele.physics.CombatEntityQueryR44.ray(server,from,impact,.3,
                entity->entity!=this&&entity.isAlive()&&(entity instanceof EvaUnit01Entity||entity instanceof Player));
        if(hit!=null)impact=hit.getLocation();
        SeeleNetwork.CHANNEL.send(PacketDistributor.TRACKING_ENTITY_AND_SELF.with(() -> this),
                new ClientboundCannonBeamPacket(from.x, from.y, from.z, impact.x, impact.y, impact.z));
        SeeleNetwork.CHANNEL.send(PacketDistributor.TRACKING_ENTITY_AND_SELF.with(() -> this),
                new ClientboundNukeFxPacket(impact.x, impact.y, impact.z, 2.2F, true));
        if(hit!=null)hit.getEntity().hurt(this.damageSources().mobAttack(this),125.0F);
        server.explode(this, impact.x, impact.y, impact.z, 10.0F, ExplosionInteraction.MOB);
    }

    @Override
    public void setSiegeBeacon(BlockPos beacon)
    {
        this.siegeBeacon = beacon == null ? null : beacon.immutable();
    }

    @Override
    public void addAdditionalSaveData(CompoundTag tag)
    {
        super.addAdditionalSaveData(tag);
        if (this.siegeBeacon != null)
        {
            tag.putLong("SiegeBeacon", this.siegeBeacon.asLong());
        }
    }

    @Override
    public void readAdditionalSaveData(CompoundTag tag)
    {
        super.readAdditionalSaveData(tag);
        this.siegeBeacon = tag.contains("SiegeBeacon")
                ? BlockPos.of(tag.getLong("SiegeBeacon")) : null;
    }

    @Override
    public boolean hurt(DamageSource source, float amount)
    {
        if (this.atField > 0.0F && !com.projectseele.combat.AtFieldRules.bypassesAtField(source))
        {
            if (source.getEntity() instanceof EvaUnit01Entity eva && eva.isMeleeWeapon())
            {
                this.atField = Math.max(0.0F, this.atField - amount);
                if (this.level() instanceof ServerLevel server)
                {
                    AtFieldFX.ripple(server, this.getBoundingBox().getCenter(), eva.getForward());
                }
                return true;
            }
            return false;
        }
        return super.hurt(source, amount);
    }

    @Override
    public void die(DamageSource source)
    {
        if (this.level() instanceof ServerLevel server)
        {
            CrossExplosionFX.spawn(server, this.position(), 2.4F);
        }
        super.die(source);
    }
}
