package com.projectseele.world;

import com.projectseele.world.NervAirTransportManifestR52.Corridor;
import com.projectseele.world.NervAirTransportManifestR52.Frame;

/** Flight clocks are planned once and persisted with the trip. */
final class NervAirTravelR53
{
    static int ticks(Corridor corridor,Frame from,Frame to)
    {
        double distance=from.plane().translation().distanceTo(to.plane().translation());
        if(from.cargo()!=null&&to.cargo()!=null)
            distance=Math.max(distance,from.cargo().translation().distanceTo(to.cargo().translation()));
        int old=corridor.id().endsWith("/actual_loaded_bridge_r53")
                ?Math.max(1,(int)Math.ceil(distance*1.875/2.8)):corridor.ticks();
        // Docking still eases to zero; old fixed clocks could spend tens of
        // seconds on only a few metres of travel.
        double peak=distance>=512?36:distance>=256?24:distance>=128?12:distance>=64?2.8:1.2;
        return Math.min(old,Math.max(20,(int)Math.ceil(distance*1.875/peak)));
    }

    private NervAirTravelR53(){}
}
