package com.projectseele.entity;

import com.projectseele.ProjectSeele;
import com.projectseele.config.SeeleConfig;
import com.projectseele.event.EvaHitFeedback;
import com.projectseele.fx.AtFieldFX;
import com.projectseele.fx.CrossExplosionFX;
import com.projectseele.world.TvCampaignSavedData;
import java.util.ArrayList;
import java.util.List;
import net.minecraft.core.particles.DustParticleOptions;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.syncher.EntityDataAccessor;
import net.minecraft.network.syncher.EntityDataSerializers;
import net.minecraft.network.syncher.SynchedEntityData;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.util.Mth;
import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.entity.MoverType;
import net.minecraft.world.entity.ai.attributes.AttributeSupplier;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.entity.monster.Monster;
import net.minecraft.world.level.ClipContext;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.HitResult;
import net.minecraft.world.phys.Vec3;
import org.joml.Vector3f;

/**
 * R66: the Ninth Angel (episode 11). A round body carried high on four long legs; acid falls from the eyes on its
 * underside, eats into whatever it lands on and lies there in pools. Over NERV it drips onto the surface armour plate,
 * as the original dissolved its way toward headquarters.
 * <p>
 * Its field is weak, but nothing reaches it except from underneath: a blow or a shot counts only when it comes from
 * below the body and close under it, where the core is. While its operation runs the city has no power: units fight
 * on their internal batteries ({@link #blackoutR66}). Values in SeeleConfig ("matarael").
 */
public class MataraelEntity extends Monster implements Angel
{
    /** Body centre and core, in blocks above the feet. */
    public static final double BODY_Y = 32, CORE_Y = 26.3, UNDER_RADIUS = 12;
    public static final String MISSION_TAG = "seele_tv_matarael_r66";
    private static final EntityDataAccessor<Float> FIELD = SynchedEntityData.defineId(MataraelEntity.class, EntityDataSerializers.FLOAT);
    private static final DustParticleOptions ACID = new DustParticleOptions(new Vector3f(.72F, .86F, .18F), 2.2F);

    private record Drop(Vec3 pos, Vec3 velocity) {}
    private record Pool(Vec3 at, int until) {}
    private final List<Drop> drops = new ArrayList<>();
    private final List<Pool> pools = new ArrayList<>();
    private Vec3 armorAim;
    private float armorDamage;
    private int acidClock;
    private boolean configured;

    public MataraelEntity(EntityType<? extends MataraelEntity> type, Level level)
    {
        super(type, level);
        this.setMaxUpStep(2.2F);
        this.setPersistenceRequired();
    }

    public static AttributeSupplier.Builder createAttributes()
    {
        return Mob.createMobAttributes()
                .add(Attributes.MAX_HEALTH, 450.0D)
                .add(Attributes.ARMOR, 6.0D)
                .add(Attributes.MOVEMENT_SPEED, 0.12D)
                .add(Attributes.FOLLOW_RANGE, 128.0D)
                .add(Attributes.KNOCKBACK_RESISTANCE, 1.0D);
    }

    @Override protected void defineSynchedData(){super.defineSynchedData();this.entityData.define(FIELD, 300F);}
    @Override public float getAtField(){return this.entityData.get(FIELD);}
    @Override public boolean isPushable(){return false;}
    @Override protected void doPush(Entity entity){}
    @Override public boolean removeWhenFarAway(double distance){return false;}
    public Vec3 coreWorldR66(){return this.position().add(0, CORE_Y, 0);}

    /** True while a Matarael operation runs in this level: no cable power anywhere in the city (episode 11). */
    public static boolean blackoutR66(ServerLevel level)
    {
        if (!SeeleConfig.COMMON_SPEC.isLoaded() || !SeeleConfig.MATARAEL_BLACKOUT.get()) return false;
        var data = TvCampaignSavedData.get(level);
        return data.active.equals("matarael") && (data.phase.equals("approach") || data.phase.equals("combat"));
    }

