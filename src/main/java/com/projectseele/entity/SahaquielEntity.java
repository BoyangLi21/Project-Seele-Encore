package com.projectseele.entity;

import com.projectseele.ProjectSeele;
import com.projectseele.config.SeeleConfig;
import com.projectseele.event.EvaHitFeedback;
import com.projectseele.fx.AtFieldFX;
import com.projectseele.fx.CrossExplosionFX;
import com.projectseele.world.TvCampaignSavedData;
import com.projectseele.world.TvSortiesR32;
import net.minecraft.core.particles.DustParticleOptions;
import net.minecraft.core.particles.ParticleOptions;
import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.syncher.EntityDataAccessor;
import net.minecraft.network.syncher.EntityDataSerializers;
import net.minecraft.network.syncher.SynchedEntityData;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.entity.ai.attributes.AttributeSupplier;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.entity.monster.Monster;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import org.joml.Vector3f;

/**
 * R66: the Tenth Angel (episode 12). It hangs high over the city and, once the first unit is up on the surface, falls
 * on NERV: two test pieces first, then the whole body toward a landing point the ring on the ground narrows down to.
 * A unit standing under the landing point when it comes down catches it; more units under it hold it, fewer let it
 * sink. Caught, its underside is open: blows and shots from below reach the core. Not caught in time, or let sink to
 * the ground, it explodes and the operation fails; a retry starts the fall again from the top.
 * <p>
 * The operation drives it through {@link #tickOperationR66}, called by the surface route each tick; it never walks.
 * Values in SeeleConfig ("sahaquiel"). The explosions hurt units but do not break blocks.
 */
public class SahaquielEntity extends Monster implements Angel
{
    public static final String MISSION_TAG = "seele_tv_sahaquiel_r66";
    public static final int WAIT = 0, FALL = 1, CAUGHT = 2;
    /** Its underside rests this far above the ground while it is held: on the raised hands of a unit (24 tall). */
    public static final double CATCH_HEIGHT = 22, UNDER_RADIUS = 20;
    private static final EntityDataAccessor<Integer> STATE = SynchedEntityData.defineId(SahaquielEntity.class, EntityDataSerializers.INT);
    private static final EntityDataAccessor<Float> SUPPORT = SynchedEntityData.defineId(SahaquielEntity.class, EntityDataSerializers.FLOAT);
    private static final DustParticleOptions RING = new DustParticleOptions(new Vector3f(1F, .25F, .1F), 4F);

    private Vec3 landing;
    private double groundY;
    private int fallAge, pieces, lastCatchers = -1;
    private boolean configured;

    public SahaquielEntity(EntityType<? extends SahaquielEntity> type, Level level)
    {
        super(type, level);
        this.setNoGravity(true);
        this.setPersistenceRequired();
    }

    public static AttributeSupplier.Builder createAttributes()
    {
        return Mob.createMobAttributes()
                .add(Attributes.MAX_HEALTH, 600.0D)
                .add(Attributes.ARMOR, 6.0D)
                .add(Attributes.FOLLOW_RANGE, 256.0D)
                .add(Attributes.KNOCKBACK_RESISTANCE, 1.0D);
    }

    @Override protected void defineSynchedData(){super.defineSynchedData();this.entityData.define(STATE, WAIT);this.entityData.define(SUPPORT, 100F);}
    @Override public float getAtField(){return 0;}
    @Override public boolean isPushable(){return false;}
    @Override protected void doPush(Entity entity){}
    @Override public boolean removeWhenFarAway(double distance){return false;}
    @Override public void travel(Vec3 input){}
    @Override public boolean shouldRenderAtSqrDistance(double distance){return true;}
    public int stateR66(){return this.entityData.get(STATE);}
    public boolean caughtR66(){return stateR66() == CAUGHT;}
    public float supportR66(){return this.entityData.get(SUPPORT);}
    public Vec3 landingR66(){return this.landing;}
    public Vec3 coreWorldR66(){return this.position().add(0, .3, 0);}
    /** How far through the fall it is, 0 at the top and 1 at the catch height. */
    public float fallProgressR66(){return Math.min(1, this.fallAge / (float) SeeleConfig.SAHAQUIEL_FALL_TICKS.get());}

