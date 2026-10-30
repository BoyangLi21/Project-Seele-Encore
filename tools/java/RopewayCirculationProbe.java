import java.nio.file.*;
import java.util.*;
import org.mtr.core.data.*;
import org.mtr.core.serializer.*;
import org.mtr.core.simulation.Simulator;
import org.mtr.libraries.com.google.gson.*;

/** Bounded offline native circulation check, with no Minecraft client/world. */
public final class RopewayCirculationProbe
{
    private static final class ProbeSimulator extends Simulator
    {
        private final java.lang.reflect.Field previous;
        ProbeSimulator(String dim,Path root)throws Exception
        {
            super(dim,new String[]{dim},root,false);
            previous=Simulator.class.getDeclaredField("lastMillis");previous.setAccessible(true);
        }
        void advance(long millis)throws Exception
        {previous.setLong(this,getCurrentMillis());setCurrentMillis(millis);}
    }
    private static JsonObject json(SerializedDataBase value)
    {JsonObject out=new JsonObject();value.serializeFullData(new JsonWriter(out));return out;}

    public static void main(String[] args)throws Exception
    {
        Path root=Path.of(args[0]).toAbsolutePath().normalize();
        if(java.util.stream.StreamSupport.stream(root.spliterator(),false).noneMatch(p->p.toString().equalsIgnoreCase(".Codex")))
            throw new IllegalArgumentException("Copied authoring database only");
        String dim="projectseele/geofront";
        ProbeSimulator sim=new ProbeSimulator(dim,root);
        for(int i=0;i<30;i++){sim.tick();Thread.sleep(5);}
        List<Siding> sidings=sim.sidings.stream().filter(s->Set.of("HRW 車庫","HRE 車庫").contains(s.getName())).toList();
        if(sidings.size()!=2)throw new IllegalStateException("Expected the two Hakone sidings");
        long start=sim.getCurrentMillis();JsonArray samples=new JsonArray();
        for(int second=0;second<=2400;second++)
        {
            if(second>0)
            {
                sim.advance(start+second*1000L);
                for(Siding siding:sidings)siding.simulateTrain(1000,null);
            }
            if(second%300==0)
            {
                JsonObject row=new JsonObject();row.addProperty("simulatedSeconds",second);
                for(Siding siding:sidings)row.addProperty(siding.getName(),json(siding).getAsJsonArray("vehicles").size());
                samples.add(row);
            }
        }
        JsonObject result=new JsonObject();result.add("fleetCounts",samples);
        result.addProperty("nativeDefaultIntervalMillis",8000);
        result.addProperty("note","Tests return-to-depot lifecycle at the native eight-second stress cadence; game mixin changes the two named services to 45 seconds.");
        Files.writeString(Path.of(args[1]),new GsonBuilder().setPrettyPrinting().create().toJson(result));
        sim.stop();System.out.println(result);
    }
}
