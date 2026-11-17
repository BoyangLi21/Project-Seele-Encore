package com.projectseele.util;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.WeakHashMap;

/** Run with AllChecks: state kept per entity follows the object, not the network id. */
public final class WeakIdentityMapTest
{
    /** Compares the way Minecraft's Entity does: by network id. */
    private static final class Tracked
    {
        final int id;
        Tracked(int id) { this.id = id; }
        @Override public boolean equals(Object other) { return other instanceof Tracked tracked && tracked.id == id; }
        @Override public int hashCode() { return id; }
    }

    private static int checks;
    private static void check(boolean value, String why)
    {
        checks++;
        if (!value) throw new AssertionError(why);
    }

    private static void collect()
    {
        for (int i = 0; i < 20; i++)
        {
            System.gc();
            byte[] pressure = new byte[1 << 20];
            if (pressure.length == 0) break;
        }
    }

    public static void main(String[] args)
    {
        var states = new WeakIdentityMap<Tracked, List<String>>();
        var first = new Tracked(50);
        List<String> samples = states.computeIfAbsent(first, ignored -> new ArrayList<>());
        samples.add("carrying, cradle out");
        check(states.computeIfAbsent(first, ignored -> new ArrayList<>()) == samples, "The same object keeps its state");

        // The aircraft flew out of range and came back: a new client object, the old one not yet collected.
        var returned = new Tracked(50);
        check(returned.equals(first) && returned != first, "The returning entity has the old id");
        check(states.get(returned) == null, "A returning entity must not find the samples from before the gap");
        List<String> after = states.computeIfAbsent(returned, ignored -> new ArrayList<>());
        check(after != samples && after.isEmpty(), "It starts with state of its own");
        check(states.get(first) == samples, "The object that left still has its own, until it is collected");

        // In singleplayer the server's copy and the client's copy of one entity are equal as well.
        check(states.remove(returned) == after && states.get(first) == samples, "Removing one object's state leaves its twin's");
        states.put(returned, after);

        // What the map keyed by the entity did instead: the first object stays the key.
        Map<Tracked, List<String>> byId = new WeakHashMap<>();
        var old = new Tracked(7);
        byId.put(old, new ArrayList<>(List.of("before the gap")));
        var next = new Tracked(7);
        check(byId.get(next) != null, "Keyed by the entity, the newcomer finds its predecessor's state");
        byId.put(next, new ArrayList<>(List.of("after the gap")));
        old = null;
        collect();
        check(byId.get(next) == null, "and loses its own state when the predecessor is collected");

        first = null;
        samples = null;
        collect();
        check(states.get(returned) == after, "Collecting the old object must not drop the new state");
        check(states.size() == 1, "The collected object's entry is gone");
        System.out.println("Weak identity map checks passed: " + checks);
    }
}
