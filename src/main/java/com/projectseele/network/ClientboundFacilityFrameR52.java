package com.projectseele.network;

import java.util.function.Supplier;
import net.minecraft.core.BlockPos;
import net.minecraft.network.FriendlyByteBuf;
import net.minecraft.resources.ResourceLocation;
import net.minecraftforge.network.NetworkEvent;

/** Server map ownership, independent of a remote marker chunk being rendered. */
public record ClientboundFacilityFrameR52(ResourceLocation dimension,boolean claimed,long epoch,
                                        boolean headquartersBound,BlockPos headquartersTranslation,String uprightGuideSourceSHA)
{
    public ClientboundFacilityFrameR52
    {if(dimension==null||epoch<0||claimed&&epoch==0||headquartersTranslation==null
            ||headquartersBound&&(!claimed||headquartersTranslation.equals(BlockPos.ZERO))||uprightGuideSourceSHA==null
            ||!uprightGuideSourceSHA.isEmpty()&&(!claimed||!uprightGuideSourceSHA.matches("[0-9a-f]{64}")||uprightGuideSourceSHA.equals("0".repeat(64))))throw new IllegalArgumentException("Actual facility claim/source required");}
    public ClientboundFacilityFrameR52(ResourceLocation dimension,boolean claimed,long epoch,boolean headquartersBound,BlockPos headquartersTranslation)
    {this(dimension,claimed,epoch,headquartersBound,headquartersTranslation,"");}
    public ClientboundFacilityFrameR52(ResourceLocation dimension,boolean claimed,long epoch)
    {this(dimension,claimed,epoch,false,BlockPos.ZERO);}
    public ClientboundFacilityFrameR52(FriendlyByteBuf buffer)
    {this(buffer.readResourceLocation(),buffer.readBoolean(),buffer.readVarLong(),buffer.readBoolean(),buffer.readBlockPos(),buffer.readUtf(64));}
    public void encode(FriendlyByteBuf buffer)
    {buffer.writeResourceLocation(dimension);buffer.writeBoolean(claimed);buffer.writeVarLong(epoch);buffer.writeBoolean(headquartersBound);buffer.writeBlockPos(headquartersTranslation);buffer.writeUtf(uprightGuideSourceSHA,64);}
    public static void handle(ClientboundFacilityFrameR52 packet,Supplier<NetworkEvent.Context> context)
    {context.get().enqueueWork(()->com.projectseele.client.FacilityFrameClientR52.receive(packet));context.get().setPacketHandled(true);}
}
