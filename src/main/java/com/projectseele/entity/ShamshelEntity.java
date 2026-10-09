package com.projectseele.entity;

import com.projectseele.fx.AtFieldFX;
import com.projectseele.fx.CrossExplosionFX;
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
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.minecraft.network.syncher.*;
import java.util.*;

/** Fourth Angel: low-hovering pursuit type with a pair of sweeping energy whips. */
public class ShamshelEntity extends Monster implements Angel, SiegeAnchorAware, software.bernie.geckolib.animatable.GeoEntity
{
    private final software.bernie.geckolib.core.animatable.instance.AnimatableInstanceCache geoCache=software.bernie.geckolib.util.GeckoLibUtil.createInstanceCache(this);
    @Override public software.bernie.geckolib.core.animatable.instance.AnimatableInstanceCache getAnimatableInstanceCache(){return geoCache;}
    @Override public void registerControllers(software.bernie.geckolib.core.animation.AnimatableManager.ControllerRegistrar controllers)
    {
        controllers.add(new software.bernie.geckolib.core.animation.AnimationController<>(this,"base",6,state->state.setAndContinue(
                software.bernie.geckolib.core.animation.RawAnimation.begin().thenLoop(state.isMoving()&&!CombatFeelR31.restrained(this)&&!EvaCombatR31.holds(this)?"animation.Shamshel.move":"animation.Shamshel.idle"))));
    }
    private static final EntityDataAccessor<Float> FIELD=SynchedEntityData.defineId(ShamshelEntity.class,EntityDataSerializers.FLOAT);
    private static final EntityDataAccessor<Integer> SWEEP=SynchedEntityData.defineId(ShamshelEntity.class,EntityDataSerializers.INT);
    private static final EntityDataAccessor<Integer> SIDE=SynchedEntityData.defineId(ShamshelEntity.class,EntityDataSerializers.INT);
    private static final EntityDataAccessor<Float> YAW=SynchedEntityData.defineId(ShamshelEntity.class,EntityDataSerializers.FLOAT);
    private static final EntityDataAccessor<Integer> SWEEP_MODE=SynchedEntityData.defineId(ShamshelEntity.class,EntityDataSerializers.INT);
    private final EvaPoseSignalClock sweepClock=new EvaPoseSignalClock();
    private final Set<UUID> hitVictims=new HashSet<>();
    @Override public float getAtField(){return entityData.get(FIELD);}
    public boolean isSweeping(){return entityData.get(SWEEP)>=0;}
    public int sweepSide(){return entityData.get(SIDE);}
    public int sweepMode(){return entityData.get(SWEEP_MODE);}
    public float sweepYaw(){return entityData.get(YAW);}
    public float sweepAge(float partial){return level().isClientSide?sweepClock.sample(FirstBattleSignals.clientFrameTime()):entityData.get(SWEEP);}
    @Override protected void defineSynchedData()
    {super.defineSynchedData();entityData.define(FIELD,700F);entityData.define(SWEEP,-1);entityData.define(SIDE,-1);entityData.define(YAW,0F);entityData.define(SWEEP_MODE,0);}
    @Override public void onSyncedDataUpdated(EntityDataAccessor<?> key)
    {super.onSyncedDataUpdated(key);if(key.equals(SWEEP)&&sweepClock!=null&&level().isClientSide)sweepClock.accept(entityData.get(SWEEP),false,true);}
    private int sweepCooldown = 30;
    private int sweepChoice;
    private BlockPos siegeBeacon;

    public ShamshelEntity(EntityType<? extends ShamshelEntity> type, Level level)
    {
        super(type, level);
        this.setNoGravity(true);
    }

    public static AttributeSupplier.Builder createAttributes()
    {
        return Mob.createMobAttributes()
                .add(Attributes.MAX_HEALTH, 620.0D)
                .add(Attributes.ARMOR, 7.0D)
                .add(Attributes.ATTACK_DAMAGE, 30.0D)
                .add(Attributes.MOVEMENT_SPEED, 0.34D)
                .add(Attributes.FLYING_SPEED, 0.38D)
                .add(Attributes.FOLLOW_RANGE, 96.0D)
                .add(Attributes.KNOCKBACK_RESISTANCE, 1.0D);
    }

    @Override
    protected void registerGoals()
    {
        this.targetSelector.addGoal(1, new NearestAttackableTargetGoal<>(this, EvaUnit01Entity.class, true));
        this.targetSelector.addGoal(2, new NearestAttackableTargetGoal<>(this, Player.class, true));
    }

    public void cancelSweepR31()
    {if(isSweeping()){entityData.set(SWEEP,-1);hitVictims.clear();sweepCooldown=Math.max(sweepCooldown,16);}getNavigation().stop();}

    @Override public void aiStep()
    {
        if(!level().isClientSide&&(EvaCombatR31.constrainVictim(this)||CombatFeelR31.travel(this)))return;
        if(!level().isClientSide&&CombatFeelR31.hitPaused(this)){setDeltaMovement(Vec3.ZERO);return;}
        super.aiStep();
    }

