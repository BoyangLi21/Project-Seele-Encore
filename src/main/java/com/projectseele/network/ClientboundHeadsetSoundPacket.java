package com.projectseele.network;

import java.util.function.Supplier;

import net.minecraft.network.FriendlyByteBuf;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.sounds.SoundSource;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.fml.DistExecutor;
import net.minecraftforge.network.NetworkEvent;

/**
 * A sound played at the listener's ear instead of at a place: mission alarms and PA lines for the sortie
 * participants wherever they are, or, as an echo, the distant reflections of a city-wide Angel attack.
 */
public class ClientboundHeadsetSoundPacket
{
    public final ResourceLocation sound;
    public final SoundSource source;
    public final float volume;
    public final float pitch;
    public final boolean echo;

    public ClientboundHeadsetSoundPacket(ResourceLocation sound, SoundSource source, float volume, float pitch, boolean echo)
    {
        this.sound = sound;
        this.source = source;
        this.volume = volume;
        this.pitch = pitch;
        this.echo = echo;
    }

    public ClientboundHeadsetSoundPacket(FriendlyByteBuf buf)
    {
        this(buf.readResourceLocation(), buf.readEnum(SoundSource.class), buf.readFloat(), buf.readFloat(), buf.readBoolean());
    }

    public void encode(FriendlyByteBuf buf)
    {
        buf.writeResourceLocation(this.sound);
        buf.writeEnum(this.source);
        buf.writeFloat(this.volume);
        buf.writeFloat(this.pitch);
        buf.writeBoolean(this.echo);
    }

    public void handle(Supplier<NetworkEvent.Context> ctx)
    {
        DistExecutor.unsafeRunWhenOn(Dist.CLIENT,
                () -> () -> com.projectseele.client.sound.HeadsetSoundsR64.play(this));
        ctx.get().setPacketHandled(true);
    }
}
