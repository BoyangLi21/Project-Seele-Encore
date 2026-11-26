import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;
import org.mtr.core.data.*;
import org.mtr.core.serializer.JsonWriter;
import org.mtr.core.simulation.Simulator;
import org.mtr.core.tool.Vector;
import org.mtr.libraries.com.google.gson.*;

/** MTR 4.0.5 offline check. Only point this at a marked scratch copy of the world's mtr folder.
 * sample ROOT passing-rails.json output.json, or run ROOT output.json durationMs [stepMs].
 */
public class SpiralServiceCheck {
    private static final long SIDING = 7095002157700150526L;
    private static final Gson GSON = new GsonBuilder().setPrettyPrinting().create();
    private static Field field(Class<?> type, String name) throws Exception {
        Field f = type.getDeclaredField(name);
        f.setAccessible(true);
        return f;
    }

    record Node(long x, long y, long z) {
        static Node read(JsonElement e) {
            if (e.isJsonArray()) {
                var p = e.getAsJsonArray();
                return new Node(p.get(0).getAsLong(), p.get(1).getAsLong(), p.get(2).getAsLong());
            }
            var p = e.getAsJsonObject();
            return new Node(p.get("x").getAsLong(), p.get("y").getAsLong(), p.get("z").getAsLong());
        }
        String text() { return x + "," + y + "," + z; }
    }

    private static void sample(Simulator sim, Path selection, Path output) throws Exception {
        Set<Set<Node>> wanted = new HashSet<>();
        for (var edge : JsonParser.parseString(Files.readString(selection)).getAsJsonArray()) {
            var ends = edge.getAsJsonArray();
            wanted.add(Set.of(Node.read(ends.get(0)), Node.read(ends.get(1))));
        }
        JsonArray samples = new JsonArray();
        for (var rail : sim.rails) {
            var row = new JsonObject();
            rail.serializeFullData(new JsonWriter(row));
            Node a = Node.read(row.get("position1")), b = Node.read(row.get("position2"));
            if (!wanted.remove(Set.of(a,b))) continue;
            double length = rail.railMath.getLength();
            JsonArray points = new JsonArray();
            for (double s = 0; s < length + .25; s += .25) {
                var p = rail.railMath.getPosition(Math.min(s, length), false);
                points.add(GSON.toJsonTree(new double[]{p.x,p.y,p.z}));
            }
            JsonObject sample = new JsonObject();
            sample.addProperty("id", a.text()+"/"+b.text());
            sample.add("points", points);
            samples.add(sample);
        }
        if (!wanted.isEmpty()) throw new IllegalStateException("Missing passing rails " + wanted);
        Files.writeString(output, samples.toString());
    }

    record Car(double x, double y, double z, double dx, double dz, double halfLength, double halfWidth) {
        double projection(double ax, double az) {
            return Math.abs(ax * dx + az * dz) * halfLength + Math.abs(-ax * dz + az * dx) * halfWidth;
        }
        double gapOn(Car other, double ax, double az) {
            return Math.abs((other.x-x)*ax + (other.z-z)*az) - projection(ax,az) - other.projection(ax,az);
        }
        double gap(Car other) {
            return Math.max(Math.abs(other.y-y)-3.9, Math.max(Math.max(gapOn(other,dx,dz),gapOn(other,-dz,dx)),
                    Math.max(gapOn(other,other.dx,other.dz),gapOn(other,-other.dz,other.dx))));
        }
    }

    private static List<Car> body(Vehicle v) {
        List<Car> cars=new ArrayList<>();
        for (var car : v.getVehicleCarsAndPositions()) {
            var bogies=car.right();
            var a=bogies.get(0);
            var b=bogies.get(bogies.size()-1);
            var first=Vector.getAverage(a.left(),a.right());
            var last=Vector.getAverage(b.left(),b.right());
            var center=Vector.getAverage(first,last);
            double dx=first.x-last.x, dz=first.z-last.z, norm=Math.hypot(dx,dz);
            if (norm < .001) throw new IllegalStateException("Degenerate bogies on the GS train");
            cars.add(new Car(center.x,center.y,center.z,dx/norm,dz/norm,car.left().getLength()/2,
                    Math.max(2.98,car.left().getWidth())/2));
        }
        return cars;
    }

    record Stop(long time,long vehicle,long stopIndex) {}
    record Interval(long id,double start,double end) {}

