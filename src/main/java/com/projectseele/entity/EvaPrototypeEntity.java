package com.projectseele.entity;

import net.minecraft.world.entity.EntityType;
import net.minecraft.world.level.Level;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.phys.Vec3;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.InteractionResult;
import net.minecraft.network.chat.Component;

/** Independent experimental airframe; it never occupies a canonical Unit-01 fleet slot. */
public final class EvaPrototypeEntity extends EvaUnit01Entity
{
    private static final net.minecraft.network.syncher.EntityDataAccessor<Boolean> FLIGHT=net.minecraft.network.syncher.SynchedEntityData.defineId(EvaPrototypeEntity.class,net.minecraft.network.syncher.EntityDataSerializers.BOOLEAN);
    private static final net.minecraft.network.syncher.EntityDataAccessor<Boolean> LANDING=net.minecraft.network.syncher.SynchedEntityData.defineId(EvaPrototypeEntity.class,net.minecraft.network.syncher.EntityDataSerializers.BOOLEAN);
    private int flightInput,noPilotFlightTicks;
    private long flightInputAt;
    public boolean isUNFlying(){return entityData.get(FLIGHT);}
    public boolean isUNLanding(){return entityData.get(LANDING);}
    public void setFlightInput(int mask){flightInput=mask&3;flightInputAt=level().getGameTime();}
    public void stopUNFlight(){entityData.set(FLIGHT,false);entityData.set(LANDING,false);flightInput=0;setNoGravity(false);}
    public void landUNFlight(){if(isUNFlying())entityData.set(LANDING,true);}
    public void toggleUNFlight(net.minecraft.server.level.ServerPlayer pilot)
    {
        if(getPilotEntity()!=pilot||CombatFeelR31.restrained(this)||EvaCombatR31.active(this))return;
        if(getUNSerial()!=1){pilot.sendSystemMessage(Component.literal("飞行系统仅配置于 EVA-UN-01。"));return;}
        if(isUNFlying()){entityData.set(LANDING,!isUNLanding());pilot.sendSystemMessage(Component.literal(isUNLanding()?"UN-01 自动降落中。":"UN-01 恢复悬停。"));return;}
        if(isNervLogisticsLocked()||!isPoweredOn()||getActivationTicks()>0||isInsideTestHangar()||isPilotProne()||isPilotCrouching()||isFirstBattleActive())
        {pilot.sendSystemMessage(Component.literal("请先完成接入、站立并离开机库，再开启飞行。"));return;}
        entityData.set(FLIGHT,true);entityData.set(LANDING,false);flightInput=0;noPilotFlightTicks=0;setNoGravity(true);
        pilot.sendSystemMessage(Component.literal("UN-01 飞行开启：WASD 平移，空格上升，Shift 下降，Ctrl 加速；F 自动降落。"));
    }
    @Override public boolean isNoGravity(){return isUNFlying()||super.isNoGravity();}
    @Override public void setPilotCrouching(net.minecraft.server.level.ServerPlayer p,boolean crouching){if(!isUNFlying())super.setPilotCrouching(p,crouching);}
    @Override public void toggleProne(net.minecraft.server.level.ServerPlayer p){if(!isUNFlying())super.toggleProne(p);}
    @Override public void pilotJump(net.minecraft.server.level.ServerPlayer p){if(!isUNFlying())super.pilotJump(p);}
    @Override public void pilotJump(net.minecraft.server.level.ServerPlayer p,int id){if(!isUNFlying())super.pilotJump(p,id);}
    @Override public void travel(Vec3 input)
    {
        if(!isUNFlying()){super.travel(input);return;}
        if(CombatFeelR31.travel(this))return;
        if(EvaCombatR31.locksInput(this))input=Vec3.ZERO;
        if(isNervLogisticsLocked()){setDeltaMovement(Vec3.ZERO);return;}
        if(!isControlledByLocalInstance())return;
        double vertical=isUNLanding()?-.48:level().getGameTime()-flightInputAt>10?0:((flightInput&1)!=0?1:0)-((flightInput&2)!=0?1:0);
        double speed=isPilotSprinting()?2.8:1.65;
        Vec3 horizontal=new Vec3(input.x,0,input.z);
        if(horizontal.lengthSqr()>1)horizontal=horizontal.normalize();
        horizontal=horizontal.yRot((float)-Math.toRadians(getYRot())).scale(isUNLanding()?0:speed);
        Vec3 wanted=horizontal.add(0,vertical*(isUNLanding()?1:1.25),0);
        Vec3 velocity=getDeltaMovement().lerp(wanted,.14);
        move(net.minecraft.world.entity.MoverType.SELF,velocity);
        setDeltaMovement(horizontalCollision?new Vec3(0,velocity.y,0):velocity);
        if(verticalCollision)setDeltaMovement(getDeltaMovement().multiply(1,0,1));
        fallDistance=0;
        if(!level().isClientSide&&onGround()&&(isUNLanding()||vertical<0)){stopUNFlight();setDeltaMovement(Vec3.ZERO);}
    }
    public int getUNSerial(){return entityData.get(UN_SERIAL);}
    public void setUNSerial(int serial){entityData.set(UN_SERIAL,net.minecraft.util.Mth.clamp(serial,0,1));}
    @Override public String experimentalAssetName(){return getUNSerial()==1?"eva_un01":"eva_prototype";}
    public Vec3 homePosition(){return new Vec3(getUNSerial()==1?6282.5:6442.5,77,-6205.5);}
    private static final net.minecraft.network.syncher.EntityDataAccessor<Integer> LASER_AGE=net.minecraft.network.syncher.SynchedEntityData.defineId(EvaPrototypeEntity.class,net.minecraft.network.syncher.EntityDataSerializers.INT);
    private static final net.minecraft.network.syncher.EntityDataAccessor<Integer> LASER_COOLDOWN=net.minecraft.network.syncher.SynchedEntityData.defineId(EvaPrototypeEntity.class,net.minecraft.network.syncher.EntityDataSerializers.INT);
    private static final net.minecraft.network.syncher.EntityDataAccessor<Float> EYE_YAW=net.minecraft.network.syncher.SynchedEntityData.defineId(EvaPrototypeEntity.class,net.minecraft.network.syncher.EntityDataSerializers.FLOAT);
    private static final net.minecraft.network.syncher.EntityDataAccessor<Float> EYE_PITCH=net.minecraft.network.syncher.SynchedEntityData.defineId(EvaPrototypeEntity.class,net.minecraft.network.syncher.EntityDataSerializers.FLOAT);
    private static final net.minecraft.network.syncher.EntityDataAccessor<org.joml.Vector3f> LASER_END=net.minecraft.network.syncher.SynchedEntityData.defineId(EvaPrototypeEntity.class,net.minecraft.network.syncher.EntityDataSerializers.VECTOR3);
    private static final net.minecraft.network.syncher.EntityDataAccessor<Integer> UN_SERIAL=net.minecraft.network.syncher.SynchedEntityData.defineId(EvaPrototypeEntity.class,net.minecraft.network.syncher.EntityDataSerializers.INT);
    private final EvaPoseSignalClock eyeClock=new EvaPoseSignalClock();
    @Override protected void defineSynchedData(){super.defineSynchedData();entityData.define(FLIGHT,false);entityData.define(LANDING,false);entityData.define(UN_SERIAL,0);entityData.define(LASER_AGE,-1);entityData.define(LASER_COOLDOWN,0);entityData.define(EYE_YAW,0F);entityData.define(EYE_PITCH,0F);entityData.define(LASER_END,new org.joml.Vector3f());}
    public boolean isEyeLaserActive(){return entityData.get(LASER_AGE)>=0;}
    public float eyeLaserAge(float partial){return level().isClientSide?eyeClock.sample(FirstBattleSignals.clientFrameTime()):entityData.get(LASER_AGE);}
    public int eyeLaserCooldown(){return entityData.get(LASER_COOLDOWN);}
    public float eyeAimYaw(){return entityData.get(EYE_YAW);}
    public float eyeAimPitch(){return entityData.get(EYE_PITCH);}
    public Vec3 eyeLaserEnd(){return new Vec3(entityData.get(LASER_END));}
    public void requestEyeLaser(net.minecraft.server.level.ServerPlayer pilot)
    {
        if(getPilotEntity()!=pilot||!isPoweredOn()||isPilotControlLocked()||isFirstBattleActive()||eyeLaserCooldown()>0)return;
        entityData.set(LASER_AGE,0);entityData.set(LASER_COOLDOWN,40);eyeAim(pilot);
        level().playSound(null,getX(),getY()+53,getZ(),com.projectseele.registry.ModSounds.BEAM_CHARGE.get(),net.minecraft.sounds.SoundSource.PLAYERS,.65F,1.45F);
    }
    private void eyeAim(net.minecraft.server.level.ServerPlayer p)
    {entityData.set(EYE_YAW,getYRot()+net.minecraft.util.Mth.clamp(net.minecraft.util.Mth.wrapDegrees(p.getYRot()-getYRot()),-65,65));entityData.set(EYE_PITCH,net.minecraft.util.Mth.clamp(p.getXRot(),-35,35));}
    @Override public void tick()
    {
        super.tick();if(level().isClientSide)return;com.projectseele.world.UNRecoveryR22.remember(this);com.projectseele.world.UNPlugDirector.tick(this);if(eyeLaserCooldown()>0)entityData.set(LASER_COOLDOWN,eyeLaserCooldown()-1);
        if(com.projectseele.world.UNAirLiftR29.waitingForDock(this)){setNervLogisticsLocked(true);setNoGravity(true);setDeltaMovement(Vec3.ZERO);}
        if(isUNFlying())
        {
            if(getPilotEntity()==null){if(++noPilotFlightTicks>100)landUNFlight();}else noPilotFlightTicks=0;
            if(isNervLogisticsLocked()||getUNSerial()!=1)stopUNFlight();
            else if(onGround()&&(isUNLanding()||(flightInput&2)!=0)&&tickCount>5){stopUNFlight();setDeltaMovement(Vec3.ZERO);}
            fallDistance=0;
        }
        if(!isEyeLaserActive())return;
        if(!(getPilotEntity() instanceof net.minecraft.server.level.ServerPlayer pilot)||!isPoweredOn()||isPilotControlLocked()){entityData.set(LASER_AGE,-1);return;}
        int age=entityData.get(LASER_AGE)+1;entityData.set(LASER_AGE,age);if(age<8)eyeAim(pilot);if(age==8)fireEyeLaser(pilot);if(age>=20)entityData.set(LASER_AGE,-1);
    }
    private void fireEyeLaser(net.minecraft.server.level.ServerPlayer pilot)
    {
        var level=(net.minecraft.server.level.ServerLevel)level();Vec3 eye=EvaUNOptics.eye(this,1),direction=Vec3.directionFromRotation(eyeAimPitch(),eyeAimYaw());Vec3 far=eye.add(direction.scale(256));
        var block=level.clip(new net.minecraft.world.level.ClipContext(eye,far,net.minecraft.world.level.ClipContext.Block.COLLIDER,net.minecraft.world.level.ClipContext.Fluid.NONE,this));Vec3 end=block.getLocation();
        var hit=com.projectseele.physics.CombatDamageTargetsR44.ray(level,eye,end,.3,this,pilot);
        if(hit!=null)
        {
            var target=hit.getEntity();
            end=hit.getLocation();
            boolean shield=target instanceof Angel a&&a.getAtField()>0;
            com.projectseele.physics.CombatDamageTargetsR44.hurt(target,pilot.damageSources().playerAttack(pilot),36,end,direction,com.projectseele.physics.CombatDamageTargetsR44.Weapon.LASER);
            if(shield)com.projectseele.fx.AtFieldFX.ripple(level,end,direction);
        }
        entityData.set(LASER_END,end.toVector3f());level.playSound(null,eye.x,eye.y,eye.z,com.projectseele.registry.ModSounds.BEAM_FIRE.get(),net.minecraft.sounds.SoundSource.PLAYERS,1,1.65F);
        level.sendParticles(net.minecraft.core.particles.ParticleTypes.ELECTRIC_SPARK,end.x,end.y,end.z,20,.55,.55,.55,.12);
        com.projectseele.ProjectSeele.LOGGER.debug("EVA-UN eye pulse {} -> {}",eye,end);
        if("r11-mechanics".equals(System.getProperty("projectseele.regionalBuild","")))com.projectseele.ProjectSeele.LOGGER.info("R11 EYE PULSE origin={} end={} hit={} direction={}",eye,end,hit==null?"none":hit.getEntity().getType(),direction);
    }
    @Override public void onSyncedDataUpdated(net.minecraft.network.syncher.EntityDataAccessor<?> key){super.onSyncedDataUpdated(key);if(key.equals(LASER_AGE)&&eyeClock!=null&&level().isClientSide)eyeClock.accept(entityData.get(LASER_AGE),false,true);}
    @Override public void addAdditionalSaveData(net.minecraft.nbt.CompoundTag t){super.addAdditionalSaveData(t);t.putInt("UNSerial",getUNSerial());t.putInt("UNEyeCooldown",eyeLaserCooldown());t.putBoolean("UNFlight",isUNFlying());t.putBoolean("UNLanding",isUNLanding());}
    @Override public void readAdditionalSaveData(net.minecraft.nbt.CompoundTag t){super.readAdditionalSaveData(t);setUNSerial(t.getInt("UNSerial"));entityData.set(LASER_COOLDOWN,t.getInt("UNEyeCooldown"));entityData.set(LASER_AGE,-1);entityData.set(FLIGHT,getUNSerial()==1&&t.getBoolean("UNFlight"));entityData.set(LANDING,t.getBoolean("UNLanding"));}
    public EvaPrototypeEntity(EntityType<? extends EvaUnit01Entity> type,Level level)
    {
        super(type,level);
    }

