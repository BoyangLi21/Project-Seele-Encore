package com.projectseele.entity;

import com.projectseele.config.SeeleConfig;
import com.projectseele.registry.ModSounds;
import net.minecraft.network.syncher.*;
import net.minecraft.util.Mth;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.phys.Vec3;

/** Roar and feral strikes share the ordinary mesh/contact path, not instant damage. */
public final class EvaBerserkMotionR34
{
    private static final EntityDataAccessor<Integer> AGE=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.INT);
    private static final EntityDataAccessor<Integer> KIND=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.INT);
    private static final EntityDataAccessor<Float> YAW=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.FLOAT);
    private static final EntityDataAccessor<net.minecraft.nbt.CompoundTag> ORIGIN=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.COMPOUND_TAG);
    private static final com.projectseele.util.WeakIdentityMap<EvaUnit01Entity,Stroke> STROKES=new com.projectseele.util.WeakIdentityMap<>();
    private static final class Stroke {LivingEntity victim;Vec3 previous;boolean hit;}
    public static boolean bootstrap(){return true;}
    public static void clear(EvaUnit01Entity e){e.getEntityData().set(AGE,-1);STROKES.remove(e);}
    public static void define(SynchedEntityData d){d.define(AGE,-1);d.define(KIND,0);d.define(YAW,0F);d.define(ORIGIN,new net.minecraft.nbt.CompoundTag());}
    public static boolean active(EvaUnit01Entity e){return e.isBerserk()&&EvaGameplayMotionR32.directed(e)&&e.getEntityData().get(AGE)>=0;}
    public static boolean striking(EvaUnit01Entity e){return active(e)&&e.getEntityData().get(KIND)>1;}
    public static boolean silent(EvaUnit01Entity e){return active(e)&&e.getEntityData().get(KIND)==0;}
    public static boolean introduction(EvaUnit01Entity e){return active(e)&&e.getEntityData().get(KIND)<=1;}
    public static int kind(EvaUnit01Entity e){return e.getEntityData().get(KIND);}
    public static String name(EvaUnit01Entity e)
    {
        String name=switch(kind(e)){case 2->"berserk_l";case 3->"berserk_r";case 4->"berserk_upper";case 5->"berserk_drive";case 6->"berserk_down";default->"berserk_roar";};
        var p=EvaGameplayMotionR32.profile(EvaGameplayMotionR32.variant(e));
        return p!=null&&p.getAsJsonObject("clips").has("r32_"+name)?name:kind(e)>1?"berserk_r":"berserk_roar";
    }
    public static void save(EvaUnit01Entity e,net.minecraft.nbt.CompoundTag tag)
    {tag.putInt("R37BerserkAge",e.getEntityData().get(AGE));tag.putInt("R37BerserkKind",kind(e));tag.putFloat("R37BerserkYaw",e.getEntityData().get(YAW));tag.put("R37BerserkOrigin",e.getEntityData().get(ORIGIN).copy());}
    public static void load(EvaUnit01Entity e,net.minecraft.nbt.CompoundTag tag)
    {
        e.getEntityData().set(KIND,Mth.clamp(tag.getInt("R37BerserkKind"),0,6));
        e.getEntityData().set(AGE,tag.contains("R37BerserkAge")&&kind(e)<=1?tag.getInt("R37BerserkAge"):-1);
        e.getEntityData().set(YAW,tag.getFloat("R37BerserkYaw"));e.getEntityData().set(ORIGIN,tag.getCompound("R37BerserkOrigin").copy());
    }
    public static int duration(EvaUnit01Entity e){return switch(kind(e)){case 0->36;case 1->60;case 2->18;case 3->17;case 4->16;case 5->20;case 6->22;default->26;};}
    public static float mouth(EvaUnit01Entity e,float partial)
    {
        if(!e.isBerserk()&&!e.isFirstBattleActive())return 0;
        if(e.isFirstBattleActive()&&!e.isBerserk())return 0;
        if(silent(e))return 0;
        if(e.isFirstBattleActive())
        {
            float time=e.firstBattleSignals().time(e,partial);
            if(time>=FirstBattleClip.DEATH_TICK/20F)
                return .72F*(1-EvaDorsalMechanism.smooth((time-FirstBattleClip.DEATH_TICK/20F)/.6F));
        }
        if(active(e)&&kind(e)==1)return EvaDorsalMechanism.smooth((e.getEntityData().get(AGE)+partial-7)/15F);
        return .72F;
    }
    public static EvaBodyPose.Sample stillPose(EvaUnit01Entity e)
    {var p=EvaBodyPose.neutralForTransportR32(e);EvaShutdownR30.decode(e.getEntityData().get(ORIGIN),p);return p;}
    public static float phase(EvaUnit01Entity e,float partial){return Mth.clamp((e.getEntityData().get(AGE)+partial)/duration(e),0,1);}
    public static void begin(EvaUnit01Entity e,int kind,LivingEntity target)
    {
        if(e.level().isClientSide||!EvaGameplayMotionR32.directed(e)||active(e))return;
        var pose=EvaBodyPose.sample(e,0);EvaGameplayMotionR32.beginAction(e);e.getEntityData().set(ORIGIN,EvaShutdownR30.encode(pose));e.getEntityData().set(KIND,kind);e.getEntityData().set(AGE,0);e.getEntityData().set(YAW,e.getYRot());
        Stroke s=new Stroke();s.victim=target;STROKES.put(e,s);
    }
    public static void tick(EvaUnit01Entity e)
    {
        if(!active(e)||e.level().isClientSide)return;
        e.getNavigation().stop();e.setDeltaMovement(0,e.getDeltaMovement().y,0);
        float yaw=e.getEntityData().get(YAW);e.setYRot(yaw);e.yBodyRot=e.yHeadRot=yaw;
        if(CombatFeelR31.hitPaused(e))return;
        int age=e.getEntityData().get(AGE)+1;e.getEntityData().set(AGE,age);
        if(kind(e)==1&&age==16)
        {
            EvaMovementSounds.play(e,e.position().add(0,e.getBbHeight()*.9,0),ModSounds.EVA_BERSERK_ROAR.get(),2.2F,1);
            if(e.getPilotEntity() instanceof net.minecraft.server.level.ServerPlayer pilot)pilot.sendSystemMessage(net.minecraft.network.chat.Component.literal("律子：没有外部供电……初号机在自己动！"));
        }
        if(striking(e))
        {
            float now=phase(e,0),before=Math.max(0,now-1F/duration(e));String clip=name(e),side=EvaGameplayMotionR32.side(e,clip);
            e.moveCombatRootR34(EvaGameplayMotionR32.root(e,clip,now).subtract(EvaGameplayMotionR32.root(e,clip,before)));
            var state=STROKES.get(e);Vec3 hand=EvaGameplayMotionR32.hand(e,side,0);
            if(age==Math.max(3,Math.round(duration(e)*.24F)))
            {
                EvaMovementSounds.swing(e,3);
                EvaMovementSounds.play(e,e.position().add(0,e.getBbHeight()*.85,0),ModSounds.EVA_ATTACK_ROAR.get(),2.4F,1);
            }
            if(state!=null&&state.victim!=null&&state.victim.isAlive()&&!state.hit&&EvaGameplayMotionR32.inContactWindowR45(e,clip,now))
            {
                Vec3 from=state.previous==null?hand:state.previous;
                var contact=com.projectseele.physics.CombatBodyContacts.clip(state.victim,from,hand,1.8);
                // A sweep can touch the victim before its trailing fist meets
                // the floor. Occlusion ends at that first real contact.
                Vec3 point=contact.orElse(hand);
                boolean unobstructed=e.level().clip(new net.minecraft.world.level.ClipContext(from,point,net.minecraft.world.level.ClipContext.Block.COLLIDER,net.minecraft.world.level.ClipContext.Fluid.NONE,e)).getType()==net.minecraft.world.phys.HitResult.Type.MISS;
                if(unobstructed&&contact.isPresent())
                {
                    float multiplier=SeeleConfig.COMMON_SPEC.isLoaded()?SeeleConfig.EVA_BERSERK_DAMAGE_MULTIPLIER.get().floatValue():2.5F;
                    Vec3 direction=state.victim.position().subtract(e.position()).normalize();
                    state.hit=com.projectseele.physics.CombatDamageTargetsR44.hurt(state.victim,e.damageSources().mobAttack(e),20*multiplier,point,direction,
                            com.projectseele.physics.CombatDamageTargetsR44.Weapon.CONTACT,from);
                    if(state.hit)EvaMovementSounds.play(e,point,ModSounds.EVA_IMPACT.get(),5,1);
                }
            }
            if(state!=null)state.previous=hand;
        }
        if(age>=duration(e))
        {
            boolean wake=kind(e)==0;e.getEntityData().set(AGE,-1);STROKES.remove(e);
            if(wake){var frozen=stillPose(e);begin(e,1,null);EvaGameplayMotionR32.beginAction(e,frozen);}
        }
    }
    private EvaBerserkMotionR34(){}
}
