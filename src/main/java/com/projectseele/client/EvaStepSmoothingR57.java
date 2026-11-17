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
    /** Spring stiffness (1/s): a kerb takes about a third of a second, a bench-high ledge about half. */
    private static final double RATE=12,RATE_HIGH=7;
    /** Longest the body waits low for a sole to reach over the ledge (seconds). */
    private static final double HOLD=1.2;
    private static final boolean DIAG=Boolean.getBoolean("projectseele.poseDiag");
    /**
     * A climb is not one tall step. Up a terraced slope of one block a block the entity rises two blocks every
     * tick at a run; the wait for a sole over the ledge then never ended before its 1.2 s were up, everything the
     * entity rose meanwhile was owed, and the body was drawn up to 36 blocks under its entity, inside the slope,
     * the third-person camera with it. Height owed again in a later tick than the first is a climb: no wait, and
     * a spring stiff enough that the body stays within CLIMB_LAG of its entity.
     * -Dprojectseele.stepClimbR64=false: as before.
     */
    private static final boolean CLIMB_R64=!"false".equals(System.getProperty("projectseele.stepClimbR64"));
    /** How far behind its entity the body is drawn on a steady climb (blocks), and the stiffest spring for it (1/s). */
    private static final double CLIMB_LAG_R64=3,CLIMB_RATE_MOST_R64=64;
    /** -Dprojectseele.cameraDiagR64=true: the third-person camera of a piloted unit says once a tick where it is. */
    public static final boolean CAMERA_DIAG_R64=Boolean.getBoolean("projectseele.cameraDiagR64");
    private static final class State {long frame;double y=Double.NaN,x,z,pace,offset,speed,held,climb;int diag,owedTick=Integer.MIN_VALUE;boolean climbing;}
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
        // A carrier's rise is not a ledge. Entity.onGround stays stale through
        // transport, and dropping the body here left it hanging below its rack.
        if(Double.isNaN(s.y)||dt<=0||dt>.25||carried(e)){s.y=y;var at=e.getPosition(partial);s.x=at.x;s.z=at.z;s.pace=0;s.offset=0;s.speed=0;return 0;}
        double rise=y-s.y;s.y=y;
        var at=e.getPosition(partial);
        // Horizontal speed, eased: a running body rises onto the ledge within
        // the lead foot's stance, a walking one over about half a second.
        s.pace=s.pace+(Math.hypot(at.x-s.x,at.z-s.z)/dt-s.pace)*(1-Math.exp(-dt/.15));s.x=at.x;s.z=at.z;
        // A ledge step-up or climb carries the body along its own path, hands
        // and feet set against the ledge: held low here as a step, the body
        // hung up to a second below where they reached.
        if(com.projectseele.entity.EvaFieldActionsR45.CLIMB.equals(com.projectseele.entity.EvaFieldActionsR45.clip(e)))
        {s.offset=0;s.speed=0;s.held=0;return 0;}
        boolean standing=e.onGround()&&!e.isVisuallyAirborneForRender();
        // Every rise while standing, however slow: a climb up a terraced slope goes up a block in a
        // tick and stands for the next two, and a rise per frame under the old step threshold reached
        // the screen as that staircase (and counted as a step or not by the frame rate).
        // How fast the entity is going up, eased as the pace is.
        s.climb=s.climb+((standing&&rise>0?rise/dt:0)-s.climb)*(1-Math.exp(-dt/.15));
        if(standing&&rise>0&&rise<24)
        {
            if(s.offset>-.05){s.owedTick=e.tickCount;s.climbing=false;}
            else if(e.tickCount!=s.owedTick)s.climbing=true;
            s.offset-=rise;
        }
        boolean climbing=CLIMB_R64&&s.climbing;
        double rate=Math.max(s.offset<-10?RATE_HIGH:RATE,Math.min(30,s.pace/2.5));
        // A critically damped spring follows a steady rise two rises-per-rate behind.
        if(climbing)rate=Math.max(rate,Math.min(CLIMB_RATE_MOST_R64,2*s.climb/CLIMB_LAG_R64));
        // A tall step rises only once a sole stands over the ledge: lifting
        // the body while both feet were still before the kerb floated it.
        if(standing&&!climbing&&s.offset<-3&&s.held<HOLD
                &&com.projectseele.client.render.EvaFootPlacement.ledgeUnderFoot(e)<-s.offset*.5)
        {
            s.held+=dt;s.speed=0;
            if(DIAG&&(s.diag++%10)==0)com.projectseele.ProjectSeele.LOGGER.info("STEP HOLD offset={} ledge={} held={}",
                    String.format("%.2f",s.offset),String.format("%.2f",com.projectseele.client.render.EvaFootPlacement.ledgeUnderFoot(e)),String.format("%.2f",s.held));
            return (float)s.offset;
        }
        if(s.offset>-.05){s.held=0;s.climbing=false;}
        // A fall while the body still lags below its entity comes out of that lag first, standing or
        // not: on a climb the entity is set a block back down several times, and each correction
        // reached the screen as a drop of the whole body.
        if(s.offset<0&&rise<0)s.offset=Math.min(0,s.offset-rise);
        double step=(s.speed+rate*s.offset)*dt,decay=Math.exp(-rate*dt);
        s.offset=(s.offset+step)*decay;s.speed=(s.speed-rate*step)*decay;
        if(s.offset>0){s.offset=0;s.speed=0;}
        return (float)s.offset;
    }
    private static boolean carried(EvaUnit01Entity e)
    {
        return e.isNervLogisticsLocked()||e.isLaunchSequenceActive()||e.hasActiveCarrierMotion()
                ||com.projectseele.entity.EvaMechanicalFrameR52.active(e)||com.projectseele.entity.EvaAirTransportR31.active(e);
    }
    private EvaStepSmoothingR57(){}
}
