package com.projectseele.network;
import java.util.UUID;
import java.util.function.Supplier;
import net.minecraft.network.FriendlyByteBuf;
import net.minecraft.network.chat.Component;
import net.minecraftforge.network.NetworkEvent;
public record ServerboundDeadSeaReadPageR45(UUID nonce,int page,String revision)
{
    public ServerboundDeadSeaReadPageR45(FriendlyByteBuf buffer){this(buffer.readUUID(),buffer.readVarInt(),buffer.readUtf(64));}
    public void encode(FriendlyByteBuf buffer){buffer.writeUUID(nonce);buffer.writeVarInt(page);buffer.writeUtf(revision,64);}
    public void handle(Supplier<NetworkEvent.Context> supplier)
    {
        var context=supplier.get();var player=context.getSender();context.enqueueWork(()->{
            if(player==null)return;boolean accepted=com.projectseele.world.DeadSeaReadingR45.confirmPage(player,nonce,page,revision);
            player.displayClientMessage(Component.literal(accepted?"已阅。":"请回到书台，重新翻开文书。"),true);
        });context.setPacketHandled(true);
    }
}
