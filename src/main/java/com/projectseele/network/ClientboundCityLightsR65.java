package com.projectseele.network;

import java.util.function.Supplier;
import net.minecraft.network.FriendlyByteBuf;
import net.minecraft.resources.ResourceLocation;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.fml.DistExecutor;
import net.minecraftforge.network.NetworkEvent;

/** A single endpoint value, or one measured retraction per moving light owner. 255 means unknown. */
public record ClientboundCityLightsR65(ResourceLocation dimension, byte[] retractions)
{
    public ClientboundCityLightsR65(FriendlyByteBuf b)
    {
        this(b.readResourceLocation(), b.readByteArray(100));
    }

    public void encode(FriendlyByteBuf b)
    {
        b.writeResourceLocation(dimension);
        b.writeByteArray(retractions);
    }

    public void handle(Supplier<NetworkEvent.Context> context)
    {
        DistExecutor.unsafeRunWhenOn(Dist.CLIENT, () -> () ->
                com.projectseele.client.CityNightLightsR65.receive(dimension, retractions));
        context.get().setPacketHandled(true);
    }
}
