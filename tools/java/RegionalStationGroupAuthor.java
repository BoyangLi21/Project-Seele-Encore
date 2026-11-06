import java.nio.file.*;
import java.util.*;
import org.mtr.core.data.*;
import org.mtr.core.operation.UpdateDataRequest;
import org.mtr.core.serializer.*;
import org.mtr.core.simulation.Simulator;
import org.mtr.core.tool.Angle;
import org.mtr.libraries.com.google.gson.*;
import org.mtr.libraries.it.unimi.dsi.fastutil.objects.ObjectArrayList;

/** Add a bounded multi-platform station in an isolated native copy, without ticks. */
public final class RegionalStationGroupAuthor {
    static JsonObject json(SerializedDataBase v){JsonObject out=new JsonObject();v.serializeFullData(new JsonWriter(out));return out;}
    static Position pos(JsonArray a){return new Position(a.get(0).getAsLong(),a.get(1).getAsLong(),a.get(2).getAsLong());}
    static Map<String,JsonObject> snapshot(Collection<? extends SerializedDataBaseWithId> values){Map<String,JsonObject> out=new TreeMap<>();for(var v:values)out.put(v.getHexId(),json(v));return out;}
    static void retained(Map<String,JsonObject> before,Collection<? extends SerializedDataBaseWithId> values){var after=snapshot(values);for(var entry:before.entrySet())if(!entry.getValue().equals(after.get(entry.getKey())))throw new IllegalStateException("Existing native object changed");}
    static String member(String kind,SerializedDataBaseWithId v){String id=v.getHexId();return "mtr/projectseele/geofront/"+kind+"/"+id.substring(id.length()-2)+"/"+id;}
    public static void main(String[] args)throws Exception {
        Path plan=Path.of(args[0]),root=Path.of(args[1]).toAbsolutePath(),out=Path.of(args[2]);
        if(!root.toString().contains(".Codex"))throw new IllegalArgumentException("Isolated .Codex native copy required");
        JsonObject spec=JsonParser.parseString(Files.readString(plan)).getAsJsonObject();
        int count=spec.getAsJsonArray("rails").size();
        if(count<2||count>4||spec.getAsJsonArray("stations").size()!=1||spec.getAsJsonArray("lines").size()!=0)throw new IllegalArgumentException("One station with two to four platforms only");
        Simulator sim=new Simulator("projectseele/geofront",new String[]{"minecraft/overworld","projectseele/geofront","minecraft/the_nether","minecraft/the_end"},root,false);
        var rails=snapshot(sim.rails);var platforms=snapshot(sim.platforms);var stations=snapshot(sim.stations);var routes=snapshot(sim.routes);var depots=snapshot(sim.depots);var sidings=snapshot(sim.sidings);var lifts=snapshot(sim.lifts);
        List<Rail> additions=new ArrayList<>();List<String> platformIds=new ArrayList<>();Set<String> requestedNames=new HashSet<>();
        var styles=new ObjectArrayList<String>();styles.add("default_3d");
        for(var raw:spec.getAsJsonArray("rails")){
            JsonObject rr=raw.getAsJsonObject();String name=rr.get("platform_name").getAsString();
            if(name.isBlank()||!requestedNames.add(name)||!rr.get("kind").getAsString().equals("platform")||!rr.get("mode").getAsString().equals("TRAIN"))throw new IllegalArgumentException("Distinct train platform names required");
            Rail rail=Rail.newPlatformRail(pos(rr.getAsJsonArray("from")),Angle.valueOf(rr.get("from_angle").getAsString()),pos(rr.getAsJsonArray("to")),Angle.valueOf(rr.get("to_angle").getAsString()),Rail.Shape.QUADRATIC,rr.get("vertical_radius").getAsDouble(),styles,TransportMode.TRAIN);
            if(!rail.isValid()||rails.containsKey(rail.getHexId())||additions.stream().anyMatch(r->r.getHexId().equals(rail.getHexId())))throw new IllegalStateException("Invalid or duplicate new station rail");
            var before=snapshot(sim.platforms);new UpdateDataRequest(sim).addRail(rail).update();sim.sync();
            var created=sim.platforms.stream().filter(p->!before.containsKey(p.getHexId())).toList();
            if(created.size()!=1)throw new IllegalStateException("Each new rail must create exactly one platform");
            Platform p=created.get(0);p.setName(name);p.setDwellTime(12000);new UpdateDataRequest(sim).addPlatform(p).update();sim.sync();
            additions.add(rail);platformIds.add(p.getHexId());
        }
        JsonObject ss=spec.getAsJsonArray("stations").get(0).getAsJsonObject();Station station=new Station(sim);station.setName(ss.get("name").getAsString());station.setColor(ss.get("color").getAsInt());station.setCorners(pos(ss.getAsJsonArray("min")),pos(ss.getAsJsonArray("max")));
        new UpdateDataRequest(sim).addStation(station).update();sim.sync();
        if(sim.stations.size()!=stations.size()+1||sim.platforms.size()!=platforms.size()+count||sim.rails.size()!=rails.size()+count)throw new IllegalStateException("Unexpected native additions");
        JsonArray members=new JsonArray();members.add(member("stations",station));JsonArray details=new JsonArray();
        for(int i=0;i<count;i++){
            final String wanted=platformIds.get(i);Platform p=sim.platforms.stream().filter(v->v.getHexId().equals(wanted)).findFirst().orElseThrow();Rail rail=additions.get(i);
            if(p.area==null||!p.getStationName().equals(station.getName()))throw new IllegalStateException("Platform not assigned to intended station");
            members.add(member("rails",rail));members.add(member("platforms",p));JsonObject detail=new JsonObject();
            detail.add("input_rail_id",spec.getAsJsonArray("rails").get(i).getAsJsonObject().get("id"));detail.addProperty("platform_name",p.getName());detail.addProperty("platform_id",Long.toString(p.getId()));detail.addProperty("platform_length",rail.railMath.getLength());detail.addProperty("rail_member",member("rails",rail));detail.addProperty("platform_member",member("platforms",p));details.add(detail);
        }
        retained(rails,sim.rails);retained(platforms,sim.platforms);retained(stations,sim.stations);retained(routes,sim.routes);retained(depots,sim.depots);retained(sidings,sim.sidings);retained(lifts,sim.lifts);
        JsonObject proof=new JsonObject();proof.addProperty("existing_loaded_objects_exact",true);proof.addProperty("station",station.getName());proof.addProperty("station_id",Long.toString(station.getId()));proof.addProperty("existing_routes",routes.size());proof.addProperty("through_service_complete",false);proof.addProperty("world_written",false);proof.add("members",members);proof.add("platforms",details);
        sim.save();sim.stop();Files.createDirectories(out);Files.writeString(out.resolve("native-station-proof.json"),new GsonBuilder().setPrettyPrinting().create().toJson(proof));
        System.out.println("Prepared "+count+" native station platforms; all old loaded objects retained; no through service authored.");
    }
}
