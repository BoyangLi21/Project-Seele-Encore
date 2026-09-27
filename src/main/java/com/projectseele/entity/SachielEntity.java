package com.projectseele.entity;

import com.projectseele.fx.AtFieldFX;
import com.projectseele.fx.CrossExplosionFX;
import com.projectseele.network.ClientboundNukeFxPacket;
import com.projectseele.network.SeeleNetwork;
import net.minecraft.core.BlockPos;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.ai.attributes.AttributeSupplier;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.entity.ai.goal.MeleeAttackGoal;
import net.minecraft.world.entity.ai.goal.WaterAvoidingRandomStrollGoal;
import net.minecraft.world.entity.ai.goal.target.NearestAttackableTargetGoal;
import net.minecraft.world.entity.monster.Monster;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.Level.ExplosionInteraction;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.network.PacketDistributor;
import software.bernie.geckolib.animatable.GeoEntity;
import software.bernie.geckolib.core.animatable.instance.AnimatableInstanceCache;
import software.bernie.geckolib.core.animation.AnimatableManager;
import software.bernie.geckolib.core.animation.AnimationController;
import software.bernie.geckolib.core.animation.RawAnimation;
import software.bernie.geckolib.util.GeckoLibUtil;

/** Third Angel: a close-range giant that ends the fight with a cross-shaped self-destruction. */
public class SachielEntity extends Monster implements Angel, GeoEntity, SiegeAnchorAware, FirstBattleSignals.Actor
{
    private static final FirstBattleSignals.SignalSet FIRST_BATTLE=new FirstBattleSignals.SignalSet(SachielEntity.class);
    private static final net.minecraft.network.syncher.EntityDataAccessor<Float> FIELD=net.minecraft.network.syncher.SynchedEntityData.defineId(SachielEntity.class,net.minecraft.network.syncher.EntityDataSerializers.FLOAT);
    private static final net.minecraft.network.syncher.EntityDataAccessor<Integer> STRIKE_AGE=net.minecraft.network.syncher.SynchedEntityData.defineId(SachielEntity.class,net.minecraft.network.syncher.EntityDataSerializers.INT);
    private static final net.minecraft.network.syncher.EntityDataAccessor<Integer> STRIKE_MODE=net.minecraft.network.syncher.SynchedEntityData.defineId(SachielEntity.class,net.minecraft.network.syncher.EntityDataSerializers.INT);
    private static final net.minecraft.network.syncher.EntityDataAccessor<org.joml.Vector3f> STRIKE_AIM=net.minecraft.network.syncher.SynchedEntityData.defineId(SachielEntity.class,net.minecraft.network.syncher.EntityDataSerializers.VECTOR3);
    private static final net.minecraft.network.syncher.EntityDataAccessor<CompoundTag> STRIKE_FROM=net.minecraft.network.syncher.SynchedEntityData.defineId(SachielEntity.class,net.minecraft.network.syncher.EntityDataSerializers.COMPOUND_TAG);
    private final EvaPoseSignalClock strikeClock=new EvaPoseSignalClock();private boolean strikeHit;private LivingEntity strikeTarget;
    private float committedStrikeYaw;
    private int strikeChoice,meleeRecovery;
    private float strikeAdvance;
    public boolean isStrikeActive(){return entityData.get(STRIKE_AGE)>=0;}
    public boolean isSelfDestructing(){return selfDestructTicks>=0;}
    public int strikeMode(){return entityData.get(STRIKE_MODE);}
    public float strikeAge(float partial){return level().isClientSide?strikeClock.sample(FirstBattleSignals.clientFrameTime()):entityData.get(STRIKE_AGE);}
    public Vec3 strikeAim(){return new Vec3(entityData.get(STRIKE_AIM));}
    public CompoundTag strikeEntryR36(){return entityData.get(STRIKE_FROM);}
    public boolean strikeReadyR34(){return meleeRecovery<=0;}
    public boolean lastStrikeConnectedR36(){return strikeHit;}
    @Override public void onSyncedDataUpdated(net.minecraft.network.syncher.EntityDataAccessor<?> key){super.onSyncedDataUpdated(key);if(key.equals(STRIKE_AGE)&&strikeClock!=null&&level().isClientSide)strikeClock.accept(entityData.get(STRIKE_AGE),false,true);}
    @Override public boolean doHurtTarget(net.minecraft.world.entity.Entity entity)
    {
        if(!(entity instanceof LivingEntity living))return false;
        int[] pattern={SachielStrike.JAB,SachielStrike.HOOK,SachielStrike.SHOVE,SachielStrike.OVERHEAD,SachielStrike.HOOK};
        int mode=pattern[strikeChoice%pattern.length];
        if(SachielGameplayMotionR32.ready())
        {
            var reaction=CombatFeelR31.beat(living);
            boolean low=living instanceof EvaUnit01Entity eva&&eva.isPilotProne()||reaction!=null&&(reaction.kind()==CombatFeelR31.DOWN||reaction.kind()==CombatFeelR31.THROWN);
            if(low&&distanceTo(living)<25)mode=SachielStrike.STOMP;
            else if(distanceTo(living)<17&&strikeChoice%2==0)mode=SachielStrike.SHOVE;
            else if(distanceTo(living)>31&&spearCooldown<=15)mode=SachielStrike.PILE;
        }
        return beginStrike(living,mode);
    }
    public void cancelStrikeR31()
    {if(isStrikeActive()){entityData.set(STRIKE_AGE,-1);strikeTarget=null;strikeHit=false;meleeRecovery=Math.max(meleeRecovery,6);}getNavigation().stop();}
    public boolean beginStrike(LivingEntity target,int mode)
    {
        if(level().isClientSide||isStrikeActive()||isFirstBattleActive()||!target.isAlive()||meleeRecovery>0||CombatFeelR31.restrained(this)||EvaCombatR31.holds(this))return false;
        if(SachielGameplayMotionR32.phrases())entityData.set(STRIKE_FROM,EvaShutdownR30.encode(SachielBodyPoseR35.sample(this,0)));
        mode=Math.max(1,Math.min(SachielGameplayMotionR32.ready()?6:5,mode));strikeTarget=target;strikeHit=false;committedStrikeYaw=yBodyRot;strikeChoice++;
        strikeAdvance=mode==SachielStrike.PILE?0:(float)Math.min(mode==SachielStrike.OVERHEAD?2:5,Math.max(0,distanceTo(target)-17));
        entityData.set(STRIKE_MODE,mode);entityData.set(STRIKE_AIM,com.projectseele.physics.CombatBodyContacts.strikeAim(this,target).toVector3f());entityData.set(STRIKE_AGE,0);getNavigation().stop();return true;
    }
    private void tickStrike()
    {
        if(CombatFeelR31.hitPaused(this))return;
        int mode=strikeMode(),age=entityData.get(STRIKE_AGE)+1;entityData.set(STRIKE_AGE,age);getNavigation().stop();setDeltaMovement(getDeltaMovement().multiply(0,1,0));
        if(age<=SachielStrike.windup(mode)-4&&strikeTarget!=null&&strikeTarget.isAlive())
        {
            Vec3 to=strikeTarget.position().subtract(position());float wanted=(float)Math.toDegrees(Math.atan2(-to.x,to.z));
            committedStrikeYaw=net.minecraft.util.Mth.approachDegrees(committedStrikeYaw,wanted,3);
            entityData.set(STRIKE_AIM,com.projectseele.physics.CombatBodyContacts.strikeAim(this,strikeTarget).toVector3f());
        }
        setYRot(committedStrikeYaw);yBodyRot=yHeadRot=committedStrikeYaw;
        double step=strikeAdvance*(SachielStrike.drive(mode,age)-SachielStrike.drive(mode,age-1));
        if(SachielGameplayMotionR32.ready())
        {
            Vec3 local=SachielGameplayMotionR32.travel(mode,age).subtract(SachielGameplayMotionR32.travel(mode,age-1));double yaw=Math.toRadians(committedStrikeYaw);
            Vec3 movement=new Vec3(Math.cos(yaw)*local.x+Math.sin(yaw)*local.z,0,Math.sin(yaw)*local.x-Math.cos(yaw)*local.z).scale(35);
            movement=CombatSpacingR32.clip(this,movement);
            boolean ground=onGround();move(net.minecraft.world.entity.MoverType.SELF,movement);
            if(ground&&level().getBlockCollisions(this,getBoundingBox().deflate(.1).move(0,-.15,0)).iterator().hasNext())setOnGround(true);
        }
        else if(step>0){double yaw=Math.toRadians(committedStrikeYaw);move(net.minecraft.world.entity.MoverType.SELF,new Vec3(-Math.sin(yaw)*step,0,Math.cos(yaw)*step));}
        if(age==SachielStrike.windup(mode))CombatFoleyR36.swing(this);
        if(age>=(SachielGameplayMotionR32.ready()?SachielStrike.windup(mode):SachielStrike.contactStart(mode))&&age<=SachielStrike.contactEnd(mode)&&!strikeHit&&strikeTarget!=null&&strikeTarget.isAlive())
        {
            for(int sample=0;sample<=4&&!strikeHit;sample++)
            {
            for(int hand=0;hand<(SachielStrike.bothHands(mode)?2:1)&&!strikeHit;hand++)
            {
            boolean left=SachielStrike.bothHands(mode)?hand==1:SachielStrike.strikingLeft(mode);
            float time=age-1+sample/4F;var f=SachielStrike.sample(this,time,1,left);
            var prior=SachielStrike.sample(this,time-.25F,1,left);
            Vec3 start=mode==SachielStrike.PILE?f.hand():prior.hand().subtract(f.direction().scale(1.4));Vec3 tip=mode==SachielStrike.PILE?f.tip():f.hand().add(f.direction().scale(1.4));
            var wall=level().clip(new net.minecraft.world.level.ClipContext(start,tip,net.minecraft.world.level.ClipContext.Block.COLLIDER,net.minecraft.world.level.ClipContext.Fluid.NONE,this));
            var contact=com.projectseele.physics.CombatBodyContacts.clip(strikeTarget,start,wall.getLocation(),1.1);
            if(contact.isPresent())
            {
                Vec3 impact=contact.orElse(start);
                strikeHit=true;boolean hit=com.projectseele.event.EvaHitFeedback.hurt(strikeTarget,damageSources().mobAttack(this),mode==SachielStrike.PILE?55:(float)getAttributeValue(Attributes.ATTACK_DAMAGE),impact,f.direction());
                if(hit)
                {
                    if(!(strikeTarget instanceof EvaUnit01Entity))strikeTarget.push(f.direction().x*.65,.16,f.direction().z*.65);
                    CombatFoleyR36.impact(this,strikeTarget,impact,false,mode==SachielStrike.OVERHEAD||mode==SachielStrike.STOMP);
                }
            }
            }
            }
        }
        if(age>=SachielStrike.duration(mode))
        {
            if(SachielGameplayMotionR32.naturalRecovery())
            {
                var release=EvaShutdownR30.encode(SachielBodyPoseR35.sample(this,0));
                release.putLong("r40_release_at",level().getGameTime());release.putFloat("r40_release_yaw",getYRot());
                release.putDouble("r40_release_x",getX());release.putDouble("r40_release_z",getZ());entityData.set(STRIKE_FROM,release);
            }
            entityData.set(STRIKE_AGE,-1);strikeTarget=null;meleeRecovery=mode==SachielStrike.OVERHEAD||mode==SachielStrike.STOMP?16:mode==SachielStrike.JAB&&strikeHit?4:8;
        }
    }
    private boolean firstBattleUsed,firstBattleDeathResolved;
    private float firstBattlePreviousField;
    @Override public FirstBattleSignals.SignalSet firstBattleSignals(){return FIRST_BATTLE;}
    @Override public boolean isFirstBattleEva(){return false;}
    public boolean isFirstBattleActive(){return FIRST_BATTLE.active(this);}
    public boolean hasUsedFirstBattle(){return firstBattleUsed;}
    @Override protected void defineSynchedData(){super.defineSynchedData();FIRST_BATTLE.define(this.entityData);SachielTacticsR34.define(this.entityData);this.entityData.define(FIELD,900F);this.entityData.define(STRIKE_AGE,-1);this.entityData.define(STRIKE_MODE,0);this.entityData.define(STRIKE_AIM,new org.joml.Vector3f());this.entityData.define(STRIKE_FROM,new CompoundTag());}
    public void beginFirstBattle(FirstBattleSignals.Spec spec,int partner)
    {
        entityData.set(STRIKE_AGE,-1);strikeTarget=null;firstBattlePreviousField=atField;firstBattleUsed=true;selfDestructTicks=-1;this.getNavigation().stop();FIRST_BATTLE.begin(this,spec,partner,-1);setFirstBattleField(900);
    }
    public void endFirstBattle(){if(isFirstBattleActive())FIRST_BATTLE.end(this);}
    public void recoverFirstBattle(){endFirstBattle();setFirstBattleField(firstBattlePreviousField);}
    public void setFirstBattleField(float value){atField=Math.max(0,value);this.entityData.set(FIELD,atField);}
    public void finishFirstBattle(EvaUnit01Entity eva,net.minecraft.server.level.ServerPlayer pilot)
    {
        if(firstBattleDeathResolved||!this.isAlive())return;firstBattleDeathResolved=true;this.setLastHurtByPlayer(pilot);this.setHealth(0);this.die(this.damageSources().mobAttack(eva));
    }
    @Override public void aiStep()
    {
        FIRST_BATTLE.clientPhysics(this);if(isFirstBattleActive()){FirstBattleClip.applyKinematics(this);return;}
        if(!level().isClientSide&&(EvaCombatR31.constrainVictim(this)||CombatFeelR31.travel(this)))return;
        if(!level().isClientSide&&CombatFeelR31.hitPaused(this)){setDeltaMovement(0,getDeltaMovement().y,0);getNavigation().stop();return;}
        super.aiStep();
    }
    private static final RawAnimation ANIM_IDLE = RawAnimation.begin().thenLoop("animation.Sachiel.idle");
    private static final RawAnimation ANIM_WALK = RawAnimation.begin().thenLoop("animation.Sachiel.move");
    private final AnimatableInstanceCache geoCache = GeckoLibUtil.createInstanceCache(this);
    private static final float AT_FIELD_MAX = 900.0F;
    private float atField = AT_FIELD_MAX;
    private int spearCooldown = 45;
    private int selfDestructTicks = -1;
    private BlockPos siegeBeacon;

