package com.projectseele.network;

import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import java.util.function.Supplier;

import com.projectseele.ProjectSeele;
import com.projectseele.config.SeeleConfig;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.visual.GeoFrontCommands;
import com.projectseele.world.IntegratedNervMapBuilder;
import com.projectseele.world.EvaPilotResolver;
import com.projectseele.world.FacilityV2SavedData;
import com.projectseele.world.PerformanceCounters;
import net.minecraft.core.BlockPos;
import net.minecraft.network.FriendlyByteBuf;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.network.NetworkEvent;
import net.minecraftforge.network.PacketDistributor;

/**
 * Authenticated first-person optical frame uploaded by the actual EVA pilot.
 * The server never decodes image data; it validates and relays only to players
 * physically present in the NERV command area.
 */
public final class ServerboundEvaVideoFramePacket
{
    private static boolean reviewLoopback(MinecraftServer server)
    {
        return Boolean.getBoolean("projectseele.feedReviewR06")&&server.getWorldPath(
                net.minecraft.world.level.storage.LevelResource.ROOT).normalize().getFileName().toString().startsWith("SEELE_EVA_FEED_REVIEW");
    }
    public static final int FRAME_WIDTH = 1280;
    public static final int FRAME_HEIGHT = 720;
    public static final int MAX_FRAME_BYTES =
            EvaVideoFrameTransport.MAX_FRAME_BYTES;
    public static final int MAX_CHUNK_BYTES =
            EvaVideoFrameTransport.MAX_CHUNK_BYTES;
    private static final int MIN_FRAME_INTERVAL_TICKS = 1;
    public static final int FEED_ACTIVE_TICKS = 60;
    private static final Map<UUID, Long> LAST_ACCEPTED_TICK = new HashMap<>();
    private static final Map<UUID, EvaVideoFrameTransport.Assembly>
            UPLOADS = new HashMap<>();
    private static final long[] LAST_VARIANT_TICK = {
            Long.MIN_VALUE / 2, Long.MIN_VALUE / 2, Long.MIN_VALUE / 2
    };
    private static final long[] LAST_HUMAN_VARIANT_TICK = {
            Long.MIN_VALUE / 2, Long.MIN_VALUE / 2, Long.MIN_VALUE / 2
    };
    private final int variant;
    private final int frameId;
    private final int chunkIndex;
    private final int chunkCount;
    private final int totalBytes;
    private final byte[] chunk;

    public ServerboundEvaVideoFramePacket(int variant, int frameId,
                                          int chunkIndex, int chunkCount,
                                          int totalBytes, byte[] chunk)
    {
        this.variant = variant;
        this.frameId = frameId;
        this.chunkIndex = chunkIndex;
        this.chunkCount = chunkCount;
        this.totalBytes = totalBytes;
        this.chunk = chunk;
    }

    public ServerboundEvaVideoFramePacket(FriendlyByteBuf buffer)
    {
        this(buffer.readUnsignedByte(), buffer.readVarInt(),
                buffer.readVarInt(), buffer.readVarInt(), buffer.readVarInt(),
                buffer.readByteArray(MAX_CHUNK_BYTES));
    }

    public void encode(FriendlyByteBuf buffer)
    {
        buffer.writeByte(this.variant);
        buffer.writeVarInt(this.frameId);
        buffer.writeVarInt(this.chunkIndex);
        buffer.writeVarInt(this.chunkCount);
        buffer.writeVarInt(this.totalBytes);
        buffer.writeByteArray(this.chunk);
    }

    public void handle(Supplier<NetworkEvent.Context> contextSupplier)
    {
        NetworkEvent.Context context = contextSupplier.get();
        ServerPlayer sender = context.getSender();
        if (sender != null)
        {
            context.enqueueWork(() -> acceptChunk(sender));
        }
        context.setPacketHandled(true);
    }

