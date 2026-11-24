package com.projectseele.world;

import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * R65: the transport shaft between the surface and the GeoFront, held open on an order from the phone.
 *
 * Its two gates open only for an aircraft's passage and close behind it. With the hold on they are driven open and
 * left open, and the idle closing stroke is not asked for. Taking the hold off hands both gates back to that stroke.
 * A gate a passage has leased is left to the passage either way.
 *
 * The gates stand far from the headquarters: their chunks are kept loaded only until each one has been seen resting
 * open, and for no longer than the allowance if a door cannot be found or cannot move.
 */
final class AirshaftHoldR65
{
    static final List<String> GATES = List.of("remote_airshaft_surface", "remote_airshaft_south");
    /** An opening stroke is 160 ticks; this leaves room for chunks to load and for a door waiting for its turn. */
    static final long ALLOWANCE_TICKS = 2400;

    enum Step
    {
        /** A passage owns the gate, or the gate is no part of the shaft and is not idle. */
        LEAVE,
        /** Drive towards open and keep the chunks loaded for it. */
        OPEN,
        /** Held and already seen open, or out of allowance: nothing to do and nothing to load. */
        REST,
        /** The idle closing stroke, as before R65. */
        CLOSE
    }

    private final Set<String> seenOpen = new HashSet<>();
    private final Map<String, Long> askedAt = new HashMap<>();

    static boolean shaftGate(String gate)
    {
        return GATES.contains(gate);
    }

    /**
     * What to do with one door of the transport plant on this tick.
     *
     * @param held   the hold is on
     * @param leased an active passage has this gate
     * @param free   nobody else holds the gate's resource
     */
    Step step(String gate, boolean held, boolean leased, boolean free, long gameTime)
    {
        if (leased)
        {
            // What the passage leaves behind is looked at again.
            seenOpen.remove(gate);
            askedAt.remove(gate);
            return Step.LEAVE;
        }
        if (!free) return Step.LEAVE;
        if (!held || !shaftGate(gate)) return Step.CLOSE;
        if (seenOpen.contains(gate)) return Step.REST;
        Long at = askedAt.putIfAbsent(gate, gameTime);
        if (at != null && (gameTime < at || gameTime - at > ALLOWANCE_TICKS)) return Step.REST;
        return Step.OPEN;
    }

    /** The gate reported resting open. */
    void opened(String gate)
    {
        seenOpen.add(gate);
        askedAt.remove(gate);
    }

    /** The order changed (either way): every gate is looked at afresh. */
    void ordered()
    {
        seenOpen.clear();
        askedAt.clear();
    }

    boolean seenOpen(String gate)
    {
        return seenOpen.contains(gate);
    }
}