    public SachielEntity(EntityType<? extends SachielEntity> type, Level level)
    {
        super(type, level);
        this.setMaxUpStep(2.0F);
    }
    @Override protected net.minecraft.world.phys.AABB makeBoundingBox()
    {var box=com.projectseele.physics.CombatBodyDynamics.bounds(this);return box==null?super.makeBoundingBox():box;}
    @Override public boolean canAttack(net.minecraft.world.entity.LivingEntity target)
    {return !(target instanceof EvaUnit01Entity eva&&EvaShutdownR30.wreck(eva))&&super.canAttack(target);}

    @Override public void move(net.minecraft.world.entity.MoverType type,Vec3 motion)
    {
        if(tickCount>0&&!isFirstBattleActive()&&!CombatFeelR31.restrained(this)&&!EvaCombatR31.holds(this))motion=CombatSpacingR32.clip(this,motion);
        super.move(type,motion);
    }

    public static AttributeSupplier.Builder createAttributes()
    {
        return Monster.createMonsterAttributes()
                .add(Attributes.MAX_HEALTH, 800.0D)
                .add(Attributes.ARMOR, 10.0D)
                .add(Attributes.MOVEMENT_SPEED, 0.28D)
                .add(Attributes.ATTACK_DAMAGE, 42.0D)
                .add(Attributes.KNOCKBACK_RESISTANCE, 1.0D)
                .add(Attributes.FOLLOW_RANGE, 96.0D);
    }

