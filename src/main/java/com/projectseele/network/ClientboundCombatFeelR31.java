package com.projectseele.network;

import com.projectseele.entity.CombatFeelR31;
import net.minecraft.network.FriendlyByteBuf;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.network.NetworkEvent;
import java.util.function.Supplier;

public record ClientboundCombatFeelR31(int entity,CombatFeelR31.Beat beat,float phase,float push)
{
    public ClientboundCombatFeelR31(int entity,CombatFeelR31.Beat beat,float phase){this(entity,beat,phase,0);}
    public ClientboundCombatFeelR31(FriendlyByteBuf b){this(b.readVarInt(),new CombatFeelR31.Beat(b.readVarInt(),b.readLong(),b.readVarInt(),new Vec3(b.readFloat(),b.readFloat(),b.readFloat()),b.readFloat(),b.readVarInt()),b.readFloat(),b.readFloat());}
    public void encode(FriendlyByteBuf b){b.writeVarInt(entity);b.writeVarInt(beat.kind());b.writeLong(beat.start());b.writeVarInt(beat.duration());b.writeFloat((float)beat.direction().x);b.writeFloat((float)beat.direction().y);b.writeFloat((float)beat.direction().z);b.writeFloat(beat.strength());b.writeVarInt(beat.stopTicks());b.writeFloat(phase);b.writeFloat(push);}
    public static void handle(ClientboundCombatFeelR31 p,Supplier<NetworkEvent.Context> c)
    {c.get().enqueueWork(()->com.projectseele.client.CombatFeelClientR31.receive(p));c.get().setPacketHandled(true);}
}
