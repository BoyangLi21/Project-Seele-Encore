package com.projectseele.world;

import com.google.gson.JsonParser;
import com.projectseele.world.NervAirTransportManifestR52.*;
import com.projectseele.world.NervRouteDirectoryR52.Region;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;

public final class NervSurfaceFlightsR64Test {
    public static void main(String[] args) throws Exception {
        var nodes = new HashMap<String, Node>();
        var edges = new HashMap<String, Corridor>();
        var frame = new RigidTransform(Vec3.ZERO, 0, 0, 0, 1);
        var sample = new Frame(frame, frame, new Rig(24, 1, 0));
        String a = "airport/climb", b = "pickup/main", c = "port/main", hub = "shaft_top", pass = "hakone_approach";
        for (String id : List.of(a, b, c, hub, pass, "shaft_bottom"))
            nodes.put(id, new Node(id, id.equals("shaft_bottom") ? Region.GEOFRONT : Region.SURFACE, sample, Set.of("space/c0_0_0"), List.of()));
        List<String> out = chain(edges, a, hub, b), loaded = chain(edges, b, pass, hub, c), back = chain(edges, c, hub, a);
        var trip = new Mission("surface", Intent.RECOVER, "aircraft", Set.of(1), Region.SURFACE, new AABB(0,0,0,1,1,1), b, "dock", out, loaded, back);
        var below = new Mission("below", Intent.DELIVER, "aircraft", Set.of(1), Region.GEOFRONT, trip.pickupDomain(), "shaft_bottom", "dock",
                out, chain(edges, "shaft_bottom", hub, c), back);
        var missions = new HashMap<>(Map.of(trip.id(), trip, below.id(), below));
        var receiver = new Receiver("dock", Region.SURFACE, c, frame, Map.of(), false, List.of(), Set.of());
        NervSurfaceFlightsR64.addItineraries(missions, edges, nodes, Map.of("dock", receiver));
        var shorter = missions.get("surface" + NervSurfaceFlightsR64.SUFFIX);
        if (shorter == null || missions.size() != 3 || missions.get("surface") != trip)
            throw new AssertionError("Old save and cross-layer identities must survive");
        for (var route : List.of(shorter.outbound(), shorter.loaded(), shorter.retreat())) {
            if (route.size() != 1) throw new AssertionError("Detour remains");
            var leg = edges.get(route.get(0));
            var reverse = edges.get(leg.reverseOf());
            if (!reverse.to().equals(leg.from()) || !reverse.from().equals(leg.to()) || !leg.spaces().equals(reverse.spaces()))
                throw new AssertionError("Cancellation must follow the same physical path");
        }
        if (!edges.get(shorter.loaded().get(0)).to().equals(c)) throw new AssertionError("Receiver moved");
        if (args.length == 1) installed(Path.of(args[0]));
    }

    private static List<String> chain(Map<String, Corridor> edges, String... nodes) {
        var ids = new ArrayList<String>();
        for (int i = 1; i < nodes.length; i++) {
            String id = nodes[i-1] + "-" + nodes[i];
            edges.put(id, new Corridor(id, nodes[i-1], nodes[i], 40, "", Set.of("space/c0_0_0"),
                    nodes[i-1].equals("shaft_bottom") ? Set.of("shaftDoor") : Set.of()));
            ids.add(id);
        }
        return List.copyOf(ids);
    }

    private static void installed(Path world) throws Exception {
        var ground = NervRouteDirectoryR52.parse(JsonParser.parseString(Files.readString(world.resolve("ROOT_RUNTIME_DIRECTORY.json"))).getAsJsonObject());
        var air = NervAirTransportManifestR52.parse(JsonParser.parseString(Files.readString(world.resolve("ROOT_AIR_TRANSPORT.json"))).getAsJsonObject(), ground);
        int direct = 0;
        for (var m : air.missions().values()) if (m.id().endsWith(NervSurfaceFlightsR64.SUFFIX)) {
            direct++;
            if (m.region() != Region.SURFACE || air.receiver(m.receiver()).region() != Region.SURFACE)
                throw new AssertionError("Underground destination was rerouted");
            if (air.node(air.aircraft().get(m.aircraft()).stand()).region() != Region.SURFACE) continue;
            for (var route : List.of(m.outbound(), m.loaded(), m.retreat())) for (var id : route) {
                var e = air.corridor(id);
                if (e.to().equals("shaft_top") || e.to().equals("hakone_approach"))
                    throw new AssertionError("Surface-only itinerary retained a detour: " + m.id());
            }
        }
        String actual = "nerv_surface_0/pickup/city_well/v1__port/v1/b2";
        var legacy = Objects.requireNonNull(air.missions().get(actual));
        var current = Objects.requireNonNull(air.missions().get(actual + NervSurfaceFlightsR64.SUFFIX));
        System.out.println("Surface routes " + direct + ", recorded city recovery legs (out, loaded, retreat) "
                + List.of(legacy.outbound().size(), legacy.loaded().size(), legacy.retreat().size()) + " -> "
                + List.of(current.outbound().size(), current.loaded().size(), current.retreat().size()));
    }
}