    @Override
    public boolean isExperimentalUnit()
    {
        return true;
    }

    public boolean isInsideTestHangar()
    {
        return this.level().dimension().equals(com.projectseele.world.FacilitySchemaV2.DIMENSION)
                && Math.abs(this.getX()-homePosition().x)<=58
                && this.getY()>=76 && this.getY()<=160
                && this.getZ()>=-6288 && this.getZ()<=-6136
                && this.level().getBlockState(net.minecraft.core.BlockPos.containing(homePosition().add(0,-1,0)))
                    .is(com.projectseele.registry.ModBlocks.NERV_FLOOR_PANEL.get());
    }

    @Override
    public InteractionResult tryEnterFromPlug(Player player,boolean requireAim)
    {
        if(this.isNervLogisticsLocked())
        {
            player.displayClientMessage(Component.literal("请先在控制室排空 LCL 并开启试验舱门"),true);
            return InteractionResult.CONSUME;
        }
        var capsule=com.projectseele.world.UNPlugDirector.capsule(this);
        if(capsule!=null)return capsule.tryBoardFromHatch(player);
        return super.tryEnterFromPlug(player,requireAim);
    }

    @Override
    public Vec3 getDismountLocationForPassenger(LivingEntity passenger)
    {
        // This surface project has its own gantry and never borrows Unit-01's capsule.
        if(this.position().distanceTo(homePosition())<4
                &&this.level().dimension().equals(com.projectseele.world.FacilitySchemaV2.DIMENSION))
            return homePosition().add(4,50,-12);
        return super.getDismountLocationForPassenger(passenger);
    }
}
