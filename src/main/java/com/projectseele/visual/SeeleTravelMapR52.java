package com.projectseele.visual;

import com.projectseele.world.NervTravelDirectoryR52;
import java.util.LinkedHashMap;
import java.util.Map;
import net.minecraft.server.level.ServerLevel;

/** Compatibility view of the single installed arrival directory. */
public final class SeeleTravelMapR52
{
    public static Map<String,SeeleTravelCommandsR43.Destination> read(ServerLevel level)
    {
        var directory=NervTravelDirectoryR52.installed(level);
        if(directory==null)throw new IllegalStateException("R52 传送目录未安装或与当前地图不一致");
        var result=new LinkedHashMap<String,SeeleTravelCommandsR43.Destination>();
        for(var arrival:directory.arrivals())result.put(arrival.key(),new SeeleTravelCommandsR43.Destination(
                arrival.key(),arrival.label(),arrival.position(),arrival.yaw()));
        return java.util.Collections.unmodifiableMap(result);
    }
    private SeeleTravelMapR52(){}
}