    @Override
    protected void registerGoals()
    {
        this.goalSelector.addGoal(1,new SachielTacticsR36(this));
        this.goalSelector.addGoal(1,new SachielTacticsR34(this));
        this.goalSelector.addGoal(2, new MeleeAttackGoal(this, 1.0D, true){@Override public boolean canUse(){return !SachielGameplayMotionR32.directed()&&super.canUse();}});
        this.goalSelector.addGoal(7, new WaterAvoidingRandomStrollGoal(this, 0.65D));
        this.targetSelector.addGoal(1, new NearestAttackableTargetGoal<>(this, EvaUnit01Entity.class, true));
        this.targetSelector.addGoal(2, new NearestAttackableTargetGoal<>(this, Player.class, true));
    }

    @Override
    public void tick()
    {
        super.tick();
        if(isFirstBattleActive())return;
        if(!this.level().isClientSide&&!firstBattleUsed&&this.getHealth()<=this.getMaxHealth()*.32F&&this.tickCount%5==0)
        {
            // Contact root motion can temporarily clear vanilla's onGround bit.
            // Retry once the pair settles; rifle damage is eligible as well.
            for(var eva:this.level().getEntitiesOfClass(EvaUnit01Entity.class,this.getBoundingBox().inflate(48,80,48),e->e.getPilotEntity()!=null))
                if(com.projectseele.event.FirstBattleDirector.tryStart(this,eva,false))return;
        }
        if (this.level().isClientSide)
        {
            return;
        }
        this.entityData.set(FIELD,this.atField);
        if(isFirstBattleActive())return;
        if(CombatFeelR31.restrained(this)||EvaCombatR31.holds(this))
        {var reaction=CombatFeelR31.beat(this);if(EvaCombatR31.holds(this)||reaction!=null&&reaction.kind()>=CombatFeelR31.STAGGER&&reaction.kind()<=CombatFeelR31.THROWN)cancelStrikeR31();return;}
        if(meleeRecovery>0)meleeRecovery--;
        if (this.selfDestructTicks >= 0)
        {
            this.setDeltaMovement(Vec3.ZERO);
            if (--this.selfDestructTicks <= 0)
            {
                selfDestruct();
            }
            return;
        }
        if(isStrikeActive()){if(spearCooldown>0)spearCooldown--;tickStrike();return;}
        LivingEntity target = this.getTarget();
        if(!SachielGameplayMotionR32.directed()&&target!=null&&target.isAlive()&&distanceToSqr(target)<34*34&&meleeRecovery==0&&hasLineOfSight(target))
        {doHurtTarget(target);if(isStrikeActive())return;}
        if ((target == null || !target.isAlive()) && this.siegeBeacon != null)
        {
            if (this.distanceToSqr(Vec3.atCenterOf(this.siegeBeacon)) > 64.0D)
            {
                this.getNavigation().moveTo(this.siegeBeacon.getX() + 0.5D,
                        this.siegeBeacon.getY(), this.siegeBeacon.getZ() + 0.5D,
                        1.0D);
            }
            else
            {
                this.getNavigation().stop();
            }
        }
        if (!SachielGameplayMotionR32.directed()&&target != null && target.isAlive() && --this.spearCooldown <= 0)
        {
            this.spearCooldown = 75;
            if (this.distanceToSqr(target) > 100.0D && this.distanceToSqr(target) < 3600.0D
                    && this.hasLineOfSight(target))
            {
                beginStrike(target,2);
            }
        }
        if (this.getHealth() <= this.getMaxHealth() * 0.14F)
        {
            this.selfDestructTicks = 60;
        }
    }

