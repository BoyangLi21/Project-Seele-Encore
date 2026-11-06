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
        // A strike crosses over most of its wind-up: ending on a fixed tenth of a second, the arms
        // jumped from the hanging idle to the guard in one tick, before a contact only three ticks away.
        return Float.isFinite(contactPhase)?Math.max(end,Math.max(0,contactPhase)*.7F):end;
    }
}
