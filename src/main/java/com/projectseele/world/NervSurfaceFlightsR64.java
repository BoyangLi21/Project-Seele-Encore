package com.projectseele.world;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import com.projectseele.world.NervAirTransportManifestR52.*;
import com.projectseele.world.NervRouteDirectoryR52.Region;

/** New surface jobs fly between cruise columns. Older saves keep their exact
 * numbered legs and the physical shaft remains available for layer changes. */
final class NervSurfaceFlightsR64 {
    static final String CORRIDOR = "r64/surface/";
    static final String SUFFIX = "/direct_surface_r64";

    static void addItineraries(Map<String, Mission> missions, Map<String, Corridor> edges,
            Map<String, Node> nodes, Map<String, Receiver> receivers) {
        for (Mission trip : List.copyOf(missions.values())) {
            Receiver destination = receivers.get(trip.receiver());
            if (destination == null || trip.region() != Region.SURFACE || destination.region() != Region.SURFACE) continue;
            List<String> outbound = direct(trip.outbound(), edges, nodes);
            List<String> loaded = direct(trip.loaded(), edges, nodes);
            List<String> retreat = direct(trip.retreat(), edges, nodes);
            if (outbound.equals(trip.outbound()) && loaded.equals(trip.loaded()) && retreat.equals(trip.retreat())) continue;
            String id = trip.id() + SUFFIX;
            missions.put(id, new Mission(id, trip.intent(), trip.aircraft(), trip.variants(), trip.region(),
                    trip.pickupDomain(), trip.pickupNode(), trip.receiver(), outbound, loaded, retreat));
        }
    }

    private static boolean cruiseColumn(String id) {
        return id.endsWith("/main") || id.endsWith("/climb");
    }

    private static boolean surfaceHub(String id) {
        return id.equals("shaft_top") || id.equals("hakone_approach");
    }

    private static List<String> direct(List<String> original, Map<String, Corridor> edges, Map<String, Node> nodes) {
        var result = new ArrayList<String>();
        for (int i = 0; i < original.size(); i++) {
            Corridor first = edges.get(original.get(i));
            if (first == null || !cruiseColumn(first.from()) || !surfaceHub(first.to()) || !first.gates().isEmpty()) {
                result.add(original.get(i));
                continue;
            }
            Corridor last = first;
            int end = i;
            while (surfaceHub(last.to()) && nodes.get(last.to()).region() == Region.SURFACE && end + 1 < original.size()) {
                Corridor next = edges.get(original.get(end + 1));
                if (next == null || !last.to().equals(next.from()) || !next.gates().isEmpty()) break;
                last = next;
                end++;
            }
            if (end == i || !cruiseColumn(last.to()) || nodes.get(first.from()).region() != Region.SURFACE
                    || nodes.get(last.to()).region() != Region.SURFACE || first.from().equals(last.to())) {
                result.add(original.get(i));
                continue;
            }
            String from = first.from(), to = last.to();
            String id = CORRIDOR + from + "->" + to;
            if (!edges.containsKey(id)) {
                String reverse = CORRIDOR + to + "->" + from;
                var endpoints = new HashSet<>(nodes.get(from).spaces());
                endpoints.addAll(nodes.get(to).spaces());
                // Runtime claims each swept aircraft/payload envelope at its
                // real location, including player-selected pickup/drop columns.
                int ticks = NervAirTravelR53.cruiseTicks(nodes.get(from).frame(), nodes.get(to).frame());
                edges.put(id, new Corridor(id, from, to, ticks, reverse, endpoints, Set.of()));
                edges.put(reverse, new Corridor(reverse, to, from, ticks, id, endpoints, Set.of()));
            }
            result.add(id);
            i = end;
        }
        return result;
    }

    private NervSurfaceFlightsR64() {}
}
