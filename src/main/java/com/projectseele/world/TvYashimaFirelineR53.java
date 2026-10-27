package com.projectseele.world;

import java.util.*;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.TicketType;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.phys.Vec3;

/** Keep collision blocks along the two real firing rays, without ticking a 2 km entity corridor. */
public final class TvYashimaFirelineR53
{
    private static final TicketType<ChunkPos> TICKET = TicketType.create("yashima_fireline_blocks", Comparator.comparingLong(ChunkPos::toLong), 100);
    private static final Map<ServerLevel, Line> LINES = new WeakHashMap<>();
    private static final class Line
    {
        final long generation;
        final List<ChunkPos> chunks;
        int requested;
        Line(long generation, List<ChunkPos> chunks) { this.generation = generation;this.chunks = chunks; }
    }

    public static void retain(ServerLevel level, TvCampaignSavedData data, TvEncounterSitesR45.Site site)
    {
        var line = LINES.get(level);
        if (line == null || line.generation != data.generationR43)
        {
            clear(level);
            var chunks = new LinkedHashSet<ChunkPos>();
            var station = TvYashimaStationR52.plan(level).orElse(null);
            Vec3 muzzle = station == null ? site.hero() : station.geometry().point(station.raised(), new org.joml.Quaternionf(), station.geometry().muzzle());
            // Server rays are traced to weapon range before the nearer entity hit is selected.
            addRay(chunks, muzzle, site.angel(), site.attackRange());
            addRay(chunks, site.angel(), site.hero(), site.attackRange());
            line = new Line(data.generationR43, List.copyOf(chunks));LINES.put(level, line);
        }
        line.requested = Math.min(line.chunks.size(), line.requested + 16);
        for (int i = 0; i < line.requested; i++)
        {
            var chunk = line.chunks.get(i);
            // Distance zero gives a FULL block chunk, not an entity-ticking ticket.
            level.getChunkSource().addRegionTicket(TICKET, chunk, 0, chunk);
        }
    }

    static void addRay(Set<ChunkPos> result, Vec3 from, Vec3 target, double range)
    {
        Vec3 end = from.add(target.subtract(from).normalize().scale(range));
        int samples = Math.max(1, (int)Math.ceil(from.distanceTo(end) / 8));
        for (int n = 0; n <= samples; n++)
        {
            var chunk = new ChunkPos(BlockPos.containing(from.lerp(end, n / (double)samples)));
            // One chunk margin includes the finite muzzle/eye displacement and corner crossings.
            for (int x = -1; x <= 1; x++) for (int z = -1; z <= 1; z++)
                result.add(new ChunkPos(chunk.x + x, chunk.z + z));
        }
    }

    public static boolean ready(ServerLevel level, TvCampaignSavedData data)
    {
        var line = LINES.get(level);
        return line != null && line.generation == data.generationR43 && line.requested == line.chunks.size()
                && line.chunks.stream().allMatch(c -> level.getChunkSource().hasChunk(c.x, c.z));
    }

    public static void clear(ServerLevel level)
    {
        var line = LINES.remove(level);if (line == null) return;
        for (int i = 0; i < line.requested; i++)
        {
            var chunk = line.chunks.get(i);level.getChunkSource().removeRegionTicket(TICKET, chunk, 0, chunk);
        }
    }
    private TvYashimaFirelineR53() { }
}
