package com.projectseele.network;

import com.projectseele.world.StreetPassCellsR64;
import com.projectseele.world.StreetPassR64;
import java.util.List;
import java.util.function.Supplier;
import net.minecraft.network.FriendlyByteBuf;
import net.minecraft.resources.ResourceLocation;
import net.minecraftforge.network.NetworkEvent;

/** The street furniture a giant walks through in the level the player is in (StreetPassR64); empty cells clear it. */
public class ClientboundStreetPassR64
{
    private final ResourceLocation dimension;
    private final List<String> blocks;
    private final byte[] cells;

    public ClientboundStreetPassR64(ResourceLocation dimension, List<String> blocks, byte[] cells)
    {
        this.dimension = dimension;
        this.blocks = blocks;
        this.cells = cells;
    }

    public ClientboundStreetPassR64(FriendlyByteBuf buf)
    {
        this(buf.readResourceLocation(), buf.readList(b -> b.readUtf(256)), buf.readByteArray(StreetPassCellsR64.MAX_ENCODED));
    }

    public void encode(FriendlyByteBuf buf)
    {
        buf.writeResourceLocation(this.dimension);
        buf.writeCollection(this.blocks, (b, name) -> b.writeUtf(name, 256));
        buf.writeByteArray(this.cells);
    }

    public void handle(Supplier<NetworkEvent.Context> ctx)
    {
        StreetPassR64.receive(this.dimension, this.blocks, this.cells);
        ctx.get().setPacketHandled(true);
    }
}
