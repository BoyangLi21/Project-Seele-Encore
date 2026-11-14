package com.projectseele.client.sound;

import com.projectseele.network.ClientboundHeadsetSoundPacket;
import net.minecraft.client.Minecraft;
import net.minecraft.client.resources.sounds.SimpleSoundInstance;
import net.minecraft.client.resources.sounds.SoundInstance;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.sounds.SoundSource;

/** Sounds the server places at the listener's ear: relative, unattenuated, like the Angel alarm. */
public final class HeadsetSoundsR64
{
    // The distant echo of a city-wide attack: three late reflections, each quieter and darker
    // (VenueReverbR61 low-passes and wets them), as from hills and towers at different ranges.
    private static final int[] ECHO_DELAY_TICKS = {9, 18, 32};
    private static final float[] ECHO_GAIN = {.50F, .35F, .22F};
    private static final float ECHO_PITCH = .94F;

    private HeadsetSoundsR64() {}

    public static void play(ClientboundHeadsetSoundPacket packet)
    {
        var sounds = Minecraft.getInstance().getSoundManager();
        if (!packet.echo)
        {
            sounds.play(new HeadsetTake(packet.sound, packet.source, packet.volume, packet.pitch, 0));
            return;
        }
        for (int i = 0; i < ECHO_DELAY_TICKS.length; i++)
            sounds.play(new EchoTake(packet.sound, packet.source, packet.volume * ECHO_GAIN[i], packet.pitch * ECHO_PITCH, ECHO_DELAY_TICKS[i]));
    }

    public static class HeadsetTake extends SimpleSoundInstance
    {
        HeadsetTake(ResourceLocation sound, SoundSource source, float volume, float pitch, int delay)
        {
            super(sound, source, Math.min(1F, volume), pitch, SoundInstance.createUnseededRandom(), false, delay,
                    SoundInstance.Attenuation.NONE, 0, 0, 0, true);
        }
    }

    /** Marks the echo copies so the reverb code can low-pass them and send them to the city-night reverb. */
    public static final class EchoTake extends HeadsetTake
    {
        EchoTake(ResourceLocation sound, SoundSource source, float volume, float pitch, int delay)
        {
            super(sound, source, volume, pitch, delay);
        }
    }
}
