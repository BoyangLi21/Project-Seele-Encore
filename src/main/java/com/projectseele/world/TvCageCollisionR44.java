package com.projectseele.world;

import com.google.gson.JsonArray;
import com.google.gson.JsonParser;
import com.google.gson.JsonObject;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.EvaDorsalMechanism;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.NervCarrierPlatformEntity;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.decoration.ArmorStand;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.minecraft.world.phys.shapes.Shapes;
import net.minecraft.world.phys.shapes.VoxelShape;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Arrays;
import java.util.concurrent.ConcurrentHashMap;

/** The review cage's physical support and swept-volume stop share its mesh clock. */
public final class TvCageCollisionR44
{
    private record Component(String part, int variant, String motion, Vec3 normal,
                             double outboard, Vec3 translation, float from, float to,
                             List<AABB> boxes, AABB bounds) { }
    private record MotionSweep(Component part, Vec3 first, Vec3 last, AABB bounds) { }
    private static final double[] BAY_X = {-11.5, 30.5, 72.5};
    private static final boolean METRICS = Boolean.getBoolean("projectseele.r44TvCageCollisionMetrics")
            || Boolean.getBoolean("projectseele.r44TvCagePhysicalReview");
    private static final Map<String, QueryStats> QUERY_STATS = new ConcurrentHashMap<>();
    private static final class QueryStats
    {
        long calls, nanos, maxNanos, candidateBoxes, returnedShapes, skippedParts, missingGantries;
        final long[] latestNanos = new long[4096];
        synchronized void record(long elapsed, int candidates, int shapes, int skipped, int missing)
        {
            latestNanos[(int)(calls % latestNanos.length)] = elapsed;
            calls++; nanos += elapsed; maxNanos = Math.max(maxNanos, elapsed);
            candidateBoxes += candidates; returnedShapes += shapes; skippedParts += skipped; missingGantries += missing;
        }
        synchronized JsonObject snapshot()
        {
            int size=(int)Math.min(calls,latestNanos.length);
            long[] sorted=Arrays.copyOf(latestNanos,size);Arrays.sort(sorted);
            var row=new JsonObject();row.addProperty("calls",calls);row.addProperty("average_us",calls==0?0:nanos/1000.0/calls);
            row.addProperty("max_us",maxNanos/1000.0);row.addProperty("recent_latency_samples",size);
            row.addProperty("recent_p95_us",size==0?0:sorted[Math.max(0,(int)Math.ceil(size*.95)-1)]/1000.0);
            row.addProperty("candidate_boxes_tested",candidateBoxes);row.addProperty("returned_shapes",returnedShapes);
            row.addProperty("component_bounds_rejections",skippedParts);row.addProperty("missing_actual_gantry_queries",missingGantries);
            return row;
        }
    }

    public static JsonObject actualQueryMetricsR44()
    {
        var report=new JsonObject();report.addProperty("enabled",METRICS);
        for(var row:QUERY_STATS.entrySet())report.add(row.getKey(),row.getValue().snapshot());
        report.addProperty("scope","Measured common provider elapsed time, including query work and first resource load when applicable; latest4096 exact latency samples. Body queries and snapshot exports are separate. Not total Entity.move or whole-game performance.");
        return report;
    }
    private static final List<Component> COMPONENTS = new ArrayList<>();
    private static boolean attempted;
    private static boolean available;

    public static boolean enabled()
    {
        return com.projectseele.config.PortableRuntimeOwnersR45.tvCage();
    }

    private static Vec3 point(JsonArray values)
    {
        if (values.size() != 3) throw new IllegalArgumentException("Three coordinates required");
        Vec3 value = new Vec3(values.get(0).getAsDouble(), values.get(1).getAsDouble(), values.get(2).getAsDouble());
        if (!Double.isFinite(value.x) || !Double.isFinite(value.y) || !Double.isFinite(value.z))
            throw new IllegalArgumentException("Non-finite cage collision coordinate");
        return value;
    }

