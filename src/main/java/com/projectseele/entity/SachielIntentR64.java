package com.projectseele.entity;

import com.projectseele.ProjectSeele;
import com.projectseele.physics.CombatBodyDynamics;
import net.minecraft.util.Mth;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.MoverType;
import net.minecraft.world.entity.ai.goal.Goal;
import net.minecraft.world.phys.Vec3;

import java.util.EnumSet;

/**
 * R64 (M5): Sachiel fights with an intent.
 * <p>
 * Up to M4 it threw one strike at a time, the next in a fixed rotation as soon as its arm was free, and nothing
 * the fight did changed what it was about: struck, staggered or felled it went on where it had stopped. Here it
 * is always doing one of five things, and each ends in the next:
 * <ul>
 * <li>approach: it closes to where a fight begins;</li>
 * <li>circle: it holds its distance and walks round the Unit while it takes its breath. This is the Unit's turn;</li>
 * <li>pressure: it steps in and throws a string of one to three strikes, each out of the one before;</li>
 * <li>punish: the Unit's blow has missed, or a slow one is in its recovery: it gets a jab in at once;</li>
 * <li>retreat: after a string, and after a blow that staggered or felled it, it backs out of reach and off the line.</li>
 * </ul>
 * What it reads of the Unit's blows (C8: a slow blow is answered with a jab or by giving ground) is kept as it
 * was. Every strike is announced on its first tick (SachielTellsR64). The strikes themselves, their timing and
 * their damage are unchanged.
 * <p>
 * It takes the place of SachielTacticsR36 where the server runs the frames core (EvaCombatModelR64.angels).
 */
public final class SachielIntentR64 extends Goal
{
    public static final int APPROACH=0,CIRCLE=1,PRESSURE=2,PUNISH=3,RETREAT=4;
    private static final String[] NAMES={"approach","circle","pressure","punish","retreat"};
    /** Blocks: where a fight begins; the band it circles in; how far it backs away; inside this the close strings; beyond this the lance. */
    public static final double ENGAGE=34,NEAR=24,FAR=31,AWAY=37,CLOSE=22,LANCE=32;
    /** Blocks a strike is begun within: the lance, a hand, the shove, the stomp on a Unit that is down. */
    public static final double REACH_LANCE=42,REACH_HAND=32,REACH_SHOVE=22,REACH_STOMP=26,REACH_PUNISH=30;
    /**
     * Ticks: the breath after a string (and when its health is under RAGE of the whole); the retreat after a
     * string and after a blow that staggered it; how long after a strike's contact the next of a string comes;
     * the least time between two punishes; how long it tries to get its first strike in before it gives the string up.
     */
    public static final int BREATH=46,BREATH_RAGE=26,RETREAT_TICKS=18,RETREAT_HURT=26,CHAIN_GAP=3,PUNISH_EVERY=50,GIVE_UP=70;
    public static final float RAGE=.40F;
    /** C8, as in SachielTacticsR36: of a hundred, a slow blow is answered with a jab this often and ground is given this often. */
    public static final int COUNTER=40,GIVE=35,GIVE_TICKS=9,READ_FROM=2,READ_UNTIL=8,BREAK=3;
    public static final double THREAT=24,THREAT_SLOW=36;
    private static final int ROLL=Integer.getInteger("projectseele.sachielRollR63",-1);
    /** Review only: -Dprojectseele.combatDiagR64=true tells every change of intent and every string (R64INTENT). */
    private static final boolean DIAG=Boolean.getBoolean("projectseele.combatDiagR64");

    private final SachielEntity actor;
    private Vec3 velocity=Vec3.ZERO;
    private int intent=APPROACH,since,breath=10,retreat,side=1,sideTicks,sincePunish=PUNISH_EVERY,blocked,strings,punishes;
    /** The string in hand and the strike of it to throw next. */
    private int[] plan;
    private int next;
    private boolean wasStriking,wasHurt;
    private boolean unitLive;
    private int unitSerial,blowAge=-1,jabRoll=-1;
    private float unitPhase;

    public SachielIntentR64(SachielEntity actor){this.actor=actor;setFlags(EnumSet.of(Flag.MOVE,Flag.LOOK));}

    @Override public boolean canUse()
    {
        return EvaCombatModelR64.angels()&&SachielGameplayMotionR32.phrases()&&!actor.isFirstBattleActive()&&!actor.isSelfDestructing()
                &&actor.getTarget()!=null&&actor.getTarget().isAlive();
    }
    @Override public boolean requiresUpdateEveryTick(){return true;}
    @Override public void start(){velocity=Vec3.ZERO;intent=APPROACH;since=0;plan=null;next=0;breath=10;wasStriking=actor.isStrikeActive();}
    @Override public void stop(){halt();}
    public int intent(){return intent;}

