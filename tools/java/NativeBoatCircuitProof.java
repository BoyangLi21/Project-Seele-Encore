import java.nio.file.*;
import java.util.*;
import org.mtr.core.data.*;
import org.mtr.core.serializer.*;
import org.mtr.core.simulation.Simulator;
import org.mtr.libraries.com.google.gson.*;

/** Advance only the new boat in a disposable native-data copy, recording stops. */
public final class NativeBoatCircuitProof {
    private static final class ClockedSimulator extends Simulator {
        private final java.lang.reflect.Field previous;
        ClockedSimulator(Path root) throws Exception {
            super("projectseele/geofront",new String[]{"minecraft/overworld","projectseele/geofront"},root,false);
            previous=Simulator.class.getDeclaredField("lastMillis");previous.setAccessible(true);
        }
        void advance(long now) throws Exception {previous.setLong(this,getCurrentMillis());setCurrentMillis(now);}
    }
    private static JsonObject json(SerializedDataBase value) {
        JsonObject out = new JsonObject(); value.serializeFullData(new JsonWriter(out)); return out;
    }
    private static double distance(org.mtr.core.tool.Vector point,JsonObject platform) {
        JsonObject a=platform.getAsJsonObject("position1"),b=platform.getAsJsonObject("position2");
        double ax=a.get("x").getAsDouble()+.5,az=a.get("z").getAsDouble()+.5;
        double dx=b.get("x").getAsDouble()+.5-ax,dz=b.get("z").getAsDouble()+.5-az;
        double t=Math.max(0,Math.min(1,((point.x-ax)*dx+(point.z-az)*dz)/(dx*dx+dz*dz)));
        return Math.hypot(point.x-ax-t*dx,point.z-az-t*dz);
    }
    private static org.mtr.core.tool.Vector centre(Vehicle vehicle) {
        double x=0,y=0,z=0;int count=0;
        for(var car:vehicle.getVehicleCarsAndPositions())for(var pair:car.right())
            for(var point:List.of(pair.left(),pair.right())) {x+=point.x;y+=point.y;z+=point.z;count++;}
        if(count==0)throw new IllegalStateException("No native bogie positions");
        return new org.mtr.core.tool.Vector(x/count,y/count,z/count);
    }
    public static void main(String[] args) throws Exception {
        Path root=Path.of(args[0]).toAbsolutePath().normalize(), output=Path.of(args[2]);
        if (java.util.stream.StreamSupport.stream(root.spliterator(),false)
                .noneMatch(p->p.toString().equalsIgnoreCase(".Codex")))
            throw new IllegalArgumentException("Disposable .Codex copy required");
        ClockedSimulator simulator=new ClockedSimulator(root);
        simulator.tick(); // Initialize the native wall clock before bounded fast-forward.
        long sidingId=Long.parseLong(args[1]);
        Siding siding=simulator.sidings.stream().filter(s->s.getId()==sidingId).findFirst().orElseThrow();
        if(args.length>3&&args[3].equals("--fixed-dwell")) {
            siding.setDelayedVehicleReduceDwellTimePercentage(0);
            siding.setEarlyVehicleIncreaseDwellTime(false);
            simulator.save();Files.writeString(output,new GsonBuilder().setPrettyPrinting().create().toJson(json(siding)));
            simulator.stop();System.out.println("New boat siding now preserves its full platform dwell");return;
        }
        List<Platform> boatPlatforms=simulator.platforms.stream()
                .filter(p->json(p).get("transportMode").getAsString().equals("BOAT")).toList();
        var field=Siding.class.getDeclaredField("vehicles");field.setAccessible(true);
        long start=simulator.getCurrentMillis(), previousPlatform=0;
        JsonArray stops=new JsonArray();Set<Long> distinct=new HashSet<>();Set<Long> ids=new HashSet<>();
        JsonArray stationary=new JsonArray();Set<Long> stationaryProgress=new HashSet<>();
        int tick;
        for(tick=0;tick<30000;tick++) {
            simulator.advance(start+tick*200L);
            siding.simulateTrain(200,null);
            @SuppressWarnings("unchecked") Collection<Vehicle> vehicles=(Collection<Vehicle>)field.get(siding);
            for(Vehicle vehicle:vehicles) {
                ids.add(vehicle.getId());
                if(!vehicle.isMoving()) {
                    JsonObject state=json(vehicle);long progress=Math.round(state.get("railProgress").getAsDouble());
                    if(stationaryProgress.add(progress)) {
                        var head=vehicle.getHeadPosition();state.addProperty("head_x",head.x);state.addProperty("head_z",head.z);
                        state.addProperty("door_multiplier",vehicle.vehicleExtraData.getDoorMultiplier());stationary.add(state);
                    }
                }
                if(vehicle.isMoving()||vehicle.vehicleExtraData.getDoorMultiplier()==0)continue;
                // At the exact final path endpoint getHeadPosition can return
                // the native fallback origin. Renderer bogie positions clamp
                // inside the path and remain the correct boarding geometry.
                var head=centre(vehicle);
                Platform closest=boatPlatforms.stream().min(Comparator.comparingDouble(p->distance(head,json(p)))).orElseThrow();
                if(distance(head,json(closest))>2)continue;
                long platform=closest.getId();
                if(platform==0||platform==previousPlatform)continue;
                previousPlatform=platform;distinct.add(platform);
                JsonObject stop=new JsonObject();stop.addProperty("platform_id",platform);
                stop.addProperty("vehicle_id",vehicle.getId());stop.addProperty("elapsed_seconds",tick*.2);
                stop.addProperty("door_multiplier",vehicle.vehicleExtraData.getDoorMultiplier());
                stop.addProperty("association","nearest native platform to stationary door-open renderer bogie centre");
                stop.add("vehicle",json(vehicle));JsonArray bogies=new JsonArray();
                for(var car:vehicle.getVehicleCarsAndPositions())for(var pair:car.right()) {
                    JsonArray two=new JsonArray();
                    for(var point:List.of(pair.left(),pair.right())) {
                        JsonArray xyz=new JsonArray();xyz.add(point.x);xyz.add(point.y);xyz.add(point.z);two.add(xyz);
                    }
                    bogies.add(two);
                }
                stop.add("bogies",bogies);stops.add(stop);
            }
            if(distinct.size()==3&&stops.size()>=5)break;
        }
        JsonObject result=new JsonObject();result.addProperty("passed",distinct.size()==3&&stops.size()>=5&&ids.size()==1);
        result.addProperty("simulated_seconds",tick*.2);result.addProperty("distinct_platforms",distinct.size());
        result.addProperty("distinct_vehicles",ids.size());result.add("stops",stops);
        result.add("final_siding",json(siding));
        result.add("stationary_states",stationary);
        JsonArray platforms=new JsonArray();
        for(Platform platform:simulator.platforms)if(distinct.contains(platform.getId()))platforms.add(json(platform));
        result.add("platforms",platforms);result.addProperty("actual_world_written",false);
        Files.writeString(output,new GsonBuilder().setPrettyPrinting().create().toJson(result));
        simulator.stop();
        System.out.println("Native circuit: "+distinct.size()+" platforms, "+stops.size()+" stops, "+ids.size()+" vehicles");
        if(!result.get("passed").getAsBoolean())throw new IllegalStateException("Incomplete circuit");
    }
}
