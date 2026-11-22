package com.projectseele.client;

import com.projectseele.client.sound.AlarmSoundInstance;
import net.minecraft.client.Minecraft;

/**
 * Client-side Angel-alarm flag, driven purely by server packets. Flipping it
 * starts/stops the looping siren; the overlay reads the flag every frame.
 */
public final class ClientAlarmState
{
    private static boolean active;
    /** R65: the dry facility take and the open-city take, started together and crossfaded by place. */
    private static AlarmSoundInstance siren, city;

    private ClientAlarmState() {}

    public static void setActive(boolean value)
    {
        if (active == value)
        {
            return;
        }
        active = value;
        if (value)
        {
            siren = new AlarmSoundInstance(false);
            city = new AlarmSoundInstance(true);
            Minecraft.getInstance().getSoundManager().play(siren);
            Minecraft.getInstance().getSoundManager().play(city);
        }
        else
        {
            stopSirens();
        }
    }

    /** Disconnect is a new alarm session even if the last server never sent its stop packet. */
    public static void resetConnectionR45()
    {
        active=false;
        stopSirens();
    }

    private static void stopSirens()
    {
        var sounds = Minecraft.getInstance().getSoundManager();
        if (siren != null) sounds.stop(siren);
        if (city != null) sounds.stop(city);
        siren = null;
        city = null;
    }

    public static boolean isActive()
    {
        return active;
    }
}
