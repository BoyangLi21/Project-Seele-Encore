package com.projectseele.visual;

import com.google.gson.JsonParser;
import java.nio.file.Files;
import java.util.LinkedHashMap;
import java.util.Map;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.Vec3;

/** Explicit measured destinations for the relocated world; never rebuilds a room. */
public final class SeeleTravelMapR52
{
    public static Map<String,SeeleTravelCommandsR43.Destination> read(ServerLevel level)
    {
        var file=level.getServer().getWorldPath(LevelResource.ROOT).resolve("r52/travel.json");
        try
        {
            if(!Files.isRegularFile(file)||Files.size(file)>96000)throw new IllegalArgumentException("Missing bounded R52 travel map");
            var root=JsonParser.parseString(Files.readString(file)).getAsJsonObject();
            if(root.get("schema").getAsInt()!=52||!root.get("map_author").getAsString().equals("root")
                    ||!root.get("dimension").getAsString().equals(level.dimension().location().toString())
                    ||!root.get("measured").getAsBoolean())throw new IllegalArgumentException("Unmeasured R52 travel map");
            var result=new LinkedHashMap<String,SeeleTravelCommandsR43.Destination>();
            for(var raw:root.getAsJsonArray("destinations"))
            {
                var o=raw.getAsJsonObject();String key=o.get("key").getAsString(),label=o.get("label").getAsString();
                var a=o.getAsJsonArray("position");if(!key.matches("[a-z0-9_]{1,40}")||a.size()!=3||label.length()>100)throw new IllegalArgumentException("Invalid destination");
                var p=new Vec3(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble());float yaw=o.get("yaw").getAsFloat();
                if(!Double.isFinite(p.lengthSqr())||!Float.isFinite(yaw)||p.y<level.getMinBuildHeight()||p.y>=level.getMaxBuildHeight())throw new IllegalArgumentException("Invalid destination position");
                if(result.putIfAbsent(key,new SeeleTravelCommandsR43.Destination(key,label,p,yaw))!=null)throw new IllegalArgumentException("Duplicate destination");
            }
            return java.util.Collections.unmodifiableMap(result);
        }
        catch(Exception failure){throw new IllegalStateException("R52 传送目录未就绪："+failure.getMessage(),failure);}
    }
    private SeeleTravelMapR52(){}
}