    private void configureR66()
    {
        if (this.configured) return;
        this.configured = true;
        var health = this.getAttribute(Attributes.MAX_HEALTH);
        double max = SeeleConfig.MATARAEL_MAX_HEALTH.get();
        if (health != null && Math.abs(health.getBaseValue() - max) > 1e-3)
        {
            float share = this.getHealth() / this.getMaxHealth();
            health.setBaseValue(max);
            this.setHealth((float) (max * share));
        }
        if (this.tickCount < 5) this.entityData.set(FIELD, (float) (double) SeeleConfig.MATARAEL_AT_FIELD.get());
    }

    /** The surface route's plate attack: drip onto the armour plate under the body for a while. */
    public boolean beginAcidOnArmorR66(Vec3 aim, float damage)
    {
        this.armorAim = aim;
        this.armorDamage = damage;
        return true;
    }
    public void stopAcidOnArmorR66(){this.armorAim = null;}
    public boolean dripping(){return this.armorAim != null || !this.isNoAi();}

    @Override
    public void tick()
    {
        super.tick();
        if (this.level().isClientSide || !(this.level() instanceof ServerLevel server)) return;
        configureR66();
        if (!this.isNoAi()) tickCombatR66();
        if (dripping() && ++this.acidClock >= SeeleConfig.MATARAEL_ACID_PERIOD_TICKS.get())
        {
            this.acidClock = 0;
            // the eyes ring the underside; one of them lets a drop go
            double a = this.random.nextDouble() * Math.PI * 2, r = 2 + this.random.nextDouble() * 3;
            Vec3 eye = this.position().add(Math.cos(a) * r, CORE_Y - .4, Math.sin(a) * r);
            this.drops.add(new Drop(eye, new Vec3(this.random.nextGaussian() * .03, -.1, this.random.nextGaussian() * .03)));
        }
        tickDropsR66(server);
        tickPoolsR66(server);
    }

    /** In the fight it edges over its target so the acid falls on it, slowly, as a spider settles. */
    private void tickCombatR66()
    {
        LivingEntity target = this.getTarget();
        if (target == null || !target.isAlive()) return;
        Vec3 to = target.position().subtract(this.position()).multiply(1, 0, 1);
        float yaw = (float) Math.toDegrees(Math.atan2(-to.x, to.z));
        this.setYRot(Mth.approachDegrees(this.getYRot(), yaw, 1.2F));
        this.yBodyRot = this.yHeadRot = this.getYRot();
        if (to.length() > 3)
        {
            Vec3 step = to.normalize().scale(.06).add(0, -.08, 0);
            this.move(MoverType.SELF, step);
        }
    }

    private void tickDropsR66(ServerLevel server)
    {
        for (int i = this.drops.size() - 1; i >= 0; i--)
        {
            Drop d = this.drops.get(i);
            Vec3 next = d.pos().add(d.velocity());
            var hit = server.clip(new ClipContext(d.pos(), next, ClipContext.Block.COLLIDER, ClipContext.Fluid.NONE, this));
            Vec3 end = hit.getType() == HitResult.Type.MISS ? next : hit.getLocation();
            LivingEntity struck = null;
            for (var unit : server.getEntitiesOfClass(EvaUnit01Entity.class, new AABB(d.pos(), end).inflate(2), e -> e.isAlive()))
                if (com.projectseele.physics.CombatBodyContacts.clip(unit, d.pos(), end, .6).isPresent()) {struck = unit; break;}
            server.sendParticles(ACID, end.x, end.y, end.z, 2, .15, .15, .15, 0);
            if (struck != null)
            {
                EvaHitFeedback.hurt(struck, this.damageSources().mobAttack(this), SeeleConfig.MATARAEL_ACID_DAMAGE.get().floatValue(), end, new Vec3(0, -1, 0));
                server.sendParticles(net.minecraft.core.particles.ParticleTypes.SMOKE, end.x, end.y, end.z, 10, .8, .8, .8, .02);
                this.drops.remove(i);
                continue;
            }
            if (hit.getType() != HitResult.Type.MISS)
            {
                if (this.armorAim != null && end.distanceTo(this.armorAim) < 14)
                    com.projectseele.world.NervArmorColumnR50.surfaceImpactR52(server, this, d.pos(), end.add(0, -.5, 0), this.armorDamage);
                this.pools.add(new Pool(end, this.tickCount + 140));
                server.sendParticles(net.minecraft.core.particles.ParticleTypes.SMOKE, end.x, end.y + .3, end.z, 14, 1.5, .2, 1.5, .02);
                server.playSound(null, end.x, end.y, end.z, net.minecraft.sounds.SoundEvents.FIRE_EXTINGUISH, net.minecraft.sounds.SoundSource.HOSTILE, 2.5F, .6F);
                this.drops.remove(i);
                continue;
            }
            if (end.y < this.level().getMinBuildHeight() || this.drops.get(i).pos().y < this.getY() - 64) {this.drops.remove(i); continue;}
            this.drops.set(i, new Drop(next, d.velocity().add(0, -.08, 0).scale(.98)));
        }
    }