    private static boolean load()
    {
        if (attempted) return available;
        attempted = true;
        try (var stream = TvCageCollisionR44.class.getResourceAsStream("/assets/projectseele/mesh/tv_shoulder_shells_r44.json"))
        {
            if (stream == null) throw new IllegalStateException("Cage mesh missing");
            try (var reader = new InputStreamReader(stream, StandardCharsets.UTF_8))
            {
                var root = JsonParser.parseReader(reader).getAsJsonObject();
                if (!root.get("frame").getAsString().equals("fixed_gantry_local_metres_world_axes"))
                    throw new IllegalArgumentException("Cage collision frame differs from visual frame");
                var shapes = new HashMap<String, List<AABB>>();
                for (var entry : root.getAsJsonObject("collision_parts").entrySet())
                {
                    var boxes = new ArrayList<AABB>();
                    for (var item : entry.getValue().getAsJsonArray())
                    {
                        var pair = item.getAsJsonArray();
                        Vec3 low = point(pair.get(0).getAsJsonArray()), high = point(pair.get(1).getAsJsonArray());
                        if (low.x >= high.x || low.y >= high.y || low.z >= high.z)
                            throw new IllegalArgumentException("Empty collision member");
                        boxes.add(new AABB(low, high));
                    }
                    shapes.put(entry.getKey(), List.copyOf(boxes));
                }
                int shoulders = 0, beamStages = 0;
                for (var item : root.getAsJsonArray("components"))
                {
                    var row = item.getAsJsonObject();
                    String part = row.get("part").getAsString(), motion = row.get("motion").getAsString();
                    if (part.startsWith("thin_side_rails")) continue;
                    if (!shapes.containsKey(part)) throw new IllegalArgumentException("Visible machinery lacks physical support: " + part);
                    Vec3 normal = Vec3.ZERO, translation = Vec3.ZERO;
                    double outboard = 0;
                    float from = 0, to = 1;
                    int variant = row.has("variant") ? row.get("variant").getAsInt() : -1;
                    switch (motion)
                    {
                        case "fixed" -> { }
                        case "translation_only_with_exact_facet_pad" ->
                        {
                            normal = point(row.getAsJsonArray("normal"));
                            outboard = row.get("outboard_m").getAsDouble();
                            if (variant < 0 || variant > 2 || Math.abs(normal.length() - 1) > .0001
                                    || Math.abs(Math.abs(outboard) - 5.35) > .0001
                                    || Math.abs(row.get("normal_lift_m").getAsDouble() - 2.1) > .0001)
                                throw new IllegalArgumentException("Shoulder collision release differs from the contact pad");
                            shoulders++;
                        }
                        case "telescoping_translation" ->
                        {
                            translation = point(row.getAsJsonArray("translation_open_local"));
                            var interval = row.getAsJsonArray("opening_interval");
                            from = interval.get(0).getAsFloat();
                            to = interval.get(1).getAsFloat();
                            if (from < 0 || to > 1 || from >= to) throw new IllegalArgumentException("Invalid sleeve release clock");
                            beamStages++;
                        }
                        default -> throw new IllegalArgumentException("Unknown cage collision motion");
                    }
                    var boxes=shapes.get(part);
                    if(boxes.isEmpty())throw new IllegalArgumentException("Visible physical part has no positive volume: "+part);
                    AABB bounds=boxes.get(0);
                    for(int i=1;i<boxes.size();i++)bounds=bounds.minmax(boxes.get(i));
                    COMPONENTS.add(new Component(part, variant, motion, normal, outboard, translation, from, to, boxes, bounds));
                }
                if (shoulders != 6 || beamStages != 10 || !shapes.containsKey("cage_frame_lower_r44"))
                    throw new IllegalArgumentException("Incomplete physical cage assembly");
                available = true;
            }
        }
        catch (Exception failure)
        {
            COMPONENTS.clear();
            ProjectSeele.LOGGER.error("R44 TV cage physical contract rejected; review motion will remain stopped", failure);
        }
        return available;
    }

    private static float ramp(float opening, float from, float to)
    {
        return EvaDorsalMechanism.smooth((opening - from) / (to - from));
    }

    private static Vec3 translation(Component part, float closed)
    {
        float opening = 1 - closed;
        return switch (part.motion)
        {
            case "translation_only_with_exact_facet_pad" -> part.normal.scale(2.1 * ramp(opening, 0, .25F))
                    .add(part.outboard * ramp(opening, .23F, .88F), 0, 0);
            case "telescoping_translation" -> part.translation.scale(ramp(opening, part.from, part.to));
            default -> Vec3.ZERO;
        };
    }

