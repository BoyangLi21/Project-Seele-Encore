package com.projectseele.entity;

/**
 * Drawn locomotion blend (move, run) eased between its synchronised steps.
 * <p>
 * Those blends arrive once a tick and were drawn as a staircase: a sixth of
 * the way from standing to walking held for two frames, then the next sixth,
 * so the legs started and stopped in ten to seventeen degree jerks. Leaving a
 * walk the synchronised value also leapt back up and dropped to zero. A
 * critically damped spring with a rate limit follows it without either.
 */
final class EvaSignalEaseR57
{
    /** Spring stiffness (1/s); about a tick and a half to close most of a step. */
    private static final double RATE=Double.parseDouble(System.getProperty("projectseele.blendEaseR57","22"));
    /** Fastest change (full blend per second): a whole start or stop takes at least a fifth of a second. */
    private static final double LIMIT=5;

    private double value=Double.NaN,speed;
    private long frame;
    private float output;

    float sample(float synchronised,long now)
    {
        if(!EvaGaitClockR57.ENABLED)return synchronised;
        if(now==frame&&!Double.isNaN(value))return output;
        double dt=(now-frame)/1e9;frame=now;
        if(Double.isNaN(value)||dt<=0||dt>.25)
        {
            value=synchronised;speed=0;
            return output=synchronised;
        }
        double error=value-synchronised,step=(speed+RATE*error)*dt,decay=Math.exp(-RATE*dt);
        double next=synchronised+(error+step)*decay;
        speed=(speed-RATE*step)*decay;
        double limit=LIMIT*dt;
        if(Math.abs(next-value)>limit)
        {
            next=value+Math.copySign(limit,next-value);
            speed=Math.copySign(Math.min(Math.abs(speed),LIMIT),speed);
        }
        value=Math.max(0,Math.min(1,next));
        return output=(float)value;
    }
}