    @Override
    public boolean hurt(DamageSource source, float amount)
    {
        if(isFirstBattleActive())return source.is(net.minecraft.tags.DamageTypeTags.BYPASSES_INVULNERABILITY)&&super.hurt(source,amount);
        if (this.selfDestructTicks >= 0)
        {
            return false;
        }
        if (this.atField > 0.0F && !com.projectseele.combat.AtFieldRules.bypassesAtField(source))
        {
            if (source.getEntity() instanceof EvaUnit01Entity eva && eva.isMeleeWeapon())
            {
                this.atField = Math.max(0.0F, this.atField - amount);
                this.entityData.set(FIELD,this.atField);
                if (this.level() instanceof ServerLevel server)
                {
                    AtFieldFX.ripple(server, this.getBoundingBox().getCenter(), eva.getForward());
                }
                return true;
            }
            return false;
        }
        if (amount >= this.getHealth())
        {
            this.setHealth(1.0F);
            if(source.getEntity() instanceof EvaUnit01Entity eva&&com.projectseele.event.FirstBattleDirector.tryStart(this,eva,false))return true;
            this.selfDestructTicks = 45;
            return true;
        }
        boolean accepted=super.hurt(source,amount);
        if(accepted&&source.getEntity() instanceof EvaUnit01Entity eva)com.projectseele.event.FirstBattleDirector.tryStart(this,eva,false);
        return accepted;
    }

