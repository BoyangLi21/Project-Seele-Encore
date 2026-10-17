package com.projectseele.client;

public final class LiftTransferRenderClockR53
{
    private static final ThreadLocal<Float> PARTIAL=new ThreadLocal<>();
    private LiftTransferRenderClockR53() {}
    // Physics reads the current tick; only rendering interpolates the last step.
    public static float partial(){Float value=PARTIAL.get();return value==null?1F:value;}
    public static void begin(float partial){PARTIAL.set(partial);}
    public static void end(){PARTIAL.remove();}
}
