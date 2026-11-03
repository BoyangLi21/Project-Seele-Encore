package com.projectseele.client;

import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.util.WeakIdentityMap;

/**
 * Drawn height of an EVA stepping onto a ledge. Vanilla step-up lifts the
 * entity onto a kerb within one tick; at a giant's step height that read as
 * the whole body and camera jumping. The drawn body starts from where it was
 * and rises onto the ledge through a critically damped spring instead. Jumps
 * and falls are left alone.
 */
public final class EvaStepSmoothingR57
{
    /** A rise this fast while standing (blocks per frame) is a step, not a slope. */
    private static final double STEP_RISE=.6;
    /** Spring stiffness (1/s): most of the rise within about a third of a second. */
    private static final double RATE=12;
    private static final class State {long frame;double y=Double.NaN,offset,speed;}
    private static final WeakIdentityMap<EvaUnit01Entity,State> STATES=new WeakIdentityMap<>();

    /** Blocks to add to the entity's drawn height this frame (zero or negative). */
    public static float offset(EvaUnit01Entity e,float partial)
    {
        long now=AircraftRenderClockR21.frameNanos();
        State s=STATES.get(e);
        if(s==null){s=new State();STATES.put(e,s);}
        if(s.frame==now)return (float)s.offset;
        double dt=(now-s.frame)/1e9,y=e.getPosition(partial).y;
        s.frame=now;
        if(Double.isNaN(s.y)||dt<=0||dt>.25){s.y=y;s.offset=0;s.speed=0;return 0;}
        double rise=y-s.y;s.y=y;
        boolean standing=e.onGround()&&!e.isVisuallyAirborneForRender();
        if(standing&&rise>STEP_RISE&&rise<12)s.offset-=rise;
        if(!standing&&s.offset<0&&rise<0)s.offset=Math.min(0,s.offset-rise);
        double step=(s.speed+RATE*s.offset)*dt,decay=Math.exp(-RATE*dt);
        s.offset=(s.offset+step)*decay;s.speed=(s.speed-RATE*step)*decay;
        if(s.offset>0){s.offset=0;s.speed=0;}
        return (float)s.offset;
    }
    private EvaStepSmoothingR57(){}
}