    private void halt(){velocity=Vec3.ZERO;SachielTacticsR34.recordMotion(actor,Vec3.ZERO);actor.getNavigation().stop();}
    private int roll(){return ROLL>=0?ROLL:actor.getRandom().nextInt(100);}
    private void told(String what)
    {if(DIAG)ProjectSeele.LOGGER.info("R64INTENT tick {} {}: {}",actor.level().getGameTime(),NAMES[intent],what);}
    private void go(int to)
    {
        if(to==intent)return;
        if(DIAG)ProjectSeele.LOGGER.info("R64INTENT tick {} {} -> {} after {} ticks, breath {}",actor.level().getGameTime(),NAMES[intent],NAMES[to],since,breath);
        intent=to;since=0;
    }
    private static String name(int mode)
    {return switch(mode){case SachielStrike.JAB->"jab";case SachielStrike.PILE->"lance";case SachielStrike.HOOK->"hook";case SachielStrike.OVERHEAD->"overhead";case SachielStrike.SHOVE->"shove";default->"stomp";};}
    public static double reach(int mode)
    {return mode==SachielStrike.PILE?REACH_LANCE:mode==SachielStrike.STOMP?REACH_STOMP:mode==SachielStrike.SHOVE?REACH_SHOVE:REACH_HAND;}

    /** The string for where the Unit stands. A Unit on the ground is stamped on; far off it is the lance; close, strings that begin fast. */
    private int[] choose(double range,boolean low,boolean rage){return string(range,low,rage,strings++);}
    /** The pick-th string (they are taken in turn) for a Unit at this range. */
    public static int[] string(double range,boolean low,boolean rage,int pick)
    {
        if(low&&range<REACH_STOMP)return new int[]{SachielStrike.STOMP};
        if(range>LANCE)return rage&&pick%2==0?new int[]{SachielStrike.PILE,SachielStrike.HOOK}:new int[]{SachielStrike.PILE};
        if(range<CLOSE)return switch(pick%4)
        {
            case 0->new int[]{SachielStrike.SHOVE,SachielStrike.HOOK};
            case 1->new int[]{SachielStrike.JAB,SachielStrike.HOOK};
            case 2->rage?new int[]{SachielStrike.JAB,SachielStrike.JAB,SachielStrike.OVERHEAD}:new int[]{SachielStrike.HOOK,SachielStrike.OVERHEAD};
            default->new int[]{SachielStrike.JAB,SachielStrike.SHOVE};
        };
        return switch(pick%4)
        {
            case 0->new int[]{SachielStrike.JAB,SachielStrike.HOOK};
            case 1->new int[]{SachielStrike.HOOK,SachielStrike.PILE};
            case 2->rage?new int[]{SachielStrike.JAB,SachielStrike.HOOK,SachielStrike.OVERHEAD}:new int[]{SachielStrike.OVERHEAD};
            default->new int[]{SachielStrike.HOOK,SachielStrike.JAB};
        };
    }
    private String list(int[] string)
    {StringBuilder b=new StringBuilder();for(int m:string)b.append(b.length()==0?"":", ").append(name(m));return b.toString();}

    /** The string is over: back out and take a breath. */
    private void finish(boolean rage)
    {
        plan=null;next=0;retreat=RETREAT_TICKS;breath=(rage?BREATH_RAGE:BREATH)+actor.getRandom().nextInt(12);
        go(RETREAT);
    }

    /** The Unit's blow can be punished: it has missed, or it is a slow one, and enough of its recovery is left. */
    private static boolean open(EvaUnit01Entity unit)
    {
        var machine=unit.combatR64();
        if(machine.busy())return machine.spent()&&(!machine.landed()||machine.row().slow())&&machine.recoveryLeft()>=6;
        return unit.hasLiveActionForRender(1)&&unit.strikeSpentR63()&&unit.readSlowR64();
    }

    /** C8: a blow the Unit has begun is read from its second tick to its eighth. */
    private void read(EvaUnit01Entity unit)
    {
        if(unit==null||!SachielTacticsR36.ANSWERS_R63){blowAge=-1;jabRoll=-1;return;}
        boolean live=unit.hasLiveActionForRender(1)&&!unit.strikeSpentR63();float phase=unit.combatPhaseR31();
        if(live&&(!unitLive||phase<unitPhase-.2F||unit.combatR64().serial()!=unitSerial)){blowAge=0;jabRoll=-1;}
        else if(blowAge>=0)blowAge=live&&blowAge<READ_UNTIL?blowAge+1:-1;
        unitLive=live;unitPhase=phase;unitSerial=unit.combatR64().serial();
        if(blowAge<0)jabRoll=-1;
    }

