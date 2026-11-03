package com.projectseele.entity;

/**
 * Drawn gait phase, advanced by how far the drawn body actually moves.
 * <p>
 * The synchronised phase reaches the client once a tick, while a locally
 * driven EVA is drawn ahead of the newest packet. Read straight from those
 * packets the legs held still for a frame at the newest sample and then
 * jumped ten to twenty degrees when the next one arrived: a stutter in every
 * step. Here the legs advance with the drawn body's own travel, at the
 * cycles per block the synchronised phase has been showing, and drift back
 * onto that phase only while the body moves, never running backwards.
 */
final class EvaGaitClockR57
{
    static final boolean ENABLED=Boolean.parseBoolean(System.getProperty("projectseele.gaitClockR57","true"));
    /** Seconds over which the cycles-per-block rate is averaged. */
    private static final double RATE_WINDOW=.6;
    /** Seconds over which the drawn phase closes its distance to the synchronised one. */
    private static final double PULL=1.0;
    /** A synchronised phase this far away (cycles) is a real jump: take it. */
    private static final double RESYNC=.45;
    /** Drawn travel beyond this in one frame (blocks) is a teleport, not a step. */
    private static final double TELEPORT=6;

    private double phase=Double.NaN,reference,x,z,cycles,blocks;
    private long frame;
    private float output;

    float sample(EvaUnit01Entity entity,float partial,float synchronised,long now)
    {
        if(!ENABLED)return synchronised;
        if(now==frame&&!Double.isNaN(phase))return output;
        var origin=entity.getPosition(partial);
        double dt=(now-frame)/1e9,step=Math.hypot(origin.x-x,origin.z-z);
        double change=synchronised-reference;change-=Math.round(change);
        frame=now;x=origin.x;z=origin.z;reference=synchronised;
        if(Double.isNaN(phase)||dt<=0||dt>.25||step>TELEPORT)
        {
            phase=synchronised;cycles=0;blocks=0;
            return output=synchronised;
        }
        double keep=Math.exp(-dt/RATE_WINDOW);
        cycles=cycles*keep+change;blocks=blocks*keep+step;
        double error=synchronised-phase;error-=Math.round(error);
        if(Math.abs(error)>RESYNC)
        {
            phase=synchronised;
            return output=synchronised;
        }
        if(step>1e-5&&blocks>1e-3)
        {
            double advance=cycles/blocks*step,moved=advance+error*(1-Math.exp(-dt/PULL));
            if(advance!=0&&Math.signum(moved)!=Math.signum(advance))moved=0;
            phase+=moved;
            phase-=Math.floor(phase);
        }
        return output=(float)phase;
    }
}
