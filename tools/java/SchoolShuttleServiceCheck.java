import java.lang.reflect.Field;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import org.mtr.core.data.Siding;
import org.mtr.core.data.Vehicle;
import org.mtr.core.simulation.Simulator;
import org.mtr.core.tool.Vector;
import org.mtr.libraries.com.google.gson.Gson;
import org.mtr.libraries.com.google.gson.JsonArray;
import org.mtr.libraries.com.google.gson.JsonObject;
import org.mtr.libraries.com.google.gson.JsonParser;

/** Replay a native service in an offline simulation snapshot; both stops must open doors. */
public final class SchoolShuttleServiceCheck {
    private static final class Replay extends Simulator {
        private final Field previousMillis;
        Replay(Path snapshot) throws ReflectiveOperationException {
            super("projectseele/geofront", new String[]{"minecraft/overworld", "projectseele/geofront"},
                    snapshot, false);
            previousMillis = Simulator.class.getDeclaredField("lastMillis");
            previousMillis.setAccessible(true);
        }
        void advance(long time) throws ReflectiveOperationException {
            previousMillis.setLong(this, getCurrentMillis());
            setCurrentMillis(time);
        }
    }

    private static String boardingStation(Vehicle vehicle) {
        if (vehicle.vehicleExtraData.getDoorMultiplier() <= 0) return "";
        var cars = vehicle.getVehicleCarsAndPositions();
        if (cars.isEmpty()) return "";
        var car = cars.get(cars.size() / 2);
        double x = 0, y = 0, z = 0;
        int n = 0;
        for (var pair : car.right()) {
            for (Vector p : List.of(pair.left(), pair.right())) {
                x += p.x; y += p.y; z += p.z; n++;
            }
        }
        if (n == 0) return "";
        x /= n; y /= n; z /= n;
        if (Math.abs(x + 114.5) < 1.5 && Math.abs(y - 75) < 2 && z < -150 && z > -195) return "central";
        if (Math.abs(x - 250.5) < 1.5 && Math.abs(y - 60) < 2 && z < -624 && z > -675) return "school";
        return "";
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 3)
            throw new IllegalArgumentException("offline simulator directory, author receipt, output receipt");
        JsonObject receipt = JsonParser.parseString(Files.readString(Path.of(args[1]))).getAsJsonObject();
        long sidingId = 0;
        for (var entry : receipt.getAsJsonArray("lines")) {
            JsonObject line = entry.getAsJsonObject();
            if (line.get("line").getAsString().equals("S")) sidingId = line.get("siding_id").getAsLong();
        }
        final long targetId = sidingId;
        if (targetId == 0) throw new IllegalStateException("No commissioned school siding in receipt");
        Replay sim = new Replay(Path.of(args[0]));
        try {
            sim.setGameTime(0, 1200000, true);
            var siding = sim.sidings.stream().filter(s -> s.getId() == targetId).findFirst().orElseThrow();
            Field vehicles = Siding.class.getDeclaredField("vehicles");
            vehicles.setAccessible(true);
            Map<Long, String> previous = new HashMap<>();
            Map<Long, Integer> progress = new HashMap<>();
            JsonArray stops = new JsonArray();
            boolean complete = false;
            long start = sim.getCurrentMillis();
            for (long elapsed = 0; elapsed <= 1000000 && !complete; elapsed += 200) {
                sim.advance(start + elapsed);
                siding.simulateTrain(200, null);
                for (Object obj : (Iterable<?>) vehicles.get(siding)) {
                    Vehicle car = (Vehicle) obj;
                    if (!car.getIsOnRoute()) continue;
                    long id = car.getId();
                    String stop = boardingStation(car);
                    String last = previous.put(id, stop);
                    if (stop.isEmpty() || stop.equals(last)) continue;
                    JsonObject event = new JsonObject();
                    event.addProperty("vehicle", id);
                    event.addProperty("elapsed_ms", elapsed);
                    event.addProperty("station", stop);
                    stops.add(event);
                    int p = progress.getOrDefault(id, 0);
                    if (stop.equals("central")) p = p == 2 ? 3 : 1;
                    if (stop.equals("school") && p == 1) p = 2;
                    progress.put(id, p);
                    complete |= p == 3;
                }
            }
            JsonObject result = new JsonObject();
            result.add("doors_open", stops);
            result.addProperty("same_vehicle_round_trip", complete);
            Files.writeString(Path.of(args[2]), new Gson().toJson(result));
            if (!complete) throw new IllegalStateException("No central-school-central round trip with doors open");
        } finally {
            sim.stop();
        }
    }
}
