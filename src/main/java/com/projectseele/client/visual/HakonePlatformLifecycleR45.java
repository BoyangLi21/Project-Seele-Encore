package com.projectseele.client.visual;

import com.google.gson.*;
import net.minecraft.client.Minecraft;
import net.minecraft.core.BlockPos;
import net.minecraft.world.phys.Vec3;
import java.util.*;
import java.util.function.Consumer;
import java.util.function.Predicate;

/** Exact native APG/vehicle doorway evidence. Never uses or switches an APG. */
public final class HakonePlatformLifecycleR45
{
    public record Selection(Object car, Object resource, RegionalTransitRidingChecks.NativeDoorway doorway,
                            int carIndex, JsonObject evidence) { }

    private static final JsonArray history = new JsonArray();
    private static final Set<String> closed = new LinkedHashSet<>(), opened = new LinkedHashSet<>();
    private static int selectedCarIndex;
    private static long observedTick = Long.MIN_VALUE;

    public static void beginCase(JsonObject current)
    {
        while (history.size() > 0) history.remove(0);
        closed.clear(); opened.clear(); selectedCarIndex = -1; observedTick = Long.MIN_VALUE;
    }

    private static Object call(Object object, String method) throws Exception
    { return object.getClass().getMethod(method).invoke(object); }

    private static double axis(Object object, String name) throws Exception
    { return object.getClass().getField(name).getDouble(object); }

    private static BlockPos pos(JsonElement value)
    {
        var a = value.getAsJsonArray();
        return new BlockPos(a.get(0).getAsInt(), a.get(1).getAsInt(), a.get(2).getAsInt());
    }

    private static Vec3 vec(JsonArray a)
    { return new Vec3(a.get(0).getAsDouble(), a.get(1).getAsDouble(), a.get(2).getAsDouble()); }

    private static List<BlockPos> leaves(JsonObject current)
    {
        var result = new ArrayList<BlockPos>();
        var contract = current.getAsJsonObject("r45_apg");
        for (String field : List.of("leaves", "upper_leaves"))
            for (var q : contract.getAsJsonArray(field)) result.add(pos(q));
        return result;
    }

    public static void observe(Minecraft mc, JsonObject current, JsonObject result, int stage) throws Exception
    {
        if (mc.level == null || mc.player == null || observedTick == mc.level.getGameTime()) return;
        observedTick = mc.level.getGameTime();
        var item = new JsonObject(); item.addProperty("client_game_time", observedTick); item.addProperty("phase", stage);
        item.addProperty("actual_player_UUID", mc.player.getUUID().toString());
        item.addProperty("actual_player_position", mc.player.position().toString());
        item.addProperty("APG_use_or_switch_called", false);
        item.addProperty("server_shape_cannot_certify_closed_leaf", true);
        var cells = new JsonArray();
        for (var q : leaves(current))
        {
            var row = new JsonObject(); row.addProperty("position", q.toShortString());
            boolean cached = mc.level.getChunkSource().hasChunk(q.getX() >> 4, q.getZ() >> 4);
            row.addProperty("actual_client_chunk_cached", cached);
            if (cached)
            {
                var state = mc.level.getBlockState(q); var entity = mc.level.getBlockEntity(q);
                row.addProperty("actual_state", state.toString());
                row.addProperty("actual_BE_type", entity == null ? "MISSING" : entity.getType().toString());
                if (entity != null)
                {
                    double value = ((Number) call(entity, "getDoorValue")).doubleValue();
                    row.addProperty("actual_client_APG_door_value", value);
                    var boxes = state.getCollisionShape(mc.level, q).toAabbs();
                    row.add("actual_client_collision_boxes", new Gson().toJsonTree(boxes.stream().map(b ->
                        new double[] { b.minX, b.minY, b.minZ, b.maxX, b.maxY, b.maxZ }).toList()));
                    // Locked MTR 4.0.5 returns closed collision only at exactly
                    // zero, on the client. A server EMPTY shape proves neither.
                    if (value == 0 && !boxes.isEmpty()) closed.add(q.toShortString());
                    if (value > .8 && boxes.isEmpty()) opened.add(q.toShortString());
                }
            }
            cells.add(row);
        }
        item.add("all_actual_native_APG_halves", cells); history.add(item);
        if (history.size() > 120) history.remove(0);
        result.add("r45_APG_last120_native_client_observations", history.deepCopy());
        result.add("r45_APG_closed_collision_observed_halves", new Gson().toJsonTree(closed));
        result.add("r45_APG_open_collision_observed_halves", new Gson().toJsonTree(opened));
    }

