package com.projectseele.network;

import net.minecraft.network.FriendlyByteBuf;
import net.minecraftforge.network.NetworkEvent;
import java.util.function.Supplier;

/** No client-supplied slot, variant, actor identity or exit coordinate. */
public final class ServerboundSynchLabExitR47
{
    public ServerboundSynchLabExitR47() {}
    public ServerboundSynchLabExitR47(FriendlyByteBuf buffer) {}
    public void encode(FriendlyByteBuf buffer) {}
    public void handle(Supplier<NetworkEvent.Context> supplier)
    {
        var context=supplier.get();var player=context.getSender();
        context.enqueueWork(()->{
            if(player!=null)
            {
                long now=player.serverLevel().getGameTime();var data=player.getPersistentData();
                if(now>=data.getLong("R47LabExitAfter"))
                {data.putLong("R47LabExitAfter",now+5);com.projectseele.world.SynchLabDirectorR47.requestExit(player);}
            }
        });context.setPacketHandled(true);
    }
}