    @Override
    public void tick()
    {
        super.tick();
        if(this.isDeadOrDying())
        {
            if(!level().isClientSide){cancelSweepR31();setTarget(null);setDeltaMovement(Vec3.ZERO);}
            return;
        }
        var reaction=CombatFeelR31.beat(this);
        this.setNoGravity(reaction==null||reaction.kind()!=CombatFeelR31.THROWN&&reaction.kind()!=CombatFeelR31.DOWN);
        if(level().isClientSide)return;
        if(CombatFeelR31.restrained(this)||EvaCombatR31.holds(this))
        {if(EvaCombatR31.holds(this)||reaction!=null&&reaction.kind()>=CombatFeelR31.STAGGER&&reaction.kind()<=CombatFeelR31.THROWN)cancelSweepR31();return;}
        if(isSweeping()){tickSweep();return;}
        if(sweepCooldown>0)sweepCooldown--;
        LivingEntity target = this.getTarget();
        if (target == null || !target.isAlive())
        {
            if (this.siegeBeacon != null)
            {
                Vec3 anchor = Vec3.atCenterOf(this.siegeBeacon).add(0.0D, 10.0D, 0.0D);
                Vec3 approach = anchor.subtract(this.position().add(0.0D, 6.0D, 0.0D));
                if (approach.lengthSqr() > 64.0D)
                {
                    this.setDeltaMovement(this.getDeltaMovement().scale(0.72D)
                            .add(approach.normalize().scale(0.11D)));
                }
                else
                {
                    this.setDeltaMovement(this.getDeltaMovement().scale(0.82D));
                }
            }
            else
            {
                this.setDeltaMovement(this.getDeltaMovement().scale(0.85D).add(0.0D,
                        Math.sin(this.tickCount * 0.08D) * 0.006D, 0.0D));
            }
            return;
        }
        Vec3 aim = target.getBoundingBox().getCenter().subtract(this.position().add(0.0D, 30.0D, 0.0D));
        double distance = aim.length();
        float yaw=(float)Math.toDegrees(Math.atan2(-aim.x,aim.z));
        setYRot(net.minecraft.util.Mth.approachDegrees(getYRot(),yaw,3));yBodyRot=getYRot();yHeadRot=getYRot();
        Vec3 toward=aim.multiply(1,0,1).normalize(),lateral=new Vec3(toward.z,0,-toward.x);
        double closing=distance>46?1.05:distance<27?-.90:distance>36?.35:0;
        Vec3 intended=toward.scale(closing).add(lateral.scale(sweepChoice%2==0?.52:-.52)).add(0,net.minecraft.util.Mth.clamp(aim.y*.018,-.25,.25),0);
        this.setDeltaMovement(this.getDeltaMovement().lerp(intended,.14));
        if (distance < 44.0D && this.sweepCooldown <= 0
                &&Math.abs(net.minecraft.util.Mth.wrapDegrees(yaw-getYRot()))<15)
        {
            entityData.set(SWEEP,0);entityData.set(SIDE,-sweepSide());entityData.set(SWEEP_MODE,sweepChoice++%3);entityData.set(YAW,getYRot());hitVictims.clear();
            playSound(com.projectseele.registry.ModSounds.SHAMSHEL_WHIP_CHARGE.get(),1.3F,1);
        }
    }

