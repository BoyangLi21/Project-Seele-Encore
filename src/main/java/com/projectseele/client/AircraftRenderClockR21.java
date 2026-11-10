package com.projectseele.client;

import com.projectseele.ProjectSeele;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Presentation time belongs to a whole frame, not an occasionally visible car. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID,value=Dist.CLIENT)
public final class AircraftRenderClockR21
{
    private static long previous,presented;
    private static long frameStarted,nativeStarted,nativeFrame=-1;
    private static double nativeFraction;
    public static long duplicateMtrPasses;
    public static double simulationSeconds;
    public static long frame;
    public static double seconds=1D/60;
    /** One timestamp per rendered frame: the main and shadow passes of the same
     * frame must evaluate time-driven poses identically. */
    public static long frameNanos(){return frameStarted==0?System.nanoTime():frameStarted;}
    private static long stamped;
    /**
     * Called at the head of Minecraft.runTick, where vanilla samples its own
     * frame timer. RenderTickEvent fires only after that frame's client
     * ticks, so stamping there added their four to eight milliseconds to every
     * third frame interval: time-driven poses sped up and slowed down against
     * the evenly interpolated body, a visible judder in every walk.
     */
    public static void stampFrame(){stamped=System.nanoTime();}
    public static long simulationMillis()
    {
        if(nativeFrame==frame){duplicateMtrPasses++;return 0;}
        nativeFrame=frame;
        double duration=nativeStarted==0?seconds:Math.max(0,(frameStarted-nativeStarted)/1e9);
        nativeStarted=frameStarted;
        if(net.minecraft.client.Minecraft.getInstance().isPaused())return 0;
        double millis=duration*1000+nativeFraction;long whole=(long)millis;nativeFraction=millis-whole;
        simulationSeconds+=whole/1000D;return whole;
    }
    @SubscribeEvent(priority=net.minecraftforge.eventbus.api.EventPriority.HIGHEST)
    public static void begin(TickEvent.RenderTickEvent event)
    {
        if(event.phase!=TickEvent.Phase.START)return;
        long now=stamped>frameStarted?stamped:System.nanoTime();
        seconds=previous==0?1D/60:Math.max(0,(now-previous)/1e9);
        previous=now;frameStarted=now;frame++;
        if(net.minecraft.client.Minecraft.getInstance().isPaused())nativeStarted=now;
    }
    @SubscribeEvent(priority=net.minecraftforge.eventbus.api.EventPriority.LOWEST)
    public static void presented(TickEvent.RenderTickEvent event)
    {
        if(event.phase!=TickEvent.Phase.END)return;
        presented=System.nanoTime();
    }
    private AircraftRenderClockR21(){}
}
