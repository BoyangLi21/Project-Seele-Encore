package com.projectseele.entity;

import com.projectseele.event.EvaHitFeedback;
import com.projectseele.registry.ModSounds;
import com.projectseele.util.WeakIdentityMap;
import net.minecraft.core.particles.BlockParticleOption;
import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.network.syncher.*;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.sounds.SoundSource;
import net.minecraft.util.Mth;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.level.ClipContext;
import net.minecraft.world.phys.*;
import java.util.*;

/** Player-controlled aerial strikes. */
public final class EvaCombatR31
{
    public static final int NONE=0,AIR_STRIKE=1,AIR_SLAM=2,LAND=6;
    private static final EntityDataAccessor<Integer> ACTION=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.INT);
    private static final EntityDataAccessor<Long> SINCE=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.LONG);
    private static final EntityDataAccessor<Long> STROKE=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.LONG);
    private static final EntityDataAccessor<Integer> TARGET=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.INT);
    private static final WeakIdentityMap<EvaUnit01Entity,Runtime> STATES=new WeakIdentityMap<>();
    private static final class Runtime {boolean contact,airborne;Vec3 previousContact;}
    public static boolean bootstrap(){return true;}
    public static void define(SynchedEntityData d){d.define(ACTION,NONE);d.define(SINCE,0L);d.define(STROKE,-1L);d.define(TARGET,-1);}
    public static float strokeAge(EvaUnit01Entity e,float partial){long t=e.getEntityData().get(STROKE);return t<0?-1:e.level().getGameTime()-t+partial;}
    public static int action(EvaUnit01Entity e){return e.getEntityData().get(ACTION);}
    public static float age(EvaUnit01Entity e,float partial){return (float)((e.level().getGameTime()-e.getEntityData().get(SINCE))+(double)partial);}
    public static boolean active(EvaUnit01Entity e){return action(e)!=NONE;}
    public static LivingEntity target(EvaUnit01Entity e){return e.level().getEntity(e.getEntityData().get(TARGET)) instanceof LivingEntity t?t:null;}
    private static Vec3 forward(EvaUnit01Entity e){Vec3 v=e.getForward().multiply(1,0,1);return v.lengthSqr()<1e-8?new Vec3(0,0,1):v.normalize();}
    private static void start(EvaUnit01Entity e,int action,LivingEntity target)
    {e.getEntityData().set(ACTION,action);e.getEntityData().set(SINCE,e.level().getGameTime());e.getEntityData().set(STROKE,-1L);e.getEntityData().set(TARGET,target==null?-1:target.getId());var s=STATES.computeIfAbsent(e,k->new Runtime());s.contact=false;s.previousContact=null;}
    public static void clear(EvaUnit01Entity e)
    {if(!e.level().isClientSide){e.getEntityData().set(ACTION,NONE);e.getEntityData().set(TARGET,-1);}STATES.remove(e);}
    private static boolean available(EvaUnit01Entity e)
    {return !e.level().isClientSide&&!e.isPilotControlLocked()&&!e.isFirstBattleActive()&&!CombatFeelR31.restrained(e)&&e.getPilotEntity()!=null;}
    public static boolean attack(EvaUnit01Entity e,boolean heavy)
    {
        if(active(e))return true;
        // Horizontal authored root motion can clear vanilla's onGround bit.
        // An aerial action needs the same confirmed jump/fall state as the body.
        if(e.onGround()||!e.isVisuallyAirborneForRender()||e.isPilotProne()||!e.isMeleeWeapon())return false;
        if(!available(e))return true;
        if(heavy&&e instanceof EvaPrototypeEntity un&&un.isUNFlying())un.stopUNFlight();
        e.interruptCombatR31();start(e,heavy?AIR_SLAM:AIR_STRIKE,nearest(e,52));STATES.get(e).airborne=true;
        return true;
    }
    private static LivingEntity nearest(EvaUnit01Entity e,double range)
    {
        Vec3 direction=forward(e);
        return com.projectseele.physics.CombatEntityQueryR44.candidates(e.level(),e.getBoundingBox().inflate(range,22,range),t->
                t.isAlive()&&(t instanceof SachielEntity||t instanceof ShamshelEntity||t instanceof ZeruelEntity||t instanceof IsrafelEntity)
                &&t.position().subtract(e.position()).multiply(1,0,1).normalize().dot(direction)>.55&&e.hasLineOfSight(t))
                .stream().filter(t->e.distanceTo(t)<range).min(Comparator.comparingDouble(e::distanceToSqr)).orElse(null);
    }
    public static Vec3 aerialHand(EvaUnit01Entity e,float partial)
    {
        if(EvaGameplayMotionR32.ready(e))return EvaGameplayMotionR32.airContact(e,partial);
        double p=Mth.clamp(age(e,partial)/20,0,1);Vec3 f=forward(e),r=f.cross(new Vec3(0,1,0));
        double drive=CombatMotionR29.ease((p-.22)/.36);
        var desired=e.getPosition(partial).add(0,e.getBbHeight()*(.84-.22*drive),0).add(f.scale(5+17*drive)).add(r.scale(4*(1-drive)));
        return CombatReachR31.clampContact(e,"r",desired,partial);
    }
    public static void tick(EvaUnit01Entity e)
    {
        if(e.level().isClientSide)return;int a=action(e);if(a==NONE)return;
        if(e.isNervLogisticsLocked()||e.isFirstBattleActive()||e.getPilotEntity()==null||EvaShutdownR30.disabled(e)){clear(e);return;}
        var s=STATES.computeIfAbsent(e,k->new Runtime());float age=age(e,0);var victim=target(e);
        if(a==AIR_STRIKE||a==AIR_SLAM)
        {
            if(!e.onGround())s.airborne=true;
            boolean motion=EvaGameplayMotionR32.ready(e);
            if(motion&&strokeAge(e,0)<0&&age>=EvaAirDriveR59.gather(a))
            {e.getEntityData().set(STROKE,e.level().getGameTime());e.playSound(ModSounds.EVA_SWING.get(),2.6F,a==AIR_SLAM?.58F:.75F);}
            float stroke=strokeAge(e,0);
            // The air kick is thrown from high up and is live until the body lands: stopped nine
            // ticks after the stroke, it ended in mid-air on any jump above a low hop.
            boolean kick=a==AIR_SLAM&&motion;
            boolean window=motion?stroke>=0&&(kick||stroke<=9):a==AIR_STRIKE&&age>=6&&age<=18;
            boolean hadContact=s.contact;
            if(window&&!s.contact)
            {
                Vec3 hand=aerialHand(e,1),previous=s.previousContact==null?hand:s.previousContact;
                double radius=kick?AIR_KICK_RADIUS:2;
                // The kicking leg strikes along its length, not only at the foot.
                Vec3 hip=kick?EvaGameplayMotionR32.kickingLeg(e,EvaGameplayMotionR32.side(e,"air_kick"),1)[0]:hand;
                // Vanilla's section index stores a giant at its feet. A small
                // hand-height query omits it even when the hand crosses its body.
                // Broaden only the candidate search; keep the swept contact below.
                for(var t:com.projectseele.physics.CombatEntityQueryR44.candidates(e.level(),new AABB(previous,hand).minmax(new AABB(hip,hip)).inflate(radius),t->t instanceof Angel&&t.isAlive()))
                {
                    var clipped=com.projectseele.physics.CombatBodyContacts.clip(t,previous,hand,radius);
                    if(clipped.isEmpty()&&kick)clipped=com.projectseele.physics.CombatBodyContacts.clip(t,hip,hand,radius);
                    if(clipped.isEmpty())continue;
                    Vec3 hit=clipped.orElse(previous);
                    if(e.distanceTo(t)<45&&visible(e,previous,hit))
                    {Vec3 impulse=hand.subtract(previous).normalize().scale(.35).add(forward(e).scale(.65)).normalize();s.contact=EvaHitFeedback.hurt(t,e.damageSources().mobAttack(e),35,hit,impulse);if(s.contact)break;}
                }
                s.previousContact=hand;
            }
            if(s.contact&&!hadContact)CombatFoleyR36.impact(e,victim,aerialHand(e,1),victim instanceof Angel angel&&angel.getAtField()>0,true);
            if(e.onGround()&&s.airborne&&age>0)
            {
                if(a==AIR_SLAM){if(motion)landingDust(e);else slam(e);}
                else if(motion)hammerImpact(e);
                start(e,LAND,null);return;
            }
            if(age>150)clear(e);return;
        }
        if(a==LAND){if(age>12)clear(e);return;}
    }
    /** How far from the kicking leg an air kick connects (blocks). */
    private static final double AIR_KICK_RADIUS=4;
    private static boolean visible(EvaUnit01Entity e,Vec3 a,Vec3 b)
    {return e.level().clip(new ClipContext(a,b,ClipContext.Block.COLLIDER,ClipContext.Fluid.NONE,e)).getType()==HitResult.Type.MISS;}
    private static void slam(EvaUnit01Entity e)
    {
        var l=(ServerLevel)e.level();Vec3 centre=e.position().add(forward(e).scale(7));
        for(var t:com.projectseele.physics.CombatEntityQueryR44.overlap(l,new AABB(centre,centre).inflate(18,60,18),t->t instanceof Angel&&t.isAlive()))
            if(visible(e,centre.add(0,4,0),t.position().add(0,5,0)))
            {var d=t.position().subtract(centre).multiply(1,0,1).normalize();float hp=t.getHealth();if(EvaHitFeedback.hurt(t,e.damageSources().mobAttack(e),35,t.position().add(0,5,0),d)&&t.getHealth()<hp)CombatFeelR31.send(t,CombatFeelR31.DOWN,d,1.2F,56,3);}
        var floor=l.getBlockState(e.blockPosition().below());
        l.sendParticles(new BlockParticleOption(ParticleTypes.BLOCK,floor),centre.x,centre.y+.3,centre.z,80,8,.4,8,.18);
        l.sendParticles(ParticleTypes.POOF,centre.x,centre.y+1,centre.z,30,7,.5,7,.2);
        l.playSound(null,e.blockPosition(),ModSounds.EVA_IMPACT.get(),SoundSource.PLAYERS,7,.58F);
        CombatFeelR31.send(e,CombatFeelR31.CONTACT,forward(e),1.25F,9,2);
    }
    private static void landingDust(EvaUnit01Entity e)
    {
        var l=(ServerLevel)e.level();var p=e.position();var floor=l.getBlockState(e.blockPosition().below());
        l.sendParticles(new BlockParticleOption(ParticleTypes.BLOCK,floor),p.x,p.y+.3,p.z,90,6,.25,6,.2);
        l.sendParticles(ParticleTypes.POOF,p.x,p.y+1,p.z,18,5,.4,5,.16);
        l.playSound(null,e.blockPosition(),ModSounds.EVA_IMPACT.get(),SoundSource.PLAYERS,6,.58F);
        CombatFeelR31.send(e,CombatFeelR31.CONTACT,forward(e),1.2F,8,2);
    }
    /**
     * The air hammer's fists meet the ground in front of the feet as the body
     * lands: dust and a blow there, and the jolt. Without it the strike ended
     * on a plain landing. Feedback only; the blow's damage is its swing's.
     */
    private static void hammerImpact(EvaUnit01Entity e)
    {
        var l=(ServerLevel)e.level();Vec3 centre=e.position().add(forward(e).scale(7));var floor=l.getBlockState(e.blockPosition().below());
        l.sendParticles(new BlockParticleOption(ParticleTypes.BLOCK,floor),centre.x,centre.y+.3,centre.z,110,7,.3,7,.24);
        l.sendParticles(ParticleTypes.POOF,centre.x,centre.y+1,centre.z,24,6,.4,6,.2);
        l.playSound(null,net.minecraft.core.BlockPos.containing(centre),ModSounds.EVA_IMPACT.get(),SoundSource.PLAYERS,6,.55F);
        CombatFeelR31.send(e,CombatFeelR31.CONTACT,forward(e),1.35F,9,2);
    }
    private EvaCombatR31() {}
}
