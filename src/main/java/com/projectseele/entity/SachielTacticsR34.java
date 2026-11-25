package com.projectseele.entity;

import net.minecraft.network.syncher.*;
import net.minecraft.util.Mth;
import net.minecraft.world.entity.ai.goal.Goal;
import net.minecraft.world.entity.MoverType;
import net.minecraft.world.phys.Vec3;
import org.joml.Vector3f;
import java.util.EnumSet;

/** Distance, recovery and visible player windups govern a continuous exchange. */
public final class SachielTacticsR34 extends Goal
{
    private static final EntityDataAccessor<Float> PHASE=SynchedEntityData.defineId(SachielEntity.class,EntityDataSerializers.FLOAT);
    private static final EntityDataAccessor<Vector3f> MOTION=SynchedEntityData.defineId(SachielEntity.class,EntityDataSerializers.VECTOR3);
    private final SachielEntity actor;
    private int choice,decision,evadeTicks,evadeCooldown;
    private Vec3 velocity=Vec3.ZERO;
    private long previousHit=-1000;
    public SachielTacticsR34(SachielEntity actor){this.actor=actor;setFlags(EnumSet.of(Flag.MOVE,Flag.LOOK));}
    public static void define(SynchedEntityData data){data.define(PHASE,0F);data.define(MOTION,new Vector3f());}
    public static float phase(SachielEntity actor,float partial)
    {
        float now=actor.getEntityData().get(PHASE);
        var move=actor.getEntityData().get(MOTION);float speed=(float)Math.sqrt(move.x*move.x+move.z*move.z);
        return Mth.positiveModulo(now+partial*speed/SachielGameplayMotionR32.stride(),1);
    }
    public static Vector3f motion(SachielEntity actor){return new Vector3f(actor.getEntityData().get(MOTION));}
    @Override public boolean canUse(){return SachielGameplayMotionR32.directed()&&!SachielGameplayMotionR32.phrases()&&!actor.isFirstBattleActive()&&!actor.isSelfDestructing()&&actor.getTarget()!=null&&actor.getTarget().isAlive();}
    public static void recordMotion(SachielEntity actor,Vec3 delta)
    {
        double angle=Math.toRadians(actor.getYRot());float right=(float)(delta.x*Math.cos(angle)+delta.z*Math.sin(angle)),front=(float)(-delta.x*Math.sin(angle)+delta.z*Math.cos(angle));
        actor.getEntityData().set(MOTION,new Vector3f(right,0,front));
        float old=actor.getEntityData().get(PHASE),next=Mth.positiveModulo(old+(float)delta.horizontalDistance()/SachielGameplayMotionR32.stride(),1);actor.getEntityData().set(PHASE,next);
        if(delta.horizontalDistance()>.05&&(next<old||old<.5F&&next>=.5F))CombatFoleyR36.step(actor,actor.position(),false,1);
    }
    @Override public boolean requiresUpdateEveryTick(){return true;}
    @Override public void stop(){velocity=Vec3.ZERO;actor.getEntityData().set(MOTION,new Vector3f());actor.getNavigation().stop();}
    @Override public void tick()
    {
        actor.getNavigation().stop();
        if(actor.isStrikeActive()||CombatFeelR31.restrained(actor)||CombatFeelR31.hitPaused(actor))
        {velocity=Vec3.ZERO;actor.getEntityData().set(MOTION,new Vector3f());return;}
        var target=actor.getTarget();if(target==null)return;
        Vec3 to=target.position().subtract(actor.position()).multiply(1,0,1);double range=to.length();
        Vec3 forward=to.normalize(),side=new Vec3(forward.z,0,-forward.x);
        float yaw=(float)Math.toDegrees(Math.atan2(-forward.x,forward.z));
        actor.setYRot(Mth.approachDegrees(actor.getYRot(),yaw,4.5F));actor.yBodyRot=actor.yHeadRot=actor.getYRot();
        if(evadeCooldown>0)evadeCooldown--;
        var hit=CombatFeelR31.beat(actor);
        if(hit!=null&&hit.kind()!=CombatFeelR31.CONTACT&&hit.start()!=previousHit)
        {
            previousHit=hit.start();
            if(hit.kind()==CombatFeelR31.FLINCH)decision=Math.min(decision,5);
        }
        Vec3 desired;
        if(evadeTicks>0)
        {evadeTicks--;desired=forward.scale(-.7).add(side.scale(choice%2==0?.85:-.85));}
        else
        {
            boolean facing=Math.abs(Mth.wrapDegrees(yaw-actor.getYRot()))<18;
            if(--decision<=0&&actor.strikeReadyR34()&&facing&&range<42&&actor.hasLineOfSight(target))
            {
                var response=CombatFeelR31.beat(target);boolean low=target instanceof EvaUnit01Entity e&&e.isPilotProne()||response!=null&&(response.kind()==CombatFeelR31.DOWN||response.kind()==CombatFeelR31.THROWN);
                int mode=low&&range<26?SachielStrike.STOMP:range>32?SachielStrike.PILE:range<21?SachielStrike.SHOVE:
                        new int[]{SachielStrike.PILE,SachielStrike.SHOVE,SachielStrike.HOOK,SachielStrike.PILE,SachielStrike.OVERHEAD,SachielStrike.JAB}[choice%6];
                if(actor.beginStrike(target,mode)){choice++;decision=8;stop();return;}
            }
            double inward=range>42?1.25:range>29?.70:range<18?-.35:0;
            // Sachiel presses in behind long arms and the forearm lance.
            // Constant boxing circles obscured that silhouette and intent.
            desired=forward.scale(inward);
        }
        velocity=velocity.lerp(desired,.22);Vec3 before=actor.position();
        boolean ground=actor.onGround();actor.move(MoverType.SELF,velocity);actor.setDeltaMovement(0,actor.getDeltaMovement().y,0);
        if(ground&&actor.level().getBlockCollisions(actor,actor.getBoundingBox().deflate(.1).move(0,-.18,0)).iterator().hasNext())actor.setOnGround(true);
        Vec3 delta=actor.position().subtract(before);double angle=Math.toRadians(actor.getYRot());
        float right=(float)(delta.x*Math.cos(angle)+delta.z*Math.sin(angle)),front=(float)(-delta.x*Math.sin(angle)+delta.z*Math.cos(angle));
        actor.getEntityData().set(MOTION,new Vector3f(right,0,front));
        float oldPhase=actor.getEntityData().get(PHASE),newPhase=Mth.positiveModulo(oldPhase+(float)delta.horizontalDistance()/SachielGameplayMotionR32.stride(),1);
        actor.getEntityData().set(PHASE,newPhase);
        if(delta.horizontalDistance()>.05&&(newPhase<oldPhase||oldPhase<.5F&&newPhase>=.5F))
            actor.level().playSound(null,actor.getX(),actor.getY(),actor.getZ(),com.projectseele.registry.ModSounds.EVA_FOOT_CONCRETE.get(),net.minecraft.sounds.SoundSource.HOSTILE,2.4F,.84F);
        if(delta.horizontalDistance()<.035&&desired.lengthSqr()>.3&&++decision>15){evadeTicks=10;decision=0;}
    }
}
