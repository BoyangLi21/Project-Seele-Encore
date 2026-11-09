package com.projectseele.world;

import com.projectseele.ProjectSeele;
import java.util.Comparator;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.TicketType;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.level.ChunkPos;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** A giant seen across the city must not be saved away with the chunk under its feet. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID)
public final class GiantChunkTicketsR61
{
    private static final int PERIOD = 40;
    private static final TicketType<ChunkPos> TICKET =
            TicketType.create("seele_giant_view_r61", Comparator.comparingLong(ChunkPos::toLong), 100);

    @SubscribeEvent
    public static void tick(TickEvent.LevelTickEvent event)
    {
        if (event.phase != TickEvent.Phase.END || !(event.level instanceof ServerLevel level)
                || level.getGameTime() % PERIOD != 0 || level.players().isEmpty()) return;
        for (Entity entity : level.getAllEntities())
        {
            if (entity instanceof com.projectseele.entity.RamielEntity ramiel) ramiel.updateBossBarAudienceR61(level);
            if (!FacilityVisibilityR54.giant(entity) || !observed(level, entity)) continue;
            // Level 33 keeps the entity tracked without simulating it: only
            // a mission's own tickets may keep a far Angel walking.
            var chunk = entity.chunkPosition();
            level.getChunkSource().addRegionTicket(TICKET, chunk, 0, chunk);
        }
    }

    private static boolean observed(ServerLevel level, Entity entity)
    {
        double range = FacilityVisibilityR54.GIANT_DISTANCE;
        for (var player : level.players())
        {
            double dx = player.getX() - entity.getX(), dz = player.getZ() - entity.getZ();
            if (dx * dx + dz * dz <= range * range) return true;
        }
        return false;
    }

    private GiantChunkTicketsR61() { }
}
