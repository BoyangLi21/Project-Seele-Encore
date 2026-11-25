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
 * R64 (M5): Sachiel fights as it does in the original.
 * <p>
 * There it does not fight like a man. It walks at its mark, slowly and straight, arms hanging. It stops and
 * regards it. Then, without a stance or a step back, it is violent all at once: the lance of light driven out of
 * its palm, a hand that seizes, and the lance again and again into what it holds. It does not circle, does not
 * give ground, does not box.
 * <p>
 * Up to M4 it threw one strike at a time in a fixed rotation of six (two of them a boxer's jab and hook), the
 * next eleven to eighteen ticks after the last, and backed away between them. Here it is always doing one of four
 * things:
 * <ul>
 * <li>advance: it walks straight at the Unit, at one slow pace, until it is in reach;</li>
 * <li>regard: it stands and looks. Nothing moves but its facing. This is the Unit's turn, and it is the
 * stillness the next strike comes out of;</li>
 * <li>strike: one to three strikes without a pause between them, from this list only: the lance (from where it
 * stands, at any range it reaches), the palm (both hands driven into a Unit that is close) and the lance out of
 * it, the lance repeated into a Unit it has just struck or that lies on the ground, the downward blow;</li>
 * <li>seize: the Unit has left itself open (a blow that missed, or a slow one in its recovery): the palm at once,
 * and the lance after it.</li>
 * </ul>
 * Struck hard enough to stagger or fall it does not retreat: it regards again, a little longer. What it read of
 * the Unit's blows before (C8) is kept in its own terms: a slow blow thrown at it from close is met with the palm
 * four times in ten; it never steps away from one. Every strike is announced as the original announces it
 * (AngelTellsR64). The strikes themselves, their timing and their damage are unchanged.
 * <p>
 * It takes the place of SachielTacticsR36 where the server runs the frames core (EvaCombatModelR64.angels).
 */
public final class SachielIntentR64 extends Goal
{
    public static final int ADVANCE=0,REGARD=1,STRIKE=2,SEIZE=3;
    private static final String[] NAMES={"advance","regard","strike","seize"};
    /** Blocks: where it stops walking and regards; inside this the palm; beyond this only the lance. */
    public static final double ENGAGE=34,CLOSE=22,LANCE=32;
    /**
     * The lance is not thrown at a Unit nearer than this. Its hand is then already past the Unit's surface when
     * the lance comes out, and it met nothing: after the palm at 8 to 18 blocks three lances of four missed a
     * Unit that stood still.
     */
    public static final double LANCE_MIN=20;
    /** Blocks a strike is begun within: the lance, the downward blow, the palm. */
    public static final double REACH_LANCE=42,REACH_HAND=32,REACH_PALM=22;
    /** Blocks a tick it walks: one pace, a third of a Unit's walk. Up to M4 it came on at twice that from afar. */
    public static final double PACE=.55;
    /**
     * Ticks: how long it regards between strings, and after a blow that staggered or felled it; how long
     * after a strike's contact the next of a string comes; the least time between two seizures; how long it
     * walks at a Unit that keeps out of its first strike's reach before it regards again.
     */
    public static final int STARE=46,STARE_HURT=60,CHAIN_GAP=3,SEIZE_EVERY=50,GIVE_UP=90;
    /**
     * A Unit that does nothing while it is regarded is not regarded for as long: this many ticks. Regarded the
     * full time, a Unit that only stood there lost 41 points of health in a hundred ticks where it had lost 66.
     */
    public static final int STARE_IDLE=28;
    /** C8, as in SachielTacticsR36: of a hundred, a slow blow thrown from close is met with the palm this often. */
    public static final int COUNTER=40,READ_FROM=2,READ_UNTIL=8,BREAK=3;
    private static final int ROLL=Integer.getInteger("projectseele.sachielRollR63",-1);
    /** Review only: -Dprojectseele.combatDiagR64=true tells every change of intent and every string (R64INTENT). */
    private static final boolean DIAG=Boolean.getBoolean("projectseele.combatDiagR64");

    private final SachielEntity actor;
    private Vec3 velocity=Vec3.ZERO;
    private int intent=ADVANCE,since,stare=10,sinceSeize=SEIZE_EVERY,blocked,strings;
    /** The string in hand and the strike of it to throw next. */
    private int[] plan;
    private int next;
    private boolean wasStriking,wasHurt;
    private boolean unitLive;
    private int unitSerial,blowAge=-1,roll=-1;
    private float unitPhase;

    public SachielIntentR64(SachielEntity actor){this.actor=actor;setFlags(EnumSet.of(Flag.MOVE,Flag.LOOK));}

    @Override public boolean canUse()
    {
        return EvaCombatModelR64.angels()&&SachielGameplayMotionR32.phrases()&&!actor.isFirstBattleActive()&&!actor.isSelfDestructing()
                &&actor.getTarget()!=null&&actor.getTarget().isAlive();
    }
    @Override public boolean requiresUpdateEveryTick(){return true;}
    @Override public void start(){velocity=Vec3.ZERO;intent=ADVANCE;since=0;plan=null;next=0;stare=10;wasStriking=actor.isStrikeActive();}
    @Override public void stop(){halt();}
    public int intent(){return intent;}

    private void halt(){velocity=Vec3.ZERO;SachielTacticsR34.recordMotion(actor,Vec3.ZERO);actor.getNavigation().stop();}
    private int roll(){return ROLL>=0?ROLL:actor.getRandom().nextInt(100);}
    private void told(String what)
    {if(DIAG)ProjectSeele.LOGGER.info("R64INTENT tick {} {}: {}",actor.level().getGameTime(),NAMES[intent],what);}
    private void go(int to)
    {
        if(to==intent)return;
        if(DIAG)ProjectSeele.LOGGER.info("R64INTENT tick {} {} -> {} after {} ticks, stare {}",actor.level().getGameTime(),NAMES[intent],NAMES[to],since,stare);
        intent=to;since=0;
    }
    private static String name(int mode)
    {return switch(mode){case SachielStrike.PILE->"lance";case SachielStrike.OVERHEAD->"downward blow";case SachielStrike.SHOVE->"palm";default->"strike "+mode;};}
    private static String list(int[] string)
    {StringBuilder b=new StringBuilder();for(int m:string)b.append(b.length()==0?"":", ").append(name(m));return b.toString();}
    public static double reach(int mode)
    {return mode==SachielStrike.PILE?REACH_LANCE:mode==SachielStrike.SHOVE?REACH_PALM:REACH_HAND;}

    /**
     * The pick-th string (they are taken in turn) for a Unit at this range. Only the lance, the palm and the
     * downward blow: the jab and the hook of the old rotation are a boxer's, and the stomp is not Sachiel's.
     */
    public static int[] string(double range,boolean low,int pick)
    {
        // A Unit on the ground: the lance, driven down into it, twice. Too near for the lance it is only looked at.
        if(low)return range>=LANCE_MIN?new int[]{SachielStrike.PILE,SachielStrike.PILE}:null;
        if(range>LANCE)return pick%3==0?new int[]{SachielStrike.PILE,SachielStrike.PILE}:new int[]{SachielStrike.PILE};
        if(range<CLOSE)return switch(pick%3)
        {
            case 0->new int[]{SachielStrike.SHOVE,SachielStrike.PILE};
            case 1->new int[]{SachielStrike.SHOVE,SachielStrike.PILE,SachielStrike.PILE};
            default->new int[]{SachielStrike.OVERHEAD};
        };
        return switch(pick%3)
        {
            case 0->new int[]{SachielStrike.PILE,SachielStrike.PILE};
            case 1->new int[]{SachielStrike.OVERHEAD};
            default->new int[]{SachielStrike.PILE};
        };
    }

    /** The string is over: it stands and regards the Unit again. */
    private void regard(int ticks)
    {
        plan=null;next=0;stare=ticks>0?ticks:STARE+actor.getRandom().nextInt(12);unitActed=false;
        go(REGARD);
    }
    /** The Unit has thrown a blow, or struck Sachiel, since Sachiel began to regard it. */
    private boolean unitActed;

    /** The Unit has left itself open: its blow has missed, or it is a slow one, and enough of its recovery is left. */
    private static boolean open(EvaUnit01Entity unit)
    {
        var machine=unit.combatR64();
        if(machine.busy())return machine.spent()&&(!machine.landed()||machine.row().slow())&&machine.recoveryLeft()>=8;
        return unit.hasLiveActionForRender(1)&&unit.strikeSpentR63()&&unit.readSlowR64();
    }

    /** C8: a blow the Unit has begun is read from its second tick to its eighth. */
    private void read(EvaUnit01Entity unit)
    {
        if(unit==null||!SachielTacticsR36.ANSWERS_R63){blowAge=-1;roll=-1;return;}
        boolean live=unit.hasLiveActionForRender(1)&&!unit.strikeSpentR63();float phase=unit.combatPhaseR31();
        if(live&&(!unitLive||phase<unitPhase-.2F||unit.combatR64().serial()!=unitSerial)){blowAge=0;roll=-1;unitActed=true;}
        else if(blowAge>=0)blowAge=live&&blowAge<READ_UNTIL?blowAge+1:-1;
        unitLive=live;unitPhase=phase;unitSerial=unit.combatR64().serial();
        if(blowAge<0)roll=-1;
    }

    @Override public void tick()
    {
        actor.getNavigation().stop();LivingEntity target=actor.getTarget();if(target==null)return;
        since++;if(sinceSeize<1000)sinceSeize++;
        EvaUnit01Entity unit=target instanceof EvaUnit01Entity u?u:null;
        read(unit);
        Vec3 delta=target.position().subtract(actor.position()).multiply(1,0,1);double range=delta.length();
        boolean low=CombatBodyDynamics.active(target)||unit!=null&&unit.isPilotProne();

        if(actor.isStrikeActive())
        {
            wasStriking=true;
            if(CombatFeelR31.hitPaused(actor)){halt();return;}
            int mode=actor.strikeMode();float at=actor.strikeAge(0);
            // A slow blow from close, read while its own strike is still in the wind-up: broken off for the palm.
            if(unit!=null&&blowAge>=READ_FROM&&at<=SachielStrike.windup(mode)-BREAK)
            {
                int rolled=roll>=0?roll:roll();blowAge=-1;roll=-1;
                if(unit.readSlowR64()&&range<REACH_PALM&&rolled<COUNTER&&mode!=SachielStrike.SHOVE&&actor.breakIntoR63(target,SachielStrike.SHOVE))
                {plan=null;told("breaks off for the palm");}
            }
            // The next strike of the string, out of the rest of this one. The lance is repeated only into a Unit
            // the strike before it has reached: one that missed is not followed.
            if(actor.isStrikeActive()&&plan!=null&&next<plan.length&&actor.strikeAge(0)>=SachielStrike.contactEnd(actor.strikeMode())+CHAIN_GAP)
            {
                int follow=plan[next];boolean repeat=follow==SachielStrike.PILE&&actor.strikeMode()==SachielStrike.PILE;
                if(repeat&&!actor.lastStrikeConnectedR36()&&!low){told("string ends: the lance did not reach");plan=null;}
                else if(follow==SachielStrike.PILE&&range<LANCE_MIN){told("string ends: too near for the lance at "+Math.round(range));plan=null;}
                else if(range>=reach(follow)+4||!actor.hasLineOfSight(target)){told("string ends: "+name(follow)+" out of reach at "+Math.round(range));plan=null;}
                else if(actor.followStrikeR64(target,follow)){next++;told("follows with the "+name(follow));}
            }
            halt();return;
        }
        if(wasStriking)
        {
            wasStriking=false;
            if(plan==null||next>=plan.length)regard(0);
        }
        if(CombatFeelR31.restrained(actor)||CombatFeelR31.hitPaused(actor))
        {
            var beat=CombatFeelR31.beat(actor);
            if(CombatBodyDynamics.active(actor)||beat!=null&&beat.kind()>=CombatFeelR31.STAGGER&&beat.kind()<=CombatFeelR31.THROWN)wasHurt=true;
            halt();return;
        }
        if(wasHurt)
        {
            // Staggered, knocked back or felled: it does not retreat and does not go on where it stopped. It regards.
            wasHurt=false;told("was staggered or felled");regard(STARE_HURT);unitActed=true;
        }
        if(range<.01)return;
        Vec3 forward=delta.normalize();
        float yaw=(float)Math.toDegrees(Math.atan2(-forward.x,forward.z));
        actor.setYRot(Mth.approachDegrees(actor.getYRot(),yaw,4.5F));actor.yHeadRot=actor.yBodyRot=actor.getYRot();
        boolean facing=Math.abs(Mth.wrapDegrees(yaw-actor.getYRot()))<16,sight=actor.hasLineOfSight(target);
        if(stare>0)stare--;

        // C8, between strikes: a slow blow thrown from close is met with the palm. It never steps away from one.
        if(unit!=null&&blowAge>=READ_FROM)
        {
            if(!unit.readSlowR64()||range>=REACH_PALM){blowAge=-1;roll=-1;}
            else
            {
                int rolled=roll>=0?roll:roll();
                if(rolled<COUNTER)
                {
                    if(facing&&sight&&(actor.strikeReadyR34()?actor.beginStrike(target,SachielStrike.SHOVE):actor.followStrikeR64(target,SachielStrike.SHOVE)))
                    {
                        blowAge=-1;roll=-1;plan=null;wasStriking=true;told("meets a slow blow with the palm");halt();return;
                    }
                    if(blowAge<READ_UNTIL)roll=rolled;else{blowAge=-1;roll=-1;}
                }
                else{blowAge=-1;roll=-1;}
            }
        }
        // The Unit has left itself open: the palm at once and the lance after it; from further off, the lance
        // where there is time for it.
        if(unit!=null&&sinceSeize>=SEIZE_EVERY&&facing&&sight&&open(unit))
        {
            int[] with=range<REACH_PALM?new int[]{SachielStrike.SHOVE,SachielStrike.PILE}
                    :range<REACH_LANCE&&unit.combatR64().busy()&&unit.combatR64().recoveryLeft()>=SachielStrike.windup(SachielStrike.PILE)?new int[]{SachielStrike.PILE}:null;
            if(with!=null&&(actor.strikeReadyR34()?actor.beginStrike(target,with[0]):actor.followStrikeR64(target,with[0])))
            {
                plan=with;next=1;sinceSeize=0;wasStriking=true;go(SEIZE);told("seizes the opening with "+list(with));halt();return;
            }
        }
        // A string in hand: its next strike, as soon as the arm is free and the Unit in reach.
        if(plan!=null&&next<plan.length&&(intent==STRIKE||intent==SEIZE)&&facing&&sight&&range<reach(plan[next]))
        {
            if(actor.strikeReadyR34()?actor.beginStrike(target,plan[next]):next>0&&actor.followStrikeR64(target,plan[next]))
            {
                told((next==0?"begins the ":"goes on with the ")+name(plan[next])+" of "+list(plan)+" at "+Math.round(range));
                next++;wasStriking=true;halt();return;
            }
        }
        Vec3 wanted=Vec3.ZERO;
        switch(intent)
        {
            case ADVANCE ->
            {
                // Straight at the Unit, at one pace.
                wanted=forward.scale(PACE);
                if(range<ENGAGE)go(REGARD);
            }
            case REGARD ->
            {
                // It stands. Only its facing follows the Unit.
                if(range>ENGAGE+6)go(ADVANCE);
                else if((stare<=0||!unitActed&&since>=STARE_IDLE)&&facing&&sight)
                {
                    plan=string(range,low,strings++);next=0;
                    if(plan==null){stare=20;since=0;unitActed=true;told("stands over the Unit: too near for the lance");}
                    else{go(STRIKE);told("string "+list(plan)+" from "+Math.round(range)+(low?", the Unit down":"")+(stare>0?", the Unit idle":""));}
                }
            }
            default ->
            {
                // A strike still to throw at a Unit out of its reach: it walks into reach, as it walks anywhere.
                if(plan==null||next>=plan.length)regard(0);
                else
                {
                    if(range>reach(plan[next])-3)wanted=forward.scale(PACE);
                    if(since>GIVE_UP&&next==0){told("gives the string up: the Unit kept out of reach");regard(12);}
                }
            }
        }
        if(blocked>14&&range>35){actor.getNavigation().moveTo(target,1);blocked=0;}
        velocity=velocity.lerp(wanted,.20);Vec3 before=actor.position();boolean ground=actor.onGround();
        actor.move(MoverType.SELF,CombatSpacingR32.clip(actor,velocity));
        actor.setDeltaMovement(0,actor.getDeltaMovement().y,0);
        if(ground&&actor.level().getBlockCollisions(actor,actor.getBoundingBox().deflate(.1).move(0,-.18,0)).iterator().hasNext())actor.setOnGround(true);
        Vec3 moved=actor.position().subtract(before);SachielTacticsR34.recordMotion(actor,moved);
        if(moved.horizontalDistance()<.03&&wanted.lengthSqr()>.25)blocked++;else blocked=0;
    }
}
