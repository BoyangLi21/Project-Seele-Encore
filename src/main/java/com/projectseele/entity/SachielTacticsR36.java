package com.projectseele.entity;

import com.projectseele.physics.CombatBodyDynamics;
import net.minecraft.util.Mth;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.MoverType;
import net.minecraft.world.entity.ai.goal.Goal;
import net.minecraft.world.phys.Vec3;
import java.util.EnumSet;

/** Approach, commit, recover space. Decisions read bodies, never player inputs. */
public final class SachielTacticsR36 extends Goal
{
    private final SachielEntity actor;
    private Vec3 velocity=Vec3.ZERO;
    private boolean wasStriking;
    private int regroup,choice,blocked;
    /**
     * R63: how Sachiel answers a Unit's blow. A blow is read off the Unit's body from the tick it begins until it is
     * thrown, inside THREAT blocks (THREAT_SLOW for a heavy blow or a kick), and answered at most once. Out of a
     * hundred, COUNTER: against a heavy blow or a kick Sachiel gets a jab in first if its arm is free; the next
     * GIVE: it gives ground for GIVE_TICKS at GIVE_SPEED blocks a tick, a little to one side; the rest of the time
     * it does what it would have done. A strike of its own still in the wind-up is broken off for either.
     */
    /**
     * (R64: the share of the jab was 25 until the owner asked for it more often, 2026-11-15. The share that
     * gives ground is as it was, so Sachiel now does what it would have done 25 times in a hundred, not 40.)
     */
    public static final int COUNTER_R63=40,GIVE_R63=35,GIVE_TICKS_R63=9;
    public static final double THREAT_R63=24,GIVE_SPEED_R63=.9;
    /**
     * The threat of a heavy blow or a kick: the Unit is carried forward by them, and throws them from farther off.
     * Read inside 24 blocks like a punch, 15 of 18 were out of reach (thrown from 25 to 32 blocks) and none was
     * answered.
     */
    public static final double THREAT_SLOW_R63=36;
    /** -Dprojectseele.sachielRecoveryJabR64=false: the jab waits for Sachiel's own recovery, as up to R63. */
    private static final boolean RECOVERY_JAB_R64=!"false".equals(System.getProperty("projectseele.sachielRecoveryJabR64"));
    /** -Dprojectseele.sachielAnswersR63=false: Sachiel does not answer, as before. */
    static final boolean ANSWERS_R63=Boolean.parseBoolean(System.getProperty("projectseele.sachielAnswersR63","true"));
    /** -Dprojectseele.sachielRollR63=0..99, review only: every answer is rolled as this number, to see one answer many times in a fight. */
    private static final int ROLL_R63=Integer.getInteger("projectseele.sachielRollR63",-1);
    private int rollR63(){return ROLL_R63>=0?ROLL_R63:actor.getRandom().nextInt(100);}
    /** -Dprojectseele.poseDiag=true: every blow read off the Unit and what was done about it goes to the log. */
    private static final boolean TOLD_R63=Boolean.getBoolean("projectseele.poseDiag");
    private boolean unitLive;
    /** R64 (M4): the frames core numbers its blows; a string's next blow is a new number whatever the phase did. */
    private int unitSerial;
    private float unitPhase;
    private int giveGround,giveSide;
    /** Ticks since the Unit's blow in hand began, -1 with none to answer. */
    private int blowAge=-1;
    /** The roll that asked for a jab while the arm was not free: kept, not thrown again, until it is or the blow is past reading. -1 with none. */
    private int jabRoll=-1;
    public static final int READ_FROM_R63=2,READ_UNTIL_R63=8;
    /** A strike is broken off for an answer no later than this many ticks before its wind-up ends. */
    public static final int BREAK_R63=3;
    /** A heavy blow or a kick: the two the Unit's own flags mark, set by the server when the motion starts. */
    private static boolean slowR63(EvaUnit01Entity unit){return unit.readSlowR64();}
    /** With poseDiag: the body as it stood a tick ago, and for how many more ticks its turning is told after an answer. */
    private EvaBodyPose.Sample toldPoseR63;
    private int toldTicksR63;
    /**
     * With poseDiag, for eight ticks after an answer: the bone that turned farthest since the tick before and by
     * how much (degrees). A strike given up that drops to the standing pose in a frame shows here as one large turn.
     */
    private void toldTurnR63()
    {
        var pose=SachielBodyPoseR35.sample(actor,0);
        if(toldPoseR63!=null&&toldTicksR63>0)
        {
            toldTicksR63--;String most="-";double turn=0;
            for(String name:pose.rig.keySet())
            {
                var was=toldPoseR63.rotations.get(name);var is=pose.rotations.get(name);
                if(was==null||is==null)continue;
                double angle=Math.toDegrees(2*Math.acos(Math.min(1,Math.abs(was.dot(is)))));
                if(angle>turn){turn=angle;most=name;}
            }
            com.projectseele.ProjectSeele.LOGGER.info("R63SACHIELTURN {} ticks left: {} turned {} in a tick; strike {} at {}",toldTicksR63,most,
                    String.format(java.util.Locale.ROOT,"%.1f",turn),actor.isStrikeActive()?actor.strikeMode():-1,actor.strikeAge(0));
        }
        toldPoseR63=pose;
    }
    private void toldR63(double range,int age,EvaUnit01Entity unit,int roll,String what)
    {
        if(TOLD_R63&&!what.startsWith("out of reach"))toldTicksR63=8;
        if(TOLD_R63)com.projectseele.ProjectSeele.LOGGER.info("R63SACHIEL blow range {} age {} heavy {} kick {} punch {} roll {} own strike {} at {}: {}",String.format(java.util.Locale.ROOT,"%.1f",range),age,
                unit.isHeavyMotionActive(),unit.isKickMotionActive(1),unit.getOrdinaryAttackStage(),roll,actor.isStrikeActive()?actor.strikeMode():-1,actor.strikeAge(0),what);
    }
    public SachielTacticsR36(SachielEntity actor){this.actor=actor;setFlags(EnumSet.of(Flag.MOVE,Flag.LOOK));}
    @Override public boolean canUse(){return !EvaCombatModelR64.angels()&&SachielGameplayMotionR32.phrases()&&!actor.isFirstBattleActive()&&!actor.isSelfDestructing()&&actor.getTarget()!=null&&actor.getTarget().isAlive();}
    @Override public boolean requiresUpdateEveryTick(){return true;}
    @Override public void stop(){velocity=Vec3.ZERO;SachielTacticsR34.recordMotion(actor,Vec3.ZERO);actor.getNavigation().stop();}
    @Override public void tick()
    {
        actor.getNavigation().stop();LivingEntity target=actor.getTarget();if(target==null)return;
        if(TOLD_R63)toldTurnR63();
        // The Unit's blow is read every tick, whatever Sachiel is doing: read only while it stood free, four
        // blows in five began while it was striking and were never seen (70 blows, 12 read).
        if(ANSWERS_R63&&target instanceof EvaUnit01Entity unit)
        {
            // Begun: the Unit has gone into a blow, or from one blow of a string into the next.
            boolean live=unit.hasLiveActionForRender(1)&&!unit.strikeSpentR63();float phase=unit.combatPhaseR31();
            if(live&&(!unitLive||phase<unitPhase-.2F||unit.combatR64().serial()!=unitSerial)){blowAge=0;jabRoll=-1;}
            else if(blowAge>=0)blowAge=live&&blowAge<READ_UNTIL_R63?blowAge+1:-1;
            unitLive=live;unitPhase=phase;unitSerial=unit.combatR64().serial();
        }
        else blowAge=-1;
        if(blowAge<0)jabRoll=-1;
        var delta=target.position().subtract(actor.position()).multiply(1,0,1);double range=delta.length();
        // A strike still in its wind-up is broken off for the answer: Sachiel is striking two ticks in three,
        // and answering only between strikes it gave ground to 15 blows of 251 and jabbed at none.
        if(actor.isStrikeActive()&&blowAge>=READ_FROM_R63&&target instanceof EvaUnit01Entity unit
                &&actor.strikeAge(0)<=SachielStrike.windup(actor.strikeMode())-BREAK_R63&&!CombatFeelR31.hitPaused(actor))
        {
            int age=blowAge,mode=actor.strikeMode(),kept=jabRoll;blowAge=-1;jabRoll=-1;
            if(range>=(slowR63(unit)?THREAT_SLOW_R63:THREAT_R63))toldR63(range,age,unit,-1,"out of reach (striking)");
            else
            {
                int roll=kept>=0?kept:rollR63();
                if(slowR63(unit)&&roll<COUNTER_R63&&mode!=SachielStrike.JAB&&actor.breakIntoR63(target,SachielStrike.JAB)){toldR63(range,age,unit,roll,"breaks off for a jab");choice++;}
                else if(roll>=COUNTER_R63&&roll<COUNTER_R63+GIVE_R63)
                {
                    actor.callOffStrikeR63();giveGround=GIVE_TICKS_R63;giveSide=actor.getRandom().nextBoolean()?1:-1;
                    toldR63(range,age,unit,roll,"breaks off and gives ground");
                }
                else toldR63(range,age,unit,roll,"goes on with its strike");
            }
        }
        // R64: and a strike that has been thrown is left for the jab. The rest of a strike and the pause after it
        // are most of the time Sachiel is not winding up; held to them the jab came a quarter as often as it was rolled.
        if(RECOVERY_JAB_R64&&actor.isStrikeActive()&&blowAge>=READ_FROM_R63&&target instanceof EvaUnit01Entity unit&&slowR63(unit)
                &&range<THREAT_SLOW_R63&&!CombatFeelR31.hitPaused(actor))
        {
            int roll=jabRoll>=0?jabRoll:rollR63();jabRoll=roll;
            if(roll<COUNTER_R63&&actor.hasLineOfSight(target)&&actor.jabOutOfRecoveryR64(target))
            {
                int age=blowAge;blowAge=-1;jabRoll=-1;toldR63(range,age,unit,roll,"jab out of its own recovery (strike)");
                choice++;wasStriking=true;stop();return;
            }
        }
        if(actor.isStrikeActive()) {wasStriking=true;stop();return;}
        if(wasStriking){wasStriking=false;regroup=actor.lastStrikeConnectedR36()?9:16;}
        if(CombatFeelR31.restrained(actor)||CombatFeelR31.hitPaused(actor)){stop();return;}
        if(range<.01)return;
        var forward=delta.normalize();var lateral=new Vec3(forward.z,0,-forward.x);
        float yaw=(float)Math.toDegrees(Math.atan2(-forward.x,forward.z));actor.setYRot(Mth.approachDegrees(actor.getYRot(),yaw,4.5F));actor.yHeadRot=actor.yBodyRot=actor.getYRot();
        boolean facing=Math.abs(Mth.wrapDegrees(yaw-actor.getYRot()))<16,low=CombatBodyDynamics.active(target)||target instanceof EvaUnit01Entity eva&&eva.isPilotProne();
        // Answered once, from the second tick of the blow (whether it is a heavy one or a kick is not known on
        // its first) to the eighth: later than that the blow is on its way and the answer is too late to read.
        if(blowAge>=READ_FROM_R63&&target instanceof EvaUnit01Entity unit)
        {
            int age=blowAge;boolean slow=slowR63(unit);
            if(range>=(slow?THREAT_SLOW_R63:THREAT_R63)){blowAge=-1;jabRoll=-1;toldR63(range,age,unit,-1,"out of reach");}
            else
            {
                int roll=jabRoll>=0?jabRoll:rollR63();
                if(slow&&roll<COUNTER_R63)
                {
                    // The jab is a reaction: it does not wait for the pause Sachiel takes between strikes, only
                    // for its arm to be free. Held to that pause it was never able (12 blows read, none).
                    if(facing&&actor.strikeReadyR34()&&actor.hasLineOfSight(target)&&actor.beginStrike(target,SachielStrike.JAB))
                    {
                        blowAge=-1;jabRoll=-1;toldR63(range,age,unit,roll,"jab");
                        choice++;wasStriking=true;stop();return;
                    }
                    // R64: or out of the pause after a strike of its own.
                    if(RECOVERY_JAB_R64&&facing&&actor.hasLineOfSight(target)&&actor.jabOutOfRecoveryR64(target))
                    {
                        blowAge=-1;jabRoll=-1;toldR63(range,age,unit,roll,"jab out of its own recovery (pause)");
                        choice++;wasStriking=true;stop();return;
                    }
                    // The arm is still coming back from a strike of its own: the jab waits for it, on the same
                    // roll, while the blow can still be read. Asked for once and dropped, five in six were lost.
                    if(age<READ_UNTIL_R63)jabRoll=roll;
                    else{blowAge=-1;jabRoll=-1;toldR63(range,age,unit,roll,"stands (no arm free for the jab)");}
                }
                else
                {
                    blowAge=-1;jabRoll=-1;
                    boolean gives=roll>=COUNTER_R63&&roll<COUNTER_R63+GIVE_R63;
                    toldR63(range,age,unit,roll,gives?"gives ground":"stands");
                    if(gives){giveGround=GIVE_TICKS_R63;giveSide=actor.getRandom().nextBoolean()?1:-1;}
                }
            }
        }
        if(giveGround<=0&&regroup<=0&&facing&&actor.strikeReadyR34()&&actor.hasLineOfSight(target)&&range<42)
        {
            // Long bone-lance attacks claim space. Close pressure uses a palm
            // drive, with a visible recovery opening before another commitment.
            int mode=low&&range<26?SachielStrike.STOMP:range>32?SachielStrike.PILE:range<22?
                    switch(choice%4){case 0->SachielStrike.SHOVE;case 1->SachielStrike.HOOK;case 2->SachielStrike.JAB;default->SachielStrike.OVERHEAD;}:
                    switch(choice%4){case 0->SachielStrike.HOOK;case 1->SachielStrike.PILE;case 2->SachielStrike.OVERHEAD;default->SachielStrike.JAB;};
            if(actor.beginStrike(target,mode)){choice++;wasStriking=true;stop();return;}
        }
        Vec3 wanted;
        if(giveGround>0)
        {
            // Back out of reach and off the line: straight back is the easiest to follow.
            giveGround--;if(regroup>0)regroup--;
            wanted=forward.scale(-GIVE_SPEED_R63).add(lateral.scale(giveSide*.25));
        }
        else if(regroup>0)
        {
            regroup--;
            wanted=range<17?forward.scale(-.65):range<32?lateral.scale((choice%2==0?1:-1)*.32):Vec3.ZERO;
        }
        else wanted=range>39?forward.scale(1.1):range>30?forward.scale(.55):range<22?forward.scale(-.45):Vec3.ZERO;
        // Failed movement invokes navigation around a real obstacle, rather
        // than continually shuffling into its collision box.
        if(blocked>14&&range>35){actor.getNavigation().moveTo(target,1);blocked=0;}
        velocity=velocity.lerp(wanted,.20);Vec3 before=actor.position();boolean ground=actor.onGround();actor.move(MoverType.SELF,CombatSpacingR32.clip(actor,velocity));
        actor.setDeltaMovement(0,actor.getDeltaMovement().y,0);
        if(ground&&actor.level().getBlockCollisions(actor,actor.getBoundingBox().deflate(.1).move(0,-.18,0)).iterator().hasNext())actor.setOnGround(true);
        var moved=actor.position().subtract(before);SachielTacticsR34.recordMotion(actor,moved);
        if(moved.horizontalDistance()<.03&&wanted.lengthSqr()>.25)blocked++;else blocked=0;
    }
}