    public static Selection select(Minecraft mc, Object vehicle, JsonObject current) throws Exception
    {
        var contract = current.getAsJsonObject("r45_apg");
        var lower = contract.getAsJsonArray("leaves");
        if (lower.size() != 2) throw new IllegalStateException("Exact APG needs both original lower leaves");
        for (var q : leaves(current))
        {
            if (!mc.level.getChunkSource().hasChunk(q.getX() >> 4, q.getZ() >> 4)) return null;
            var entity = mc.level.getBlockEntity(q);
            if (entity == null || ((Number) call(entity, "getDoorValue")).doubleValue() <= .8) return null;
            if (!mc.level.getBlockState(q).getCollisionShape(mc.level, q).isEmpty()) return null;
        }
        Object extra = vehicle.getClass().getField("vehicleExtraData").get(vehicle);
        var cars = (List<?>) extra.getClass().getField("immutableVehicleCars").get(extra);
        Vec3 preferred = vec(contract.getAsJsonArray("public_approach"));
        int minX = Math.min(pos(lower.get(0)).getX(), pos(lower.get(1)).getX());
        int z = pos(lower.get(0)).getZ(); boolean publicNorth = contract.get("facing").getAsString().equals("south");
        Selection best = null; double distance = Double.POSITIVE_INFINITY;
        for (int ordinal = 0; ordinal < cars.size(); ordinal++)
        {
            Object car = cars.get(ordinal), resource = resource(vehicle, car, ordinal, cars.size());
            if (resource == null) continue;
            var doorway = measured(vehicle, resource, car, ordinal, preferred, p ->
                p.x >= minX-.05 && p.x <= minX+2.05 && Math.abs(p.y-preferred.y) < .15
                    && (publicNorth ? p.z < z+.5 : p.z > z+.5) && supported(mc, p));
            if (doorway == null || doorway.door().x < minX-.05 || doorway.door().x > minX+2.05) continue;
            double candidateDistance = doorway.door().distanceToSqr(preferred);
            if (candidateDistance >= distance) continue;
            var evidence = new JsonObject(); evidence.addProperty("actual_car_ordinal", ordinal);
            evidence.addProperty("native_car_count", cars.size()); evidence.addProperty("native_resource_id", (String) call(car, "getVehicleId"));
            evidence.addProperty("actual_native_door", doorway.door().toString());
            evidence.addProperty("actual_supported_approach", doorway.approach().toString());
            evidence.addProperty("actual_inside", doorway.inside().toString());
            evidence.add("both_bound_original_lower_leaves", lower.deepCopy());
            evidence.addProperty("same_first_car_reused_for_all_ports", false);
            best = new Selection(car, resource, doorway, ordinal, evidence); distance = candidateDistance;
        }
        if (best != null) selectedCarIndex = best.carIndex;
        return best;
    }

    private static Object resource(Object vehicle, Object car, int ordinal, int count) throws Exception
    {
        Class<?> mode = Class.forName("org.mtr.core.data.TransportMode"); Object train = mode.getField("TRAIN").get(null);
        Object[] holder = { null };
        Consumer<Object> consumer = pair ->
        {
            try { holder[0] = pair.getClass().getMethod("left").invoke(pair); }
            catch (Exception error) { throw new IllegalStateException(error); }
        };
        Class.forName("org.mtr.mod.client.CustomResourceLoader").getMethod("getVehicleById", mode, String.class, Consumer.class)
            .invoke(null, train, (String) call(car, "getVehicleId"), consumer);
        return holder[0] == null ? null : holder[0].getClass().getMethod("getCachedVehicleResource", int.class, int.class, boolean.class)
            .invoke(holder[0], ordinal, count, true);
    }

    private static Object body(Object vehicle, Object car, int ordinal) throws Exception
    {
        Class<?> vector = Class.forName("org.mtr.core.tool.Vector"), frame = Class.forName("org.mtr.mod.render.PositionAndRotation");
        Class<?> arrayList = Class.forName("org.mtr.libraries.it.unimi.dsi.fastutil.objects.ObjectArrayList");
        var positions = (List<?>) call(vehicle, "getVehicleCarsAndPositions");
        if (ordinal < 0 || ordinal >= positions.size()) throw new IllegalStateException("Native car/position index differs");
        var frames = new ArrayList<Object>();
        for (Object bogies : (Iterable<?>) call(positions.get(ordinal), "right"))
            frames.add(frame.getConstructor(vector, vector, boolean.class).newInstance(call(bogies, "left"), call(bogies, "right"), true));
        return frame.getConstructor(arrayList, Class.forName("org.mtr.core.data.VehicleCar"), boolean.class)
            .newInstance(arrayList.getConstructor(Collection.class).newInstance(frames), car, true);
    }

