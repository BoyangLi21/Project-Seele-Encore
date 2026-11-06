import java.nio.file.*;
import org.mtr.core.data.*;
import org.mtr.core.tool.Angle;
import org.mtr.libraries.com.google.gson.*;
import org.mtr.libraries.it.unimi.dsi.fastutil.objects.ObjectArrayList;

/** Dense, endpoint-inclusive samples from the installed MTR native rail geometry. */
public final class NativeBoatRouteSamples {
    private static Position pos(JsonArray a) {
        return new Position(a.get(0).getAsLong(), a.get(1).getAsLong(), a.get(2).getAsLong());
    }
    public static void main(String[] args) throws Exception {
        JsonObject plan = JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject();
        double spacing = Double.parseDouble(args[2]);
        if (spacing <= 0 || spacing > 0.25) throw new IllegalArgumentException("Use spacing in (0, 0.25]");
        JsonArray result = new JsonArray();
        for (JsonElement item : plan.getAsJsonArray("rails")) {
            JsonObject r = item.getAsJsonObject();
            Position a = pos(r.getAsJsonArray("from")), b = pos(r.getAsJsonArray("to"));
            Angle aa = Angle.valueOf(r.get("from_angle").getAsString());
            Angle ab = Angle.valueOf(r.get("to_angle").getAsString());
            Rail rail = Rail.newRail(a, aa, b, ab, Rail.Shape.QUADRATIC, 100,
                    new ObjectArrayList<String>(), 24, 24, false, false, true, false, true, TransportMode.BOAT);
            if (!rail.isValid()) throw new IllegalArgumentException("Invalid rail " + r.get("id"));
            double length = rail.railMath.getLength();
            var first = rail.railMath.getPosition(0, false);
            boolean reverse = Math.hypot(first.x - a.getX() - 0.5, first.z - a.getZ() - 0.5) > 0.01;
            int steps = (int)Math.ceil(length / spacing);
            JsonArray points = new JsonArray();
            for (int i = 0; i <= steps; i++) {
                double d = length * i / steps;
                var p = rail.railMath.getPosition(d, reverse);
                JsonArray xyz = new JsonArray(); xyz.add(p.x); xyz.add(p.y); xyz.add(p.z); points.add(xyz);
            }
            JsonObject row = new JsonObject();
            row.add("id", r.get("id")); row.add("kind", r.get("kind"));
            row.addProperty("length", length); row.addProperty("spacing", length / steps);
            row.add("points", points); result.add(row);
        }
        Files.writeString(Path.of(args[1]), new Gson().toJson(result));
        System.out.println("Sampled " + result.size() + " native rails including both endpoints");
    }
}
