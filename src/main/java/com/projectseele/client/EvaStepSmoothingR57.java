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
    /** Spring stiffness (1/s): a kerb takes about a third of a second, a bench-high ledge about half. */
    private static final double RATE=12,RATE_HIGH=7;
    /** Longest the body waits low for a sole to reach over the ledge (seconds). */
    private static final double HOLD=1.2;
    private static final boolean DIAG=Boolean.getBoolean("projectseele.poseDiag");
    private static final class State {long frame;double y=Double.NaN,x,z,pace,offset,speed,held;int diag;}
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
        if(Double.isNaN(s.y)||dt<=0||dt>.25){s.y=y;var at=e.getPosition(partial);s.x=at.x;s.z=at.z;s.pace=0;s.offset=0;s.speed=0;return 0;}
        double rise=y-s.y;s.y=y;
        var at=e.getPosition(partial);
        // Horizontal speed, eased: a running body rises onto the ledge within
        // the lead foot's stance, a walking one over about half a second.
        s.pace=s.pace+(Math.hypot(at.x-s.x,at.z-s.z)/dt-s.pace)*(1-Math.exp(-dt/.15));s.x=at.x;s.z=at.z;
        boolean standing=e.onGround()&&!e.isVisuallyAirborneForRender();
        if(standing&&rise>STEP_RISE&&rise<24)s.offset-=rise;
        double rate=Math.max(s.offset<-10?RATE_HIGH:RATE,Math.min(30,s.pace/2.5));
        // A tall step rises only once a sole stands over the ledge: lifting
        // the body while both feet were still before the kerb floated it.
        if(standing&&s.offset<-3&&s.held<HOLD
                &&com.projectseele.client.render.EvaFootPlacement.ledgeUnderFoot(e)<-s.offset*.5)
        {
            s.held+=dt;s.speed=0;
            if(DIAG&&(s.diag++%10)==0)com.projectseele.ProjectSeele.LOGGER.info("STEP HOLD offset={} ledge={} held={}",
                    String.format("%.2f",s.offset),String.format("%.2f",com.projectseele.client.render.EvaFootPlacement.ledgeUnderFoot(e)),String.format("%.2f",s.held));
            return (float)s.offset;
        }
        if(s.offset>-.05)s.held=0;
        if(!standing&&s.offset<0&&rise<0)s.offset=Math.min(0,s.offset-rise);
        double step=(s.speed+rate*s.offset)*dt,decay=Math.exp(-rate*dt);
        s.offset=(s.offset+step)*decay;s.speed=(s.speed-rate*step)*decay;
        if(s.offset>0){s.offset=0;s.speed=0;}
        return (float)s.offset;
    }
    private EvaStepSmoothingR57(){}
}
