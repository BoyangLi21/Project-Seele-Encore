package com.projectseele.network;

import net.minecraft.network.FriendlyByteBuf;
import net.minecraftforge.network.NetworkEvent;
import java.util.Map;
import java.util.TreeMap;
import java.util.function.Supplier;

/** Only gameplay-critical contracts are synchronized; visual packs stay local. */
public record ClientboundCombatContractR44(Map<String,String> resources)
{
    public ClientboundCombatContractR44(FriendlyByteBuf buffer){this(read(buffer));}
    public void encode(FriendlyByteBuf buffer){write(buffer,resources);}
    static Map<String,String> read(FriendlyByteBuf buffer)
    {
        int count=buffer.readVarInt();if(count<1||count>16)throw new IllegalArgumentException("Combat contract entry count");
        Map<String,String> values=new TreeMap<>();
        for(int i=0;i<count;i++)
            if(values.put(buffer.readUtf(64),buffer.readUtf(160))!=null)throw new IllegalArgumentException("Duplicate combat contract entry");
        return Map.copyOf(values);
    }
    static void write(FriendlyByteBuf buffer,Map<String,String> values)
    {
        buffer.writeVarInt(values.size());
        new TreeMap<>(values).forEach((name,hash)->{buffer.writeUtf(name,64);buffer.writeUtf(hash,160);});
    }
    public static void handle(ClientboundCombatContractR44 packet,Supplier<NetworkEvent.Context> context)
    {
        context.get().enqueueWork(()->com.projectseele.client.CombatContractClientR44.receive(packet));
        context.get().setPacketHandled(true);
    }
}
