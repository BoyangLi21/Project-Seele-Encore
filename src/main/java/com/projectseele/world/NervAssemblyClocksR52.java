package com.projectseele.world;
/** Original R51 leaf/bridge/capsule/fluid clocks, shared by mapped service. */
public final class NervAssemblyClocksR52
{
    public static int bridgeRemaining(int age){return Math.max(0,9-(int)Math.ceil(Math.max(0,age)*9D/40));}
    public static final double CRANE_HANDOFF_PROGRESS = .80;
    public static final int INSERT_HANDOFF_TICK = 132;
    public static final int QUICK_INSERTION_TICKS_R54 = 100;
    public static final int QUICK_HANDOFF_TICK_R54 = 72;
    public static final int QUICK_BRIDGE_TICKS_R54 = 20;
    public static final int QUICK_RAISE_TICKS_R54 = 48;
    public static final int HEAD_SUBSTEPS_R54 = 3;
    public static final int EXTRACT_HANDOFF_TICK = 64;
    public static final int EXTRACT_GRIP_TICK = 100;
    public static double insertionProgress(int age)
    {
        if(age<=INSERT_HANDOFF_TICK)return CRANE_HANDOFF_PROGRESS*smoother(clamp((age-36)/96D));
        return CRANE_HANDOFF_PROGRESS+(1-CRANE_HANDOFF_PROGRESS)*smoother(clamp((age-INSERT_HANDOFF_TICK)/(double)(EntryPlugDirector.INSERTION_TICKS-INSERT_HANDOFF_TICK)));
    }
    public static double insertionProgress(int age, boolean quick)
    {
        if(!quick)return insertionProgress(age);
        // The first36 ticks retain the real crane approach and socket opening.
        if(age<=QUICK_HANDOFF_TICK_R54)return CRANE_HANDOFF_PROGRESS*smoother(clamp((age-36)/36D));
        return CRANE_HANDOFF_PROGRESS+(1-CRANE_HANDOFF_PROGRESS)*smoother(clamp((age-QUICK_HANDOFF_TICK_R54)/(double)(QUICK_INSERTION_TICKS_R54-QUICK_HANDOFF_TICK_R54)));
    }
    public static double extractionProgress(int age)
    {
        if(age<=EXTRACT_HANDOFF_TICK)return 1-(1-CRANE_HANDOFF_PROGRESS)*smoother(clamp((age-36)/28D));
        if(age<=EXTRACT_GRIP_TICK)return CRANE_HANDOFF_PROGRESS;
        return CRANE_HANDOFF_PROGRESS*(1-smoother(clamp((age-EXTRACT_GRIP_TICK)/41D)));
    }
    public static final int LCL_TICKS_PER_LAYER = 2;
    public static int drainedLayers(int count,int age){return Math.min(count,Math.max(0,age)/LCL_TICKS_PER_LAYER);}
    /** Remove the layer containing the falling surface before drawing its fractional height. */
    public static int drainingLayers(int count,int age){return Math.min(count,(int)Math.ceil(Math.max(0,age)/(double)LCL_TICKS_PER_LAYER));}
    public static float liquidLayers(int count,int age){return Math.min(count,Math.max(0,age)/(float)LCL_TICKS_PER_LAYER);}
    private static double smoother(double t){return t*t*t*(t*(t*6-15)+10);}
    private static double clamp(double t){return Math.max(0,Math.min(1,t));}
    private NervAssemblyClocksR52(){}
}
