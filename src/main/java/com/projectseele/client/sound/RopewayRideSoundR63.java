package com.projectseele.client.sound;

import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.Map;

import com.projectseele.ProjectSeele;
import com.projectseele.registry.ModSounds;

import net.minecraft.client.Minecraft;
import net.minecraft.client.resources.sounds.AbstractTickableSoundInstance;
import net.minecraft.client.resources.sounds.SoundInstance;
import net.minecraft.sounds.SoundSource;
import net.minecraft.util.Mth;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** MTR plays nothing while you ride one of its cable cars, so the cabin gets its own loop. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, value = Dist.CLIENT)
public final class RopewayRideSoundR63
{
    private static boolean unavailable;
    private static Field vehicleId;
    private static Field sidingId;
    private static Method isRiding;
    private static Method clientData;
    private static Field sidingIdMap;
    private static Method transportMode;
    private static Object cableCar;
    private static Hum hum;
    private static int tick;
    private static boolean logged;

    private RopewayRideSoundR63() {}

    @SubscribeEvent
    public static void clientTick(TickEvent.ClientTickEvent event)
    {
        if (event.phase != TickEvent.Phase.END || unavailable)
        {
            return;
        }
        var minecraft = Minecraft.getInstance();
        if (minecraft.player == null || minecraft.level == null)
        {
            stop();
            return;
        }
        if (++tick % 5 != 0)
        {
            return;
        }
        if (ridingCableCar())
        {
            if (hum == null || hum.isStopped())
            {
                hum = new Hum();
                minecraft.getSoundManager().play(hum);
                if (!logged)
                {
                    logged = true;
                    ProjectSeele.LOGGER.info("Ropeway cabin sound started");
                }
            }
        }
        else
        {
            stop();
        }
    }

    private static void stop()
    {
        if (hum != null)
        {
            hum.release();
            hum = null;
        }
    }

    private static boolean ridingCableCar()
    {
        try
        {
            if (vehicleId == null)
            {
                bind();
            }
            if (!(Boolean) isRiding.invoke(null, vehicleId.getLong(null)))
            {
                return false;
            }
            Object siding = ((Map<?, ?>) sidingIdMap.get(clientData.invoke(null))).get(sidingId.getLong(null));
            return siding != null && transportMode.invoke(siding) == cableCar;
        }
        catch (ReflectiveOperationException | RuntimeException | LinkageError failure)
        {
            unavailable = true;
            ProjectSeele.LOGGER.info("Ropeway cabin sound off: MTR riding state unavailable ({})", failure.toString());
            return false;
        }
    }

    private static void bind() throws ReflectiveOperationException
    {
        Class<?> riding = Class.forName("org.mtr.mod.client.VehicleRidingMovement");
        Field vehicle = riding.getDeclaredField("ridingVehicleId");
        Field siding = riding.getDeclaredField("ridingSidingId");
        vehicle.setAccessible(true);
        siding.setAccessible(true);
        isRiding = riding.getMethod("isRiding", long.class);
        clientData = Class.forName("org.mtr.mod.client.MinecraftClientData").getMethod("getInstance");
        sidingIdMap = Class.forName("org.mtr.core.data.Data").getField("sidingIdMap");
        transportMode = Class.forName("org.mtr.core.data.NameColorDataBase").getMethod("getTransportMode");
        cableCar = Class.forName("org.mtr.core.data.TransportMode").getField("CABLE_CAR").get(null);
        sidingId = siding;
        vehicleId = vehicle;
    }

    /** Plays at the listener, so it sounds the same wherever the camera sits in the cabin. */
    private static final class Hum extends AbstractTickableSoundInstance
    {
        private boolean releasing;
        private float level;

        Hum()
        {
            super(ModSounds.ROPEWAY_RIDE.get(), SoundSource.AMBIENT, SoundInstance.createUnseededRandom());
            this.looping = true;
            this.delay = 0;
            this.relative = true;
            this.attenuation = SoundInstance.Attenuation.NONE;
            this.volume = 0.01F;
        }

        void release()
        {
            this.releasing = true;
        }

        @Override
        public void tick()
        {
            this.level = Mth.clamp(this.level + (this.releasing ? -0.05F : 0.05F), 0.0F, 1.0F);
            this.volume = Math.max(0.01F, 0.6F * this.level);
            if (this.releasing && this.level <= 0.0F)
            {
                this.stop();
            }
        }
    }
}