    private void selfDestruct()
    {
        if (!(this.level() instanceof ServerLevel server))
        {
            return;
        }
        Vec3 center = this.position().add(0.0D, 8.0D, 0.0D);
        com.projectseele.event.FirstBattleMission.naturalResolution(this);
        CrossExplosionFX.spawn(server, center, 2.2F);
        SeeleNetwork.CHANNEL.send(PacketDistributor.TRACKING_ENTITY_AND_SELF.with(() -> this),
                new ClientboundNukeFxPacket(center.x, center.y, center.z, 3.2F, false));
        server.explode(this, this.getX(), this.getY() + 4.0D, this.getZ(), 16.0F, ExplosionInteraction.MOB);
        this.discard();
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
        FIRST_BATTLE.save(this,tag);tag.putFloat("SachielAtField",atField);tag.putInt("SachielSelfDestruct",selfDestructTicks);tag.putBoolean("FirstBattleUsed",firstBattleUsed);tag.putBoolean("FirstBattleDeathResolved",firstBattleDeathResolved);tag.putFloat("FirstBattlePreviousField",firstBattlePreviousField);
        tag.putInt("StrikeChoiceR31",strikeChoice);tag.putInt("MeleeRecoveryR31",meleeRecovery);
        if (this.siegeBeacon != null)
        {
            tag.putLong("SiegeBeacon", this.siegeBeacon.asLong());
        }
    }