    private void tickSweep()
    {
        if(CombatFeelR31.hitPaused(this))return;
        int age=entityData.get(SWEEP)+1;entityData.set(SWEEP,age);setDeltaMovement(getDeltaMovement().scale(.6));
        setYRot(sweepYaw());yBodyRot=yHeadRot=getYRot();
        if(age==ShamshelWhipMotion.contactStart(sweepMode()))playSound(com.projectseele.registry.ModSounds.SHAMSHEL_WHIP_CRACK.get(),1.6F,sweepMode()==1?1.15F:.92F);
        if(age>=ShamshelWhipMotion.contactStart(sweepMode())&&age<=ShamshelWhipMotion.contactEnd(sweepMode()))
        {
            // Sample the same rendered chain through time. The old invisible
            // thirteen-block damage box also hit behind walls and through EVA.
            for(int sample=0;sample<=4;sample++)
            {
                var points=ShamshelWhipMotion.points(this,age-1+sample/4F,1);
                var previous=ShamshelWhipMotion.points(this,age-1.25F+sample/4F,1);
                AABB sweep=new AABB(points.get(0),points.get(0));
                for(var point:points)sweep=sweep.minmax(new AABB(point,point));
                var victims=com.projectseele.physics.CombatEntityQueryR44.candidates(level(),sweep.inflate(1.2),
                        e->(e instanceof EvaUnit01Entity||e instanceof Player&&!e.isPassenger())&&e.isAlive());
                for(int i=1;i<points.size();i++)
                {
                    Vec3 from=points.get(i-1),to=points.get(i);
                    var wall=level().clip(new net.minecraft.world.level.ClipContext(from,to,net.minecraft.world.level.ClipContext.Block.COLLIDER,net.minecraft.world.level.ClipContext.Fluid.NONE,this));
                    Vec3 end=wall.getLocation();
                    for(var victim:victims)
                    {
                        if(hitVictims.contains(victim.getUUID()))continue;
                        var contact=com.projectseele.physics.CombatBodyContacts.clip(victim,from,end,.7);
                        if(contact.isEmpty())continue;
                        hitVictims.add(victim.getUUID());Vec3 motion=points.get(i).subtract(previous.get(i));
                        Vec3 direction=motion.lengthSqr()>1e-6?motion.normalize():end.subtract(from).normalize();
                        if(com.projectseele.event.EvaHitFeedback.hurt(victim,damageSources().mobAttack(this),30F,contact.orElse(from),direction)&&!(victim instanceof EvaUnit01Entity))
                            victim.push(direction.x*.8,.22,direction.z*.8);
                    }
                    if(wall.getType()!=net.minecraft.world.phys.HitResult.Type.MISS)break;
                }
            }
        }
        if(age>=ShamshelWhipMotion.cycle(sweepMode())){entityData.set(SWEEP,-1);sweepCooldown=8;}
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
        tag.putFloat("AtField",getAtField());tag.putInt("SweepCooldown",sweepCooldown);tag.putInt("SweepAge",entityData.get(SWEEP));
        tag.putInt("SweepSide",sweepSide());tag.putFloat("SweepYaw",sweepYaw());
        tag.putInt("SweepModeR31",sweepMode());tag.putInt("SweepChoiceR31",sweepChoice);
        var hits=new net.minecraft.nbt.ListTag();hitVictims.forEach(id->hits.add(net.minecraft.nbt.StringTag.valueOf(id.toString())));tag.put("SweepHits",hits);
        if (this.siegeBeacon != null)
        {
            tag.putLong("SiegeBeacon", this.siegeBeacon.asLong());
        }
    }

    @Override
    public void readAdditionalSaveData(CompoundTag tag)
    {
        super.readAdditionalSaveData(tag);
        if(tag.contains("AtField"))entityData.set(FIELD,Math.max(0,Math.min(700,tag.getFloat("AtField"))));
        if(tag.contains("SweepCooldown"))sweepCooldown=Math.max(0,Math.min(34,tag.getInt("SweepCooldown")));
        if(tag.contains("SweepAge"))entityData.set(SWEEP,Math.max(-1,Math.min(ShamshelWhipMotion.CYCLE-1,tag.getInt("SweepAge"))));
        entityData.set(SIDE,tag.getInt("SweepSide")<0?-1:1);entityData.set(YAW,tag.getFloat("SweepYaw"));
        entityData.set(SWEEP_MODE,Math.max(0,Math.min(2,tag.getInt("SweepModeR31"))));sweepChoice=Math.max(0,tag.getInt("SweepChoiceR31"));
        hitVictims.clear();for(var hit:tag.getList("SweepHits",8))try{hitVictims.add(UUID.fromString(hit.getAsString()));}catch(IllegalArgumentException ignored){}
        this.siegeBeacon = tag.contains("SiegeBeacon")
                ? BlockPos.of(tag.getLong("SiegeBeacon")) : null;
    }

    @Override
    public boolean hurt(DamageSource source, float amount)
    {
        com.projectseele.physics.ShamshelDamageWitnessR48.record("hurt_enter",source.getEntity(),this,source,amount,"before_original_gate");
        if (this.getAtField() > 0.0F && !com.projectseele.combat.AtFieldRules.bypassesAtField(source))
        {
            if (source.getEntity() instanceof EvaUnit01Entity eva && eva.isMeleeWeapon())
            {
                this.entityData.set(FIELD,Math.max(0.0F,this.getAtField()-amount));
                if (this.level() instanceof ServerLevel server)
                {
                    AtFieldFX.ripple(server, this.getBoundingBox().getCenter(), eva.getForward());
                }
                com.projectseele.physics.ShamshelDamageWitnessR48.record("at_melee_consumed",source.getEntity(),this,source,amount,"accepted=true; hull_not_called");
                return true;
            }
            com.projectseele.physics.ShamshelDamageWitnessR48.record("at_rejected",source.getEntity(),this,source,amount,"accepted=false; hull_not_called");
            return false;
        }
        boolean accepted=super.hurt(source,amount);
        com.projectseele.physics.ShamshelDamageWitnessR48.record("super_hurt_return",source.getEntity(),this,source,amount,"accepted="+accepted);
        return accepted;
    }

    @Override
    public void die(DamageSource source)
    {
        super.die(source);
        if (this.isDeadOrDying()&&this.level() instanceof ServerLevel server)
        {
            cancelSweepR31();setTarget(null);setDeltaMovement(Vec3.ZERO);
            CrossExplosionFX.spawn(server, this.position(), 1.25F);
        }
    }
}