    private void acceptChunk(ServerPlayer sender)
    {
        if (!canUpload(sender)
                || !EvaVideoFrameTransport.validHeader(this.chunkIndex,
                this.chunkCount, this.totalBytes, this.chunk))
        {
            return;
        }
        long nowNanos = System.nanoTime();
        UPLOADS.entrySet().removeIf(entry ->
                entry.getValue().expired(nowNanos));
        EvaVideoFrameTransport.Assembly assembly = UPLOADS.get(
                sender.getUUID());
        if (assembly == null || !assembly.matches(this.frameId,
                this.chunkCount, this.totalBytes))
        {
            assembly = new EvaVideoFrameTransport.Assembly(this.frameId,
                    this.chunkCount, this.totalBytes);
            UPLOADS.put(sender.getUUID(), assembly);
        }
        if (!assembly.accept(this.chunkIndex, this.chunk))
        {
            UPLOADS.remove(sender.getUUID());
            return;
        }
        if (assembly.complete())
        {
            UPLOADS.remove(sender.getUUID());
            byte[] frame = assembly.join();
            if (frame != null)
            {
                relay(sender, frame);
            }
        }
    }

    private boolean canUpload(ServerPlayer sender)
    {
        EvaUnit01Entity eva = EvaPilotResolver.controlTarget(sender);
        if (!SeeleConfig.liveCockpitVideoEnabled()
                || !SeeleConfig.videoFrameRelayEnabled()
                || eva == null || !eva.isAlive() || eva.isExperimentalUnit()
                || eva.getUnitVariant() != this.variant
                || EvaPilotResolver.pilot(eva) != sender
                || this.variant < EvaUnit01Entity.UNIT_00
                || this.variant > EvaUnit01Entity.UNIT_02
                || !sender.serverLevel().dimension().equals(
                GeoFrontCommands.GEOFRONT)&&!reviewLoopback(sender.server))
        {
            return false;
        }
        long now = sender.serverLevel().getGameTime();
        long previous = LAST_ACCEPTED_TICK.getOrDefault(sender.getUUID(),
                Long.MIN_VALUE / 2);
        return now - previous >= MIN_FRAME_INTERVAL_TICKS;
    }

    private void relay(ServerPlayer sender, byte[] frame)
    {
        EvaUnit01Entity eva = EvaPilotResolver.controlTarget(sender);
        if (!SeeleConfig.liveCockpitVideoEnabled()
                || !SeeleConfig.videoFrameRelayEnabled()
                || eva == null
                || !eva.isAlive() || eva.getUnitVariant() != this.variant
                || EvaPilotResolver.pilot(eva) != sender
                || this.variant < EvaUnit01Entity.UNIT_00
                || this.variant > EvaUnit01Entity.UNIT_02
                || !validFrame(frame))
        {
            return;
        }

        ServerLevel level = sender.serverLevel();
        if (!level.dimension().equals(GeoFrontCommands.GEOFRONT)&&!reviewLoopback(sender.server))
        {
            return;
        }
        long now = level.getGameTime();
        long previous = LAST_ACCEPTED_TICK.getOrDefault(
                sender.getUUID(), Long.MIN_VALUE / 2);
        if (now - previous < MIN_FRAME_INTERVAL_TICKS)
        {
            return;
        }
        boolean acquired = !isFeedActive(level, this.variant);
        LAST_ACCEPTED_TICK.put(sender.getUUID(), now);
        LAST_VARIANT_TICK[this.variant] = now;
        LAST_HUMAN_VARIANT_TICK[this.variant] = now;

        int viewers = 0;
        for (ServerPlayer viewer : level.players())
        {
            if (isCommandViewer(level, viewer.position())||viewer==sender&&reviewLoopback(sender.server))
            {
                ClientboundEvaVideoFramePacket.send(viewer, this.variant,
                        frame);
                PerformanceCounters.recordVideoFrame(frame.length);
                viewers++;
            }
        }
        if (acquired)
        {
            ProjectSeele.LOGGER.info(
                    "NERV cockpit video uplink acquired: eva={} pilot={} viewers={}",
                    this.variant, sender.getGameProfile().getName(), viewers);
        }
    }

