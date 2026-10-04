package com.projectseele.world;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.RamielEntity;
import com.projectseele.event.TvEncounterDirectorR45;
import com.projectseele.network.ClientboundEncounterObserverPacket;
import com.projectseele.network.ServerboundEncounterObserverReadyPacket;
import com.projectseele.network.SeeleNetwork;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.event.entity.player.PlayerEvent;
import net.minecraftforge.event.level.LevelEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.network.PacketDistributor;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;
import java.util.WeakHashMap;

/** Authorized observation of the mission's sole real Ramiel; never creates or loads a target. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID)
public final class EncounterObserverR45
{
    private static final int CAPABILITY_LEASE = 120;
    private static final int MAX_OBSERVERS = 16;
    private static String expectedRamielResource = "";
    private record Sent(UUID target, long tick) {}
    private static final class Session
    {
        final UUID nonce = UUID.randomUUID(), owner;
        final long generation, created;
        long sequence, lastCapability, lastReceipt, lastOffer = -100;
        boolean capable, drawn;
        UUID target;
        String resource = "", renderer = "";
        final Map<Long, Sent> sent = new LinkedHashMap<>();
        final Map<Long, Long> offers = new LinkedHashMap<>();
        Session(TvCampaignSavedData data, long now)
        { owner = data.owner; generation = data.generationR43; created = now; }
    }
    private static final Map<ServerLevel, Map<UUID, Session>> SESSIONS = new WeakHashMap<>();

    /** Root supplies the approved real-model resource manifest hash on the server; absent means no ready ACK. */
    public static void installRamielResourceContract(String approvedSha256)
    {
        if (approvedSha256 == null || !approvedSha256.matches("[0-9a-f]{64}"))
            throw new IllegalArgumentException("Actual Ramiel resource contract hash");
        if (approvedSha256.equals(expectedRamielResource)) return;
        for (var level : java.util.List.copyOf(SESSIONS.keySet())) clear(level);
        expectedRamielResource = approvedSha256;
    }

    private static boolean live(TvCampaignSavedData data)
    {
        return "ramiel".equals(data.active) && data.owner != null && data.generationR43 > 0
                && !data.phase.equals("cancel") && !data.phase.equals("failure") && !data.phase.equals("idle");
    }

    private static boolean participant(ServerLevel level, TvCampaignSavedData data, ServerPlayer player)
    {
        if (player == null || player.level() != level || !player.isAlive()) return false;
        if (player.getUUID().equals(data.owner)
                || data.sorties.values().stream().anyMatch(sortie -> player.getUUID().equals(sortie.commander))) return true;
        var eva = EvaPilotResolver.controlTarget(player);
        return eva != null && eva.getPilotEntity() == player && data.sorties.values().stream()
                .anyMatch(sortie -> eva.getUUID().equals(sortie.eva));
    }

    private static void send(ServerPlayer player, ClientboundEncounterObserverPacket packet)
    { SeeleNetwork.CHANNEL.send(PacketDistributor.PLAYER.with(() -> player), packet); }

    private static ClientboundEncounterObserverPacket envelope(ServerLevel level, Session session,
            ClientboundEncounterObserverPacket.Kind kind, ClientboundEncounterObserverPacket.Snapshot state)
    {
        return new ClientboundEncounterObserverPacket(kind, session.nonce, session.generation,
                level.dimension().location(), ClientboundEncounterObserverPacket.RAMIEL,
                session.sequence, level.getGameTime(), state);
    }

    private static void revoke(ServerLevel level, UUID listener, Session session, boolean notify)
    {
        var player = level.getServer().getPlayerList().getPlayer(listener);
        if (player != null)
        {
            if (notify && player.level() == level)
                send(player, envelope(level, session, ClientboundEncounterObserverPacket.Kind.CLEAR, null));
            // This also removes previous-dimension Rules membership.
            TvEncounterRulesR45.logout(player);
        }
    }

    private static ClientboundEncounterObserverPacket.Snapshot sample(RamielEntity target)
    {
        int flags = (target.isAlive() ? ClientboundEncounterObserverPacket.ALIVE : 0)
                | (target.isCharging() ? ClientboundEncounterObserverPacket.CHARGING : 0)
                | (target.isDrilling() ? ClientboundEncounterObserverPacket.DRILLING : 0)
                | (target.isExposed() ? ClientboundEncounterObserverPacket.EXPOSED : 0)
                | (target.isEnraged() ? ClientboundEncounterObserverPacket.ENRAGED : 0);
        // Ramiel spin/exposure easing are client-only fields. Do not pretend the server's zero is a pose.
        return new ClientboundEncounterObserverPacket.Snapshot(target.getUUID(), target.getId(), target.tickCount,
                target.position(), target.getDeltaMovement(), target.getYRot(), target.getXRot(),
                target.yBodyRot, target.yHeadRot, target.getBbWidth(), target.getBbHeight(), target.getHealth(), target.getMaxHealth(),
                target.getAtFieldEnergy(), target.getAtFieldMax(), flags, target.getBeamTicks(),
                target.getBeamEnd(), target.getDrillDepth());
    }

    @SubscribeEvent
    public static void tick(TickEvent.LevelTickEvent event)
    {
        if (event.phase != TickEvent.Phase.END || !(event.level instanceof ServerLevel level)
                || level.getGameTime() % 2 != 0) return;
        var data = TvCampaignSavedData.get(level);
        var site = live(data) ? TvEncounterSitesR45.site(level, data.active).orElse(null) : null;
        if (site == null || !site.geometryValidated() || !site.modelReady()
                || !site.visibility().equals("remote_actual_entity_v1"))
        { clear(level); return; }
        var sessions = SESSIONS.computeIfAbsent(level, ignored -> new HashMap<>());
        long now = level.getGameTime();
        for (var iterator = sessions.entrySet().iterator(); iterator.hasNext();)
        {
            var entry = iterator.next(); var session = entry.getValue();
            var player = level.getServer().getPlayerList().getPlayer(entry.getKey());
            if (!participant(level, data, player) || session.generation != data.generationR43
                    || !session.owner.equals(data.owner) || now < session.created
                    || (session.capable ? now - session.lastCapability > CAPABILITY_LEASE
                                        : now - session.created > CAPABILITY_LEASE)
                    || (session.drawn && now - session.lastReceipt > ClientboundEncounterObserverPacket.STALE_TICKS)
                    || (session.target != null && !session.target.equals(data.angel)))
            { revoke(level, entry.getKey(), session, true); iterator.remove(); }
        }
        var target = data.angel == null ? null : level.getEntity(data.angel);
        RamielEntity actual = target instanceof RamielEntity ramiel && ramiel.isAlive()
                && TvEncounterDirectorR45.owned(ramiel, data) ? ramiel : null;
        for (var player : level.players())
        {
            if (!participant(level, data, player) || player.position().distanceTo(site.angel()) > 4096) continue;
            var session = sessions.get(player.getUUID());
            if (session == null)
            {
                if (sessions.size() >= MAX_OBSERVERS) continue;
                clearPlayer(player, false);
                session = new Session(data, now); sessions.put(player.getUUID(), session);
            }
            if (now - session.lastOffer >= 40)
            {
                send(player, envelope(level, session, ClientboundEncounterObserverPacket.Kind.CAPABILITY, null));
                session.offers.entrySet().removeIf(entry -> now - entry.getKey() > CAPABILITY_LEASE);
                session.offers.put(now, session.sequence);
                session.lastOffer = now;
            }
            if (!session.capable || actual == null) continue;
            session.target = actual.getUUID(); session.sequence++;
            var state = sample(actual);
            session.sent.entrySet().removeIf(entry -> now - entry.getValue().tick() > ClientboundEncounterObserverPacket.STALE_TICKS);
            session.sent.put(session.sequence, new Sent(state.target(), now));
            while (session.sent.size() > 32) session.sent.remove(session.sent.keySet().iterator().next());
            send(player, envelope(level, session, ClientboundEncounterObserverPacket.Kind.STATE, state));
        }
    }

    public static void accept(ServerPlayer player, ServerboundEncounterObserverReadyPacket ack)
    {
        if (player == null) return;
        var level = player.serverLevel();
        var session = SESSIONS.getOrDefault(level, Map.of()).get(player.getUUID());
        if (session == null || !session.nonce.equals(ack.nonce()) || session.generation != ack.generation()
                || !level.dimension().location().equals(ack.dimension())) return;
        var data = TvCampaignSavedData.get(level); long now = level.getGameTime();
        if (!live(data) || !participant(level, data, player) || session.generation != data.generationR43
                || !session.owner.equals(data.owner) || !expectedRamielResource.equals(ack.resourceSha256())
                || !ClientboundEncounterObserverPacket.RENDERER_ID.equals(ack.rendererId())
                || ack.serverTick() > now
                || now - ack.serverTick() > CAPABILITY_LEASE
                || (session.capable ? now - session.lastCapability > CAPABILITY_LEASE
                                    : now - session.created > CAPABILITY_LEASE)) return;
        if (ack.kind() == ServerboundEncounterObserverReadyPacket.Kind.DISABLE)
        { clearPlayer(player, true); return; }
        if (session.capable && (!session.resource.equals(ack.resourceSha256()) || !session.renderer.equals(ack.rendererId())))
        { clearPlayer(player, true); return; }
        if (ack.kind() == ServerboundEncounterObserverReadyPacket.Kind.CAPABILITY)
        {
            if (ack.target() != null || !Long.valueOf(ack.sequence()).equals(session.offers.get(ack.serverTick()))) return;
            session.capable = true; session.lastCapability = now;
            session.resource = ack.resourceSha256(); session.renderer = ack.rendererId();
            TvEncounterRulesR45.remoteObserver(player, true); return;
        }
        if (!session.capable || data.angel == null || !data.angel.equals(ack.target())) return;
        var sent = session.sent.get(ack.sequence());
        if (sent == null || !sent.target().equals(ack.target()) || sent.tick() != ack.serverTick()
                || now - sent.tick() > ClientboundEncounterObserverPacket.STALE_TICKS
                || !(level.getEntity(data.angel) instanceof RamielEntity actual)
                || !actual.isAlive() || !TvEncounterDirectorR45.owned(actual, data)) return;
        if (ack.kind() == ServerboundEncounterObserverReadyPacket.Kind.FRAME) session.drawn = true;
        if (!session.drawn) return; // Receipt alone can never establish first visibility.
        session.lastCapability = session.lastReceipt = now;
        TvEncounterRulesR45.remoteTargetObserved(player, actual.getUUID(), data.generationR43, true);
    }

    public static boolean actualFrameSeen(ServerPlayer player, UUID target, long generation)
    {
        if (player == null || target == null || generation < 1) return false;
        var data = TvCampaignSavedData.get(player.serverLevel());
        var session = SESSIONS.getOrDefault(player.serverLevel(), Map.of()).get(player.getUUID());
        return live(data) && participant(player.serverLevel(), data, player)
                && session != null && session.capable && session.drawn && session.generation == generation
                && generation == data.generationR43 && target.equals(data.angel) && target.equals(session.target)
                && player.serverLevel().getGameTime() >= session.lastReceipt
                && player.serverLevel().getGameTime() - session.lastReceipt
                    <= ClientboundEncounterObserverPacket.STALE_TICKS;
    }

    public static void clear(ServerLevel level)
    {
        var sessions = SESSIONS.remove(level);
        if (sessions != null) sessions.forEach((listener, session) -> revoke(level, listener, session, true));
    }

    private static void clearPlayer(ServerPlayer player, boolean notify)
    {
        SESSIONS.forEach((level, sessions) ->
        {
            var session = sessions.remove(player.getUUID());
            if (session != null) revoke(level, player.getUUID(), session, notify);
        });
        TvEncounterRulesR45.logout(player);
    }

    @SubscribeEvent public static void logout(PlayerEvent.PlayerLoggedOutEvent event)
    { if (event.getEntity() instanceof ServerPlayer player) clearPlayer(player, false); }
    @SubscribeEvent public static void dimension(PlayerEvent.PlayerChangedDimensionEvent event)
    { if (event.getEntity() instanceof ServerPlayer player) clearPlayer(player, true); }
    @SubscribeEvent public static void unloaded(LevelEvent.Unload event)
    { if (event.getLevel() instanceof ServerLevel level) clear(level); }

    private EncounterObserverR45() {}
}