    /** Ordinary vanilla motion receives the same physical geometry on both logical sides. */
    public static List<VoxelShape> append(Level level, Entity actor, AABB query, List<VoxelShape> original)
    {
        if (!enabled() || !level.dimension().equals(FacilitySchemaV2.DIMENSION)
                || actor instanceof EvaUnit01Entity || actor instanceof NervCarrierPlatformEntity) return original;
        long began=METRICS?System.nanoTime():0;
        if(!load())return original;
        boolean relevant=false;int tested=0,returned=0,skipped=0,missing=0;
        List<VoxelShape> result = null;
        for (int variant = 0; variant < 3; variant++)
        {
            double x = BAY_X[variant];
            if (!query.intersects(new AABB(x - 20.5, -444, -268, x + 20.5, -355, -213))) continue;
            relevant=true;
            final int identity = variant;
            var gantries = level.getEntitiesOfClass(NervCarrierPlatformEntity.class,
                    new AABB(x - 1, -444, -240.5, x + 1, -440, -238.5),
                    e -> e.isAlive() && e.isRestraintGantry() && e.getUnitVariant() == identity);
            if (gantries.isEmpty()) { missing++; continue; }
            var gantry = gantries.get(0);
            for (var part : COMPONENTS)
            {
                if (part.variant >= 0 && part.variant != variant) continue;
                Vec3 move = gantry.position().add(translation(part, gantry.getRestraintProgress()));
                AABB localQuery=query.move(-move.x,-move.y,-move.z);
                if(!part.bounds.intersects(localQuery)) { skipped++; continue; }
                for (var local : part.boxes)
                {
                    tested++;
                    if (!local.intersects(localQuery)) continue;
                    if (result == null) result = new ArrayList<>(original);
                    result.add(Shapes.create(local.move(move)));returned++;
                }
            }
        }
        if(METRICS&&relevant)
            QUERY_STATS.computeIfAbsent((level.isClientSide?"client":"server")+(actor==null?"_snapshot":"_body"),unused->new QueryStats())
                    .record(System.nanoTime()-began,tested,returned,skipped,missing);
        return result == null ? original : List.copyOf(result);
    }

    /** No actor is pushed or damaged: occupied travel leaves the real clock stopped. */
    public static boolean canMove(ServerLevel level, EvaUnit01Entity owner,
                                  NervCarrierPlatformEntity gantry, float requested)
    {
        if (!enabled()) return true;
        if (!load()) return false;
        float before = gantry.getRestraintProgress();
        if (Math.abs(before - requested) < .0001) return true;
        var staffFault=TvPersonnelPlatformInterlockR44.movementFault(level,gantry.getUnitVariant());
        if (staffFault.isPresent())
        {
            gantry.getPersistentData().putString("TvPersonnelBlockedR44",staffFault.get());
            return false;
        }
        gantry.getPersistentData().remove("TvPersonnelBlockedR44");
        var sweeps = new ArrayList<MotionSweep>();
        AABB union = null;
        for (var part : COMPONENTS)
        {
            if (part.motion.equals("fixed") || part.variant >= 0 && part.variant != gantry.getUnitVariant()) continue;
            Vec3 first = gantry.position().add(translation(part, before));
            Vec3 last = gantry.position().add(translation(part, requested));
            // Each translation coordinate is monotonic over both release ramps.
            // Endpoint box union therefore contains the complete continuous path.
            AABB bounds=part.bounds.move(first).minmax(part.bounds.move(last)).inflate(.045);
            sweeps.add(new MotionSweep(part,first,last,bounds));
            union=union==null?bounds:union.minmax(bounds);
        }
        if (union == null) return true;
        var canonicalPlug = EntryPlugDirector.canonical(level, gantry.getUnitVariant());
        for (var actor : level.getEntities((Entity) null, union, e -> e.isAlive() && !e.isSpectator()
                && e != owner && e != canonicalPlug && !(e instanceof NervCarrierPlatformEntity)
                && e.getRootVehicle() != owner && !(e instanceof ArmorStand stand && stand.isMarker())))
        {
            boolean occupied=false;AABB body=actor.getBoundingBox();
            for(var sweep:sweeps)
            {
                if(!sweep.bounds.intersects(body))continue;
                for(var local:sweep.part.boxes)
                    if(local.move(sweep.first).minmax(local.move(sweep.last)).inflate(.045).intersects(body))
                    { occupied=true;break; }
                if(occupied)break;
            }
            if(!occupied)continue;
            gantry.getPersistentData().putString("TvCageBlockedR44", actor.getUUID().toString());
            if (actor instanceof Player player && level.getGameTime() % 40 == 0)
                player.displayClientMessage(net.minecraft.network.chat.Component.literal("拘束机构暂停：请离开机械运动范围。"), true);
            return false;
        }
        gantry.getPersistentData().remove("TvCageBlockedR44");
        return true;
    }

    private TvCageCollisionR44() { }
}