    private void tickPoolsR66(ServerLevel server)
    {
        this.pools.removeIf(p -> p.until() < this.tickCount);
        if (this.tickCount % 10 == 0)
            for (Pool p : this.pools) server.sendParticles(ACID, p.at().x, p.at().y + .2, p.at().z, 3, 1.6, .05, 1.6, 0);
        if (this.tickCount % 20 != 0) return;
        float damage = SeeleConfig.MATARAEL_ACID_POOL_DAMAGE.get().floatValue();
        for (Pool p : this.pools)
            for (var unit : server.getEntitiesOfClass(EvaUnit01Entity.class, new AABB(p.at(), p.at()).inflate(4, 2, 4), e -> e.isAlive()))
                EvaHitFeedback.hurt(unit, this.damageSources().mobAttack(this), damage, p.at(), new Vec3(0, 1, 0));
    }

    /** From underneath and close under the body, where the core is. */
    private boolean fromBelowR66(DamageSource source)
    {
        Vec3 from = source.getSourcePosition();
        if (from == null) return false;
        Vec3 core = coreWorldR66();
        return from.y < core.y - .5 && from.subtract(core).horizontalDistance() <= UNDER_RADIUS;
    }

    @Override
    public boolean hurt(DamageSource source, float amount)
    {
        if (this.level().isClientSide || com.projectseele.combat.AtFieldRules.bypassesAtField(source)) return super.hurt(source, amount);
        if (!fromBelowR66(source))
        {
            if (amount > 0 && this.level() instanceof ServerLevel server) AtFieldFX.blocked(server, this, source);
            return false;
        }
        float field = this.getAtField();
        if (field > 0)
        {
            float left = Math.max(0, field - amount);
            this.entityData.set(FIELD, left);
            CombatFoleyR36.fieldBroken(this, field, left);
            if (this.level() instanceof ServerLevel server) AtFieldFX.ripple(server, coreWorldR66(), new Vec3(0, 1, 0));
            amount -= field;
            if (amount <= 0) return true;
        }
        boolean hurt = super.hurt(source, amount);
        if (hurt && this.tickCount % 10 == 0) ProjectSeele.LOGGER.info("R66 MATARAEL core hit from below: health {}", this.getHealth());
        return hurt;
    }

    @Override
    public void die(DamageSource source)
    {
        if (this.level() instanceof ServerLevel server) CrossExplosionFX.spawn(server, this.position().add(0, BODY_Y, 0), 1F);
        ProjectSeele.LOGGER.info("R66 MATARAEL down");
        super.die(source);
    }

    @Override
    public void addAdditionalSaveData(CompoundTag tag)
    {
        super.addAdditionalSaveData(tag);
        tag.putFloat("MataraelFieldR66", this.getAtField());
    }

    @Override
    public void readAdditionalSaveData(CompoundTag tag)
    {
        super.readAdditionalSaveData(tag);
        if (tag.contains("MataraelFieldR66")) {this.entityData.set(FIELD, tag.getFloat("MataraelFieldR66")); this.configured = true;}
    }
}
