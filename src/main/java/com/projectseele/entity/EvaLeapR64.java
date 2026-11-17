package com.projectseele.entity;

import net.minecraft.util.Mth;

/**
 * R64: the jump of the planted model.
 * <p>
 * Up to R63 a Unit left the ground at 4.05 blocks a tick and a pilot's jump topped out 26 blocks up, under half
 * the Unit's own height (the owner, 2026-11-16: it should be far higher; in the original a Unit clears rooftops in
 * one bound and Unit-02 goes from ship to ship). Here the height is what is set ([eva_motion] jumpHeight, the
 * server's, carried to its clients), and the speed the body leaves the ground at is worked out from it.
 * <p>
 * A jump is flown by the pilot's own client. There LivingEntity.aiStep takes two hundredths off the speed of a
 * body its own side drives before each tick's move, which a body the server drives does not lose: the same
 * take-off went 26 blocks up for a player and 35 for a computer pilot. A Unit of this model gets that back
 * (EvaUnit01Entity.travel), so the arc is one arc whoever flies it.
 * <p>
 * The body gathers before it goes (SQUAT_TICKS, the pelvis let down over planted feet by EvaPlantedGaitR64) and
 * takes the ground up as it comes down, by how fast it came (hard): the pelvis sinks further and comes up more
 * slowly, and the pilot's keys are not heard for the first of it (stun).
 */
public final class EvaLeapR64
{
    /**
     * Blocks a tick taken off the speed each tick, going up and coming down (up to R63: 0.20 and 0.36). Heavier, so
     * that a jump three and a half times as high is half as long again in the air and not twice.
     */
    public static final double RISE=.30,FALL=.46;
    /** What vanilla leaves of the vertical speed each tick, and what aiStep leaves of a body its own side drives. */
    private static final double DRAG=.98F;
    public static final double OWN_SIDE=.98D;
    /**
     * Over the ground: vanilla's friction on a body in the air, which a jump is given back; the speed the keys
     * alone give a body in the air (blocks a tick; half a walk); and the longest step that is still a step (a fast
     * run's is 9.45).
     */
    public static final double AIR_FRICTION=.91F,AIR_OWN=.8,CARRY_MOST=14;
    /** A body that comes down faster over the ground than this (blocks a tick; a run is 3.3, a fast run 9.45) does not hear its keys for BRAKE_TICKS, however softly it came down. */
    public static final double LAND_RUNNING=4.5;
    public static final int BRAKE_TICKS=4,BRAKE_AIR_TICKS=8;
    /** Ticks from the press to the feet leaving the ground (up to R63 by the clip: 6 for Unit-01). */
    public static final int SQUAT_TICKS=9;
    /** Blocks the pelvis is let down in the squat: standing, and at a run or faster (the hips stand 35 up). */
    public static final double SQUAT_STANDING=11,SQUAT_RUNNING=6.5;
    /** Share of the squat's ticks spent going down; the rest drives up. As EvaJumpChoreographyR57.takeoff. */
    public static final float SQUAT_DOWN=.65F;
    /**
     * A landing is hard by the speed it comes down at (blocks a tick): nothing at SOFT, which is a drop of the
     * old jump's height, all of it at HARD, which is this jump from its full height.
     */
    public static final double SOFT=4.5,HARD=7.5;
    /** Ticks after the hardest landing in which the body does not move off, strike or jump again. */
    public static final int STUN_MOST=8;
    /** Ticks the landing's pose runs: as up to R63, and more by how hard it is. */
    public static final float LANDING_TICKS=18,LANDING_MORE=10;

    /** This Unit jumps by this model: one of the planted model, with a height set. */
    public static boolean on(EvaUnit01Entity e){return EvaMotionModelR64.jumpHeight(e)>0;}

    private record Arc(float height,double launch,int rise){}
    private static volatile Arc arc=new Arc(0,0,1);

    private static Arc arc(float height)
    {
        Arc a=arc;
        if(a.height()==height)return a;
        double low=0,high=40;
        for(int i=0;i<50;i++)
        {
            double mid=(low+high)*.5;
            if(top(mid)[0]<height)low=mid;else high=mid;
        }
        a=new Arc(height,high,Math.max(1,(int)top(high)[1]));
        arc=a;
        return a;
    }

    /** How high a body that leaves the ground at a speed goes, and the ticks it takes: each tick it moves by its speed, then loses RISE and vanilla's drag. */
    static double[] top(double speed)
    {
        double y=0,v=speed;int ticks=0;
        while(v>0&&ticks<400){y+=v;v=(v-RISE)*DRAG;ticks++;}
        return new double[]{y,ticks};
    }

    /** The speed this Unit leaves the ground at (blocks a tick). */
    public static double launch(EvaUnit01Entity e){return arc(EvaMotionModelR64.jumpHeight(e)).launch();}

    /** Ticks from leaving the ground to the top. */
    public static float riseTicks(EvaUnit01Entity e){return arc(EvaMotionModelR64.jumpHeight(e)).rise();}

    /** How far the pelvis is let down, as a share of the squat's depth, by how far through the squat the body is (0 to 1 and on). */
    public static float squat(float progress)
    {
        if(progress<0)return 0;
        if(progress<SQUAT_DOWN){float u=progress/SQUAT_DOWN;return u*u*(3-2*u);}
        // Up faster than down: the drive is the legs straightening against the ground.
        float u=Mth.clamp((progress-SQUAT_DOWN)/(1-SQUAT_DOWN),0,1);
        return (1-u)*(1-u);
    }

    /** How hard a landing is, 0 to 1, by the speed the body came down at (blocks a tick). */
    public static float hard(double fall){return (float)Mth.clamp((fall-SOFT)/(HARD-SOFT),0,1);}

    public static int stun(float hard){return Math.round(hard*STUN_MOST);}

    /** Ticks the landing's pose takes for a landing this hard. */
    public static float landingTicks(float hard){return LANDING_TICKS+LANDING_MORE*hard;}

    private EvaLeapR64(){}
}