    private static RegionalTransitRidingChecks.NativeDoorway measured(Object vehicle, Object resource, Object car,
            int ordinal, Vec3 preferred, Predicate<Vec3> eligible) throws Exception
    {
        Object body = body(vehicle, car, ordinal), point = body.getClass().getField("position").get(body);
        double yaw = body.getClass().getField("yaw").getDouble(body), c = Math.cos(yaw), s = Math.sin(yaw), nearest = Double.POSITIVE_INFINITY;
        RegionalTransitRidingChecks.NativeDoorway chosen = null;
        for (Object box : (Iterable<?>) resource.getClass().getField("doorways").get(resource))
        {
            double x = (((Number) call(box, "getMinXMapped")).doubleValue()+((Number) call(box, "getMaxXMapped")).doubleValue())/2;
            double z = (((Number) call(box, "getMinZMapped")).doubleValue()+((Number) call(box, "getMaxZMapped")).doubleValue())/2;
            double sign = Math.signum(x), innerX = x-sign*.4, floorY = Double.NEGATIVE_INFINITY;
            for (Object floor : (Iterable<?>) resource.getClass().getField("floors").get(resource))
                if (innerX >= ((Number) call(floor, "getMinXMapped")).doubleValue()-.05
                    && innerX <= ((Number) call(floor, "getMaxXMapped")).doubleValue()+.05
                    && z >= ((Number) call(floor, "getMinZMapped")).doubleValue()-.05
                    && z <= ((Number) call(floor, "getMaxZMapped")).doubleValue()+.05)
                    floorY = Math.max(floorY, ((Number) call(floor, "getMaxYMapped")).doubleValue());
            if (!Double.isFinite(floorY)) continue;
            Vec3 door = new Vec3(axis(point,"x")+x*c+z*s,axis(point,"y")+floorY,axis(point,"z")+z*c-x*s);
            Vec3 outward = new Vec3(sign*c,0,-sign*s), approach = door.add(outward.scale(1.2));
            if (!eligible.test(approach) || door.distanceToSqr(preferred) >= nearest) continue;
            nearest = door.distanceToSqr(preferred);
            chosen = new RegionalTransitRidingChecks.NativeDoorway(door, approach, door.subtract(outward.scale(1.1)),
                (float) Math.toDegrees(Math.atan2(outward.x,-outward.z)));
        }
        return chosen;
    }

    public static RegionalTransitRidingChecks.NativeDoorway destinationDoorway(Object vehicle, Object resource, Object car,
            Vec3 preferred, Predicate<Vec3> eligible) throws Exception
    { return measured(vehicle, resource, car, selectedCarIndex, preferred, eligible); }

    public static void requireCrossing(Minecraft mc, JsonObject current,
            RegionalTransitRidingChecks.NativeDoorway doorway, JsonObject result) throws Exception
    {
        for (var q : leaves(current))
        {
            var entity = mc.level.getBlockEntity(q);
            if (entity == null || ((Number) call(entity,"getDoorValue")).doubleValue() <= .8)
                throw new IllegalStateException("Bound APG is not natively open while boarding: "+q);
        }
        var row = new JsonObject(); row.addProperty("actual_player_UUID",mc.player.getUUID().toString());
        row.addProperty("actual_player_position",mc.player.position().toString());
        row.addProperty("actual_native_door",doorway.door().toString());
        row.addProperty("exact_paired_APG_native_open_at_real_attach",true);
        row.addProperty("manual_APG_use_called",false);result.add("r45_exact_APG_real_boarding",row);
    }

    public static void completeCase(JsonObject result)
    {
        result.add("r45_APG_closed_collision_observed_halves",new Gson().toJsonTree(closed));
        result.add("r45_APG_open_collision_observed_halves",new Gson().toJsonTree(opened));
        if (closed.size() != 4 || opened.size() != 4)
            throw new IllegalStateException("Exact paired APG cycle lacks all four native client closed/open halves: "+closed.size()+"/"+opened.size());
        result.addProperty("r45_complete_bound_APG_client_cycle",true);
    }

    private static boolean supported(Minecraft mc, Vec3 point)
    {
        if (!mc.level.noCollision(mc.player,mc.player.getBoundingBox().move(point.subtract(mc.player.position())).deflate(.025))) return false;
        for (double dx : new double[] {-.25,0,.25}) for (double dz : new double[] {-.25,0,.25})
        {
            Vec3 start = point.add(dx,.08,dz);
            var hit = mc.level.clip(new net.minecraft.world.level.ClipContext(start,start.add(0,-.30,0),
                net.minecraft.world.level.ClipContext.Block.COLLIDER,net.minecraft.world.level.ClipContext.Fluid.NONE,mc.player));
            if (hit.getType() != net.minecraft.world.phys.HitResult.Type.BLOCK || Math.abs(hit.getLocation().y-point.y) >= .15) return false;
        }
        return true;
    }

    private HakonePlatformLifecycleR45() { }
}
