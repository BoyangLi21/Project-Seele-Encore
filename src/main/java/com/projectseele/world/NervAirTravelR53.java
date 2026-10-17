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
        // Keep the short docking and hatch crossing segments at their authored speed.
        // Quintic easing has peak derivative 1.875 and zero endpoint velocity.
        if(distance<64||!corridor.gates().isEmpty()&&distance<128)return old;
        double peak=distance>=512?36:distance>=256?24:12;
        return Math.max(30,Math.min(old,(int)Math.ceil(distance*1.875/peak)));
    }

    private NervAirTravelR53(){}
}