    private void configureR66()
    {
        if (this.configured) return;
        this.configured = true;
        var health = this.getAttribute(Attributes.MAX_HEALTH);
        double max = SeeleConfig.SAHAQUIEL_MAX_HEALTH.get();
        if (health != null && Math.abs(health.getBaseValue() - max) > 1e-3)
        {
            float share = this.getHealth() / this.getMaxHealth();
            health.setBaseValue(max);
            this.setHealth((float) (max * share));
        }
    }

    @Override
    public void tick()
    {
        super.tick();
        this.setDeltaMovement(Vec3.ZERO);
        if (!this.level().isClientSide) configureR66();
    }

    private double topY(){return this.groundY + SeeleConfig.SAHAQUIEL_FALL_HEIGHT.get();}

    /** One tick of the operation. aim: the surface armour over NERV, which it falls toward. */
    public void tickOperationR66(ServerLevel level, TvCampaignSavedData data, Vec3 aim)
    {
        if (this.landing == null)
        {
            var random = new java.util.Random(data.generationR43 * 31L + 7);
            double a = random.nextDouble() * Math.PI * 2, r = 10 + random.nextDouble() * 25;
            this.landing = aim.add(Math.cos(a) * r, 0, Math.sin(a) * r);
            this.groundY = aim.y;
            resetToTopR66();
            ProjectSeele.LOGGER.info("R66 SAHAQUIEL over the city: landing point {} ground {}", this.landing, this.groundY);
        }
        if (data.phase.equals("failure") || data.phase.equals("cancel")) return;
        int state = stateR66();
        if (state == WAIT)
        {
            this.setPos(this.landing.x, topY(), this.landing.z);
            boolean ready = data.sorties.values().stream().anyMatch(s -> TvSortiesR32.readyAssigned(level, s));
            if (!data.phase.equals("alert") && ready)
            {
                this.entityData.set(STATE, FALL);
                this.fallAge = 0;
                ProjectSeele.LOGGER.info("R66 SAHAQUIEL falling: {} ticks from {} up", SeeleConfig.SAHAQUIEL_FALL_TICKS.get(), SeeleConfig.SAHAQUIEL_FALL_HEIGHT.get());
                data.notice = "撒哈奎尔开始坠落。全部机体赶往预测落点，在它落地前接住。";
                data.setDirty();
            }
            return;
        }
        if (state == FALL)
        {
            this.fallAge++;
            float t = fallProgressR66();
            double catchY = this.groundY + CATCH_HEIGHT;
            this.setPos(this.landing.x, catchY + (topY() - catchY) * (1 - t * t * .35 - t * .65), this.landing.z);
            if (this.pieces < 2 && t >= (this.pieces == 0 ? .12F : .3F)) dropPieceR66(level);
            if (this.fallAge % 10 == 0) ringR66(level, t);
            if (t >= 1)
            {
                int catchers = catchersR66(level, SeeleConfig.SAHAQUIEL_CATCH_RADIUS.get());
                if (catchers > 0)
                {
                    this.entityData.set(STATE, CAUGHT);
                    this.entityData.set(SUPPORT, 100F);
                    data.phase = "combat";
                    data.notice = "接住了！撑住它，从下面攻击核心。";
                    data.setDirty();
                    ProjectSeele.LOGGER.info("R66 SAHAQUIEL caught by {} unit(s)", catchers);
                }
                else impactR66(level, data, "撒哈奎尔落地爆炸，没有机体在落点接住它。机体回收后可以重试。");
            }
            return;
        }
        // caught: the units under it hold it up; too few and it sinks
        int catchers = catchersR66(level, SeeleConfig.SAHAQUIEL_CATCH_RADIUS.get() + 6);
        if (catchers != this.lastCatchers)
        {
            ProjectSeele.LOGGER.info("R66 SAHAQUIEL held by {} unit(s), support {}", catchers, Math.round(supportR66()));
            this.lastCatchers = catchers;
        }
        double perSecond = catchers >= 3 ? SeeleConfig.SAHAQUIEL_SUPPORT_GAIN_THREE.get()
                : catchers == 2 ? -SeeleConfig.SAHAQUIEL_SUPPORT_LOSS_TWO.get()
                : catchers == 1 ? -SeeleConfig.SAHAQUIEL_SUPPORT_LOSS_ONE.get() : -SeeleConfig.SAHAQUIEL_SUPPORT_LOSS_NONE.get();
        float support = (float) Math.max(0, Math.min(100, supportR66() + perSecond / 20));
        this.entityData.set(SUPPORT, support);
        this.setPos(this.landing.x, this.groundY + CATCH_HEIGHT - (100 - support) * .06, this.landing.z);
        if (support <= 0) impactR66(level, data, "撒哈奎尔压垮了支撑，坠地爆炸。机体回收后可以重试。");
        else if (this.tickCount % 20 == 0)
        {
            data.notice = "支撑 " + Math.round(support) + "% · 下方机体 " + catchers + " 台（三台才撑得住）";
            data.setDirty();
        }
    }

