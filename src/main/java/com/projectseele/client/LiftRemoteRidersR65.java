package com.projectseele.client;

import com.projectseele.ProjectSeele;
import com.projectseele.mixin.client.LivingEntityLerpAccessorR65;
import com.projectseele.world.LiftPassengerPhaseR22;
import net.minecraft.client.player.RemotePlayer;
import net.minecraft.util.Mth;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.AABB;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.fml.event.lifecycle.FMLClientSetupEvent;

/**
 * Other players riding a moving lift car, as this client draws them. Their position comes from the server a link
 * delay late, while this client moves its own car (and its own player) every tick: at 0.85 block a tick the late
 * position sat two to four blocks off the floor, and each tick the car put them back and the interpolation pulled
 * them away again. Another rider shook in place and, going down, floated through the roof. While the car moves,
 * this client now keeps them on its car floor and inside its walls, interpolation target included (R65).
 */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, bus = Mod.EventBusSubscriber.Bus.MOD, value = Dist.CLIENT)
public final class LiftRemoteRidersR65
{
    /** How far (blocks) above or below the car a late rider may still be drawn and be brought back in. */
    private static final double LATE = 6.0D;

    private LiftRemoteRidersR65() {}

    @SubscribeEvent
    public static void setup(FMLClientSetupEvent event)
    {
        LiftPassengerPhaseR22.remoteRiders = LiftRemoteRidersR65::place;
    }

    /** Other players found standing inside a moving car, and the last game tick they were kept in it. */
    private static final java.util.Map<java.util.UUID, Long> RIDERS = new java.util.HashMap<>();

    private static void place(Level level, AABB car, double floor)
    {
        long now = level.getGameTime();
        RIDERS.values().removeIf(tick -> now - tick > 2);
        for (var rider : level.getEntitiesOfClass(RemotePlayer.class, car.inflate(LATE),
                p -> !p.isSpectator() && !p.isPassenger() && !p.noPhysics))
        {
            // A rider is first seen inside the walls; afterwards its late position may trail the car by up to LATE.
            boolean inside = rider.getX() > car.minX + 1 && rider.getX() < car.maxX - 1 && rider.getZ() > car.minZ + 1
                    && rider.getZ() < car.maxZ - 1 && rider.getY() > floor - LATE && rider.getY() < car.maxY + LATE;
            Long last = RIDERS.get(rider.getUUID());
            if (!inside && (last == null || now - last > 2)) continue;
            RIDERS.put(rider.getUUID(), now);
            double margin = 1 + rider.getBbWidth() * .5 + .065;
            double x = Mth.clamp(rider.getX(), car.minX + margin, car.maxX - margin);
            double z = Mth.clamp(rider.getZ(), car.minZ + margin, car.maxZ - margin);
            rider.setPos(x, floor, z);
            var lerp = (LivingEntityLerpAccessorR65) rider;
            if (lerp.seele$lerpSteps() > 0)
            {
                lerp.seele$setLerpX(Mth.clamp(lerp.seele$lerpX(), car.minX + margin, car.maxX - margin));
                lerp.seele$setLerpY(floor);
                lerp.seele$setLerpZ(Mth.clamp(lerp.seele$lerpZ(), car.minZ + margin, car.maxZ - margin));
            }
        }
    }
}
