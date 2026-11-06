package com.projectseele.entity;

import net.minecraft.world.phys.Vec3;

/**
 * An aerial attack falls like what it is: sixty metres of armour thrown at
 * the ground.
 * <p>
 * From the press a heavy pull kills what is left of the rise and the body
 * gathers; at the stroke it is thrown forward and down, at the target if it has
 * one, and keeps accelerating until it hits. Held to a steady speed, the fall
 * had no acceleration and read as slow motion. Runs where the movement is
 * decided: on the pilot's client, or on the server for a computer pilot.
 */
final class EvaAirDriveR59
{
    /** Ticks from the press to the stroke. */
    private static final int KICK_GATHER=4,HAMMER_GATHER=6;
    /** Share of the sideways speed kept each tick while gathering. */
    private static final double GATHER=.9D;
    /** Added to gravity while gathering, and from the stroke to the ground (blocks per tick, per tick). */
    private static final double GATHER_PULL=.5D,STROKE_PULL=1.1D;
    /** Speed given at the stroke, ahead and down (blocks per tick). */
    private static final double KICK_AHEAD=4.6D,KICK_DOWN=1.4D,HAMMER_AHEAD=3.4D,HAMMER_DOWN=2.0D;
    /** The server takes a vehicle's report up to ten blocks a tick. */
    private static final double FASTEST_FALL=8D;

    static int gather(int action){return action==EvaCombatR31.AIR_SLAM?KICK_GATHER:HAMMER_GATHER;}

    static void apply(EvaUnit01Entity e)
    {
        int action=EvaCombatR31.action(e);
        if(action!=EvaCombatR31.AIR_STRIKE&&action!=EvaCombatR31.AIR_SLAM||e.onGround()||!e.isControlledByLocalInstance())return;
        var motion=e.getDeltaMovement();
        float stroke=EvaCombatR31.strokeAge(e,0);
        if(stroke<0)
        {
            e.setDeltaMovement(motion.x*GATHER,motion.y-GATHER_PULL,motion.z*GATHER);
            return;
        }
        boolean kick=action==EvaCombatR31.AIR_SLAM;
        double ahead=kick?KICK_AHEAD:HAMMER_AHEAD,down=kick?KICK_DOWN:HAMMER_DOWN;
        var heading=heading(e).scale(ahead);
        double fall=stroke<1?Math.min(motion.y,-down):motion.y-STROKE_PULL;
        e.setDeltaMovement(heading.x,Math.max(fall,-FASTEST_FALL),heading.z);
    }

    private static Vec3 heading(EvaUnit01Entity e)
    {
        var victim=EvaCombatR31.target(e);
        if(victim!=null)
        {
            var to=victim.position().subtract(e.position()).multiply(1,0,1);
            if(to.lengthSqr()>1)return to.normalize();
        }
        return Vec3.directionFromRotation(0,e.getYRot());
    }

    private EvaAirDriveR59(){}
}