    private void resetToTopR66()
    {
        this.entityData.set(STATE, WAIT);
        this.entityData.set(SUPPORT, 100F);
        this.fallAge = 0;
        this.pieces = 0;
        this.lastCatchers = -1;
        this.setPos(this.landing.x, topY(), this.landing.z);
    }

    /** Units with a pilot, powered and standing, within radius of the landing point (horizontally) and on the ground. */
    private int catchersR66(ServerLevel level, double radius)
    {
        return level.getEntitiesOfClass(EvaUnit01Entity.class, new AABB(this.landing, this.landing).inflate(radius, 40, radius),
                e -> e.isAlive() && e.getPilotEntity() != null && !EvaShutdownR30.disabled(e)
                        && e.position().subtract(this.landing).horizontalDistance() <= radius && Math.abs(e.getY() - this.groundY) < 12).size();
    }

    private void dropPieceR66(ServerLevel level)
    {
        this.pieces++;
        double a = this.random.nextDouble() * Math.PI * 2, r = 70 + this.random.nextDouble() * 80;
        Vec3 at = new Vec3(this.landing.x + Math.cos(a) * r, this.groundY, this.landing.z + Math.sin(a) * r);
        int top = level.getHeight(net.minecraft.world.level.levelgen.Heightmap.Types.MOTION_BLOCKING, (int) Math.floor(at.x), (int) Math.floor(at.z));
        at = new Vec3(at.x, Math.max(top, this.groundY), at.z);
        blastR66(level, at, 6F, 30, SeeleConfig.SAHAQUIEL_PIECE_DAMAGE.get().floatValue());
        ProjectSeele.LOGGER.info("R66 SAHAQUIEL test piece {} struck {}", this.pieces, at);
    }

    private void impactR66(ServerLevel level, TvCampaignSavedData data, String notice)
    {
        Vec3 at = new Vec3(this.landing.x, this.groundY, this.landing.z);
        blastR66(level, at, 12F, SeeleConfig.SAHAQUIEL_IMPACT_RADIUS.get(), SeeleConfig.SAHAQUIEL_IMPACT_DAMAGE.get().floatValue());
        CrossExplosionFX.spawn(level, at, 1.6F);
        data.phase = "failure";
        data.notice = notice;
        data.setDirty();
        ProjectSeele.LOGGER.info("R66 SAHAQUIEL impact: operation failed ({})", notice);
        resetToTopR66();
    }

