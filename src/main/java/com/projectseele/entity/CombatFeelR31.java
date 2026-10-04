package com.projectseele.entity;

import com.projectseele.network.ClientboundCombatFeelR31;
import com.projectseele.network.SeeleNetwork;
import com.projectseele.util.WeakIdentityMap;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.MoverType;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.network.PacketDistributor;
import java.util.*;

/** Combat reactions own their short recovery window, not the world's clock. */
public final class CombatFeelR31
{
    public static final int FLINCH=1,STAGGER=2,DOWN=3,THROWN=4,CONTACT=5,BLOCKED=6;
    public record Beat(int kind,long start,int duration,Vec3 direction,float strength,int stopTicks) {}
    private static final WeakIdentityMap<LivingEntity,Beat> BEATS=new WeakIdentityMap<>();
    private static final WeakIdentityMap<LivingEntity,Double> POISE=new WeakIdentityMap<>();
    private static final WeakIdentityMap<LivingEntity,Long> POISE_AT=new WeakIdentityMap<>();
    private static final WeakIdentityMap<LivingEntity,Float> PHASES=new WeakIdentityMap<>();
    public static Beat beat(LivingEntity e){if(com.projectseele.physics.CombatBodyDynamics.rawSampling(e))return null;var b=BEATS.get(e);return b!=null&&e.level().getGameTime()-b.start<b.duration?b:null;}
    public static float age(LivingEntity e,float partial){var b=beat(e);return b==null?0:(float)((e.level().getGameTime()-b.start)+(double)partial);}
    public static boolean restrained(LivingEntity e){if(com.projectseele.physics.CombatBodyDynamics.active(e))return true;var b=beat(e);return b!=null&&b.kind>=STAGGER&&b.kind<=THROWN&&age(e,0)<(b.kind==STAGGER?7:b.duration-8);}
    public static boolean hitPaused(LivingEntity e){var b=beat(e);return b!=null&&age(e,0)<b.stopTicks;}
    public static void clear(LivingEntity e){BEATS.remove(e);POISE.remove(e);POISE_AT.remove(e);PHASES.remove(e);com.projectseele.physics.CombatBodyDynamics.cancel(e);}
    public static float frozenPhase(EvaUnit01Entity e){return PHASES.getOrDefault(e,e.combatPhaseR31());}
    public static void receive(LivingEntity e,Beat beat,float phase){CombatReactionsR36.capture(e,beat);BEATS.put(e,beat);PHASES.put(e,phase);}
    public static void send(LivingEntity e,int kind,Vec3 direction,float strength,int duration,int stop)
    {
        if(!(e.level() instanceof ServerLevel))return;
        if(kind==CONTACT&&restrained(e))return;
        var current=beat(e);
        if(kind==CONTACT&&current!=null&&current.kind()!=CONTACT&&age(e,0)<current.duration())return;
        if(current!=null&&(current.kind==THROWN&&kind!=THROWN&&kind!=DOWN||current.kind==DOWN&&(kind==FLINCH||kind==STAGGER||kind==DOWN&&age(e,0)<current.duration-8)))return;
        var beat=new Beat(kind,e.level().getGameTime(),duration,direction,strength,stop);CombatReactionsR36.capture(e,beat);BEATS.put(e,beat);
        float phase=e instanceof EvaUnit01Entity eva?eva.combatPhaseR31():0;PHASES.put(e,phase);
        if((kind==DOWN||kind==THROWN)&&e instanceof EvaPrototypeEntity un)un.stopUNFlight();
        SeeleNetwork.CHANNEL.send(PacketDistributor.TRACKING_ENTITY_AND_SELF.with(()->e),new ClientboundCombatFeelR31(e.getId(),beat,phase));
        if(kind!=CONTACT&&e instanceof Mob mob)mob.getNavigation().stop();
        if(kind>=STAGGER&&kind<=THROWN&&e instanceof EvaUnit01Entity eva){eva.interruptCombatR31();EvaCombatR31.clear(eva);}
    }
    public static void acceptedHit(LivingEntity target,LivingEntity source,float damage,Vec3 direction,boolean guard)
    {acceptedHit(target,source,damage,direction,guard,target.getBoundingBox().getCenter());}
    public static void acceptedHit(LivingEntity target,LivingEntity source,float damage,Vec3 direction,boolean guard,Vec3 point)
    {
        if(target instanceof EvaUnit01Entity eva&&(eva.isFirstBattleActive()||eva.isNervLogisticsLocked()||EvaShutdownR30.wreck(eva)))return;
        if(target instanceof FirstBattleSignals.Actor actor&&actor.firstBattleSignals().active(target))return;
        boolean melee=source instanceof EvaUnit01Entity eva&&eva.isMeleeWeapon()||source instanceof Angel;
        boolean crushing=source instanceof SachielEntity sachiel&&(sachiel.strikeMode()==SachielStrike.OVERHEAD||sachiel.strikeMode()==SachielStrike.STOMP)
                ||source instanceof EvaUnit01Entity eva&&(eva.isHeavyMotionActive()||eva.isKickMotionActive(1)||EvaCombatR31.action(eva)==EvaCombatR31.AIR_SLAM);
        float strength=(float)Math.min(1.35,.25+Math.sqrt(damage/Math.max(1,target.getMaxHealth()))*2.2);
        long now=target.level().getGameTime(),last=POISE_AT.getOrDefault(target,now);
        double poise=Math.max(0,POISE.getOrDefault(target,0D)-(now-last)*.012)+(guard?.08:melee?strength:.10);
        POISE_AT.put(target,now);int kind=guard?BLOCKED:crushing||poise>3.20?DOWN:melee?STAGGER:FLINCH;
        var previous=beat(target);
        if(kind==STAGGER&&target instanceof EvaUnit01Entity e&&e.getOrdinaryAttackStage()>=0)
        {
            float phase=e.getOrdinaryAttackProgress(0);
            if(phase>=.18F&&phase<=.66F)kind=FLINCH;
        }
        if(kind==STAGGER&&target instanceof EvaUnit01Entity e&&EvaBerserkMotionR34.striking(e))kind=FLINCH;
        if(kind==STAGGER&&target instanceof SachielEntity&&previous!=null&&previous.kind()==STAGGER)kind=FLINCH;
        if(kind==STAGGER&&target instanceof SachielEntity s&&s.isStrikeActive()
                &&(s.strikeMode()==SachielStrike.OVERHEAD||s.strikeMode()==SachielStrike.PILE||s.strikeMode()==SachielStrike.STOMP||s.strikeMode()==SachielStrike.SHOVE)
                &&s.strikeAge(0)>=3&&s.strikeAge(0)<=SachielStrike.contactEnd(s.strikeMode()))kind=FLINCH;
        if(kind==DOWN)poise=0;POISE.put(target,poise);
        if(target instanceof EvaUnit01Entity frozen&&EvaShutdownR30.retainsPoseR45(frozen)
                &&kind!=DOWN&&!com.projectseele.physics.CombatBodyDynamics.active(target))return;
        if(!guard&&(kind==DOWN||com.projectseele.physics.CombatBodyDynamics.active(target)))
            com.projectseele.physics.CombatBodyDynamics.start(target,point,direction,strength);
        send(target,kind,direction,strength,kind==DOWN?64:kind==STAGGER?16:10,guard?1:crushing?2:1);
        if(source!=null&&melee)send(source,CONTACT,direction,strength,6,crushing?2:1);
    }
    public static void throwBody(LivingEntity target,Vec3 velocity)
    {
        send(target,THROWN,velocity,1.2F,100,0);target.setOnGround(false);target.setDeltaMovement(velocity);target.hasImpulse=true;target.hurtMarked=true;
        com.projectseele.physics.CombatBodyDynamics.thrown(target,velocity);
    }
    /** Server mobs and the real local EVA driver integrate the same impulse. */
    public static boolean travel(LivingEntity e)
    {
        if(com.projectseele.physics.CombatBodyDynamics.active(e)){e.setDeltaMovement(Vec3.ZERO);return true;}
        var b=beat(e);if(b==null||b.kind==CONTACT||b.kind==BLOCKED)return false;
        if(b.kind==FLINCH)
        {
            // Committing to a blow keeps the attack, not immunity to momentum.
            // A short skid leaves its arm action intact while the body yields.
            if(e instanceof SachielEntity&&CombatReactionsR36.enabled(e)&&!e.level().isClientSide)
            {
                float age=age(e,0);
                if(age>=b.stopTicks&&age<6)
                {
                    boolean grounded=e.onGround();double speed=1.15*b.strength*Math.exp(-(age-b.stopTicks)/3);
                    Vec3 force=b.direction.multiply(1,0,1).normalize().scale(speed);e.move(MoverType.SELF,CombatSpacingR32.clip(e,force));
                    if(grounded&&e.level().getBlockCollisions(e,e.getBoundingBox().deflate(.1).move(0,-.15,0)).iterator().hasNext())e.setOnGround(true);
                }
            }
            return false;
        }
        if(e instanceof EvaUnit01Entity eva&&(eva.isNervLogisticsLocked()||!eva.isControlledByLocalInstance()))return false;
        if(!(e instanceof EvaUnit01Entity)&&e.level().isClientSide)return false;
        double t=age(e,0);if(t>=(b.kind==STAGGER?7:b.duration-8))return false;
        Vec3 v=e.getDeltaMovement();
        if(t<b.stopTicks){e.setDeltaMovement(0,v.y,0);return true;}
        if(b.kind!=THROWN)
        {
            double speed=(b.kind==DOWN?2.9:b.kind==STAGGER?1.6:.55)*b.strength*Math.exp(-(t-b.stopTicks)/6);
            Vec3 d=b.direction.multiply(1,0,1).normalize();v=new Vec3(d.x*speed,v.y,d.z*speed);
        }
        boolean grounded=e.onGround();e.move(MoverType.SELF,v);e.resetFallDistance();
        if(grounded&&Math.abs(v.y)<.002)
        {
            var box=e.getBoundingBox();var sole=new net.minecraft.world.phys.AABB(box.minX+.1,box.minY-.12,box.minZ+.1,box.maxX-.1,box.minY+.01,box.maxZ-.1);
            if(e.level().getBlockCollisions(e,sole).iterator().hasNext())e.setOnGround(true);
        }
        double gravity=e.isNoGravity()?0:.32;
        e.setDeltaMovement(v.x*(e.onGround()?.62:.97),e.onGround()?0:(e.verticalCollision?0:v.y-gravity)*.98,v.z*(e.onGround()?.62:.97));
        if(b.kind==THROWN&&e.onGround()&&t>3)
        {
            if(e.level() instanceof ServerLevel level)
            {
                send(e,DOWN,b.direction.normalize(),1.2F,46,2);
                var floor=level.getBlockState(e.blockPosition().below());
                level.sendParticles(new net.minecraft.core.particles.BlockParticleOption(net.minecraft.core.particles.ParticleTypes.BLOCK,floor),e.getX(),e.getY()+.4,e.getZ(),64,7,.6,7,.16);
                level.sendParticles(net.minecraft.core.particles.ParticleTypes.POOF,e.getX(),e.getY()+1,e.getZ(),28,6,.6,6,.15);
                level.playSound(null,e.blockPosition(),com.projectseele.registry.ModSounds.EVA_IMPACT.get(),net.minecraft.sounds.SoundSource.HOSTILE,6,.62F);
            }
            else BEATS.put(e,new Beat(DOWN,e.level().getGameTime(),46,b.direction.normalize(),1.2F,2));
        }
        return true;
    }
    private CombatFeelR31() {}
}
