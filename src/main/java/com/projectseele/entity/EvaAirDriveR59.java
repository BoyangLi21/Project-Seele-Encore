package com.projectseele.entity;

import net.minecraft.world.phys.Vec3;

/**
 * An aerial attack flies at what it strikes.
 * <p>
 * The hammer and the kick used to drop straight down from wherever the jump
 * had got to, so a standing jump struck the ground it left. Now the body bleeds
 * off its way while it gathers, and the stroke throws it forward and down at
 * the target, or along its heading with none. Runs where the movement is
 * decided: on the pilot's client, or on the server for a computer pilot.
 */
final class EvaAirDriveR59
{
    /** Share of the sideways speed kept each tick while gathering. */
    private static final double GATHER=.9D;
    /** Speed of the stroke, ahead and down (blocks per tick). */
    private static final double KICK_AHEAD=3.8D,KICK_DOWN=2.8D,HAMMER_AHEAD=2.8D,HAMMER_DOWN=3.4D;
    /** Share of the difference from that speed taken up each tick. */
    private static final double TAKE=.42D;

    static void apply(EvaUnit01Entity e)
    {
        int action=EvaCombatR31.action(e);
        if(action!=EvaCombatR31.AIR_STRIKE&&action!=EvaCombatR31.AIR_SLAM||e.onGround()||!e.isControlledByLocalInstance())return;
        var motion=e.getDeltaMovement();
        if(EvaCombatR31.strokeAge(e,0)<0)
        {
            e.setDeltaMovement(motion.x*GATHER,motion.y,motion.z*GATHER);
            return;
        }
        boolean kick=action==EvaCombatR31.AIR_SLAM;
        var wanted=heading(e).scale(kick?KICK_AHEAD:HAMMER_AHEAD).add(0,-(kick?KICK_DOWN:HAMMER_DOWN),0);
        e.setDeltaMovement(motion.add(wanted.subtract(motion).scale(TAKE)));
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
