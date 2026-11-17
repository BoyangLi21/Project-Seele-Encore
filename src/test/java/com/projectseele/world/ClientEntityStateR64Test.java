package com.projectseele.world;

import java.util.ArrayList;
import java.util.List;

/** State follows the entity object: a new object with an old network id starts afresh. */
public final class ClientEntityStateR64Test
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

    public static void main(String[] args)
    {
        var states = new ClientEntityStateR64<Tracked, List<String>>();
        var first = new Tracked(50);
        List<String> samples = states.of(first, ArrayList::new);
        samples.add("carrying, cradle out");
        check(states.of(first, ArrayList::new) == samples, "The same object keeps its state");

        // The aircraft flew out of range and came back: a new client object, the old one not yet collected.
        var returned = new Tracked(50);
        check(returned.equals(first) && returned != first, "The returning entity has the old id");
        List<String> after = states.of(returned, ArrayList::new);
        check(after != samples && after.isEmpty(), "A returning entity must not find the samples from before the gap");
        check(states.of(returned, ArrayList::new) == after, "The returning object keeps its own state from then on");
        check(states.size() == 1, "One entry per id");

        // The entry is keyed by the returning object now: it survives the old object.
        first = null;
        samples = null;
        for (int i = 0; i < 20; i++)
        {
            System.gc();
            byte[] pressure = new byte[1 << 20];
            if (pressure.length == 0) break;
        }
        check(states.of(returned, ArrayList::new) == after, "Collecting the old object must not drop the new state");

        var other = new Tracked(0);
        check(states.of(other, ArrayList::new) != after && states.size() == 2, "Another entity has its own state");
        System.out.println("Client entity state checks passed: " + checks);
    }
}
