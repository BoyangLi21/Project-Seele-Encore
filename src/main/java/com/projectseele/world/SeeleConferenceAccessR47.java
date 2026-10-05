package com.projectseele.world;

import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import com.projectseele.item.NervAccessCardR44;
import com.projectseele.registry.ModBlocks;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.sounds.SoundSource;
import net.minecraft.network.chat.Component;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.event.entity.player.PlayerEvent;
import net.minecraftforge.event.entity.player.PlayerInteractEvent;
import net.minecraftforge.event.server.ServerStoppedEvent;
import net.minecraftforge.eventbus.api.EventPriority;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.Files;
import java.util.*;

/** Three finite readers and player-local admission to the original lift's middle stop. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID)
public final class SeeleConferenceAccessR47
{
    public static final int MIDDLE = -364;
    private static final BlockPos MID_READER = new BlockPos(31, -363, 316);
    private static final Set<BlockPos> READERS = Set.of(new BlockPos(25, -387, 316), MID_READER, new BlockPos(25, -339, 316));
    private static final Map<MinecraftServer, Optional<Boolean>> ENABLED = new WeakHashMap<>();
    private static final Map<MinecraftServer, Map<UUID, Lease>> LEASES = new WeakHashMap<>();
    private static final Map<MinecraftServer, Map<UUID, Swipe>> SWIPES = new WeakHashMap<>();
    private static final Set<MinecraftServer> VISUALS_READY = Collections.newSetFromMap(new WeakHashMap<>());
    private record Lease(long until) { }
    private record Swipe(BlockPos reader, InteractionHand hand, long started, boolean decided) { }

    public static boolean enabled(ServerLevel level)
    {
        if (!level.dimension().equals(FacilitySchemaV2.DIMENSION)) return false;
        return ENABLED.computeIfAbsent(level.getServer(), server ->
        {
            var file = server.getWorldPath(LevelResource.ROOT).resolve("r47_seele_conference.json");
            if (!Files.isRegularFile(file)) return Optional.of(false);
            try
            {
                var root = JsonParser.parseString(Files.readString(file)).getAsJsonObject();
                var landing = root.getAsJsonObject("landing");
                var centre = landing.getAsJsonArray("cabin_centre");
                Set<BlockPos> actual = new HashSet<>();
                for (var raw : root.getAsJsonArray("readers"))
                {
                    var p = raw.getAsJsonObject().getAsJsonArray("position");
                    if (p.size() != 3) return Optional.of(false);
                    actual.add(new BlockPos(p.get(0).getAsInt(), p.get(1).getAsInt(), p.get(2).getAsInt()));
                }
                return Optional.of(root.get("schema").getAsInt() == 47
                        && root.get("dimension").getAsString().equals("projectseele:geofront")
                        && root.get("geometry_installed").getAsBoolean() && actual.equals(READERS)
                        && landing.get("lift_id").getAsString().equals(S20PhysicalElevatorDirector.COMMANDER_OFFICE_LIFT_ID)
                        && centre.size() == 3 && centre.get(0).getAsInt() == 28
                        && centre.get(1).getAsInt() == MIDDLE && centre.get(2).getAsInt() == 321);
            }
            catch (Exception failure)
            {
                ProjectSeele.LOGGER.error("SEELE middle-floor marker rejected; original two stops retained", failure);
                return Optional.of(false);
            }
        }).orElse(false);
    }

    public static boolean office(ServerLevel level, S20PhysicalElevatorDirector.LiftSpec spec)
    {
        return enabled(level) && spec.id().equals(S20PhysicalElevatorDirector.COMMANDER_OFFICE_LIFT_ID)
                && spec.lower().cabinCentre().equals(new BlockPos(28, -388, 321))
                && spec.upper().cabinCentre().equals(new BlockPos(28, -340, 321));
    }

    public static List<S20PhysicalElevatorDirector.LiftSpec> augment(ServerLevel level, List<S20PhysicalElevatorDirector.LiftSpec> specs)
    {
        return specs.stream().map(spec ->
        {
            if (!office(level, spec) || spec.stops().stream().anyMatch(stop -> stop.walkY() == MIDDLE)) return spec;
            var stops = new ArrayList<>(spec.stops());
            stops.add(new S20PhysicalElevatorDirector.Landing("SEELE 会议室", new BlockPos(28, MIDDLE, 321), Direction.NORTH));
            stops.sort(Comparator.comparingInt(S20PhysicalElevatorDirector.Landing::walkY));
            return new S20PhysicalElevatorDirector.LiftSpec(spec.id(), List.copyOf(stops));
        }).toList();
    }

    public static boolean protectedReader(ServerLevel level, BlockPos pos)
    {
        return enabled(level) && READERS.contains(pos);
    }

    private static boolean highest(ServerPlayer player, InteractionHand hand)
    {
        return player.getItemInHand(hand).getItem() instanceof NervAccessCardR44 card && card.clearance() >= 3;
    }

    private static boolean meetingEgress(ServerPlayer player)
    {
        if (Math.abs(player.getY() - MIDDLE) > 2) return false;
        double x = player.getX(), z = player.getZ();
        return x >= 16 && x <= 52 && z >= 300 && z <= 316
                || x >= 25 && x <= 32 && z >= 315 && z <= 325;
    }

    private static boolean withinLiftOrRoom(ServerPlayer player)
    {
        if (meetingEgress(player)) return true;
        return player.getX() >= 22 && player.getX() <= 34 && player.getZ() >= 312 && player.getZ() <= 329
                && player.getY() >= -390 && player.getY() <= -332;
    }

    private static boolean leased(ServerPlayer player)
    {
        var map = LEASES.get(player.serverLevel().getServer());
        var lease = map == null ? null : map.get(player.getUUID());
        return lease != null && lease.until() > player.serverLevel().getGameTime() && withinLiftOrRoom(player);
    }

    /** Ordinary endpoints and safe egress never consume or require admission. */
    public static boolean allowDestination(ServerPlayer player, int targetY)
    {
        if (targetY != MIDDLE)
        {
            if (Math.abs(player.getY() - MIDDLE) < 2) revoke(player);
            return true;
        }
        if (meetingEgress(player) || leased(player)) return true;
        player.displayClientMessage(Component.literal("SEELE 会议室需先刷最高权限卡；请使用本层读卡器。"), true);
        return false;
    }

    /** Gates this fixed landing while allowing an already-present occupant to leave. */
    public static boolean canOpenLanding(ServerLevel level)
    {
        return level.players().stream().anyMatch(player -> meetingEgress(player)
                || leased(player) && Math.abs(player.getY() - MIDDLE) < 3
                && player.getX() >= 25 && player.getX() <= 32 && player.getZ() >= 315 && player.getZ() <= 325);
    }

    private static void revoke(ServerPlayer player)
    {
        var leases = LEASES.get(player.serverLevel().getServer());
        if (leases != null) leases.remove(player.getUUID());
    }

    private static void visual(ServerLevel level, BlockPos pos, long start, int status, int tier)
    {
        if (!(level.getBlockEntity(pos) instanceof NervAccessReaderEntityR44 reader)) return;
        // The generic reader remains unlinked: only this finite service owns admission.
        CompoundTag tag = reader.saveWithoutMetadata();
        tag.putBoolean("Linked", false); tag.putLong("SwipeAt", start);
        tag.putInt("Status", status); tag.putInt("Presented", tier);
        tag.putLong("IndicateUntil", level.getGameTime() + 32);
        reader.load(tag); reader.setChanged();
        level.sendBlockUpdated(pos, level.getBlockState(pos), level.getBlockState(pos), 2);
    }

    @SubscribeEvent(priority = EventPriority.HIGHEST)
    public static void readerUse(PlayerInteractEvent.RightClickBlock event)
    {
        if (!(event.getEntity() instanceof ServerPlayer player) || !protectedReader(player.serverLevel(), event.getPos())
                || !player.serverLevel().getBlockState(event.getPos()).is(ModBlocks.NERV_ACCESS_READER.get())) return;
        event.setCanceled(true); event.setCancellationResult(InteractionResult.SUCCESS);
        if (player.distanceToSqr(Vec3.atCenterOf(event.getPos())) >= 16 || player.isSpectator()) return;
        InteractionHand hand = highest(player, event.getHand()) ? event.getHand()
                : highest(player, InteractionHand.OFF_HAND) ? InteractionHand.OFF_HAND
                : highest(player, InteractionHand.MAIN_HAND) ? InteractionHand.MAIN_HAND : event.getHand();
        if (!highest(player, hand))
        {
            if (event.getPos().equals(MID_READER) && meetingEgress(player))
            {
                S20MovingElevatorsAdapter.handleExternalCall(player, MID_READER);
                return;
            }
            visual(player.serverLevel(), event.getPos(), -1, 3, 0);
            player.displayClientMessage(Component.literal("权限不足：需要最高权限NERV卡。"), true);
            return;
        }
        var pending = SWIPES.computeIfAbsent(player.serverLevel().getServer(), ignored -> new HashMap<>());
        var previous = pending.get(player.getUUID());
        if (previous != null && player.serverLevel().getGameTime() - previous.started() < 12) return;
        pending.put(player.getUUID(), new Swipe(event.getPos(), hand, player.serverLevel().getGameTime(), false));
        visual(player.serverLevel(), event.getPos(), player.serverLevel().getGameTime(), 1, 3);
        player.startUsingItem(hand);
    }

    @SubscribeEvent
    public static void tick(TickEvent.ServerTickEvent event)
    {
        if (event.phase != TickEvent.Phase.END) return;
        var level = event.getServer().getLevel(FacilitySchemaV2.DIMENSION);
        if (level == null || !enabled(level)) return;
        if (READERS.stream().allMatch(level::hasChunkAt) && VISUALS_READY.add(event.getServer()))
        {
            for (var pos : READERS) visual(level, pos, -1, 0, 0);
        }
        var leases = LEASES.computeIfAbsent(event.getServer(), ignored -> new HashMap<>());
        leases.entrySet().removeIf(entry ->
        {
            var player = event.getServer().getPlayerList().getPlayer(entry.getKey());
            return player == null || player.serverLevel() != level || entry.getValue().until() <= level.getGameTime() || !withinLiftOrRoom(player);
        });
        var pending = SWIPES.computeIfAbsent(event.getServer(), ignored -> new HashMap<>());
        var iterator = pending.entrySet().iterator();
        while (iterator.hasNext())
        {
            var entry = iterator.next(); var swipe = entry.getValue();
            var player = event.getServer().getPlayerList().getPlayer(entry.getKey());
            long age = level.getGameTime() - swipe.started();
            if (player == null || player.serverLevel() != level || !level.getBlockState(swipe.reader()).is(ModBlocks.NERV_ACCESS_READER.get()))
            {
                visual(level, swipe.reader(), -1, 0, 0); iterator.remove(); continue;
            }
            if (age >= 6 && !swipe.decided())
            {
                boolean permit = highest(player, swipe.hand()) && player.distanceToSqr(Vec3.atCenterOf(swipe.reader())) < 16 && !player.isSpectator();
                if (permit) leases.put(player.getUUID(), new Lease(level.getGameTime() + 600));
                visual(level, swipe.reader(), swipe.started(), permit ? 2 : 3, permit ? 3 : 0);
                player.displayClientMessage(Component.literal(permit ? "SEELE 会议室许可已确认：30秒内进梯选择该层。" : "刷卡未完成，请保持最高卡与读卡距离。"), true);
                level.playSound(null, swipe.reader(), permit ? SoundEvents.NOTE_BLOCK_PLING.value() : SoundEvents.NOTE_BLOCK_BASS.value(), SoundSource.BLOCKS, .35F, permit ? 1.3F : .75F);
                entry.setValue(new Swipe(swipe.reader(), swipe.hand(), swipe.started(), true));
                if (permit && swipe.reader().equals(MID_READER)) S20MovingElevatorsAdapter.handleExternalCall(player, MID_READER);
            }
            if (age >= 32) { visual(level, swipe.reader(), -1, 0, 0); iterator.remove(); }
        }
    }

    @SubscribeEvent
    public static void logout(PlayerEvent.PlayerLoggedOutEvent event)
    {
        if (event.getEntity() instanceof ServerPlayer player)
        {
            revoke(player);
            var map = SWIPES.get(player.serverLevel().getServer());
            var swipe = map == null ? null : map.remove(player.getUUID());
            if (swipe != null) visual(player.serverLevel(), swipe.reader(), -1, 0, 0);
        }
    }

    @SubscribeEvent
    public static void stopped(ServerStoppedEvent event)
    {
        ENABLED.remove(event.getServer()); LEASES.remove(event.getServer()); SWIPES.remove(event.getServer()); VISUALS_READY.remove(event.getServer());
    }
    private SeeleConferenceAccessR47() { }
}