    @Override
    public void readAdditionalSaveData(CompoundTag tag)
    {
        super.readAdditionalSaveData(tag);
        entityData.set(STRIKE_AGE,-1);strikeTarget=null;strikeHit=false;
        strikeChoice=Math.max(0,tag.getInt("StrikeChoiceR31"));meleeRecovery=Math.max(0,Math.min(30,tag.getInt("MeleeRecoveryR31")));
        atField=tag.contains("SachielAtField")?tag.getFloat("SachielAtField"):900;this.entityData.set(FIELD,atField);
        selfDestructTicks=tag.contains("SachielSelfDestruct")?tag.getInt("SachielSelfDestruct"):-1;firstBattleUsed=tag.getBoolean("FirstBattleUsed");firstBattleDeathResolved=tag.getBoolean("FirstBattleDeathResolved");firstBattlePreviousField=tag.getFloat("FirstBattlePreviousField");FIRST_BATTLE.restore(this,tag);
        this.siegeBeacon = tag.contains("SiegeBeacon")
                ? BlockPos.of(tag.getLong("SiegeBeacon")) : null;
    }

    public float getAtField()
    {
        return this.level().isClientSide?this.entityData.get(FIELD):this.atField;
    }

    @Override
    public void registerControllers(AnimatableManager.ControllerRegistrar controllers)
    {
        controllers.add(new AnimationController<>(this, "base", 6, state ->
                state.setAndContinue(state.isMoving()&&!CombatFeelR31.restrained(this)&&!EvaCombatR31.holds(this)&&!isStrikeActive() ? ANIM_WALK : ANIM_IDLE)));
    }

    @Override
    public AnimatableInstanceCache getAnimatableInstanceCache()
    {
        return this.geoCache;
    }
}
