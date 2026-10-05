package com.projectseele.world;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.NervSlidingDoorEntity;
import com.projectseele.registry.ModSounds;
import net.minecraft.sounds.SoundSource;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.util.Map;
import java.util.WeakHashMap;

/** Audible pressure-door movement follows the existing entity, including command-room doors. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID)
public final class FacilityDoorSoundsR47
{
    private static final Map<NervSlidingDoorEntity, Contact> CONTACTS = new WeakHashMap<>();
    private static final class Contact { float position; boolean moving; }

    @SubscribeEvent
    public static void tick(TickEvent.ServerTickEvent event)
    {
        if (event.phase != TickEvent.Phase.END) return;
        for (var level : event.getServer().getAllLevels())
        {
            for (var entity : level.getAllEntities())
            {
                if (!(entity instanceof NervSlidingDoorEntity door) || door.isSilent()) continue;
                float position = door.getOpenProgress(1);
                var previous = CONTACTS.get(door);
                if (previous == null)
                {
                    previous = new Contact(); previous.position = position;
                    CONTACTS.put(door, previous); continue;
                }
                boolean moving = Math.abs(position - previous.position) > .0001F;
                if (moving && !previous.moving)
                    level.playSound(null, door.getX(), door.getY() + 1.5, door.getZ(),
                            ModSounds.PRESSURE_DOOR_MOTION.get(), SoundSource.BLOCKS, .55F, 1F);
                if (!moving && previous.moving && (position < .01F || position > .99F))
                    level.playSound(null, door.getX(), door.getY() + 1.5, door.getZ(),
                            ModSounds.PERSONNEL_DOOR_CLOSE.get(), SoundSource.BLOCKS, .48F, position < .01F ? 1 : 1.15F);
                previous.position = position; previous.moving = moving;
            }
        }
    }

    private FacilityDoorSoundsR47() {}
}
