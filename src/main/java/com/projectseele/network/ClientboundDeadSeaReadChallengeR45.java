package com.projectseele.network;
import java.util.UUID;
import java.util.function.Supplier;
import net.minecraft.network.FriendlyByteBuf;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.fml.DistExecutor;
import net.minecraftforge.network.NetworkEvent;
public record ClientboundDeadSeaReadChallengeR45(UUID nonce,String revision,int pages)
{
    public ClientboundDeadSeaReadChallengeR45
    {if(nonce==null||!revision.matches("[0-9a-f]{64}")||pages<1||pages>64)throw new IllegalArgumentException("Archive challenge");}
    public ClientboundDeadSeaReadChallengeR45(FriendlyByteBuf buffer){this(buffer.readUUID(),buffer.readUtf(64),buffer.readVarInt());}
    public void encode(FriendlyByteBuf buffer){buffer.writeUUID(nonce);buffer.writeUtf(revision,64);buffer.writeVarInt(pages);}
    public void handle(Supplier<NetworkEvent.Context> supplier)
    {DistExecutor.unsafeRunWhenOn(Dist.CLIENT,()->()->com.projectseele.client.DeadSeaArchiveScreenR45.attachReadChallenge(nonce,revision,pages));supplier.get().setPacketHandled(true);}
}
