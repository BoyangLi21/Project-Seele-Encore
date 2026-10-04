package com.projectseele.visual;

import com.google.gson.*;
import com.projectseele.world.*;
import com.supermartijn642.movingelevators.elevator.ElevatorGroup;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;

/** Exact directed pairs from measured native interfaces; no inferred lift stops. */
public final class CandidateLiftTripCasesR45
{
    private static JsonObject job;
    private static JsonArray interfaces;
    private static String jobHash, interfacesHash;
    private static final Map<String, Map<Integer, JsonObject>> stops = new LinkedHashMap<>();
    private static final Set<String> pairIds = new LinkedHashSet<>();
    private CandidateLiftTripCasesR45() {}

    public static JsonObject load() throws Exception
    {
        if (job != null) return job;
        Path file = Path.of(System.getProperty("projectseele.r45LiftTripCases")).toRealPath();
        byte[] bytes = Files.readAllBytes(file);
        JsonObject proposed = JsonParser.parseString(new String(bytes, java.nio.charset.StandardCharsets.UTF_8)).getAsJsonObject();
        require("projectseele.candidate-lift-trip-cases-r45.v1".equals(proposed.get("schema").getAsString())
                && proposed.get("bound").getAsBoolean(), "An explicit fresh cold candidate lift binding is required");
        require(proposed.has("candidate_binding") && proposed.get("candidate_binding_sha256").getAsString().matches("[0-9a-f]{64}"),
                "Unbound or incomplete lift lease");
        require(proposed.get("cases_required").getAsInt() == 90 && proposed.getAsJsonArray("cases").size() == 90
                && proposed.get("groups_required").getAsInt() == 7 && proposed.get("stops_required").getAsInt() == 24,
                "Exact 90 directed pairs / 7 groups / 24 stops required");
        Path interfaceFile = Path.of(System.getProperty("projectseele.r44LiftInterfaces", "")).toRealPath();
        require(interfaceFile.equals(Path.of(proposed.get("interfaces_file").getAsString()).toRealPath()), "Another measured interface file was supplied");
        byte[] interfaceBytes = Files.readAllBytes(interfaceFile);
        interfacesHash = hash(interfaceBytes);
        require(interfacesHash.equals(proposed.get("interfaces_sha256").getAsString()), "Actual complete interface bytes changed");
        interfaces = JsonParser.parseString(new String(interfaceBytes, java.nio.charset.StandardCharsets.UTF_8)).getAsJsonArray();
        require(interfaces.size() == 7, "Measured native lift denominator must be seven");
        Map<String, JsonObject> measured = new LinkedHashMap<>();
        Set<String> measuredGroups = new HashSet<>();
        for (var rawLift : interfaces)
        {
            JsonObject lift = rawLift.getAsJsonObject();
            require(measuredGroups.add(lift.get("id").getAsString()), "Duplicate measured group");
            for (var raw : lift.getAsJsonArray("landings"))
            {
                JsonObject stop = raw.getAsJsonObject();
                require(measured.put(key(position(stop, "controller")), stop) == null, "Duplicate measured controller");
                require(stop.has("outside_call_path") && !stop.get("outside_call_path").isJsonNull()
                        && stop.getAsJsonArray("outside_call_path").size() > 0, "Unresolved actual exterior approach");
                position(stop, "cabin_centre"); position(stop, "handoff"); position(stop, "reader"); position(stop, "outside_call");
            }
        }
        require(measured.size() == 24, "Measured native stop denominator must be twenty-four");
        Map<String, String> aliases = new HashMap<>();
        Set<String> usedControllers = new HashSet<>();
        for (var raw : proposed.getAsJsonArray("cases"))
        {
            JsonObject row = raw.getAsJsonObject();
            String alias = row.get("runtime_alias").getAsString(), group = row.get("group").getAsString();
            require(!alias.isBlank() && measuredGroups.contains(group), "Unknown measured group/alias");
            String previous = aliases.putIfAbsent(alias, group);
            require(previous == null || previous.equals(group), "Runtime alias combines different physical groups");
            BlockPos from = position(row, "from_cabin"), to = position(row, "to_cabin");
            require(from.getY() != to.getY() && from.getX() == to.getX() && from.getZ() == to.getZ(), "Non-travel pair or different cabin columns");
            require(pairIds.add(alias + "/" + from.getY() + "/" + to.getY()), "Duplicate directed lift pair");
            for (boolean source : new boolean[] {true, false})
            {
                BlockPos control = position(row, source ? "from_controller" : "to_controller");
                JsonObject actual = measured.get(key(control));
                require(actual != null, "Pair controller missing from measured interfaces");
                BlockPos cabin = source ? from : to;
                require(cabin.equals(position(actual, "cabin_centre")), "Pair cabin differs from its measured full interface");
                require(group.equals(measuredGroup(control)), "Pair controller belongs to a different measured group");
                Map<Integer, JsonObject> floors = stops.computeIfAbsent(alias, unused -> new LinkedHashMap<>());
                JsonObject old = floors.putIfAbsent(cabin.getY(), actual);
                require(old == null || position(old, "controller").equals(control), "A floor alias identifies different native controllers");
                usedControllers.add(key(control));
            }
        }
        require(stops.size() == 7 && aliases.values().stream().distinct().count() == 7 && usedControllers.equals(measured.keySet()),
                "Group or stop identity coverage incomplete");
        int requiredPairs = 0;
        for (var group : stops.entrySet())
            for (int from : group.getValue().keySet()) for (int to : group.getValue().keySet()) if (from != to)
            {
                requiredPairs++;
                require(pairIds.contains(group.getKey() + "/" + from + "/" + to), "A native directed menu pair is omitted");
            }
        require(requiredPairs == 90, "Actual complete directed-pair denominator differs from ninety");
        jobHash = hash(bytes); job = proposed; return job;
    }

