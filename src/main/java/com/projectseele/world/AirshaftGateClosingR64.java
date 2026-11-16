package com.projectseele.world;

import java.util.HashMap;
import java.util.Map;

/**
 * Which shaft gates still owe their closing stroke.
 *
 * A passage leases a gate only while it flies through. The idle close that follows takes as long as the opening,
 * but the passage's chunk tickets lapse five seconds after the lease ends. With nobody near, part of the door plane
 * unloaded mid-stroke and the door stayed ajar until a player loaded all of it again.
 *
 * A gate noted here keeps its chunks loaded until it reports closed. The allowance bounds that, so a door that
 * cannot close does not hold its chunks for ever.
 */
final class AirshaftGateClosingR64
{
    /** A closing stroke is 160 ticks; this leaves room for a door that has to wait for its turn. */
    static final long ALLOWANCE_TICKS = 2400;

    private final Map<String, Long> notedAt = new HashMap<>();

    /** The gate is leased by a passage on this tick, or may have been left ajar by an earlier session. */
    void noted(String gate, long gameTime)
    {
        notedAt.put(gate, gameTime);
    }

    /** Whether the gate's chunks are to be kept loaded on this tick. */
    boolean keepLoaded(String gate, long gameTime)
    {
        Long at = notedAt.get(gate);
        if (at == null) return false;
        if (gameTime < at || gameTime - at > ALLOWANCE_TICKS)
        {
            notedAt.remove(gate);
            return false;
        }
        return true;
    }

    void closed(String gate)
    {
        notedAt.remove(gate);
    }

    int pending()
    {
        return notedAt.size();
    }
}
