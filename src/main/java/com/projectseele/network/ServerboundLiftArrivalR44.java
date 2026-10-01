package com.projectseele.network;

import com.projectseele.world.NervLiftArrivalSyncR44;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.network.FriendlyByteBuf;
import net.minecraftforge.network.NetworkEvent;
import java.util.function.Supplier;

/** Acknowledges client-side cage placement; this grants no control over doors. */
public record ServerboundLiftArrivalR44(BlockPos controller, Direction facing)
{
    public ServerboundLiftArrivalR44(FriendlyByteBuf buffer)
    { this(buffer.readBlockPos(),buffer.readEnum(Direction.class)); }
    public void encode(FriendlyByteBuf buffer)
    { buffer.writeBlockPos(controller);buffer.writeEnum(facing); }
    public static void handle(ServerboundLiftArrivalR44 packet,Supplier<NetworkEvent.Context> context)
    {
        context.get().enqueueWork(()->NervLiftArrivalSyncR44.request(context.get().getSender(),packet.controller,packet.facing));
        context.get().setPacketHandled(true);
    }
}
