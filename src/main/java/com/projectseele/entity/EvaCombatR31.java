package com.projectseele.entity;

import com.projectseele.event.EvaHitFeedback;
import com.projectseele.registry.ModSounds;
import com.projectseele.util.WeakIdentityMap;
import net.minecraft.core.particles.BlockParticleOption;
import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.network.chat.Component;
import net.minecraft.network.syncher.*;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.sounds.SoundSource;
import net.minecraft.util.Mth;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.entity.MoverType;
import net.minecraft.world.level.ClipContext;
import net.minecraft.world.phys.*;
import java.util.*;

/** Player-controlled aerial strikes and a contact-led, two-hand grapple. */
public final class EvaCombatR31
{
    public static final int NONE=0,AIR_STRIKE=1,AIR_SLAM=2,REACH=3,HOLD=4,THROW=5,LAND=6;
    private static final EntityDataAccessor<Integer> ACTION=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.INT);
    private static final EntityDataAccessor<Long> SINCE=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.LONG);
    private static final EntityDataAccessor<Long> STROKE=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.LONG);
    private static final EntityDataAccessor<Integer> TARGET=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.INT);
    private static final EntityDataAccessor<org.joml.Vector3f> APPROACH_FROM=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.VECTOR3);
    private static final EntityDataAccessor<org.joml.Vector3f> APPROACH_TO=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.VECTOR3);
    private static final EntityDataAccessor<Float> FACING=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.FLOAT);
    private static final WeakIdentityMap<EvaUnit01Entity,Runtime> STATES=new WeakIdentityMap<>();
    private static final class Runtime {boolean contact,airborne;Vec3 previousContact;int cooldown;}
    public static boolean bootstrap(){return true;}
    public static void define(SynchedEntityData d){d.define(ACTION,NONE);d.define(SINCE,0L);d.define(STROKE,-1L);d.define(TARGET,-1);d.define(APPROACH_FROM,new org.joml.Vector3f());d.define(APPROACH_TO,new org.joml.Vector3f());d.define(FACING,0F);}
    public static float strokeAge(EvaUnit01Entity e,float partial){long t=e.getEntityData().get(STROKE);return t<0?-1:e.level().getGameTime()-t+partial;}
    public static int action(EvaUnit01Entity e){return e.getEntityData().get(ACTION);}
    public static float age(EvaUnit01Entity e,float partial){return (float)((e.level().getGameTime()-e.getEntityData().get(SINCE))+(double)partial);}
    public static boolean active(EvaUnit01Entity e){return action(e)!=NONE;}
    public static boolean locksInput(EvaUnit01Entity e){return action(e)>=REACH;}
    public static boolean locksFacing(EvaUnit01Entity e){return action(e)>=REACH&&action(e)<=THROW;}
    public static float facing(EvaUnit01Entity e){return e.getEntityData().get(FACING);}
    public static void approach(EvaUnit01Entity e)
    {
        if(action(e)!=REACH||!e.isControlledByLocalInstance())return;
        Vec3 from=new Vec3(e.getEntityData().get(APPROACH_FROM)),to=new Vec3(e.getEntityData().get(APPROACH_TO));
        Vec3 goal=from.lerp(to,CombatMotionR29.ease(age(e,1)/14)),delta=goal.subtract(e.position()).multiply(1,0,1);
        if(delta.lengthSqr()<1e-10)return;
        boolean grounded=e.onGround();if(delta.length()>1)delta=delta.normalize();e.move(MoverType.SELF,delta);
        if(grounded)
        {
            var b=e.getBoundingBox();var support=new AABB(b.minX+.1,b.minY-.10,b.minZ+.1,b.maxX-.1,b.minY+.01,b.maxZ-.1);
            if(e.level().getBlockCollisions(e,support).iterator().hasNext())e.setOnGround(true);
        }
    }
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
        if(action(e)==HOLD){requestThrow(e);return true;}
        if(active(e))return true;
        // Horizontal authored root motion can clear vanilla's onGround bit.
        // An aerial action needs the same confirmed jump/fall state as the body.
        if(e.onGround()||!e.isVisuallyAirborneForRender()||e.isPilotProne()||!e.isMeleeWeapon())return false;
        if(!available(e))return true;
        if(heavy&&e instanceof EvaPrototypeEntity un&&un.isUNFlying())un.stopUNFlight();
        e.interruptCombatR31();start(e,heavy?AIR_SLAM:AIR_STRIKE,nearest(e,52));STATES.get(e).airborne=true;
        return true;
    }
    public static void grapple(EvaUnit01Entity e,ServerPlayer pilot)
    {
        if(action(e)==HOLD){requestThrow(e);return;}
        if(active(e)||!available(e)||!e.onGround()||e.isPilotProne()||e.isPilotCrouching())return;
        if(e.getWeapon()!=EvaUnit01Entity.WEAPON_FISTS){pilot.displayClientMessage(Component.literal("先收起武器，再用双手抓取。"),true);return;}
        var t=nearest(e,38);
        if(t==null){pilot.displayClientMessage(Component.literal("靠近使徒，面对它再抓取。"),true);return;}
        if(AngelGrappleSurfaceR31.contact(t,true,1)==null){pilot.displayClientMessage(Component.literal("这个姿态下没有稳妥的抓取位置。"),true);return;}
        if(t instanceof SachielEntity s&&s.getAtField()>270)
        {pilot.displayClientMessage(Component.literal("力场还挡着。先近战削弱，再抓住它。"),true);return;}
        if(grappler(t)!=null||t instanceof FirstBattleSignals.Actor a&&a.firstBattleSignals().active(t))return;
        if(e.distanceTo(t)>holdDistance(e,t)+8){pilot.displayClientMessage(Component.literal("再靠近一点，抓住它的上身。"),true);return;}
        Vec3 direction=t.position().subtract(e.position()).multiply(1,0,1).normalize();
        var destination=t.position().subtract(direction.scale(holdDistance(e,t)));destination=new Vec3(destination.x,e.getY(),destination.z);
        e.getEntityData().set(APPROACH_FROM,e.position().toVector3f());e.getEntityData().set(APPROACH_TO,destination.toVector3f());
        e.getEntityData().set(FACING,(float)Math.toDegrees(Math.atan2(-direction.x,direction.z)));
        e.interruptCombatR31();start(e,REACH,t);
    }
    private static LivingEntity nearest(EvaUnit01Entity e,double range)
    {
        Vec3 direction=forward(e);
        return com.projectseele.physics.CombatEntityQueryR44.candidates(e.level(),e.getBoundingBox().inflate(range,22,range),t->
                t.isAlive()&&(t instanceof SachielEntity||t instanceof ShamshelEntity||t instanceof ZeruelEntity||t instanceof IsrafelEntity)
                &&t.position().subtract(e.position()).multiply(1,0,1).normalize().dot(direction)>.55&&e.hasLineOfSight(t))
                .stream().filter(t->e.distanceTo(t)<range).min(Comparator.comparingDouble(e::distanceToSqr)).orElse(null);
    }
    private static double holdDistance(EvaUnit01Entity e,LivingEntity t){return e.isExperimentalUnit()?17.5:18.5;}
    public static EvaUnit01Entity grappler(LivingEntity t)
    {
        for(var e:t.level().getEntitiesOfClass(EvaUnit01Entity.class,t.getBoundingBox().inflate(72)))
            if(target(e)==t&&(action(e)==HOLD||action(e)==THROW&&age(e,0)<16))return e;
        return null;
    }
    public static boolean holds(LivingEntity t){return grappler(t)!=null;}
    public static boolean constrainVictim(LivingEntity t)
    {
        var e=grappler(t);if(e==null)return false;
        if(t.level().isClientSide)return false;
        if(t instanceof Mob mob)mob.getNavigation().stop();t.setDeltaMovement(Vec3.ZERO);t.resetFallDistance();return true;
    }
    public static Vec3 grip(EvaUnit01Entity e,LivingEntity t,boolean left,float partial)
    {
        var surface=AngelGrappleSurfaceR31.contact(t,left,partial);if(surface!=null)return surface.position();
        Vec3 f=forward(e),r=f.cross(new Vec3(0,1,0));Vec3 at=t.getPosition(partial);
        return at.add(0,t.getBbHeight()*.76,0).subtract(f.scale(t.getBbWidth()*.5-.75)).add(r.scale((left?-1:1)*t.getBbWidth()*.23));
    }
    public static Vec3 aerialHand(EvaUnit01Entity e,float partial)
    {
        if(EvaGameplayMotionR32.ready(e))return EvaGameplayMotionR32.airContact(e,partial);
        double p=Mth.clamp(age(e,partial)/20,0,1);Vec3 f=forward(e),r=f.cross(new Vec3(0,1,0));
        double drive=CombatMotionR29.ease((p-.22)/.36);
        var desired=e.getPosition(partial).add(0,e.getBbHeight()*(.84-.22*drive),0).add(f.scale(5+17*drive)).add(r.scale(4*(1-drive)));
        return CombatReachR31.clampContact(e,"r",desired,partial);
    }
    private static void requestThrow(EvaUnit01Entity e)
    {if(action(e)==HOLD&&target(e)!=null)start(e,THROW,target(e));}
    public static void tick(EvaUnit01Entity e)
    {
        if(e.level().isClientSide)return;int a=action(e);if(a==NONE)return;
        if(e.isNervLogisticsLocked()||e.isFirstBattleActive()||e.getPilotEntity()==null||EvaShutdownR30.disabled(e)){clear(e);return;}
        var s=STATES.computeIfAbsent(e,k->new Runtime());float age=age(e,0);var victim=target(e);
        if(a==AIR_STRIKE||a==AIR_SLAM)
        {
            if(!e.onGround())s.airborne=true;
            boolean motion=EvaGameplayMotionR32.ready(e);
            boolean falling=EvaGameplayMotionR32.descending(e);
            boolean strikeHeight=victim==null?EvaGameplayMotionR32.clearance(e,0)<=38:e.getY()<=victim.getBoundingBox().maxY-e.getBbHeight()*.40;
            if(motion&&strokeAge(e,0)<0&&age>=4&&(a==AIR_STRIKE?falling&&strikeHeight:falling||age>=16))
            {e.getEntityData().set(STROKE,e.level().getGameTime());e.playSound(ModSounds.EVA_SWING.get(),2.6F,a==AIR_SLAM?.58F:.75F);}
            float stroke=strokeAge(e,0);
            boolean window=motion?stroke>=0&&(a==AIR_SLAM||stroke<=9):a==AIR_STRIKE&&age>=6&&age<=18;
            if(window&&!s.contact)
            {
                Vec3 hand=aerialHand(e,1),previous=s.previousContact==null?hand:s.previousContact;
                com.projectseele.visual.CombatR31Review.aerialContact(e,previous,hand);
                // Vanilla's section index stores a giant at its feet. A small
                // hand-height query omits it even when the hand crosses its body.
                // Broaden only the candidate search; keep the swept contact below.
                for(var t:com.projectseele.physics.CombatEntityQueryR44.candidates(e.level(),new AABB(previous,hand).inflate(2),t->t instanceof Angel&&t.isAlive()))
                {
                    var clipped=com.projectseele.physics.CombatBodyContacts.clip(t,previous,hand,2);if(clipped.isEmpty())continue;
                    Vec3 hit=clipped.orElse(previous);
                    if(e.distanceTo(t)<45&&visible(e,previous,hit))
                    {Vec3 impulse=hand.subtract(previous).normalize().scale(.35).add(forward(e).scale(.65)).normalize();s.contact=EvaHitFeedback.hurt(t,e.damageSources().mobAttack(e),35,hit,impulse);if(s.contact)break;}
                }
                s.previousContact=hand;
            }
            if(e.onGround()&&s.airborne&&age>0)
            {
                if(a==AIR_SLAM){if(motion)landingDust(e);else slam(e);}start(e,LAND,null);return;
            }
            if(age>150)clear(e);return;
        }
        if(a==LAND){if(age>12)clear(e);return;}
        if(victim==null||!victim.isAlive()||e.distanceTo(victim)>48){clear(e);return;}
        if(a==REACH)
        {
            if(age>=18)
            {
                if(e.distanceTo(victim)>holdDistance(e,victim)+4||!e.hasLineOfSight(victim)||!CombatReachR31.canReach(e,victim,0))
                {if(age>36)clear(e);return;}
                start(e,HOLD,victim);CombatFeelR31.send(victim,CombatFeelR31.STAGGER,forward(e),.8F,24,2);
            }
            return;
        }
        if(a==HOLD||a==THROW&&age<16)
        {
            Vec3 f=forward(e);double lift=6*CombatMotionR29.ease((a==HOLD?age:18)/18);
            double additional=e.getY()+lift-victim.getY();
            if(additional>0&&!CombatReachR31.canReach(e,victim,additional))
            {double lo=0,hi=additional;for(int i=0;i<8;i++){double mid=(lo+hi)*.5;if(CombatReachR31.canReach(e,victim,mid))lo=mid;else hi=mid;}lift=victim.getY()-e.getY()+lo;}
            Vec3 goal=e.position().add(f.scale(holdDistance(e,victim))).add(0,lift,0),delta=goal.subtract(victim.position());
            if(delta.length()>1.15)delta=delta.normalize().scale(1.15);
            Vec3 allowed=net.minecraft.world.entity.Entity.collideBoundingBox(victim,delta,victim.getBoundingBox().deflate(.06),e.level(),List.of());
            if(allowed.subtract(delta).lengthSqr()>.02){clear(e);return;}
            victim.move(MoverType.SELF,delta);victim.setDeltaMovement(Vec3.ZERO);victim.resetFallDistance();
            float yaw=Mth.approachDegrees(victim.yBodyRot,(float)Math.toDegrees(Math.atan2(f.x,-f.z)),6);victim.setYRot(yaw);victim.yBodyRot=victim.yHeadRot=yaw;victim.hurtMarked=true;
            if(a==HOLD&&age>90){clear(e);return;}
        }
        if(a==THROW&&age>=16&&!s.contact)
        {
            s.contact=true;var f=forward(e);EvaHitFeedback.hurt(victim,e.damageSources().mobAttack(e),35,victim.position().add(0,victim.getBbHeight()*.65,0),f);
            if(victim instanceof FirstBattleSignals.Actor actor&&actor.firstBattleSignals().active(victim)){clear(e);return;}
            CombatFeelR31.throwBody(victim,f.scale(3.6).add(0,2.6,0));e.playSound(ModSounds.EVA_SWING.get(),2.5F,.65F);
        }
        if(a==THROW&&age>26)clear(e);
    }
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
        l.sendParticles(new BlockParticleOption(ParticleTypes.BLOCK,floor),p.x,p.y+.3,p.z,50,5,.25,5,.12);
        l.playSound(null,e.blockPosition(),ModSounds.EVA_IMPACT.get(),SoundSource.PLAYERS,5,.62F);
        CombatFeelR31.send(e,CombatFeelR31.CONTACT,forward(e),.9F,6,1);
    }
    private EvaCombatR31() {}
}
