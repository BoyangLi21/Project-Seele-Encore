package com.projectseele.entity;

/** One server clock for the source pose, contact constraints and weapon pose. */
public final class EvaStanceTimingR53
{
    public record Step(float phase,float velocity) {}
    private static final float ACCELERATION=.006F;

    public static Step advance(float phase,float target,float velocity)
    {
        if(!Float.isFinite(phase+target+velocity))throw new IllegalArgumentException("Nonfinite stance clock");
        phase=Math.max(0,Math.min(3,phase));target=Math.max(0,Math.min(3,target));
        float remaining=target-phase;
        if(Math.abs(remaining)<.00001F&&Math.abs(velocity)<=ACCELERATION)return new Step(target,0);
        // The standing/crouching capture concentrates its knee bend in less
        // than half a phase. Limit its playback rate before the bend starts.
        float limit=.035F+.045F*smooth((phase-1.15F)/.6F);
        if(remaining<0&&phase>1.15F)
            limit=Math.min(limit,(float)Math.sqrt(.035F*.035F+2*ACCELERATION*(phase-1.15F)));
        // The phase advances in server ticks. A continuous v^2/(2a) stop
        // distance omits the next discrete step and then snaps the final
        // velocity to zero. Account for every remaining braking step instead.
        float desired=Math.copySign(Math.min(limit,brakingSpeed(Math.abs(remaining))),remaining);
        float next=velocity+Math.max(-ACCELERATION,Math.min(ACCELERATION,desired-velocity));
        // A reversed request first brakes the preceding movement. It must
        // not snap to a nearby target while still travelling away from it.
        if(next*remaining>0&&Math.abs(next)>=Math.abs(remaining)&&Math.abs(velocity)<=ACCELERATION)
            return new Step(target,0);
        float result=Math.max(0,Math.min(3,phase+next));
        return new Step(result,result==phase?0:next);
    }
    private static float brakingSpeed(float distance)
    {
        int ticks=Math.max(1,(int)Math.ceil((Math.sqrt(1+8*distance/ACCELERATION)-1)/2));
        return (distance+ACCELERATION*ticks*(ticks-1)/2)/ticks;
    }

    private static float smooth(float value)
    {float t=Math.max(0,Math.min(1,value));return t*t*(3-2*t);}
    private EvaStanceTimingR53() {}
}
