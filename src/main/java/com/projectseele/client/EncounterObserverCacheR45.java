package com.projectseele.client;

import com.projectseele.ProjectSeele;
import com.projectseele.network.ClientboundEncounterObserverPacket;
import com.projectseele.network.ServerboundEncounterObserverReadyPacket;
import com.projectseele.network.SeeleNetwork;
import net.minecraft.client.Minecraft;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.entity.Entity;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.util.Objects;
import java.util.Optional;

/** Data only. No renderer, proxy entity, AI, world insertion, collision or hit target lives here. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, value = Dist.CLIENT)
public final class EncounterObserverCacheR45
{
    public interface RendererSupport
    {
        boolean supports(ResourceLocation entityType, int schema);
        boolean resourcesReady(ResourceLocation entityType);
        String resourceSha256(ResourceLocation entityType);
        String rendererId();
    }
    public record View(ClientboundEncounterObserverPacket current,
                       ClientboundEncounterObserverPacket previous, long ageClientTicks) {}
    private record Proof(String resource, String renderer) {}
    private static RendererSupport renderer;
    private static ClientLevel boundLevel;
    private static Proof acknowledgedProof;
    private static ClientboundEncounterObserverPacket challenge, current, previous;
    private static long clock, challengeReceived, stateReceived, lastAck = -100;
    private static boolean firstDrawn;

    /** Root installs this only after its real render path and actual resources are available. */
    public static void installRendererSupport(RendererSupport actualSupport)
    {
        clear(true);
        renderer = Objects.requireNonNull(actualSupport);
    }

    public static void removeRendererSupport()
    { clear(true); renderer = null; }

    private static Proof proof()
    {
        if (renderer == null || challenge == null) return null;
        try
        {
            var type = challenge.entityType();
            if (!renderer.supports(type, ClientboundEncounterObserverPacket.SCHEMA)
                    || !renderer.resourcesReady(type)) return null;
            String resource = renderer.resourceSha256(type), name = renderer.rendererId();
            if (resource == null || name == null || !resource.matches("[0-9a-f]{64}")
                    || !ClientboundEncounterObserverPacket.RENDERER_ID.equals(name)) return null;
            return new Proof(resource, name);
        }
        catch (RuntimeException unavailable) { return null; }
    }

    private static boolean sameSession(ClientboundEncounterObserverPacket packet)
    {
        return challenge != null && challenge.nonce().equals(packet.nonce())
                && challenge.generation() == packet.generation()
                && challenge.dimension().equals(packet.dimension())
                && challenge.entityType().equals(packet.entityType());
    }

    private static boolean sameWorld(ClientboundEncounterObserverPacket packet)
    {
        var minecraft = Minecraft.getInstance();
        return minecraft.level != null && minecraft.player != null && minecraft.getConnection() != null
                && (boundLevel == null || boundLevel == minecraft.level)
                && minecraft.level.dimension().location().equals(packet.dimension());
    }

    private static boolean timeSane(ClientboundEncounterObserverPacket packet)
    {
        long worldTime = Minecraft.getInstance().level.getGameTime();
        return packet.serverTick() >= worldTime - 200 && packet.serverTick() <= worldTime + 200;
    }

    public static void receive(ClientboundEncounterObserverPacket packet)
    {
        if (boundLevel != null && boundLevel != Minecraft.getInstance().level) clear(false);
        if (!sameWorld(packet)) return;
        if (packet.kind() == ClientboundEncounterObserverPacket.Kind.CLEAR)
        { if (sameSession(packet)) clear(false); return; }
        if (!timeSane(packet)) return;
        if (packet.kind() == ClientboundEncounterObserverPacket.Kind.CAPABILITY)
        {
            if (challenge != null && (packet.generation() < challenge.generation()
                    || (packet.generation() == challenge.generation() && packet.serverTick() < challenge.serverTick()))) return;
            if (!sameSession(packet)) clear(false);
            challenge = packet; challengeReceived = clock; boundLevel = Minecraft.getInstance().level;
            var available = proof();
            if (available == null) return; // No default renderer or successful capability.
            if (acknowledgedProof != null && !acknowledgedProof.equals(available))
            { clear(true); return; }
            acknowledgedProof = available;
            ack(ServerboundEncounterObserverReadyPacket.Kind.CAPABILITY, challenge, available);
            return;
        }
        if (!sameSession(packet) || acknowledgedProof == null || !acknowledgedProof.equals(proof())) return;
        if (current != null && (packet.sequence() <= current.sequence()
                || packet.serverTick() < current.serverTick())) return;
        if (current != null && !current.snapshot().target().equals(packet.snapshot().target()))
        { clear(true); return; }
        previous = current; current = packet; stateReceived = clock;
        if (firstDrawn && clock - lastAck >= 10)
            ack(ServerboundEncounterObserverReadyPacket.Kind.RECEIPT, current, acknowledgedProof);
    }

    private static boolean fresh()
    {
        return current != null && challenge != null && sameWorld(current)
                && clock >= stateReceived && clock - stateReceived <= ClientboundEncounterObserverPacket.STALE_TICKS
                && clock - challengeReceived <= 120 && acknowledgedProof != null
                && acknowledgedProof.equals(proof());
    }

    /** UUID and type, not proximity or entity ID alone, decide normal tracking ownership. */
    public static Optional<Entity> normalEntity()
    {
        if (!fresh()) return Optional.empty();
        var level = Minecraft.getInstance().level;
        var state = current.snapshot();
        var byId = level.getEntity(state.entityId());
        if (matches(byId)) return Optional.of(byId);
        for (var entity : level.entitiesForRendering())
            if (matches(entity)) return Optional.of(entity);
        return Optional.empty();
    }

    private static boolean matches(Entity entity)
    {
        return entity != null && !entity.isRemoved() && entity.level() == Minecraft.getInstance().level
                && current.snapshot().target().equals(entity.getUUID())
                && current.entityType().equals(BuiltInRegistries.ENTITY_TYPE.getKey(entity.getType()));
    }

    /** Root reads this to draw the real model; an ordinary tracked entity always takes precedence. */
    public static Optional<View> renderCandidate()
    {
        if (!fresh() || normalEntity().isPresent()) return Optional.empty();
        return Optional.of(new View(current, previous, clock - stateReceived));
    }

    /** Call AFTER root actually draws this exact cache frame. Never call from the packet handler. */
    public static boolean markDrawn(ClientboundEncounterObserverPacket drawn)
    {
        if (!fresh() || normalEntity().isPresent() || !current.equals(drawn)) return false;
        recordFirstDraw(); return true;
    }

    /** Root may call after the ordinary real entity renderer completes its matching UUID frame. */
    public static boolean markNormalDrawn(Entity actual)
    {
        if (!fresh() || !matches(actual) || normalEntity().orElse(null) != actual) return false;
        recordFirstDraw(); return true;
    }

    private static void recordFirstDraw()
    {
        if (!firstDrawn || clock - lastAck >= 10)
            ack(ServerboundEncounterObserverReadyPacket.Kind.FRAME, current, acknowledgedProof);
        firstDrawn = true;
    }

    private static void ack(ServerboundEncounterObserverReadyPacket.Kind kind,
            ClientboundEncounterObserverPacket source, Proof available)
    {
        if (Minecraft.getInstance().getConnection() == null) return;
        SeeleNetwork.CHANNEL.sendToServer(new ServerboundEncounterObserverReadyPacket(kind, source.nonce(),
                source.generation(), source.dimension(), source.snapshot() == null ? null : source.snapshot().target(),
                source.sequence(), source.serverTick(), available.resource(), available.renderer()));
        lastAck = clock;
    }

    public static void clear(boolean notify)
    {
        if (notify && challenge != null && acknowledgedProof != null
                && Minecraft.getInstance().getConnection() != null)
            ack(ServerboundEncounterObserverReadyPacket.Kind.DISABLE, challenge, acknowledgedProof);
        challenge = current = previous = null; acknowledgedProof = null; firstDrawn = false; boundLevel = null;
    }

    @SubscribeEvent
    public static void tick(TickEvent.ClientTickEvent event)
    {
        if (event.phase != TickEvent.Phase.END) return;
        clock++;
        if (challenge == null) return;
        if (!sameWorld(challenge) || clock - challengeReceived > 120
                || (acknowledgedProof != null && !acknowledgedProof.equals(proof()))
                || (current != null && clock - stateReceived > ClientboundEncounterObserverPacket.STALE_TICKS))
        { clear(true); return; }
        if (acknowledgedProof != null && clock - lastAck >= 20)
            ack(firstDrawn && current != null ? ServerboundEncounterObserverReadyPacket.Kind.RECEIPT
                                              : ServerboundEncounterObserverReadyPacket.Kind.CAPABILITY,
                    firstDrawn && current != null ? current : challenge, acknowledgedProof);
    }

    private EncounterObserverCacheR45() {}
}
