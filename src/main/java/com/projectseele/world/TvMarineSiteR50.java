package com.projectseele.world;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.Vec3;
import java.nio.file.Files;
import java.util.Map;
import java.util.Optional;
import java.util.WeakHashMap;

/** A measured water volume and physical control locations, installed only by the world writer. */
public final class TvMarineSiteR50
{
    public record Site(String id,Vec3 spawn,Vec3 center,double radiusX,double radiusZ,double seabed,double water,
            float scale,float yaw,BlockPos powerBlock,BlockPos powerControl,BlockPos[] cannonControls,
            Vec3 escape,int cargoHealth,int deadline,boolean geometryValidated,boolean modelReady,java.util.List<BlockPos> pylons) {}
    private static final Map<ServerLevel,Optional<Site>> CACHE=new WeakHashMap<>();
    private static Vec3 vec(JsonObject object,String key)
    {var a=object.getAsJsonArray(key);return new Vec3(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble());}
    public static Optional<Site> site(ServerLevel level)
    {
        return CACHE.computeIfAbsent(level,l->{
            var file=l.getServer().getWorldPath(LevelResource.ROOT).resolve("tv_marine_site_r50.json");if(!Files.isRegularFile(file))return Optional.empty();
            try
            {
                var o=JsonParser.parseString(Files.readString(file)).getAsJsonObject();
                if(o.get("schema").getAsInt()!=50||!o.get("dimension").getAsString().equals(l.dimension().location().toString()))throw new IllegalArgumentException("Marine site identity");
                if(!o.has("installed")||!o.get("installed").getAsBoolean())return Optional.empty();
                var buttons=o.getAsJsonArray("cannon_controls");if(buttons.size()!=2)throw new IllegalArgumentException("Two original artillery posts required");
                BlockPos[] controls=new BlockPos[2];for(int i=0;i<2;i++){var a=buttons.get(i).getAsJsonArray();controls[i]=new BlockPos(a.get(0).getAsInt(),a.get(1).getAsInt(),a.get(2).getAsInt());}
                var pylons=new java.util.ArrayList<BlockPos>();
                if(o.has("mission_power_pylons"))for(var raw:o.getAsJsonArray("mission_power_pylons"))
                {var a=raw.getAsJsonArray();pylons.add(new BlockPos(a.get(0).getAsInt(),a.get(1).getAsInt(),a.get(2).getAsInt()));}
                else if(o.has("new_umbilical_pylons"))for(var raw:o.getAsJsonArray("new_umbilical_pylons"))
                {var a=raw.getAsJsonArray();pylons.add(new BlockPos(a.get(0).getAsInt(),a.get(1).getAsInt(),a.get(2).getAsInt()));}
                else if(o.has("new_umbilical_pylon"))pylons.add(BlockPos.containing(vec(o,"new_umbilical_pylon")));
                if(pylons.isEmpty()||pylons.size()>4||pylons.stream().distinct().count()!=pylons.size())throw new IllegalArgumentException("Finite installed marine cable pylons required");
                var s=new Site(o.get("id").getAsString(),vec(o,"spawn"),vec(o,"arena_center"),o.get("radius_x").getAsDouble(),o.get("radius_z").getAsDouble(),o.get("seabed_y").getAsDouble(),o.get("water_y").getAsDouble(),o.get("model_scale").getAsFloat(),o.get("yaw").getAsFloat(),BlockPos.containing(vec(o,"power_block")),BlockPos.containing(vec(o,"power_control")),controls,vec(o,"escape_point"),o.get("cargo_health").getAsInt(),o.get("deadline_ticks").getAsInt(),o.get("geometry_validated").getAsBoolean(),o.get("model_ready").getAsBoolean(),java.util.List.copyOf(pylons));
                if(!finite(s.spawn())||!finite(s.center())||!finite(s.escape())||!Float.isFinite(s.scale())||!Float.isFinite(s.yaw())
                        ||s.scale()<.2||s.scale()>1.25||s.radiusX()<8||s.radiusX()>160||s.radiusZ()<8||s.radiusZ()>160
                        ||!Double.isFinite(s.seabed())||!Double.isFinite(s.water())||s.water()-s.seabed()<39*s.scale()+1
                        ||Math.abs(s.spawn().x-s.center().x)>s.radiusX()||Math.abs(s.spawn().z-s.center().z)>s.radiusZ()
                        ||s.spawn().y<s.seabed()+24*s.scale()+1||s.spawn().y>s.water()-13*s.scale()+1
                        ||s.cargoHealth()<1||s.cargoHealth()>1000||s.deadline()<600||s.deadline()>72000)
                    throw new IllegalArgumentException("Measured marine volume does not fit the complete model");
                for(BlockPos p:s.pylons())if(p.getY()<32||Vec3.atCenterOf(p).distanceTo(s.center())>256)throw new IllegalArgumentException("Marine pylon exceeds measured cable field");
                return Optional.of(s);
            }
            catch(Exception failure){ProjectSeele.LOGGER.error("Marine R50 measured site rejected",failure);return Optional.empty();}
        });
    }
    private static boolean finite(Vec3 v){return Double.isFinite(v.x)&&Double.isFinite(v.y)&&Double.isFinite(v.z);}
    public static void clear(ServerLevel level){CACHE.remove(level);}
    private TvMarineSiteR50(){}
}
