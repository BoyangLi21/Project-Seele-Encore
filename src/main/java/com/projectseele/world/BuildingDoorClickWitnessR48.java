package com.projectseele.world;

import com.projectseele.ProjectSeele;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.WeakHashMap;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.shapes.CollisionContext;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.event.entity.player.PlayerInteractEvent;
import net.minecraftforge.eventbus.api.EventPriority;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Default-off, two original F05 leaves only. Observes input; never changes its outcome. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID)
public final class BuildingDoorClickWitnessR48
{
    private static final boolean ENABLED = Boolean.getBoolean("projectseele.r48DoorClickWitness");
    private static final Map<ServerLevel, Set<Long>> SEEN = new WeakHashMap<>();
    private static final Map<ServerLevel, List<Pending>> PENDING = new WeakHashMap<>();
    private record Pending(BlockPos lower, long observedAt, ServerPlayer player) { }
    private BuildingDoorClickWitnessR48() { }

    @SubscribeEvent(priority = EventPriority.LOWEST, receiveCanceled = true)
    public static void input(PlayerInteractEvent.RightClickBlock event)
    {
        if (!ENABLED || event.getHand() != InteractionHand.MAIN_HAND
                || !(event.getLevel() instanceof ServerLevel level)
                || !(event.getEntity() instanceof ServerPlayer player)
                || !level.dimension().equals(FacilitySchemaV2.DIMENSION)) return;
        BlockPos hit = event.getPos();
        if ((hit.getX() != -364 && hit.getX() != -363) || hit.getZ() != 621
                || (hit.getY() != 81 && hit.getY() != 82)) return;
        BlockPos lower = new BlockPos(hit.getX(), 81, 621);
        if (!SEEN.computeIfAbsent(level, ignored -> new HashSet<>()).add(lower.asLong())) return;
        ProjectSeele.LOGGER.info("R48 F05 door witness INPUT: dimension={} tick={} player={} clicked={} hit={} canceled={} useBlock={} useItem={} shift={} spectator={} item={} lower=[{}] upper=[{}]",
                level.dimension().location(), level.getGameTime(), player.getUUID(), hit.toShortString(),
                event.getHitVec().getLocation(), event.isCanceled(), event.getUseBlock(), event.getUseItem(),
                player.isShiftKeyDown(), player.isSpectator(), BuiltInRegistries.ITEM.getKey(player.getMainHandItem().getItem()),
                describe(level, lower, player), describe(level, lower.above(), player));
        PENDING.computeIfAbsent(level, ignored -> new ArrayList<>())
                .add(new Pending(lower, level.getGameTime(), player));
    }

    @SubscribeEvent
    public static void nextTick(TickEvent.ServerTickEvent event)
    {
        if (!ENABLED || event.phase != TickEvent.Phase.END || PENDING.isEmpty()) return;
        for (var entry : PENDING.entrySet())
        {
            ServerLevel level = entry.getKey();
            entry.getValue().removeIf(pending -> {
                if (level.getGameTime() <= pending.observedAt()) return false;
                ProjectSeele.LOGGER.info("R48 F05 door witness NEXT_TICK: dimension={} tick={} lowerPos={} lower=[{}] upper=[{}]",
                        level.dimension().location(), level.getGameTime(), pending.lower().toShortString(),
                        describe(level, pending.lower(), pending.player()),
                        describe(level, pending.lower().above(), pending.player()));
                return true;
            });
        }
        PENDING.values().removeIf(List::isEmpty);
    }

    private static String describe(ServerLevel level, BlockPos pos, ServerPlayer player)
    {
        if (!level.hasChunkAt(pos)) return "UNLOADED";
        BlockState state = level.getBlockState(pos);
        return state + " collisionWorld=" + state.getCollisionShape(level, pos, CollisionContext.of(player))
                .toAabbs().stream().map(box -> box.move(pos)).toList();
    }
}