    /** A blast that hurts units and people around it; it does not break blocks. */
    private void blastR66(ServerLevel level, Vec3 at, float power, double radius, float damage)
    {
        level.explode(this, at.x, at.y + 1, at.z, power, Level.ExplosionInteraction.NONE);
        sendFar(level, ParticleTypes.EXPLOSION_EMITTER, at.add(0, 2, 0), 6, 4, 0);
        sendFar(level, ParticleTypes.LARGE_SMOKE, at.add(0, 4, 0), 60, 10, .05);
        for (var unit : level.getEntitiesOfClass(EvaUnit01Entity.class, new AABB(at, at).inflate(radius), e -> e.isAlive()))
        {
            double d = unit.position().distanceTo(at);
            if (d > radius) continue;
            float scaled = (float) (damage * (1 - d / radius * .6));
            EvaHitFeedback.hurt(unit, this.damageSources().explosion(this, this), scaled, unit.position().add(0, 6, 0),
                    unit.position().subtract(at).normalize());
        }
    }

    /** The landing ring on the ground narrows as it comes down (episode 12's predicted impact area). */
    private void ringR66(ServerLevel level, float t)
    {
        double radius = 90 - 72 * t;
        int points = 48;
        for (int i = 0; i < points; i++)
        {
            double a = Math.PI * 2 * i / points;
            sendFar(level, RING, new Vec3(this.landing.x + Math.cos(a) * radius, this.groundY + 1.5, this.landing.z + Math.sin(a) * radius), 1, 0, 0);
        }
    }

    private static void sendFar(ServerLevel level, ParticleOptions particle, Vec3 at, int count, double spread, double speed)
    {
        for (var player : level.players())
            level.sendParticles(player, particle, true, at.x, at.y, at.z, count, spread, spread, spread, speed);
    }

    /** Caught, from underneath and close under it, where the core is. */
    @Override
    public boolean hurt(DamageSource source, float amount)
    {
        if (this.level().isClientSide || com.projectseele.combat.AtFieldRules.bypassesAtField(source)) return super.hurt(source, amount);
        Vec3 from = source.getSourcePosition();
        boolean below = from != null && from.y < this.getY() + .5 && from.subtract(coreWorldR66()).horizontalDistance() <= UNDER_RADIUS;
        if (!caughtR66() || !below)
        {
            if (amount > 0 && this.level() instanceof ServerLevel server) AtFieldFX.blocked(server, this, source);
            return false;
        }
        boolean hurt = super.hurt(source, amount);
        if (hurt && this.tickCount % 10 == 0) ProjectSeele.LOGGER.info("R66 SAHAQUIEL core hit from below: health {}", this.getHealth());
        return hurt;
    }

    @Override
    public void die(DamageSource source)
    {
        if (this.level() instanceof ServerLevel server) CrossExplosionFX.spawn(server, this.position(), 1.6F);
        ProjectSeele.LOGGER.info("R66 SAHAQUIEL down");
        super.die(source);
    }

    @Override
    public void addAdditionalSaveData(CompoundTag tag)
    {
        super.addAdditionalSaveData(tag);
        tag.putInt("SahaquielStateR66", stateR66());
        tag.putFloat("SahaquielSupportR66", supportR66());
        tag.putInt("SahaquielFallR66", this.fallAge);
        tag.putInt("SahaquielPiecesR66", this.pieces);
        if (this.landing != null)
        {
            tag.putDouble("SahaquielLandX", this.landing.x);
            tag.putDouble("SahaquielLandY", this.landing.y);
            tag.putDouble("SahaquielLandZ", this.landing.z);
            tag.putDouble("SahaquielGroundR66", this.groundY);
        }
    }

    @Override
    public void readAdditionalSaveData(CompoundTag tag)
    {
        super.readAdditionalSaveData(tag);
        this.entityData.set(STATE, tag.getInt("SahaquielStateR66"));
        if (tag.contains("SahaquielSupportR66")) this.entityData.set(SUPPORT, tag.getFloat("SahaquielSupportR66"));
        this.fallAge = tag.getInt("SahaquielFallR66");
        this.pieces = tag.getInt("SahaquielPiecesR66");
        if (tag.contains("SahaquielLandX"))
        {
            this.landing = new Vec3(tag.getDouble("SahaquielLandX"), tag.getDouble("SahaquielLandY"), tag.getDouble("SahaquielLandZ"));
            this.groundY = tag.getDouble("SahaquielGroundR66");
        }
        this.configured = tag.contains("SahaquielStateR66");
    }
}