    private static String measuredGroup(BlockPos control)
    {
        for (var rawLift : interfaces) for (var raw : rawLift.getAsJsonObject().getAsJsonArray("landings"))
            if (position(raw.getAsJsonObject(), "controller").equals(control)) return rawLift.getAsJsonObject().get("id").getAsString();
        throw new IllegalStateException("Measured group missing");
    }

    public static void verifyNative(ServerLevel level, S20PhysicalElevatorDirector.LiftSpec spec, ElevatorGroup group, int index)
    {
        JsonObject pair = job.getAsJsonArray("cases").get(index).getAsJsonObject();
        require(spec.id().equals(pair.get("runtime_alias").getAsString()), "Selected runtime lift alias differs");
        Map<Integer, JsonObject> expected = stops.get(spec.id());
        Set<Integer> actualFloors = new HashSet<>();
        for (var stop : spec.stops())
        {
            require(actualFloors.add(stop.walkY()), "Duplicate runtime lift floor");
            JsonObject measured = expected.get(stop.walkY());
            require(measured != null && stop.cabinCentre().equals(position(measured, "cabin_centre"))
                    && S20MovingElevatorsAdapter.controllerPosition(spec, stop).equals(position(measured, "controller")),
                    "Runtime native cabin/controller differs from the frozen measured interface");
        }
        require(actualFloors.equals(expected.keySet()), "Runtime stop list differs from actual complete measured floors");
        Set<Integer> nativeFloors = new HashSet<>();
        for (int n = 0; n < group.getFloorCount(); n++) require(nativeFloors.add(group.getFloorYLevel(n)), "Duplicate native registered floor");
        require(nativeFloors.equals(expected.keySet()), "Native registered menu differs from measured complete floors");
    }

    public static JsonObject evidence(int index)
    {
        JsonObject result = job.getAsJsonArray("cases").get(index).getAsJsonObject().deepCopy();
        result.addProperty("case_index", index); result.addProperty("job_sha256", jobHash);
        result.addProperty("interfaces_sha256", interfacesHash); result.addProperty("candidate_binding_sha256", job.get("candidate_binding_sha256").getAsString());
        result.addProperty("declared_session_phase", System.getProperty("projectseele.r45LiftLifecyclePhase", "current_native_function"));
        return result;
    }

    private static BlockPos position(JsonObject row, String field)
    {
        JsonArray values = row.getAsJsonArray(field);
        require(values != null && values.size() == 3, "Exact position required: " + field);
        int[] coordinates = new int[3];
        for (int n = 0; n < 3; n++)
        {
            double value = values.get(n).getAsDouble();
            require(Double.isFinite(value) && value == Math.rint(value) && value >= Integer.MIN_VALUE && value <= Integer.MAX_VALUE,
                    "Non-integral measured block coordinate: " + field);
            coordinates[n] = (int)value;
        }
        return new BlockPos(coordinates[0], coordinates[1], coordinates[2]);
    }
    private static String key(BlockPos pos) { return pos.getX() + "/" + pos.getY() + "/" + pos.getZ(); }
    private static String hash(byte[] bytes) throws Exception { return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes)); }
    private static void require(boolean pass, String reason) { if (!pass) throw new IllegalStateException(reason); }
}