    public static boolean isFeedActive(ServerLevel level, int variant)
    {
        if (variant < EvaUnit01Entity.UNIT_00
                || variant > EvaUnit01Entity.UNIT_02)
        {
            return false;
        }
        long now = level.getGameTime();
        long accepted = LAST_VARIANT_TICK[variant];
        return now >= accepted && now - accepted <= FEED_ACTIVE_TICKS;
    }
    public static boolean isHumanFeedActive(ServerLevel level, int variant)
    {
        if (variant < EvaUnit01Entity.UNIT_00
                || variant > EvaUnit01Entity.UNIT_02)
        {
            return false;
        }
        long now = level.getGameTime();
        long accepted = LAST_HUMAN_VARIANT_TICK[variant];
        return now >= accepted && now - accepted <= FEED_ACTIVE_TICKS;
    }

    public static boolean hasCommandViewers(ServerLevel level)
    {
        if (!SeeleConfig.videoFrameRelayEnabled())
        {
            return false;
        }
        return level.players().stream().anyMatch(
                viewer -> isCommandViewer(level, viewer.position()));
    }

    /**
     * Tells real pilots whether a remote operator can currently see the command
     * wall. No viewer means no full-frame GPU readback and no PNG work.
     */
    public static void syncCaptureDemand(MinecraftServer server)
    {
        if (!SeeleConfig.liveCockpitVideoEnabled()
                || !SeeleConfig.videoFrameRelayEnabled())
        {
            return;
        }
        ServerLevel level = server.getLevel(GeoFrontCommands.GEOFRONT);
        if (level == null)
        {
            return;
        }
        boolean viewers = level.players().stream().anyMatch(
                viewer -> isCommandViewer(level, viewer.position())
                        && EvaPilotResolver.controlTarget(viewer) == null);
        for (ServerPlayer player : level.players())
        {
            if (EvaPilotResolver.controlTarget(player) != null)
            {
                SeeleNetwork.CHANNEL.send(
                        PacketDistributor.PLAYER.with(() -> player),
                        new ClientboundEvaVideoDemandPacket(viewers));
            }
        }
    }

    /** Relays a server-sampled view only while no real pilot owns this feed. */
    public static void relayTrainingFrame(ServerLevel level, int variant,
                                          byte[] png)
    {
        if (!SeeleConfig.dummyPilotVideoEnabled()
                || !SeeleConfig.videoFrameRelayEnabled()
                || !level.dimension().equals(GeoFrontCommands.GEOFRONT)
                || variant < EvaUnit01Entity.UNIT_00
                || variant > EvaUnit01Entity.UNIT_02
                || isHumanFeedActive(level, variant) || !validFrame(png))
        {
            return;
        }
        LAST_VARIANT_TICK[variant] = level.getGameTime();
        for (ServerPlayer viewer : level.players())
        {
            if (isCommandViewer(level, viewer.position()))
            {
                ClientboundEvaVideoFramePacket.send(viewer, variant, png);
                PerformanceCounters.recordVideoFrame(png.length);
            }
        }
    }

    private static boolean isCommandViewer(ServerLevel level, Vec3 position)
    {
        if(com.projectseele.world.NervRouteRuntimeR52.claimed(level))
        {var frame=com.projectseele.world.NervHeadquartersFrameR52.frame(level);return frame!=null&&frame.apply(legacyCommandArea()).contains(position);}
        if (legacyCommandArea().contains(position))
        {
            return true;
        }
        FacilityV2SavedData facility = FacilityV2SavedData.get(level);
        if (!facility.commissioned()
                || facility.requireZone("COMMAND_VOLUME").state()
                != FacilityV2SavedData.ZoneState.COMPLETE)
        {
            return false;
        }
        BlockPos centre = facility.manifest().centre();
        AABB command = new AABB(
                centre.getX() - 80.0D, -376.0D,
                centre.getZ() - 92.0D,
                centre.getX() + 80.0D, -296.0D,
                centre.getZ() + 92.0D);
        return command.contains(position);
    }

    private static AABB legacyCommandArea()
    {
        BlockPos origin = IntegratedNervMapBuilder.GEOFRONT_ORIGIN;
        return new AABB(origin.getX() - 72.0D, origin.getY() - 35.0D,
                origin.getZ() - 50.0D, origin.getX() + 73.0D,
                origin.getY() + 91.0D, origin.getZ() + 111.0D);
    }

    private static boolean validFrame(byte[] data)
    {
        return EvaFrameCodec.inspect(data) != null;
    }

}
