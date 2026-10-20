package com.projectseele.entity;

/** Bounded continuation of the last moving gait interval at a packet boundary. */
public final class EvaGaitPacketTailR53
{
    public static final class Cursor
    {
        private boolean initialized;
        private float rendered,direction;
        private long tick;

        public float accept(float candidate,float previous,float latest,float move,long serverTick)
        {
            float travel=wrapped(latest-previous);
            float nextDirection=Math.abs(travel)>1e-7F?Math.signum(travel):direction;
            float correction=wrapped(candidate-rendered);
            boolean reset=!initialized||serverTick<tick||serverTick-tick>8
                    ||Math.abs(correction)>.25F||move<=.05F;
            // A new stationary/slower endpoint can arrive after a bounded
            // predicted tail. Wait for it to catch up instead of playing the
            // forward gait backwards. A real reverse interval changes direction.
            if(!reset&&nextDirection==direction&&correction*direction<0)
                candidate=rendered;
            rendered=candidate;direction=move<=.05F?0:nextDirection;
            tick=serverTick;initialized=true;
            return rendered;
        }
    }

    private static float wrapped(float value)
    {return value-Math.round(value);}

    public static float sample(float previous,float latest,float previousMove,float latestMove,
                               long interval,double ahead)
    {
        if(interval<=0||interval>3||!Double.isFinite(ahead)||ahead<=0
                ||previousMove<=.05F||latestMove<=.05F||latestMove+.0001F<previousMove)
            return latest;
        float distance=wrapped(latest-previous);
        // Discontinuities are not a velocity estimate. Keep deliberate reverse
        // walking, but do not predict through a stopped interval or a reset.
        if(!Float.isFinite(distance)||Math.abs(distance)<1e-7F||Math.abs(distance)/interval>.125F)
            return latest;
        // Metadata silence must stop within one server tick. This only bridges
        // the observed sub-tick packet tail; it never advances the server pose.
        return latest+distance*(float)(Math.min(ahead,1D)/interval);
    }

    private EvaGaitPacketTailR53() {}
}
