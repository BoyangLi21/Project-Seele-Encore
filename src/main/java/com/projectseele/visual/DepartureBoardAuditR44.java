package com.projectseele.visual;

import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import com.projectseele.world.FacilitySchemaV2;
import com.projectseele.world.NativeStationDepartures;
import com.projectseele.world.StationDepartureBoardBlockEntity;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.TicketType;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.IdentityHashMap;
import java.util.ArrayDeque;

/** Opt-in read-only audit of actual board BEs and the running upstream predictor. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID)
public final class DepartureBoardAuditR44
{
    private static final boolean ENABLED = Boolean.getBoolean("projectseele.r44DepartureBoardAudit");
    private static final TicketType<Long> TICKET = TicketType.create("r44_departure_audit", Long::compareTo, 240);
    private static final DateTimeFormatter CLOCK = DateTimeFormatter.ofPattern("HH:mm").withZone(ZoneId.of("Asia/Shanghai"));
    private static final List<BlockPos> TICKETS = new ArrayList<>();
    private static final JsonArray RESULTS = new JsonArray();
    private static final Map<Long, Object> ROUTES = new HashMap<>();
    private static final JsonArray ROUTE_DATA = new JsonArray();
    private record Source(Object response, long capturedNanos) { }
    private static final Map<NativeStationDepartures.Snapshot, Source> SOURCES = new IdentityHashMap<>();
    private static final ArrayDeque<NativeStationDepartures.Snapshot> SOURCE_ORDER = new ArrayDeque<>();
    public static volatile boolean finished;
    private static ServerLevel level;
    private static JsonArray boards;
    private static Path output;
    private static int age, loadedAt, index;

    private static Object call(Object object, String method) throws ReflectiveOperationException
    { return object.getClass().getMethod(method).invoke(object); }
    private static long number(Object object, String method) throws ReflectiveOperationException
    { return ((Number)call(object, method)).longValue(); }
    private static String text(Object object, String method, int limit) throws ReflectiveOperationException
    {
        String value = String.valueOf(call(object, method)).split("\\|", 2)[0].trim();
        return value.length() <= limit ? value : value.substring(0, limit);
    }
    private static BlockPos position(JsonArray values)
    { return new BlockPos(values.get(0).getAsInt(), values.get(1).getAsInt(), values.get(2).getAsInt()); }
    private static JsonArray strings(List<String> values)
    { var result = new JsonArray(); values.forEach(result::add); return result; }
    private static JsonArray longs(List<Long> values)
    { var result = new JsonArray(); values.forEach(result::add); return result; }

    /** Called only for a newly produced real snapshot with this opt-in review flag. */
    public static synchronized void captureSource(NativeStationDepartures.Snapshot snapshot, Object response)
    {
        if (!ENABLED || finished) return;
        SOURCES.put(snapshot, new Source(response, System.nanoTime())); SOURCE_ORDER.addLast(snapshot);
        while (SOURCE_ORDER.size() > 256) SOURCES.remove(SOURCE_ORDER.removeFirst());
    }
    private static synchronized Source source(NativeStationDepartures.Snapshot snapshot)
    { return SOURCES.get(snapshot); }
    private static synchronized NativeStationDepartures.Snapshot boardEpoch(StationDepartureBoardBlockEntity board)
    {
        for (var snapshot : SOURCES.keySet())
            if (snapshot.platformId() == board.linkedPlatformId() && snapshot.clock() == board.nativeClock()
                    && snapshot.departures().equals(board.departureTimes()) && snapshot.rows().equals(board.rows())) return snapshot;
        return null;
    }
    private static List<String> reconstruct(NativeStationDepartures.Snapshot snapshot, Object response, boolean airport) throws ReflectiveOperationException
    {
        var rows = new ArrayList<String>();
        for (Object arrival : (Iterable<?>)call(response, "getArrivals"))
        {
            if (Boolean.TRUE.equals(call(arrival, "getIsTerminating"))) continue;
            var names = new LinkedHashSet<String>(); Object route = ROUTES.get(number(arrival, "getRouteId"));
            if (route != null)
            {
                var stops = new ArrayList<Object>(); for (Object stop : (Iterable<?>)call(route, "getRoutePlatforms")) stops.add(call(stop, "getPlatform"));
                for (int i = 0; i + 1 < stops.size(); i++)
                    if (stops.get(i) != null && stops.get(i + 1) != null && number(stops.get(i), "getId") == snapshot.platformId()
                            && number(stops.get(i + 1), "getId") != snapshot.platformId()) names.add(text(stops.get(i + 1), "getStationName", 15));
            }
            long departure = number(arrival, "getDeparture"), seconds = Math.max(0, (departure - snapshot.clock()) / 1000);
            String line = text(arrival, "getRouteNumber", 7); if (line.isBlank()) line = text(arrival, "getRouteName", 10);
            String label = names.size() == 1 ? "下一站 " + names.iterator().next() : "终点 " + text(arrival, "getDestination", 15);
            String eta = seconds <= 30 ? airport ? "即将起飞" : "即将进站" : "约" + ((seconds + 59) / 60) + "分钟";
            rows.add(CLOCK.format(Instant.ofEpochMilli(departure)) + "  " + line + "  " + label + "  " + eta);
            if (rows.size() == 2) break;
        }
        if (rows.isEmpty()) rows.add("当前暂无待发班次"); return rows;
    }

    private static void readRoutes(Object simulator) throws ReflectiveOperationException
    {
        for (Object route : (Iterable<?>)simulator.getClass().getField("routes").get(simulator))
        {
            long id = number(route, "getId"); ROUTES.put(id, route);
            var record = new JsonObject(); record.addProperty("route_id", id);
            var sequence = new JsonArray(); Long first = null, last = null;
            int stopIndex = 0;
            for (Object stop : (Iterable<?>)call(route, "getRoutePlatforms"))
            {
                var row = new JsonObject(); row.addProperty("index", stopIndex++);
                Object platform = call(stop, "getPlatform");
                row.addProperty("resolved", platform != null);
                if (platform != null)
                {
                    long pid = number(platform, "getId");
                    row.addProperty("platform_id", pid); row.addProperty("station_name", String.valueOf(call(platform, "getStationName")));
                    if (first == null) first = pid; last = pid;
                }
                sequence.add(row);
            }
            record.add("whole_platform_sequence", sequence);
            record.addProperty("out_and_back", first != null && first.equals(last) && sequence.size() > 1);
            ROUTE_DATA.add(record);
        }
    }

    private static JsonObject audit(JsonObject declared, Object simulator) throws Exception
    {
        var row = new JsonObject(); row.addProperty("id", declared.get("id").getAsString());
        row.add("position", declared.get("position")); var errors = new JsonArray();
        BlockPos at = position(declared.getAsJsonArray("position"));
        if (!(level.getBlockEntity(at) instanceof StationDepartureBoardBlockEntity board))
        { row.addProperty("status", "MISSING_ACTUAL_BOARD_BE"); return row; }
        row.addProperty("actual_block_state", level.getBlockState(at).toString());
        var tag = board.saveWithoutMetadata(); row.addProperty("actual_be_nbt", tag.toString());
        row.addProperty("actual_title", board.title());
        var config = declared.getAsJsonObject("configuration");
        for (String key : new String[] {"Station", "Route"})
            if (!tag.getString(key).equals(config.get(key).getAsString())) errors.add("CONFIG_CHANGED:" + key);
        for (String key : new String[] {"PlatformCentre", "NativePlatformId"})
        {
            long actual = tag.contains(key) ? tag.getLong(key) : key.equals("NativePlatformId") ? -1 : 0;
            if (actual != config.get(key).getAsLong()) errors.add("CONFIG_CHANGED:" + key);
        }
        if (tag.getBoolean("Wayfinding") || board.routeMap()) errors.add("NOT_A_LIVE_DEPARTURE_BOARD");
        BlockPos centre = BlockPos.of(tag.getLong("PlatformCentre"));
        long preferred = tag.contains("NativePlatformId") ? tag.getLong("NativePlatformId") : -1;
        var nativeSnapshot = NativeStationDepartures.read(centre, preferred);
        row.addProperty("preferred_id", preferred); row.addProperty("helper_platform_id", nativeSnapshot.platformId());
        row.addProperty("helper_clock", nativeSnapshot.clock()); row.add("helper_rows", strings(nativeSnapshot.rows()));
        row.add("helper_departures", longs(nativeSnapshot.departures()));
        row.addProperty("actual_be_clock", board.nativeClock()); row.addProperty("actual_be_platform_id", board.linkedPlatformId());
        row.add("actual_be_rows", strings(board.rows())); row.add("actual_be_departures", longs(board.departureTimes()));
        Object selected = null; double minimum = 16; var tied = new LinkedHashSet<Long>();
        for (Object platform : (Iterable<?>)simulator.getClass().getField("platforms").get(simulator))
        {
            long pid = number(platform, "getId");
            if (preferred != -1) { if (pid == preferred) selected = platform; continue; }
            Object p = call(platform, "getMidPosition");
            double dx = number(p, "getX") - centre.getX(), dy = number(p, "getY") - centre.getY(), dz = number(p, "getZ") - centre.getZ();
            double distance = dx * dx + 4 * dy * dy + dz * dz;
            if (distance < minimum - 1e-9) { minimum = distance; selected = platform; tied.clear(); tied.add(pid); }
            else if (distance < 16 && Math.abs(distance - minimum) <= 1e-9) tied.add(pid);
        }
        var candidates = new JsonArray(); tied.forEach(candidates::add); row.add("nearest_equal_distance_ids", candidates);
        if (selected == null) { row.addProperty("status", "MISSING_NATIVE_PLATFORM"); row.add("errors", errors); return row; }
        long selectedId = number(selected, "getId");
        if (nativeSnapshot.platformId() != selectedId) errors.add("HELPER_PLATFORM_DIFFERS_FROM_ACTUAL_BINDING");
        boolean airport = String.valueOf(call(selected, "getTransportMode")).equals("AIRPLANE");
        if (airport != tag.getBoolean("AirService")) errors.add("AIR_SERVICE_TITLE_DIFFERS_FROM_NATIVE_MODE");
        Class<?> longsClass = Class.forName("org.mtr.libraries.it.unimi.dsi.fastutil.longs.LongImmutableList");
        Object ids = longsClass.getConstructor(long[].class).newInstance((Object)new long[] {selectedId});
        Class<?> requestClass = Class.forName("org.mtr.core.operation.ArrivalsRequest");
        Object request = requestClass.getConstructor(longsClass, int.class, int.class).newInstance(ids, 16, 16);
        Object laterResponse = requestClass.getMethod("getArrivals", simulator.getClass()).invoke(request, simulator);
        row.addProperty("later_independent_raw_clock", number(laterResponse, "getCurrentTime"));
        var laterTimes = new JsonArray();
        for (Object arrival : (Iterable<?>)call(laterResponse, "getArrivals")) laterTimes.add(number(arrival, "getDeparture"));
        row.add("later_independent_departures", laterTimes);
        Source captured = source(nativeSnapshot);
        if (captured == null) { row.addProperty("status", "MISSING_HELPER_SOURCE_CAPTURE"); row.add("errors", errors); return row; }
        Object response = captured.response();
        long now = number(response, "getCurrentTime");
        row.addProperty("raw_current_time", now); row.addProperty("clock_zone", "Asia/Shanghai");
        row.addProperty("raw_clock_shanghai", Instant.ofEpochMilli(now).atZone(ZoneId.of("Asia/Shanghai")).toString());
        row.addProperty("helper_clock_delta_ms", now - nativeSnapshot.clock());
        row.addProperty("source_object_identity_matched", true);
        row.addProperty("source_capture_age_ms", (System.nanoTime() - captured.capturedNanos()) / 1_000_000.0);
        var raw = new JsonArray(); var expectedTimes = new ArrayList<Long>(); var expectedRows = new ArrayList<String>();
        boolean ambiguous = false; int terminating = 0;
        for (Object arrival : (Iterable<?>)call(response, "getArrivals"))
        {
            var item = new JsonObject(); long routeId = number(arrival, "getRouteId"); long departure = number(arrival, "getDeparture");
            item.addProperty("route_id", routeId); item.addProperty("platform_id", number(arrival, "getPlatformId"));
            if (number(arrival, "getPlatformId") != selectedId) errors.add("RAW_PREDICTION_PLATFORM_MISMATCH");
            item.addProperty("arrival", number(arrival, "getArrival")); item.addProperty("departure", departure);
            item.addProperty("departure_index", number(arrival, "getDepartureIndex"));
            item.addProperty("deviation", number(arrival, "getDeviation")); item.addProperty("realtime", (Boolean)call(arrival, "getRealtime"));
            item.addProperty("route_number", String.valueOf(call(arrival, "getRouteNumber")));
            item.addProperty("route_name", String.valueOf(call(arrival, "getRouteName")));
            item.addProperty("trip_destination", String.valueOf(call(arrival, "getDestination")));
            boolean finalArrival = Boolean.TRUE.equals(call(arrival, "getIsTerminating")); item.addProperty("terminating", finalArrival);
            raw.add(item); if (finalArrival) { terminating++; continue; }
            if (expectedRows.size() >= 2) continue;
            var labels = new LinkedHashSet<String>(); var nextIds = new LinkedHashSet<Long>(); var nextData = new JsonArray();
            Object route = ROUTES.get(routeId);
            if (route == null) errors.add("UNRESOLVED_ROUTE:" + routeId);
            else
            {
                var stops = new ArrayList<Object>(); for (Object stop : (Iterable<?>)call(route, "getRoutePlatforms")) stops.add(call(stop, "getPlatform"));
                for (int i = 0; i + 1 < stops.size(); i++)
                {
                    Object current = stops.get(i), next = stops.get(i + 1);
                    if (current == null || next == null) { errors.add("UNRESOLVED_ROUTE_PLATFORM:" + routeId); continue; }
                    long nextId = number(next, "getId");
                    if (number(current, "getId") == selectedId && nextId != selectedId)
                    {
                        labels.add(text(next, "getStationName", 15)); nextIds.add(nextId);
                        var n = new JsonObject(); n.addProperty("current_route_index", i); n.addProperty("next_route_index", i + 1);
                        n.addProperty("next_platform_id", nextId); n.addProperty("next_station_name", String.valueOf(call(next, "getStationName"))); nextData.add(n);
                    }
                }
            }
            item.add("whole_route_next_candidates", nextData);
            if (nextIds.size() > 1) ambiguous = true;
            String line = text(arrival, "getRouteNumber", 7); if (line.isBlank()) line = text(arrival, "getRouteName", 10);
            String destination = labels.size() == 1 ? "下一站 " + labels.iterator().next() : "终点 " + text(arrival, "getDestination", 15);
            long seconds = Math.max(0, (departure - nativeSnapshot.clock()) / 1000);
            String eta = seconds <= 30 ? airport ? "即将起飞" : "即将进站" : "约" + ((seconds + 59) / 60) + "分钟";
            expectedTimes.add(departure); expectedRows.add(CLOCK.format(Instant.ofEpochMilli(departure)) + "  " + line + "  " + destination + "  " + eta);
        }
        row.add("raw_arrivals_16", raw); row.addProperty("terminating_predictions_filtered", terminating);
        if (expectedRows.isEmpty()) expectedRows.add("当前暂无待发班次");
        row.add("expected_rows_from_upstream", strings(expectedRows)); row.add("expected_departures_from_upstream", longs(expectedTimes));
        if (nativeSnapshot.clock() <= 0 || now <= 0) errors.add("NO_NATIVE_EPOCH_CLOCK");
        if (now != nativeSnapshot.clock()) errors.add("HELPER_SOURCE_CLOCK_DIFFERS");
        if (!nativeSnapshot.departures().equals(expectedTimes)) errors.add("HELPER_DIFFERS_FROM_ITS_ACTUAL_SOURCE");
        if (!nativeSnapshot.rows().equals(expectedRows)) errors.add("FORMATTING_OR_ROUTE_LABEL_DIFFERS_FROM_UPSTREAM");
        var actualEpoch = boardEpoch(board); Source actualSource = actualEpoch == null ? null : source(actualEpoch);
        boolean olderEpoch = actualEpoch != null && actualEpoch.clock() != nativeSnapshot.clock();
        row.addProperty("be_ticker_relation", actualSource == null ? "NO_CAPTURED_BE_SOURCE" : olderEpoch ? "OLDER_NORMAL_TICKER_EPOCH" : "SAME_PRODUCTION_EPOCH");
        row.addProperty("be_vs_helper_clock_lag_ms", nativeSnapshot.clock() - board.nativeClock());
        if (actualSource == null || board.linkedPlatformId() != selectedId) errors.add("ACTUAL_BE_SOURCE_NOT_VERIFIED");
        else
        {
            row.addProperty("be_source_clock", number(actualSource.response(), "getCurrentTime"));
            var beExpected = reconstruct(actualEpoch, actualSource.response(), airport);
            row.add("be_expected_rows_at_its_actual_epoch", strings(beExpected));
            var beExpectedTimes = new ArrayList<Long>();
            for (Object arrival : (Iterable<?>)call(actualSource.response(), "getArrivals"))
            {
                if (Boolean.TRUE.equals(call(arrival, "getIsTerminating"))) continue;
                beExpectedTimes.add(number(arrival, "getDeparture")); if (beExpectedTimes.size() == 2) break;
            }
            row.add("be_expected_departures_at_its_actual_epoch", longs(beExpectedTimes));
            if (board.nativeClock() != number(actualSource.response(), "getCurrentTime") || !beExpectedTimes.equals(board.departureTimes())) errors.add("BE_CLOCK_OR_TIMES_DIVERGE_FROM_ITS_ACTUAL_SOURCE");
            if (!beExpected.equals(board.rows())) errors.add("BE_ROWS_DIVERGE_FROM_ITS_ACTUAL_SOURCE");
        }
        row.add("errors", errors);
        row.addProperty("status", errors.size() > 0 ? "DIVERGED_OR_UNVERIFIED" : tied.size() > 1 ? "AMBIGUOUS_PLATFORM_BINDING" : ambiguous ? "AMBIGUOUS_ROUTE_OCCURRENCE" : expectedTimes.isEmpty() ? "EMPTY_NATIVE_SERVICE" : olderEpoch ? "VERIFIED_SOURCE_WITH_TICKER_LAG" : "VERIFIED_LIVE_SERVICE");
        return row;
    }

    private static void release()
    {
        if (level != null) for (BlockPos pos : TICKETS) level.getChunkSource().removeRegionTicket(TICKET, new ChunkPos(pos), 2, pos.asLong());
        TICKETS.clear();
    }
    private static void finish(String failure) throws Exception
    {
        release(); var result = new JsonObject(); result.addProperty("completed", failure == null);
        if (failure != null) result.addProperty("failure", failure);
        result.add("boards", RESULTS); result.add("whole_native_routes", ROUTE_DATA);
        result.addProperty("all50_audited", RESULTS.size() == 50);
        result.addProperty("all50_live_service_verified", RESULTS.size() == 50 && java.util.stream.StreamSupport.stream(RESULTS.spliterator(), false).allMatch(q -> q.getAsJsonObject().get("status").getAsString().equals("VERIFIED_LIVE_SERVICE")));
        result.addProperty("all50_source_epochs_verified", RESULTS.size() == 50 && java.util.stream.StreamSupport.stream(RESULTS.spliterator(), false).allMatch(q -> java.util.Set.of("VERIFIED_LIVE_SERVICE", "VERIFIED_SOURCE_WITH_TICKER_LAG").contains(q.getAsJsonObject().get("status").getAsString())));
        result.addProperty("direct_world_entity_player_schedule_mutation", false);
        result.addProperty("runtime_load", "Own temporary tickets load declared existing FULL chunks; BEs refresh only through their normal scheduled ticker. Tickets always removed. No direct tickServer/setChanged/setBlock/teleport/schedule mutation.");
        result.addProperty("limits", "Primary reconstruction uses the exact response object captured at production Snapshot creation, with original final DTO clock/arrival fields. Later independent request is drift evidence only. BE is checked against its own captured source epoch; natural ticker lag is separate. Empty/ambiguous/unresolved services are not automatically passed.");
        Files.writeString(output, new GsonBuilder().setPrettyPrinting().create().toJson(result)); finished = true;
        synchronized (DepartureBoardAuditR44.class) { SOURCES.clear(); SOURCE_ORDER.clear(); }
    }

    @SubscribeEvent
    public static void tick(TickEvent.ServerTickEvent event)
    {
        if (!ENABLED || finished || event.phase != TickEvent.Phase.END) return;
        try
        {
            if (++age > 2400) throw new IllegalStateException("Native board audit timeout");
            var server = event.getServer(); var world = server.getWorldPath(LevelResource.ROOT).toAbsolutePath().normalize();
            if (!world.getFileName().toString().equals(com.projectseele.visual.NativeReviewWorldsR45.expectedName())) throw new IllegalStateException("Review world only");
            if (output == null)
            {
                output = Path.of(System.getProperty("projectseele.r44DepartureBoardOutput", "")).toAbsolutePath().normalize();
                if (output.startsWith(world) || Files.exists(output) || !Files.isDirectory(output.getParent())) throw new IllegalStateException("Fresh artifact report outside world required");
            }
            Object simulator = RegionalNativeTransitInspection.simulator(); if (simulator == null || age < 100) return;
            if (boards == null)
            {
                var manifest = JsonParser.parseString(Files.readString(Path.of(System.getProperty("projectseele.r44DepartureBoardManifest", "")))).getAsJsonObject();
                boards = manifest.getAsJsonArray("boards"); if (boards.size() != 50) throw new IllegalStateException("All fifty actual owners required");
                level = server.getLevel(FacilitySchemaV2.DIMENSION); if (level == null) return;
                for (var item : boards)
                {
                    var board = item.getAsJsonObject();
                    if (!board.get("chunk_full").getAsBoolean() || !board.get("actual_be_present").getAsBoolean()) throw new IllegalStateException("Manifest has missing/non-FULL owner; no speculative chunk generation");
                    BlockPos at = position(board.getAsJsonArray("position")); TICKETS.add(at);
                    level.getChunkSource().addRegionTicket(TICKET, new ChunkPos(at), 2, at.asLong()); level.getChunkAt(at);
                }
                readRoutes(simulator); loadedAt = age; return;
            }
            if (age - loadedAt < 120) return;
            var item = boards.get(index++).getAsJsonObject();
            try { RESULTS.add(audit(item, simulator)); }
            catch (Exception error)
            {
                var row = new JsonObject(); row.addProperty("id", item.get("id").getAsString()); row.addProperty("status", "AUDIT_ERROR"); row.addProperty("error", error.toString()); RESULTS.add(row);
            }
            if (index == boards.size()) finish(null);
        }
        catch (Exception failure)
        {
            ProjectSeele.LOGGER.error("R44 departure audit failed", failure);
            try { if (output != null) finish(failure.toString()); else { release(); finished = true; } }
            catch (Exception reportFailure) { release(); finished = true; ProjectSeele.LOGGER.error("R44 audit report unavailable", reportFailure); }
        }
    }

    private DepartureBoardAuditR44() { }
}
