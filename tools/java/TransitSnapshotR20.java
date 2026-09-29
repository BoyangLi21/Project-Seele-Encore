import java.nio.file.*;
import java.util.*;
import org.mtr.core.data.*;
import org.mtr.core.serializer.*;
import org.mtr.core.simulation.Simulator;
import org.mtr.libraries.com.google.gson.*;

/** Read the installed MTR engine's own object schema and continuous curves. */
public final class TransitSnapshotR20
{
    static JsonObject json(SerializedDataBase v){JsonObject o=new JsonObject();v.serializeFullData(new JsonWriter(o));return o;}
    static JsonArray objects(Collection<? extends SerializedDataBase> values){JsonArray a=new JsonArray();for(var v:values)a.add(json(v));return a;}
    public static void main(String[] args)throws Exception
    {
        Path root=Path.of(args[0]).toAbsolutePath();if(!root.toString().contains(".Codex"))throw new IllegalArgumentException("Snapshot copy required");
        Simulator sim=new Simulator("projectseele/geofront",new String[]{"minecraft/overworld","projectseele/geofront","minecraft/the_nether","minecraft/the_end"},root,false);
        JsonObject out=new JsonObject();out.add("stations",objects(sim.stations));out.add("platforms",objects(sim.platforms));out.add("routes",objects(sim.routes));out.add("sidings",objects(sim.sidings));out.add("depots",objects(sim.depots));out.add("rails",objects(sim.rails));out.add("lifts",objects(sim.lifts));
        JsonArray curves=new JsonArray();
        for(Rail r:sim.rails)
        {
            JsonObject q=new JsonObject();q.addProperty("id",r.getHexId());q.addProperty("mode",r.getTransportMode().name());q.addProperty("kind",r.isPlatform()?"platform":r.isSiding()?"siding":"rail");JsonArray points=new JsonArray();
            for(double d=0;d<=r.railMath.getLength();d+=1){var p=r.railMath.getPosition(d,false);JsonArray a=new JsonArray();a.add(p.x);a.add(p.y);a.add(p.z);points.add(a);}q.add("points",points);curves.add(q);
        }
        out.add("curves",curves);
        JsonArray paths=new JsonArray();
        for(Depot depot:sim.depots){JsonObject p=new JsonObject();p.addProperty("depot",depot.getId());p.addProperty("name",depot.getName());p.add("path",objects(depot.getPath()));paths.add(p);}
        out.add("depot_paths",paths);
        JsonArray resolved=new JsonArray();
        for(Platform platform:sim.platforms)
        {
            JsonObject p=new JsonObject();p.addProperty("platform_id",Long.toString(platform.getId()));
            p.addProperty("platform_hex",platform.getHexId());p.addProperty("mode",platform.getTransportMode().name());
            p.addProperty("station_name",platform.getStationName());
            if(platform.area!=null)p.addProperty("station_id",Long.toString(platform.area.getId()));
            JsonArray routes=new JsonArray();for(Route route:platform.routes)routes.add(Long.toString(route.getId()));p.add("route_ids",routes);
            resolved.add(p);
        }
        out.add("resolved_platforms",resolved);
        Files.writeString(Path.of(args[1]),new GsonBuilder().setPrettyPrinting().create().toJson(out));sim.stop();System.out.println("Snapshot rails="+sim.rails.size()+" stations="+sim.stations.size()+" platforms="+sim.platforms.size()+" routes="+sim.routes.size());
    }
}
