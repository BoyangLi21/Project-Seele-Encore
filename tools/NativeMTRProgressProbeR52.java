import org.mtr.core.data.*;
import org.mtr.core.serializer.*;
import org.mtr.core.tool.Angle;
import org.mtr.libraries.com.google.gson.*;
import org.mtr.libraries.org.msgpack.core.MessagePack;
import java.nio.file.*;
import java.lang.reflect.*;
import java.util.*;
import java.util.zip.*;

/** Read delivered MessagePack into isolated native objects, never a Simulator. */
public final class NativeMTRProgressProbeR52
{
    private static JsonObject serialize(SerializedDataBase value)
    {
        JsonObject result=new JsonObject();value.serializeData(new JsonWriter(result));return result;
    }
    private static Object field(Object o,String name) throws Exception
    {
        for(Class<?> c=o.getClass();c!=null;c=c.getSuperclass())
        {
            try{Field f=c.getDeclaredField(name);f.setAccessible(true);return f.get(o);}
            catch(NoSuchFieldException ignored){}
        }
        throw new NoSuchFieldException(name);
    }
    private static JsonArray point(Position p)
    {
        JsonArray a=new JsonArray();a.add(p.getX());a.add(p.getY());a.add(p.getZ());return a;
    }
    private static JsonArray vector(org.mtr.core.tool.Vector p)
    {
        JsonArray a=new JsonArray();a.add(p.x);a.add(p.y);a.add(p.z);return a;
    }
    private static String key(Position a,Position b)
    {
        return point(Position.getMin(a,b)).toString()+"|"+point(Position.getMax(a,b)).toString();
    }
    private static Position pos(JsonArray p)
    {return new Position(p.get(0).getAsLong(),p.get(1).getAsLong(),p.get(2).getAsLong());}
    private static Position pos(JsonObject p)
    {return new Position(p.get("x").getAsLong(),p.get("y").getAsLong(),p.get("z").getAsLong());}
    private static JsonObject path(PathData p,Map<String,Integer> originals)
    {
        JsonObject q=serialize(p);q.add("ordered_start",point(p.getOrderedPosition1()));q.add("ordered_end",point(p.getOrderedPosition2()));
        q.addProperty("native_rail_length",p.getRailLength());q.addProperty("reverse_positions",p.reversePositions);
        q.addProperty("native_speed_limit_kph",p.getSpeedLimitKilometersPerHour());
        Integer index=originals.get(key(p.getOrderedPosition1(),p.getOrderedPosition2()));
        if(index!=null)q.addProperty("changed_original_rail_index",index);
        return q;
    }
    private static JsonArray paths(Iterable<PathData> p,Map<String,Integer> originals)
    {
        JsonArray a=new JsonArray();for(PathData v:p)a.add(path(v,originals));return a;
    }
    private static JsonObject partialUpdateProbe(Vehicle original,Siding siding,Data data) throws Exception
    {
        JsonObject before=serialize(original);
        Vehicle fixture=new Vehicle(original.vehicleExtraData,siding,new JsonReader(before),data);
        Map<String,Object> privateBefore=new LinkedHashMap<>();
        for(String name:List.of("stoppingCooldown","deviation","deviationSpeedAdjustment","manualCooldown","doorCooldown","atoOverride"))
            privateBefore.put(name,field(fixture,name));
        JsonObject edit=new JsonObject();edit.addProperty("railProgress",before.get("railProgress").getAsDouble()+123.);
        edit.addProperty("nextStoppingIndexAto",before.get("nextStoppingIndexAto").getAsLong()+4);
        edit.addProperty("nextStoppingIndexManual",before.get("nextStoppingIndexManual").getAsLong()+4);
        fixture.updateData(new JsonReader(edit));
        JsonObject after=serialize(fixture);
        for(var e:before.entrySet())
            if(!edit.has(e.getKey())&&!after.get(e.getKey()).equals(e.getValue()))throw new AssertionError("Partial update changed "+e.getKey());
        for(var e:edit.entrySet())if(!after.get(e.getKey()).equals(e.getValue()))throw new AssertionError("Partial update failed "+e.getKey());
        for(var e:privateBefore.entrySet())if(!Objects.equals(field(fixture,e.getKey()),e.getValue()))throw new AssertionError("Private state changed "+e.getKey());
        if(fixture.vehicleExtraData!=original.vehicleExtraData)throw new AssertionError("Extra data replaced");
        JsonObject result=new JsonObject();result.addProperty("native_partial_update_only_three_fields",true);
        result.addProperty("all_other_serialized_state_preserved",true);result.addProperty("private_Vehicle_state_preserved",true);
        result.addProperty("immutable_path_identity_preserved",true);return result;
    }
    @SuppressWarnings("unchecked")
    public static void main(String[] args) throws Exception
    {
        Path output=Path.of(args[3]);if(Files.exists(output))throw new IllegalArgumentException("Preserve previous output; use a new output filename");
        JsonObject report=new JsonObject();report.addProperty("schema","projectseele.r52.native-mtr-progress-readonly.v1");
        report.addProperty("source_archive",args[0]);report.addProperty("native_database_written",false);report.addProperty("simulator_started",false);
        Map<String,Integer> originals=new HashMap<>();
        JsonArray ten=JsonParser.parseString(Files.readString(Path.of(args[1]))).getAsJsonArray();
        for(int i=0;i<ten.size();i++)
        {
            JsonObject d=ten.get(i).getAsJsonObject().getAsJsonObject("data");
            originals.put(key(pos(d.getAsJsonObject("position1")),pos(d.getAsJsonObject("position2"))),i);
        }
        Data data=new Data(){};
        Map<String,Integer> readCounts=new TreeMap<>();Map<Long,JsonObject> rawSidingVehicles=new HashMap<>();
        try(ZipFile zip=new ZipFile(args[0]))
        {
            var entries=zip.entries();while(entries.hasMoreElements())
            {
                ZipEntry entry=entries.nextElement();String name=entry.getName();String marker="/mtr/projectseele/geofront/";
                int offset=name.indexOf(marker);if(offset<0||entry.isDirectory())continue;
                String type=name.substring(offset+marker.length()).split("/")[0];
                byte[] bytes=zip.getInputStream(entry).readAllBytes();
                try(var unpacker=MessagePack.newDefaultUnpacker(bytes))
                {
                    ReaderBase reader=new MessagePackReader(unpacker);
                    switch(type)
                    {
                        case "stations" -> data.stations.add(new Station(reader,data));
                        case "platforms" -> data.platforms.add(new Platform(reader,data));
                        case "rails" -> data.rails.add(new Rail(reader));
                        case "routes" -> data.routes.add(new Route(reader,data));
                        case "depots" -> data.depots.add(new Depot(reader,data));
                        case "sidings" -> {
                            Siding siding=new Siding(reader,data);data.sidings.add(siding);
                            JsonObject vehicles=new JsonObject();reader.iterateReaderArray("vehicles",()->{},v->{
                                Vehicle fixture=new Vehicle(v);JsonObject q=serialize(fixture);vehicles.add(q.get("id").getAsString(),q);
                            });rawSidingVehicles.put(siding.getId(),vehicles);
                        }
                        default -> {}
                    }
                    readCounts.merge(type,1,Integer::sum);
                }
            }
        }
        report.add("original_messagepack_record_counts",new Gson().toJsonTree(readCounts));
        data.sync();
        for(Depot depot:data.depots)depot.writePathCache();
        Method write=Siding.class.getDeclaredMethod("writePathCache");write.setAccessible(true);
        for(Siding siding:data.sidings)write.invoke(siding);
        // This is native startup restoration from the original readers, in an
        // isolated Data instance. Never call this on live gameplay sidings.
        for(Siding siding:data.sidings)siding.init();
        JsonArray depots=new JsonArray(),sidings=new JsonArray();int vehicles=0;
        for(Depot depot:data.depots)
        {
            JsonObject q=new JsonObject();q.addProperty("id",Long.toString(depot.getId()));q.addProperty("hex_id",String.format("%016X",depot.getId()));
            q.addProperty("name",depot.getName());q.add("path",paths(depot.getPath(),originals));depots.add(q);
        }
        for(Siding siding:data.sidings)
        {
            JsonObject q=new JsonObject();q.addProperty("id",Long.toString(siding.getId()));q.addProperty("hex_id",String.format("%016X",siding.getId()));
            q.addProperty("name",siding.getName());q.add("entry_path",paths((Iterable<PathData>)field(siding,"pathSidingToMainRoute"),originals));
            q.add("main_path",paths((Iterable<PathData>)field(siding,"pathMainRoute"),originals));
            q.add("return_path",paths((Iterable<PathData>)field(siding,"pathMainRouteToSiding"),originals));
            JsonArray all=new JsonArray();
            for(Vehicle vehicle:(Iterable<Vehicle>)field(siding,"vehicles"))
            {
                JsonObject v=serialize(vehicle);JsonObject raw=rawSidingVehicles.get(siding.getId()).getAsJsonObject(Long.toString(vehicle.getId()));
                if(!v.equals(raw))throw new AssertionError("Original native saved vehicle state altered during restore "+vehicle.getId());
                v.addProperty("original_saved_state_equal",true);v.addProperty("depot_id",Long.toString(vehicle.vehicleExtraData.getDepotId()));
                v.add("path",paths(vehicle.vehicleExtraData.immutablePath,originals));
                double progress=v.get("railProgress").getAsDouble();
                int index=org.mtr.core.tool.Utilities.getIndexFromConditionalList(vehicle.vehicleExtraData.immutablePath,progress);
                v.addProperty("native_current_path_index",index);
                if(index>=0)
                {
                    PathData p=vehicle.vehicleExtraData.immutablePath.get(index);double local=progress-p.getStartDistance();
                    v.addProperty("native_local_distance",local);v.addProperty("native_local_fraction",local/p.getRailLength());
                    v.add("native_progress_position",vector(p.getPosition(local)));
                }
                v.add("native_head_position",vector(vehicle.getHeadPosition()));
                v.add("native_partial_update_probe",partialUpdateProbe(vehicle,siding,data));all.add(v);vehicles++;
            }
            q.add("vehicles",all);sidings.add(q);
        }
        report.add("depots",depots);report.add("sidings",sidings);report.addProperty("native_restored_vehicle_count",vehicles);
        JsonObject candidate=JsonParser.parseString(Files.readString(Path.of(args[2]))).getAsJsonObject();JsonArray lengths=new JsonArray();
        for(JsonElement value:candidate.getAsJsonArray("segments"))
        {
            JsonObject segment=value.getAsJsonObject();
            JsonObject record=ten.get(segment.getAsJsonArray("source_original_indices").get(0).getAsInt()).getAsJsonObject().getAsJsonObject("data").deepCopy();
            JsonObject start=new JsonObject(),end=new JsonObject();String[] axes={"x","y","z"};
            for(int i=0;i<3;i++){start.add(axes[i],segment.getAsJsonArray("from").get(i));end.add(axes[i],segment.getAsJsonArray("to").get(i));}
            record.add("position1",start);record.add("position2",end);record.add("angle1",segment.get("from_angle"));record.add("angle2",segment.get("to_angle"));
            record.add("shape",segment.get("shape"));record.add("verticalRadius",segment.get("vertical_radius"));
            // Native Rail canonicalizes its endpoints before constructing
            // math. Direct reversed RailMath differs by ~1e-5m on curves.
            RailMath math=new Rail(new JsonReader(record)).railMath;
            double length=math.getLength();if(!Double.isFinite(length)||length<=0)throw new AssertionError("Invalid candidate length "+segment.get("id"));
            JsonObject q=segment.deepCopy();q.addProperty("native_rail_length",length);
            q.addProperty("native_effective_vertical_radius",math.getVerticalRadius());lengths.add(q);
        }
        report.add("candidate_native_segments",lengths);report.add("candidate_routes",candidate.get("routes"));
        Files.createDirectories(output.toAbsolutePath().getParent());Files.writeString(output,new GsonBuilder().setPrettyPrinting().create().toJson(report)+"\n");
        System.out.println("Read-only native PASS: "+readCounts+", restored="+vehicles+", candidate segments="+lengths.size());
    }
}
