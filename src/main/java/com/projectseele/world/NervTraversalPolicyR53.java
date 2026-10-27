package com.projectseele.world;

import java.util.Map;
import java.util.WeakHashMap;
import net.minecraft.server.level.ServerLevel;

/** Operator-selected diagnostics, scoped to one running dimension. */
public final class NervTraversalPolicyR53
{
    public enum Mode { NORMAL, STRICT, BYPASS }
    private static final Map<ServerLevel, Mode> MODES = new WeakHashMap<>();

    private NervTraversalPolicyR53() {}

    public static synchronized Mode mode(ServerLevel level)
    {
        return MODES.getOrDefault(level, Mode.NORMAL);
    }

    public static synchronized void setMode(ServerLevel level, Mode mode)
    {
        if (mode == Mode.NORMAL) MODES.remove(level);
        else MODES.put(java.util.Objects.requireNonNull(level), java.util.Objects.requireNonNull(mode));
    }

    public static boolean strict(ServerLevel level) { return mode(level) == Mode.STRICT; }
    public static boolean bypass(ServerLevel level) { return mode(level) == Mode.BYPASS; }
}
