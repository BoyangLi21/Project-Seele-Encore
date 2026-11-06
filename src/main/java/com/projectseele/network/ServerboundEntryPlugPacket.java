package com.projectseele.network;

import java.util.function.Supplier;

import com.projectseele.entity.EntryPlugCarrierEntity;
import com.projectseele.entity.EvaUnit01Entity;
import net.minecraft.network.FriendlyByteBuf;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.Entity;
import net.minecraftforge.network.NetworkEvent;

/** Extended right-click ray for synthetic dorsal plug hardware outside the AABB. */
public class ServerboundEntryPlugPacket
{
    private final int entityId;

    public ServerboundEntryPlugPacket(int entityId)
    {
        this.entityId = entityId;
    }

    public ServerboundEntryPlugPacket(FriendlyByteBuf buf)
    {
        this(buf.readVarInt());
    }

    public void encode(FriendlyByteBuf buf)
    {
        buf.writeVarInt(this.entityId);
    }

    public void handle(Supplier<NetworkEvent.Context> ctx)
    {
        NetworkEvent.Context context = ctx.get();
        ServerPlayer sender = context.getSender();
        context.enqueueWork(() ->
        {
            if (sender == null || sender.isPassenger())
            {
                return;
            }
            Entity target = sender.serverLevel().getEntity(this.entityId);
            if (target instanceof EntryPlugCarrierEntity plug)
            {
                plug.tryBoardFromHatch(sender);
            }
            else if (target instanceof EvaUnit01Entity eva)
            {
                // Legacy standalone-silo compatibility. Canonical GeoFront
                // boarding is handled by the physical carrier branch above.
                eva.tryEnterFromPlug(sender);
            }
        });
        context.setPacketHandled(true);
    }
}
