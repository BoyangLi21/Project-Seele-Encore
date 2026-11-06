import org.mtr.core.data.*;
import org.mtr.libraries.com.google.gson.*;
import java.nio.file.*;
import java.lang.reflect.*;

/** Pinned isolated native speed policy; does not start a simulator or write DB. */
public final class NativeDirectHQOperatingR53
{
    static Object field(Object o,String name)throws Exception
    {Field f=o.getClass().getDeclaredField(name);f.setAccessible(true);return f.get(o);}
    @SuppressWarnings("unchecked")
    public static void main(String[]args)throws Exception
    {
        JsonObject records=JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject();
        Method load=NativeMTRCompleteCandidateVerifier.class.getDeclaredMethod("load",JsonObject.class,boolean.class);load.setAccessible(true);
        Data data=(Data)load.invoke(null,records,true);JsonArray operating=new JsonArray();
        for(Siding siding:data.sidings)
        {
            if(!java.util.Set.of("DF5FECA5A69869EA","870D8E318A61ABC0").contains(siding.getHexId()))continue;
            Vehicle vehicle=((Iterable<Vehicle>)field(siding,"vehicles")).iterator().next();
            JsonObject row=new JsonObject();row.addProperty("siding",siding.getHexId());row.addProperty("original_vehicle_id",Long.toString(vehicle.getId()));
            JsonArray path=new JsonArray();
            for(PathData p:vehicle.vehicleExtraData.immutablePath)
            {
                if(p.getEndDistance()>1e300)continue;
                JsonObject q=new JsonObject();p.serializeData(new org.mtr.core.serializer.JsonWriter(q));
                q.addProperty("actual_native_limit_kph",p.getSpeedLimitKilometersPerHour());q.addProperty("actual_native_rail_length",p.getRailLength());path.add(q);
            }
            row.add("actual_native_path",path);operating.add(row);
        }
        JsonArray directions=new JsonArray();
        for(Rail rail:data.rails)
        {
            JsonObject raw=new JsonObject();rail.serializeData(new org.mtr.core.serializer.JsonWriter(raw));
            JsonObject p=raw.getAsJsonObject("position1"),q=raw.getAsJsonObject("position2");
            int x=p.get("x").getAsInt();
            if((x==296||x==304)&&q.get("x").getAsInt()==x&&p.get("y").getAsInt()==-467&&q.get("y").getAsInt()==-467&&java.util.Set.of(p.get("z").getAsInt(),q.get("z").getAsInt()).equals(java.util.Set.of(212,240)))
            {
                JsonObject d=new JsonObject();d.addProperty("native_hex_id",rail.getHexId());d.add("position1",p);d.add("position2",q);
                Position fromPosition=new Position(p.get("x").getAsLong(),p.get("y").getAsLong(),p.get("z").getAsLong()),toPosition=new Position(q.get("x").getAsLong(),q.get("y").getAsLong(),q.get("z").getAsLong());
                long from=Math.round(rail.getSpeedLimitMetersPerMillisecond(fromPosition)*3600),to=Math.round(rail.getSpeedLimitMetersPerMillisecond(toPosition)*3600);
                d.addProperty("actual_native_stored_from_limit_kph",from);d.addProperty("actual_native_stored_to_limit_kph",to);
                d.addProperty("actual_passenger_direction_limit_kph",x==304?from:to);d.addProperty("actual_opposite_forbidden_limit_kph",x==304?to:from);directions.add(d);
            }
        }
        JsonObject output=new JsonObject();output.addProperty("world_written",false);output.addProperty("native_simulator_started",false);
        output.add("actual_native_U2_flat_throat_directions",directions);
        output.add("actual_native_operating_paths",operating);Files.writeString(Path.of(args[1]),new GsonBuilder().setPrettyPrinting().create().toJson(output)+"\n");
        System.out.println("Read-only native effective speed policy: "+operating.size()+" original operating sidings");
    }
}
