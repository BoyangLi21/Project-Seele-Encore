package com.projectseele.network;

import net.minecraft.network.FriendlyByteBuf;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.fml.DistExecutor;
import net.minecraftforge.network.NetworkEvent;
import java.util.Objects;
import java.util.UUID;
import java.util.function.Supplier;

/** Bounded mission observation data, never a spawn, movement or damage packet. */
public record ClientboundEncounterObserverPacket(Kind kind, UUID nonce, long generation,
        ResourceLocation dimension, ResourceLocation entityType, long sequence, long serverTick,
        Snapshot snapshot)
{
    public enum Kind { CAPABILITY, STATE, CLEAR }
    public static final int SCHEMA = 1;
    public static final int MAX_BYTES = 1024;
    public static final int STALE_TICKS = 60;
    public static final String RENDERER_ID = "projectseele:ramiel_remote_r45_v1";
    public static final ResourceLocation RAMIEL = new ResourceLocation("projectseele", "ramiel");
    public static final int ALIVE = 1, CHARGING = 2, DRILLING = 4, EXPOSED = 8, ENRAGED = 16;

    public record Snapshot(UUID target, int entityId, int poseTick, Vec3 position, Vec3 velocity,
            float yaw, float pitch, float bodyYaw, float headYaw, float width, float height, float health, float maxHealth,
            float fieldEnergy, float fieldMax, int flags, int beamTicks, Vec3 beamEnd, float drillDepth)
    {
        public Snapshot
        {
            Objects.requireNonNull(target);
            if (entityId < 0 || poseTick < 0 || (flags & ~31) != 0 || beamTicks < 0 || beamTicks > 2000)
                throw new IllegalArgumentException("Observer state identity/time");
            validVector(position, 30_000_000);
            validVector(velocity, 4096);
            validVector(beamEnd, 30_000_000);
            for (float value : new float[]{yaw, pitch, bodyYaw, headYaw, width, height, health, maxHealth,
                    fieldEnergy, fieldMax, drillDepth})
                if (!Float.isFinite(value) || Math.abs(value) > 1_000_000_000)
                    throw new IllegalArgumentException("Non-finite observer state");
            if (width <= 0 || height <= 0 || width > 4096 || height > 4096
                    || health < 0 || maxHealth <= 0 || health > maxHealth + 1 || fieldEnergy < 0
                    || fieldMax <= 0 || fieldEnergy > fieldMax + 1 || drillDepth < 0 || drillDepth > 4096)
                throw new IllegalArgumentException("Observer vitality/depth bounds");
        }
        private Snapshot(FriendlyByteBuf buffer)
        {
            this(buffer.readUUID(), buffer.readVarInt(), buffer.readVarInt(), vector(buffer), vector(buffer),
                    buffer.readFloat(), buffer.readFloat(), buffer.readFloat(), buffer.readFloat(),
                    buffer.readFloat(), buffer.readFloat(),
                    buffer.readFloat(), buffer.readFloat(), buffer.readFloat(), buffer.readFloat(),
                    buffer.readUnsignedByte(), buffer.readVarInt(), vector(buffer), buffer.readFloat());
        }
        private void encode(FriendlyByteBuf buffer)
        {
            buffer.writeUUID(target); buffer.writeVarInt(entityId); buffer.writeVarInt(poseTick);
            vector(buffer, position); vector(buffer, velocity);
            buffer.writeFloat(yaw); buffer.writeFloat(pitch); buffer.writeFloat(bodyYaw); buffer.writeFloat(headYaw);
            buffer.writeFloat(width); buffer.writeFloat(height);
            buffer.writeFloat(health); buffer.writeFloat(maxHealth); buffer.writeFloat(fieldEnergy); buffer.writeFloat(fieldMax);
            buffer.writeByte(flags); buffer.writeVarInt(beamTicks); vector(buffer, beamEnd); buffer.writeFloat(drillDepth);
        }
    }

    public ClientboundEncounterObserverPacket
    {
        Objects.requireNonNull(kind); Objects.requireNonNull(nonce);
        Objects.requireNonNull(dimension); Objects.requireNonNull(entityType);
        if (!RAMIEL.equals(entityType) || generation < 1 || sequence < 0 || serverTick < 0
                || dimension.toString().length() > 128 || (kind == Kind.STATE) != (snapshot != null))
            throw new IllegalArgumentException("Observer envelope");
    }

    public ClientboundEncounterObserverPacket(FriendlyByteBuf buffer)
    {
        this(readKind(buffer), buffer.readUUID(), buffer.readVarLong(), resource(buffer), resource(buffer),
                buffer.readVarLong(), buffer.readVarLong(), readSnapshot(buffer));
        if (buffer.isReadable()) throw new IllegalArgumentException("Observer trailing payload");
    }

    private static Kind readKind(FriendlyByteBuf buffer)
    {
        if (buffer.readableBytes() > MAX_BYTES || buffer.readVarInt() != SCHEMA)
            throw new IllegalArgumentException("Observer size/schema");
        int kind = buffer.readUnsignedByte();
        if (kind >= Kind.values().length) throw new IllegalArgumentException("Observer kind");
        return Kind.values()[kind];
    }

    private static Snapshot readSnapshot(FriendlyByteBuf buffer)
    {
        return buffer.readBoolean() ? new Snapshot(buffer) : null;
    }

    private static ResourceLocation resource(FriendlyByteBuf buffer)
    {
        return Objects.requireNonNull(ResourceLocation.tryParse(buffer.readUtf(128)), "Observer resource id");
    }

    private static void validVector(Vec3 vector, double bound)
    {
        Objects.requireNonNull(vector);
        if (!Double.isFinite(vector.x) || !Double.isFinite(vector.y) || !Double.isFinite(vector.z)
                || Math.abs(vector.x) > bound || Math.abs(vector.y) > bound || Math.abs(vector.z) > bound)
            throw new IllegalArgumentException("Observer vector bounds");
    }

    private static Vec3 vector(FriendlyByteBuf buffer)
    { return new Vec3(buffer.readDouble(), buffer.readDouble(), buffer.readDouble()); }
    private static void vector(FriendlyByteBuf buffer, Vec3 value)
    { buffer.writeDouble(value.x); buffer.writeDouble(value.y); buffer.writeDouble(value.z); }

    public void encode(FriendlyByteBuf buffer)
    {
        int start = buffer.writerIndex();
        buffer.writeVarInt(SCHEMA); buffer.writeByte(kind.ordinal()); buffer.writeUUID(nonce);
        buffer.writeVarLong(generation); buffer.writeUtf(dimension.toString(), 128);
        buffer.writeUtf(entityType.toString(), 128); buffer.writeVarLong(sequence); buffer.writeVarLong(serverTick);
        buffer.writeBoolean(snapshot != null); if (snapshot != null) snapshot.encode(buffer);
        if (buffer.writerIndex() - start > MAX_BYTES) throw new IllegalArgumentException("Observer encoded size");
    }

    public static void handle(ClientboundEncounterObserverPacket packet, Supplier<NetworkEvent.Context> context)
    {
        DistExecutor.unsafeRunWhenOn(Dist.CLIENT,
                () -> () -> com.projectseele.client.EncounterObserverCacheR45.receive(packet));
        context.get().setPacketHandled(true);
    }
}
