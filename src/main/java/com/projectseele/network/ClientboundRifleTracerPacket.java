package com.projectseele.network;

import java.util.function.Supplier;

import net.minecraft.network.FriendlyByteBuf;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.fml.DistExecutor;
import net.minecraftforge.network.NetworkEvent;

/** One short-lived, non-explosive pallet-SMG tracer. */
public class ClientboundRifleTracerPacket
{
    public final int entityId;
    public final double x1;
    public final double y1;
    public final double z1;
    public final double x2;
    public final double y2;
    public final double z2;

    public ClientboundRifleTracerPacket(int entityId,
                                        double x1, double y1, double z1,
                                        double x2, double y2, double z2)
    {
        this.entityId = entityId;
        this.x1 = x1;
        this.y1 = y1;
        this.z1 = z1;
        this.x2 = x2;
        this.y2 = y2;
        this.z2 = z2;
    }

    public ClientboundRifleTracerPacket(FriendlyByteBuf buffer)
    {
        this(buffer.readVarInt(),
                buffer.readDouble(), buffer.readDouble(), buffer.readDouble(),
                buffer.readDouble(), buffer.readDouble(), buffer.readDouble());
    }

    public void encode(FriendlyByteBuf buffer)
    {
        buffer.writeVarInt(this.entityId);
        buffer.writeDouble(this.x1);
        buffer.writeDouble(this.y1);
        buffer.writeDouble(this.z1);
        buffer.writeDouble(this.x2);
        buffer.writeDouble(this.y2);
        buffer.writeDouble(this.z2);
    }

    public void handle(Supplier<NetworkEvent.Context> context)
    {
        if(com.projectseele.visual.NpcCombatR30Review.ENABLED&&entityId==com.projectseele.visual.NpcCombatR30Review.evaId)com.projectseele.visual.NpcCombatR30Review.tracerPackets++;
        var networkContext=context.get();
        // Effects and sound share client state with rendering, never Netty.
        networkContext.enqueueWork(() -> DistExecutor.unsafeRunWhenOn(Dist.CLIENT,
                () -> () -> com.projectseele.client.fx.ClientFxManager.addRifleTracer(this)));
        networkContext.setPacketHandled(true);
    }
}