    private static void run(Simulator sim, Path output, long duration, int step) throws Exception {
        Method tick=Simulator.class.getDeclaredMethod("tick",long.class);
        tick.setAccessible(true);
        var siding=sim.sidings.stream().filter(s->s.getId()==SIDING).findFirst().orElseThrow();
        Field vehicles=field(Siding.class,"vehicles"), next=field(Vehicle.class.getSuperclass(),"nextStoppingIndexAto");
        var positions=(List<?>)((List<?>)field(Simulator.class,"vehiclePositions").get(sim)).get(siding.getTransportModeOrdinal());
        var segments=field(VehiclePosition.class,"blockedSegments");
        var segmentClass=Class.forName("org.mtr.core.data.VehiclePosition$BlockedSegment");
        Field start=field(segmentClass,"startDistance"),end=field(segmentClass,"endDistance"),id=field(segmentClass,"id");
        List<Stop> stops=new ArrayList<>();
        Map<Long,Long> lastStop=new HashMap<>();
        Set<Long> activeIds=new HashSet<>();
        Set<Long> initial=new HashSet<>();
        for(Object obj:(Iterable<?>)vehicles.get(siding)) initial.add(((Vehicle)obj).getId());
        int peak=0;
        long trackOverlaps=0, carOverlaps=0, intervalsChecked=0, comparisons=0;
        double minGap=Double.MAX_VALUE;
        for(long t=0;t<=duration;t+=step) {
            tick.invoke(sim,(long)step);
            var trains=new ArrayList<List<Car>>();
            activeIds.clear();
            for(Object obj:(Iterable<?>)vehicles.get(siding)) {
                Vehicle vehicle=(Vehicle)obj;
                if(!vehicle.getIsOnRoute())continue;
                activeIds.add(vehicle.getId());
                trains.add(body(vehicle));
                long index=vehicle.vehicleExtraData.getDoorMultiplier()>0?next.getLong(vehicle):-1;
                if(index>=0 && index!=lastStop.getOrDefault(vehicle.getId(),-1L))
                    stops.add(new Stop(t,vehicle.getId(),index));
                lastStop.put(vehicle.getId(),index);
            }
            peak=Math.max(peak,trains.size());
            // Actual train-length occupancy intervals emitted by MTR's own tick on each undirected rail.
            for(Object row:((Map<?,?>)positions.get(1)).values()) for(Object bucket:((Map<?,?>)row).values()) {
                List<Interval> prior=new ArrayList<>();
                for(Object seg:(Iterable<?>)segments.get(bucket)) {
                    var current=new Interval(id.getLong(seg),start.getDouble(seg),end.getDouble(seg));
                    if(!activeIds.contains(current.id))continue;
                    intervalsChecked++;
                    for (var seen:prior)
                        if(seen.id!=current.id && Math.min(seen.end,current.end)-Math.max(seen.start,current.start)>.01) trackOverlaps++;
                    prior.add(current);
                }
            }
            // Distinct parallel rails have independent occupancy. Check the actual bogies of every opposing car too.
            for(int i=0;i<trains.size();i++) for(int j=0;j<i;j++) for(Car a:trains.get(i))for(Car b:trains.get(j)) {
                double gap=a.gap(b);
                minGap=Math.min(gap,minGap);
                if(gap<=0)carOverlaps++;
                comparisons++;
            }
        }
        var report=new JsonObject();
        report.addProperty("step_ms",step);
        report.addProperty("duration_ms",duration);
        report.addProperty("peak_active_trains",peak);
        report.add("saved_vehicle_ids",GSON.toJsonTree(initial));
        report.addProperty("native_occupancy_intervals_checked",intervalsChecked);
        report.addProperty("overlapping_native_intervals",trackOverlaps);
        report.addProperty("car_pairs_checked",comparisons);
        if(comparisons>0)report.addProperty("minimum_body_separation_lower_bound",minGap);
        report.addProperty("overlapping_car_envelopes",carOverlaps);
        report.add("doors",GSON.toJsonTree(stops));
        Files.writeString(output,GSON.toJson(report));
        if(intervalsChecked==0 || stops.isEmpty() || trackOverlaps>0 || carOverlaps>0)
            throw new IllegalStateException("Incomplete service or overlapping trains; inspect "+output);
    }

    public static void main(String[] args) throws Exception {
        Path root=Path.of(args[1]);
        if(!Files.isRegularFile(root.resolve(".spiral-test-copy"))) throw new IllegalArgumentException("Mark a disposable MTR copy first");
        Simulator sim=new Simulator("projectseele/geofront", new String[]{"minecraft/overworld","projectseele/geofront"}, root,false);
        try {
            if(args[0].equals("sample"))sample(sim,Path.of(args[2]),Path.of(args[3]));
            else if(args[0].equals("run")){
                sim.setGameTime(0,1200000,true);
                run(sim,Path.of(args[2]),Long.parseLong(args[3]),args.length>4?Integer.parseInt(args[4]):50);
            } else throw new IllegalArgumentException("Expected sample or run");
        } finally { sim.stop(); }
    }
}
