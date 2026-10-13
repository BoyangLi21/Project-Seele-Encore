package com.projectseele.world;
/** Original R51 leaf/bridge/capsule/fluid clocks, shared by mapped service. */
public final class NervAssemblyClocksR52
{
    public static int bridgeRemaining(int age){return Math.max(0,9-(int)Math.ceil(Math.max(0,age)*9D/40));}
    public static double insertionProgress(int age){return smoother(Math.max(0,Math.min(1,(age-36)/(double)(EntryPlugDirector.INSERTION_TICKS-36))));}
    public static double extractionProgress(int age){return 1-Math.max(0,Math.min(1,(age-36)/105D));}
    public static int drainedLayers(int count,int age){return Math.min(count,Math.max(0,age)/4);}
    private static double smoother(double t){return t*t*t*(t*(t*6-15)+10);}
    private NervAssemblyClocksR52(){}
}
