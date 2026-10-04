package com.projectseele.network;

import net.minecraft.network.FriendlyByteBuf;
import net.minecraft.resources.ResourceLocation;
import net.minecraftforge.network.NetworkEvent;
import com.projectseele.world.EncounterObserverR45;
import java.util.Objects;
import java.util.UUID;
import java.util.function.Supplier;

/** Capability and first real draw are distinct; receiving a snapshot cannot claim its first draw. */
public record ServerboundEncounterObserverReadyPacket(Kind kind, UUID nonce, long generation,
        ResourceLocation dimension, UUID target, long sequence, long serverTick,
        String resourceSha256, String rendererId)
{
    public enum Kind { CAPABILITY, FRAME, RECEIPT, DISABLE }
    public static final int MAX_BYTES = 512;

    public ServerboundEncounterObserverReadyPacket
    {
        Objects.requireNonNull(kind); Objects.requireNonNull(nonce); Objects.requireNonNull(dimension);
        Objects.requireNonNull(resourceSha256); Objects.requireNonNull(rendererId);
        if (generation < 1 || sequence < 0 || serverTick < 0 || dimension.toString().length() > 128
                || !resourceSha256.matches("[0-9a-f]{64}")
                || !rendererId.matches("[a-zA-Z0-9_.:/-]{3,64}")
                || ((kind == Kind.FRAME || kind == Kind.RECEIPT) && target == null))
            throw new IllegalArgumentException("Observer ACK identity/capability");
    }

    public ServerboundEncounterObserverReadyPacket(FriendlyByteBuf buffer)
    {
        this(readKind(buffer), buffer.readUUID(), buffer.readVarLong(),
                Objects.requireNonNull(ResourceLocation.tryParse(buffer.readUtf(128))),
                buffer.readBoolean() ? buffer.readUUID() : null, buffer.readVarLong(), buffer.readVarLong(),
                buffer.readUtf(64), buffer.readUtf(64));
        if (buffer.isReadable()) throw new IllegalArgumentException("Observer ACK trailing payload");
    }

    private static Kind readKind(FriendlyByteBuf buffer)
    {
        if (buffer.readableBytes() > MAX_BYTES || buffer.readVarInt() != ClientboundEncounterObserverPacket.SCHEMA)
            throw new IllegalArgumentException("Observer ACK size/schema");
        int kind = buffer.readUnsignedByte();
        if (kind >= Kind.values().length) throw new IllegalArgumentException("Observer ACK kind");
        return Kind.values()[kind];
    }

    public void encode(FriendlyByteBuf buffer)
    {
        int start = buffer.writerIndex();
        buffer.writeVarInt(ClientboundEncounterObserverPacket.SCHEMA); buffer.writeByte(kind.ordinal());
        buffer.writeUUID(nonce); buffer.writeVarLong(generation); buffer.writeUtf(dimension.toString(), 128);
        buffer.writeBoolean(target != null); if (target != null) buffer.writeUUID(target);
        buffer.writeVarLong(sequence); buffer.writeVarLong(serverTick);
        buffer.writeUtf(resourceSha256, 64); buffer.writeUtf(rendererId, 64);
        if (buffer.writerIndex() - start > MAX_BYTES) throw new IllegalArgumentException("Observer ACK encoded size");
    }

    public static void handle(ServerboundEncounterObserverReadyPacket packet, Supplier<NetworkEvent.Context> context)
    {
        EncounterObserverR45.accept(context.get().getSender(), packet);
        context.get().setPacketHandled(true);
    }
}
