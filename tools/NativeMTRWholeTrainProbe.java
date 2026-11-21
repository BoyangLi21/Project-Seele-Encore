import org.mtr.core.data.*;
import org.mtr.core.serializer.*;
import org.mtr.libraries.com.google.gson.*;
import java.nio.file.*;
import java.lang.reflect.*;
import java.util.*;

/** Pure native car/bogie sampling, no simulator, no world or database writes. */
public final class NativeMTRWholeTrainProbe
{
    static Object field(Object o,String name)throws Exception
    {for(Class<?>c=o.getClass();c!=null;c=c.getSuperclass())try{Field f=c.getDeclaredField(name);f.setAccessible(true);return f.get(o);}catch(NoSuchFieldException ignored){}throw new NoSuchFieldException(name);}
    static Field mutableField(Object o,String name)throws Exception
    {for(Class<?>c=o.getClass();c!=null;c=c.getSuperclass())try{Field f=c.getDeclaredField(name);f.setAccessible(true);return f;}catch(NoSuchFieldException ignored){}throw new NoSuchFieldException(name);}
    static JsonArray vector(org.mtr.core.tool.Vector p)
    {JsonArray a=new JsonArray();a.add(p.x);a.add(p.y);a.add(p.z);return a;}
    static boolean close(org.mtr.core.tool.Vector p)
    {
        return p.y>=-590&&p.y<=-440&&((p.x>=-100&&p.x<=160&&p.z>=430&&p.z<=590)||(p.x>=-370&&p.x<=-190&&p.z>=730&&p.z<=850)||(p.x>=260&&p.x<=370&&p.z>=380&&p.z<=600)||(p.x>=240&&p.x<=380&&p.z>=180&&p.z<=330));
    }
    @SuppressWarnings("unchecked")
    public static void main(String[]args)throws Exception
    {
        Path out=Path.of(args[1]);if(Files.exists(out))throw new IllegalArgumentException("Keep previous proof");
        JsonObject records=JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject();
        Method load=NativeMTRCompleteCandidateVerifier.class.getDeclaredMethod("load",JsonObject.class,boolean.class);load.setAccessible(true);
        Data data=(Data)load.invoke(null,records,true);JsonArray frames=new JsonArray();int checked=0;Set<Long>done=new HashSet<>();
        for(Siding siding:data.sidings)
        {
            if(!Set.of("DF5FECA5A69869EA","870D8E318A61ABC0").contains(siding.getHexId()))continue;
            for(Vehicle vehicle:(Iterable<Vehicle>)field(siding,"vehicles"))
            {
                if(!done.add(siding.getId()))continue;
                Field progress=mutableField(vehicle,"railProgress");double original=progress.getDouble(vehicle);
                var path=vehicle.vehicleExtraData.immutablePath;double end=0;
                for(var segment:path)if(segment.getEndDistance()<1e300)end=Math.max(end,segment.getEndDistance());
                for(double distance=vehicle.vehicleExtraData.getTotalVehicleLength()+1;distance<end;distance+=.5)
                {
                    progress.setDouble(vehicle,distance);checked++;
                    var cars=vehicle.getVehicleCarsAndPositions();boolean keep=args.length>2&&args[2].equals("all");
                    for(var car:cars)for(var points:car.right())if(close(points.left())||close(points.right()))keep=true;
                    if(!keep)continue;
                    JsonObject f=new JsonObject();f.addProperty("siding",siding.getHexId());f.addProperty("vehicle_id",Long.toString(vehicle.getId()));f.addProperty("progress",distance);f.addProperty("reversed",vehicle.getReversed());JsonArray cs=new JsonArray();
                    for(var item:cars)
                    {
                        VehicleCar car=item.left();JsonObject c=new JsonObject();c.addProperty("vehicleId",car.getVehicleId());c.addProperty("length",car.getLength());c.addProperty("width",car.getWidth());c.addProperty("bogie1",car.getBogie1Position());c.addProperty("bogie2",car.getBogie2Position());JsonArray pairs=new JsonArray();
                        for(var points:item.right()){JsonArray pair=new JsonArray();pair.add(vector(points.left()));pair.add(vector(points.right()));pairs.add(pair);}
                        c.add("native_position_pairs",pairs);cs.add(c);
                    }
                    f.add("cars",cs);frames.add(f);
                }
                progress.setDouble(vehicle,original);
            }
        }
        JsonObject report=new JsonObject();report.addProperty("world_written",false);report.addProperty("sample_step_metres",.5);report.addProperty("whole_path_positions_examined",checked);report.addProperty("interface_frames",frames.size());report.addProperty("sidings",done.size());report.add("frames",frames);Files.writeString(out,new Gson().toJson(report));System.out.println("Native full car bogie frames="+frames.size()+", examined="+checked);
    }
}