    @Override public void tick()
    {
        actor.getNavigation().stop();LivingEntity target=actor.getTarget();if(target==null)return;
        since++;if(sincePunish<1000)sincePunish++;
        EvaUnit01Entity unit=target instanceof EvaUnit01Entity u?u:null;
        read(unit);
        Vec3 delta=target.position().subtract(actor.position()).multiply(1,0,1);double range=delta.length();
        boolean rage=actor.getHealth()<actor.getMaxHealth()*RAGE;
        boolean low=CombatBodyDynamics.active(target)||unit!=null&&unit.isPilotProne();

        if(actor.isStrikeActive())
        {
            wasStriking=true;
            if(CombatFeelR31.hitPaused(actor)){halt();return;}
            int mode=actor.strikeMode();float at=actor.strikeAge(0);
            if(unit!=null&&blowAge>=READ_FROM)
            {
                boolean slow=unit.readSlowR64();
                if(range>=(slow?THREAT_SLOW:THREAT)){if(at<=SachielStrike.windup(mode)-BREAK){blowAge=-1;jabRoll=-1;}}
                else if(at<=SachielStrike.windup(mode)-BREAK)
                {
                    // Its own strike is still in the wind-up: broken off for the answer, or gone on with.
                    int roll=jabRoll>=0?jabRoll:roll();blowAge=-1;jabRoll=-1;
                    if(slow&&roll<COUNTER&&mode!=SachielStrike.JAB&&actor.breakIntoR63(target,SachielStrike.JAB)){plan=null;told("breaks off for a jab");}
                    else if(roll>=COUNTER&&roll<COUNTER+GIVE)
                    {
                        actor.callOffStrikeR63();plan=null;retreat=GIVE_TICKS;side=actor.getRandom().nextBoolean()?1:-1;wasStriking=false;
                        told("breaks off and gives ground");go(RETREAT);
                    }
                }
                else if(slow&&range<THREAT_SLOW)
                {
                    // Thrown already: the jab comes out of the rest of the strike.
                    int roll=jabRoll>=0?jabRoll:roll();jabRoll=roll;
                    if(roll<COUNTER&&actor.hasLineOfSight(target)&&actor.jabOutOfRecoveryR64(target)){blowAge=-1;jabRoll=-1;plan=null;told("jab out of its own recovery");}
                }
            }
            // The next strike of the string, out of the rest of this one.
            if(actor.isStrikeActive()&&plan!=null&&next<plan.length&&actor.strikeAge(0)>=SachielStrike.contactEnd(actor.strikeMode())+CHAIN_GAP)
            {
                int follow=plan[next];
                if(range>=reach(follow)+4||!actor.hasLineOfSight(target)){told("string ends: "+name(follow)+" out of reach at "+Math.round(range));plan=null;}
                else if(actor.followStrikeR64(target,follow)){next++;told("follows with "+name(follow));}
            }
            halt();return;
        }
        if(wasStriking)
        {
            wasStriking=false;
            if(plan==null||next>=plan.length)finish(rage);
        }
        if(CombatFeelR31.restrained(actor)||CombatFeelR31.hitPaused(actor)||EvaCombatR31.holds(actor))
        {
            var beat=CombatFeelR31.beat(actor);
            if(CombatBodyDynamics.active(actor)||beat!=null&&beat.kind()>=CombatFeelR31.STAGGER&&beat.kind()<=CombatFeelR31.THROWN)wasHurt=true;
            halt();return;
        }
        if(wasHurt)
        {
            // Staggered, knocked back or felled: it does not go on where it stopped. It backs away first.
            wasHurt=false;plan=null;next=0;retreat=RETREAT_HURT;breath=Math.max(breath,rage?12:20);side=actor.getRandom().nextBoolean()?1:-1;
            told("was staggered or felled");go(RETREAT);
        }
        if(range<.01)return;
        Vec3 forward=delta.normalize(),lateral=new Vec3(forward.z,0,-forward.x);
        float yaw=(float)Math.toDegrees(Math.atan2(-forward.x,forward.z));
        actor.setYRot(Mth.approachDegrees(actor.getYRot(),yaw,4.5F));actor.yHeadRot=actor.yBodyRot=actor.getYRot();
        boolean facing=Math.abs(Mth.wrapDegrees(yaw-actor.getYRot()))<16,sight=actor.hasLineOfSight(target);
        if(breath>0)breath--;
        if(retreat>0)retreat--;

        // C8, between strikes: a slow blow is answered with a jab, or ground is given.
        if(unit!=null&&blowAge>=READ_FROM)
        {
            boolean slow=unit.readSlowR64();
            if(range>=(slow?THREAT_SLOW:THREAT)){blowAge=-1;jabRoll=-1;}
            else
            {
                int roll=jabRoll>=0?jabRoll:roll();
                if(slow&&roll<COUNTER)
                {
                    if(facing&&sight&&(actor.strikeReadyR34()&&actor.beginStrike(target,SachielStrike.JAB)||actor.jabOutOfRecoveryR64(target)))
                    {
                        blowAge=-1;jabRoll=-1;plan=null;wasStriking=true;told("answers a slow blow with a jab");halt();return;
                    }
                    if(blowAge<READ_UNTIL)jabRoll=roll;else{blowAge=-1;jabRoll=-1;}
                }
                else
                {
                    blowAge=-1;jabRoll=-1;
                    if(roll>=COUNTER&&roll<COUNTER+GIVE&&intent!=PRESSURE)
                    {
                        retreat=Math.max(retreat,GIVE_TICKS);side=actor.getRandom().nextBoolean()?1:-1;told("gives ground to a blow");go(RETREAT);
                    }
                }
            }
        }
        // The Unit has left itself open.
        if(unit!=null&&sincePunish>=PUNISH_EVERY&&facing&&sight&&range<REACH_PUNISH&&open(unit))
        {
            // The jab always gets there (eight ticks). With more of the recovery left, or enraged, it is a jab and a
            // hook, or the shove (nine ticks), in turn: 18 of 26 strikes in a fight were jabs when it was the jab alone.
            boolean room=rage||unit.combatR64().busy()&&unit.combatR64().recoveryLeft()>=14;
            int turn=punishes++%3;
            int[] with=room&&turn==0?new int[]{SachielStrike.JAB,SachielStrike.HOOK}:room&&turn==1&&range<REACH_SHOVE?new int[]{SachielStrike.SHOVE,SachielStrike.JAB}
                    :new int[]{SachielStrike.JAB};
            if(actor.strikeReadyR34()?actor.beginStrike(target,with[0]):actor.followStrikeR64(target,with[0]))
            {
                plan=with;next=1;sincePunish=0;wasStriking=true;go(PUNISH);told("punishes with "+list(with));halt();return;
            }
        }
        // A string in hand: its next strike, as soon as the arm is free and the Unit in reach.
        if(plan!=null&&next<plan.length&&(intent==PRESSURE||intent==PUNISH)&&facing&&sight&&range<reach(plan[next]))
        {
            if(actor.strikeReadyR34()?actor.beginStrike(target,plan[next]):next>0&&actor.followStrikeR64(target,plan[next]))
            {
                told((next==0?"begins ":"goes on with ")+name(plan[next])+" of "+list(plan)+" at "+Math.round(range));
                next++;wasStriking=true;halt();return;
            }
        }
        Vec3 wanted;
        switch(intent)
        {
            case APPROACH ->
            {
                wanted=forward.scale(range>39?1.1:.6);
                if(range<ENGAGE)go(CIRCLE);
            }
            case RETREAT ->
            {
                // Back out of reach and off the line: straight back is the easiest to follow.
                wanted=forward.scale(-.9).add(lateral.scale(side*.25));
                if(retreat<=0||range>AWAY)go(CIRCLE);
            }
            case CIRCLE ->
            {
                if(--sideTicks<=0){side=actor.getRandom().nextBoolean()?1:-1;sideTicks=40+actor.getRandom().nextInt(30);}
                wanted=lateral.scale(side*.32).add(forward.scale(range<NEAR?-.4:range>FAR?.4:0));
                if(range>ENGAGE+6)go(APPROACH);
                else if(breath<=0&&facing&&sight)
                {
                    plan=choose(range,low,rage);next=0;go(PRESSURE);told("string "+list(plan)+" from "+Math.round(range)+(rage?", enraged":""));
                }
            }
            default ->
            {
                // Pressure or punish with a strike still to throw: step in to its reach.
                if(plan==null||next>=plan.length){finish(rage);wanted=Vec3.ZERO;}
                else
                {
                    wanted=range>reach(plan[next])-3?forward.scale(.8):Vec3.ZERO;
                    if(since>GIVE_UP&&next==0){told("gives the string up: could not get in");plan=null;breath=12;go(CIRCLE);}
                }
            }
        }
        if(blocked>14&&range>35){actor.getNavigation().moveTo(target,1);blocked=0;}
        velocity=velocity.lerp(wanted,.20);Vec3 before=actor.position();boolean ground=actor.onGround();
        actor.move(MoverType.SELF,CombatSpacingR32.clip(actor,velocity));
        actor.setDeltaMovement(0,actor.getDeltaMovement().y,0);
        if(ground&&actor.level().getBlockCollisions(actor,actor.getBoundingBox().deflate(.1).move(0,-.18,0)).iterator().hasNext())actor.setOnGround(true);
        Vec3 moved=actor.position().subtract(before);SachielTacticsR34.recordMotion(actor,moved);
        if(moved.horizontalDistance()<.03&&wanted.lengthSqr()>.25)
        {
            // Against something: the other way round the Unit.
            if(++blocked==8&&intent==CIRCLE)side=-side;
        }
        else blocked=0;
    }
}
