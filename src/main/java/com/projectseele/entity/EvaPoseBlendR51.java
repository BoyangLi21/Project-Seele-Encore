package com.projectseele.entity;

/** Pure transition weights: sampling a pose never advances a transition clock. */
public final class EvaPoseBlendR51
{
    private EvaPoseBlendR51() { }

    public static float smooth(float value)
    {
        float t=Math.max(0,Math.min(1,value));
        return t*t*(3-2*t);
    }

    public static float entryEnd(float sourceSeconds,float contactPhase)
    {
        // A percentage of a multi-second knife clip held the old pose for
        // hundreds of milliseconds. This changes only the pose crossfade.
        float end=Math.min(.18F,.12F/Math.max(.01F,sourceSeconds));
        return Float.isFinite(contactPhase)?Math.min(end,Math.max(0,contactPhase)*.5F):end;
    }
}
