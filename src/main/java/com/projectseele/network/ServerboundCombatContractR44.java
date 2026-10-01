package com.projectseele.network;

import net.minecraft.network.FriendlyByteBuf;
import net.minecraftforge.network.NetworkEvent;
import java.util.Map;
import java.util.function.Supplier;

public record ServerboundCombatContractR44(Map<String,String> resources)
{
    public ServerboundCombatContractR44(FriendlyByteBuf buffer){this(ClientboundCombatContractR44.read(buffer));}
    public void encode(FriendlyByteBuf buffer){ClientboundCombatContractR44.write(buffer,resources);}
    public static void handle(ServerboundCombatContractR44 packet,Supplier<NetworkEvent.Context> context)
    {
        context.get().enqueueWork(()->CombatBundleGateR44.accept(context.get().getSender(),packet.resources()));
        context.get().setPacketHandled(true);
    }
}
