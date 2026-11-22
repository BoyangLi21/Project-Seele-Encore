package com.projectseele.client.sound;

import com.projectseele.registry.ModSounds;
import net.minecraft.client.resources.sounds.AbstractTickableSoundInstance;
import net.minecraft.client.resources.sounds.SoundInstance;
import net.minecraft.sounds.SoundSource;
import net.minecraft.util.Mth;

/**
 * The looping air-raid siren. Global (no attenuation): the whole city hears the Angel coming. Stopped externally by
 * {@code ClientAlarmState}.
 *
 * R65 (owner, 2026-11-22): the alarm follows the listener's place. Two loops of one length start together: the dry
 * facility horn, which VenueReverbR61 gives the hangar's, cavern's, shaft's or room's reverb, and the open-city take
 * with far horns echoing across Tokyo-3. Each tick moves the mix toward the city take under open sky and toward the
 * dry one indoors, over about a second.
 */
public class AlarmSoundInstance extends AbstractTickableSoundInstance
{
    /** Kept below the action so the siren reads as backdrop; R65 owner: quieter than the 0.45 it had. */
    static final float VOLUME = 0.30F;
    private static final float FADE_PER_TICK = 0.05F;
    private final boolean city;
    private float open;

    public AlarmSoundInstance(boolean city)
    {
        super((city ? ModSounds.ALARM_CITY : ModSounds.ALARM).get(), SoundSource.HOSTILE, SoundInstance.createUnseededRandom());
        this.city = city;
        this.looping = true;
        this.delay = 0;
        this.relative = true;
        this.attenuation = SoundInstance.Attenuation.NONE;
        this.x = 0.0D;
        this.y = 0.0D;
        this.z = 0.0D;
        this.open = VenueReverbR61.outdoors() ? 1F : 0F;
        this.volume = gain();
    }

    /** Equal power, so the two together keep one loudness through the crossfade. */
    private float gain()
    {
        float angle = this.open * (float) (Math.PI / 2);
        return VOLUME * (this.city ? Mth.sin(angle) : Mth.cos(angle));
    }

    /** The take that is silent where the alarm starts must still start, in step with the other. */
    @Override
    public boolean canStartSilent()
    {
        return true;
    }

    @Override
    public void tick()
    {
        float target = VenueReverbR61.outdoors() ? 1F : 0F;
        this.open += Mth.clamp(target - this.open, -FADE_PER_TICK, FADE_PER_TICK);
        this.volume = gain();
    }
}
