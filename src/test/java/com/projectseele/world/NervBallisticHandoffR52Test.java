package com.projectseele.world;
/** The source recurrence must leave two closing ticks before actual landing. */
public final class NervBallisticHandoffR52Test {
    public static void main(String[] args){int checks=0;for(double gravity:new double[]{.42,.1,.8}){double velocity=NervBallisticHandoffR52.launchVelocity(gravity),y=0;for(int tick=1;tick<=42;tick++){y+=velocity;velocity=(velocity-gravity)*.98;if(Math.abs(y-NervBallisticHandoffR52.height(tick,gravity))>1e-10)throw new AssertionError("Native recurrence differs");checks++;}if(Math.abs(y+3)>1e-9)throw new AssertionError("Landing is not original root minus 3");checks++;}double v=NervBallisticHandoffR52.launchVelocity(.42);if(Math.abs(v-9.540150570661627)>1e-10||NervBallisticHandoffR52.height(40,.42)<=0)throw new AssertionError("Real close interval has no flight margin");checks+=2;System.out.println("Ballistic native recurrence PASS "+checks+" checks; giant impulse="+v*20+" m/s");}
}
