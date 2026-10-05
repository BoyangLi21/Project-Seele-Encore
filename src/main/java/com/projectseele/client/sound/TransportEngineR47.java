package com.projectseele.client.sound;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.UNTransportEntity;
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
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

/** Both NERV and UN aircraft keep one spatial engine, including hovering/hoisting. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, value = Dist.CLIENT)
public final class TransportEngineR47
{
    private static final Map<UUID, Engine> ENGINES = new HashMap<>();
    private static Object previousLevel;

    @SubscribeEvent
    public static void tick(TickEvent.ClientTickEvent event)
    {
        if (event.phase != TickEvent.Phase.END) return;
        var minecraft = Minecraft.getInstance();
        if (minecraft.level != previousLevel)
        {
            for (var sound : ENGINES.values()) minecraft.getSoundManager().stop(sound);
            ENGINES.clear(); previousLevel = minecraft.level;
        }
        if (minecraft.level == null || minecraft.player == null) return;
        ENGINES.entrySet().removeIf(entry -> entry.getValue().isStopped());
        for (var entity : minecraft.level.entitiesForRendering())
        {
            if (!(entity instanceof UNTransportEntity aircraft) || aircraft.groundCart()
                    || aircraft.isSilent() || aircraft.distanceToSqr(minecraft.player) > 256 * 256) continue;
            var engine = ENGINES.get(aircraft.getUUID());
            if (engine == null || (engine.age > 40 && !minecraft.getSoundManager().isActive(engine)))
            {
                if (engine != null) minecraft.getSoundManager().stop(engine);
                engine = new Engine(aircraft); ENGINES.put(aircraft.getUUID(), engine);
                minecraft.getSoundManager().play(engine);
            }
        }
    }

    private static final class Engine extends AbstractTickableSoundInstance
    {
        private final UNTransportEntity aircraft;
        private net.minecraft.world.phys.Vec3 previous;
        private float spool;
        private int age;

        private Engine(UNTransportEntity aircraft)
        {
            super(ModSounds.TRANSPORT_ENGINE.get(), SoundSource.NEUTRAL, SoundInstance.createUnseededRandom());
            this.aircraft = aircraft; previous = aircraft.position();
            looping = true; delay = 0; relative = false; volume = .01F;
            x = aircraft.getX(); y = aircraft.getY() + 9; z = aircraft.getZ();
        }

        @Override public void tick()
        {
            age++;
            var minecraft = Minecraft.getInstance();
            if (aircraft.isRemoved() || aircraft.groundCart() || aircraft.isSilent()
                    || minecraft.level != aircraft.level() || minecraft.player == null
                    || aircraft.distanceToSqr(minecraft.player) > 280 * 280)
            { stop(); return; }
            var position = aircraft.renderFlightPosition(1);
            double speed = position.distanceTo(previous); previous = position;
            // Actual ascent/descent and horizontal travel drive throttle; no timer or phase guess.
            float throttle = Mth.clamp((float) speed * .55F, 0, 1);
            spool = Mth.approach(spool, 1, .035F);
            volume = spool * (.58F + .64F * throttle);
            pitch = Mth.lerp(throttle, .86F, 1.12F);
            x = position.x; y = position.y + 9; z = position.z;
        }
    }

    private TransportEngineR47() {}
}
