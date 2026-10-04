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
    private static AlarmSoundInstance siren;

    private ClientAlarmState() {}

    public static void setActive(boolean value)
    {
        if (active == value)
        {
            return;
        }
        active = value;
        Minecraft minecraft = Minecraft.getInstance();
        if (value)
        {
            siren = new AlarmSoundInstance();
            minecraft.getSoundManager().play(siren);
        }
        else if (siren != null)
        {
            minecraft.getSoundManager().stop(siren);
            siren = null;
        }
    }

    /** Disconnect is a new alarm session even if the last server never sent its stop packet. */
    public static void resetConnectionR45()
    {
        active=false;
        if(siren!=null)Minecraft.getInstance().getSoundManager().stop(siren);
        siren=null;
    }
    public static boolean isActive()
    {
        return active;
    }
}
