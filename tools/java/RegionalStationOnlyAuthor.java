import java.nio.file.*;
import java.util.*;
import org.mtr.core.data.*;
import org.mtr.core.operation.UpdateDataRequest;
import org.mtr.core.serializer.*;
import org.mtr.core.simulation.Simulator;
import org.mtr.core.tool.Angle;
import org.mtr.libraries.com.google.gson.*;
import org.mtr.libraries.it.unimi.dsi.fastutil.objects.ObjectArrayList;

/** Add one native station/platform in an isolated copy, without running vehicles. */
public final class RegionalStationOnlyAuthor {
    static JsonObject json(SerializedDataBase value){JsonObject out=new JsonObject();value.serializeFullData(new JsonWriter(out));return out;}
    static Position pos(JsonArray a){return new Position(a.get(0).getAsLong(),a.get(1).getAsLong(),a.get(2).getAsLong());}
    static Map<String,JsonObject> snapshot(Collection<? extends SerializedDataBaseWithId> values){
        Map<String,JsonObject> out=new TreeMap<>();for(var v:values)out.put(v.getHexId(),json(v));return out;
    }
    static void retained(Map<String,JsonObject> before,Collection<? extends SerializedDataBaseWithId> values){
        var after=snapshot(values);for(var entry:before.entrySet())if(!entry.getValue().equals(after.get(entry.getKey())))throw new IllegalStateException("Retained native object changed");
    }
    static String member(String kind,SerializedDataBaseWithId value){String id=value.getHexId();return "mtr/projectseele/geofront/"+kind+"/"+id.substring(id.length()-2)+"/"+id;}
    public static void main(String[] args)throws Exception {
        Path plan=Path.of(args[0]),root=Path.of(args[1]).toAbsolutePath(),out=Path.of(args[2]);
        if(!root.toString().contains(".Codex"))throw new IllegalArgumentException("An isolated .Codex copy is required");
        JsonObject spec=JsonParser.parseString(Files.readString(plan)).getAsJsonObject();
        if(spec.getAsJsonArray("rails").size()!=1||spec.getAsJsonArray("stations").size()!=1||spec.getAsJsonArray("lines").size()!=0)throw new IllegalArgumentException("Single station only");
        Simulator sim=new Simulator("projectseele/geofront",new String[]{"minecraft/overworld","projectseele/geofront","minecraft/the_nether","minecraft/the_end"},root,false);
        var rails=snapshot(sim.rails);var platforms=snapshot(sim.platforms);var stations=snapshot(sim.stations);var routes=snapshot(sim.routes);var depots=snapshot(sim.depots);var sidings=snapshot(sim.sidings);var lifts=snapshot(sim.lifts);
        JsonObject rr=spec.getAsJsonArray("rails").get(0).getAsJsonObject();Position a=pos(rr.getAsJsonArray("from")),b=pos(rr.getAsJsonArray("to"));
        var styles=new ObjectArrayList<String>();styles.add("default_3d");
        Rail rail=Rail.newPlatformRail(a,Angle.valueOf(rr.get("from_angle").getAsString()),b,Angle.valueOf(rr.get("to_angle").getAsString()),Rail.Shape.QUADRATIC,40,styles,TransportMode.TRAIN);
        if(!rail.isValid()||rails.containsKey(rail.getHexId()))throw new IllegalStateException("Invalid or existing native station track");
        new UpdateDataRequest(sim).addRail(rail).update();sim.sync();
        Platform platform=sim.platforms.stream().filter(p->!platforms.containsKey(p.getHexId())).findFirst().orElseThrow();
        if(sim.platforms.size()!=platforms.size()+1)throw new IllegalStateException("Unexpected new platform count");
        JsonObject ss=spec.getAsJsonArray("stations").get(0).getAsJsonObject();Station station=new Station(sim);
        station.setName(ss.get("name").getAsString());station.setColor(ss.get("color").getAsInt());station.setCorners(pos(ss.getAsJsonArray("min")),pos(ss.getAsJsonArray("max")));
        platform.setName("1");platform.setDwellTime(12000);
        new UpdateDataRequest(sim).addStation(station).addPlatform(platform).update();sim.sync();
        platform=sim.platforms.stream().filter(p->!platforms.containsKey(p.getHexId())).findFirst().orElseThrow();
        if(platform.area==null||!platform.getStationName().equals(station.getName()))throw new IllegalStateException("New platform has no intended station");
        retained(rails,sim.rails);retained(platforms,sim.platforms);retained(stations,sim.stations);retained(routes,sim.routes);retained(depots,sim.depots);retained(sidings,sim.sidings);retained(lifts,sim.lifts);
        JsonObject proof=new JsonObject();proof.addProperty("existing_loaded_objects_exact",true);proof.addProperty("station",platform.getStationName());proof.addProperty("platform_length",rail.railMath.getLength());
        proof.addProperty("through_service_complete",false);proof.addProperty("existing_routes",routes.size());proof.addProperty("world_written",false);
        proof.addProperty("station_id",Long.toString(station.getId()));proof.addProperty("platform_id",Long.toString(platform.getId()));
        JsonArray members=new JsonArray();members.add(member("rails",rail));members.add(member("stations",station));members.add(member("platforms",platform));proof.add("members",members);
        sim.save();sim.stop();Files.createDirectories(out);Files.writeString(out.resolve("native-station-proof.json"),new GsonBuilder().setPrettyPrinting().create().toJson(proof));
        System.out.println("Prepared native station and platform; all existing loaded objects retained; through service remains stage 3.");
    }
}
