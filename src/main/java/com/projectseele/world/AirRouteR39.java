package com.projectseele.world;

import net.minecraft.core.BlockPos;
import net.minecraft.server.level.*;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.phys.Vec3;
import java.util.Comparator;
import java.util.HashSet;

/** Bounded, nonblocking look-ahead; a streaming pause never restarts a flight leg. */
public final class AirRouteR39
{
    private static final TicketType<ChunkPos> TICKET = TicketType.create("seele_air_route_r39", Comparator.comparingLong(ChunkPos::toLong), 15);
    private static final TicketType<ChunkPos> LANDING_TICKET = TicketType.create("seele_air_next_r54", Comparator.comparingLong(ChunkPos::toLong), 15);
    private static final int LOOK_AHEAD_TICKS = 20;
    public static int duration(Vec3 from, Vec3 to)
    { return Math.max(80, (int)Math.ceil(from.distanceTo(to) / 60)); }
    public static double progress(double ticks, int duration)
    {
        double t = Math.max(0, Math.min(1, ticks / Math.max(1, duration)));
        return t*t*t*(t*(t*6-15)+10);
    }
    public static void prefetch(ServerLevel level, Vec3 from, Vec3 to, int age, int duration)
    {
        if (level.getGameTime()%5 != 0 && age != 0) return;
        Vec3 at = from.lerp(to, progress(age, duration));
        Vec3 ahead = from.lerp(to, progress((double)age + LOOK_AHEAD_TICKS, duration));
        int steps = Math.max(1, (int)Math.ceil(at.distanceTo(ahead) / 16));
        var requested = new HashSet<ChunkPos>();
        // Cover the continuous eased interval, including every chunk between
        // successive tick positions. A fixed distance can expire before the
        // next five-tick refresh near the middle of a long flight.
        for (int i = 0; i <= steps; i++)
        {
            var chunk = new ChunkPos(BlockPos.containing(at.lerp(ahead, (double)i / steps)));
            if (requested.add(chunk))
                level.getChunkSource().addRegionTicket(TICKET,chunk,1,chunk);
        }
        // Entity ticking is needed only at actual future root positions. The
        // intervening swept corridor receives the cheaper FULL-level window.
        requested.clear();
        for (int tick = age; tick <= Math.min(duration, age + LOOK_AHEAD_TICKS); tick++)
        {
            var chunk = new ChunkPos(BlockPos.containing(from.lerp(to, progress(tick, duration))));
            if (requested.add(chunk))
                level.getChunkSource().addRegionTicket(LANDING_TICKET,chunk,2,chunk);
        }
    }
    private AirRouteR39() {}
}
