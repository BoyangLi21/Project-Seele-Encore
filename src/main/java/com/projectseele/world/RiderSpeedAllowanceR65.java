package com.projectseele.world;

import java.util.Map;
import java.util.UUID;

/**
 * Which riders a dedicated server excuses from vanilla's ten-block "moved too quickly" check (R65). Vanilla excuses
 * only the player hosting the game. An MTR train on the GeoFront spiral line runs at 700 km/h, 9.72 blocks a tick:
 * two ticks in one movement packet after any client stall are over the limit, and the server set the rider back
 * behind the train, where the chunks ahead of the train are not sent.
 */
public final class RiderSpeedAllowanceR65
{
    /** How far (blocks) an MTR rider may have gone between two movement packets: two ticks at 700 km/h and a margin. */
    public static final double MTR_MOST = 24.0D;
    private static final org.slf4j.Logger LOGGER = org.slf4j.LoggerFactory.getLogger("projectseele");
    private static volatile java.lang.reflect.Field riding;
    private static volatile boolean unavailable;

    private RiderSpeedAllowanceR65() {}

    /** Whether a step of (dx, dy, dz) from where the server has the player may skip the speed check. */
    public static boolean mtrStep(boolean ridingMtr, double dx, double dy, double dz)
    {
        return ridingMtr && dx * dx + dy * dy + dz * dz <= MTR_MOST * MTR_MOST;
    }

    /**
     * Whether MTR has this player as riding one of its vehicles: its own server-side set, filled by the rider's
     * client once a second and emptied on dismount. MTR is not on the compile classpath, so the set is read by
     * reflection; without MTR, or if the field is not there, nobody is riding.
     */
    public static boolean ridingMtr(UUID player)
    {
        if (unavailable) return false;
        try
        {
            var field = riding;
            if (field == null)
            {
                field = Class.forName("org.mtr.mod.Init", false, RiderSpeedAllowanceR65.class.getClassLoader()).getDeclaredField("RIDING_PLAYERS");
                field.setAccessible(true);
                riding = field;
            }
            return field.get(null) instanceof Map<?, ?> players && players.containsKey(player);
        }
        catch (ReflectiveOperationException | RuntimeException | LinkageError missing)
        {
            unavailable = true;
            LOGGER.warn("MTR riders unreadable; MTR riders keep the vanilla speed check", missing);
            return false;
        }
    }
}
