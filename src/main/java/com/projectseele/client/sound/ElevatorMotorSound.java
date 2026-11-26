package com.projectseele.client.sound;

import com.projectseele.ProjectSeele;
import com.projectseele.registry.ModSounds;
import com.supermartijn642.movingelevators.elevator.ElevatorGroupCapability;
import net.minecraft.client.Minecraft;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.client.resources.sounds.AbstractTickableSoundInstance;
import net.minecraft.client.resources.sounds.SoundInstance;
import net.minecraft.sounds.SoundSource;
import net.minecraft.util.Mth;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** A quiet motor at the moving cabin, audible to passengers and nearby landings. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, value = Dist.CLIENT)
public final class ElevatorMotorSound extends AbstractTickableSoundInstance {
    private static ElevatorMotorSound motor;
    private final ClientLevel world;
    private boolean moving;

    private ElevatorMotorSound(ClientLevel world, Vec3 position) {
        super(ModSounds.ELEVATOR_MOTOR.get(), SoundSource.BLOCKS, SoundInstance.createUnseededRandom());
        this.world = world;
        looping = true;
        volume = 0.02F;
        follow(position);
    }

    private void follow(Vec3 position) {
        x = position.x;
        y = position.y;
        z = position.z;
        moving = true;
    }

    @SubscribeEvent
    public static void clientTick(TickEvent.ClientTickEvent event) {
        if (event.phase != TickEvent.Phase.END) return;
        var client = Minecraft.getInstance();
        if (motor != null && (client.level != motor.world || motor.isStopped()
                || !client.getSoundManager().isActive(motor))) {
            motor.stop();
            motor = null;
        }
        if (client.level == null || client.getCameraEntity() == null || client.isPaused()
                || client.options.getSoundSourceVolume(SoundSource.BLOCKS) <= 0
                || client.options.getSoundSourceVolume(SoundSource.MASTER) <= 0) return;
        Vec3 listener = client.gameRenderer.getMainCamera().getPosition();
        Vec3 closest = null;
        double rangeSquared = 16 * 16;
        for (var group : ElevatorGroupCapability.get(client.level).getGroups()) {
            var cage = group.getCage();
            if (!group.isMoving() || cage == null) continue;
            var box = cage.bounds.move(group.getCageAnchorPos(group.getCurrentY()));
            var source = new Vec3(Mth.clamp(listener.x, box.minX, box.maxX),
                    Mth.clamp(listener.y, box.minY, box.maxY), Mth.clamp(listener.z, box.minZ, box.maxZ));
            double distance = listener.distanceToSqr(source);
            if (distance < rangeSquared) {
                closest = source;
                rangeSquared = distance;
            }
        }
        if (closest == null) {
            if (motor != null) motor.moving = false;
        } else if (motor == null) {
            motor = new ElevatorMotorSound(client.level, closest);
            client.getSoundManager().play(motor);
        } else {
            motor.follow(closest);
        }
    }

    @Override
    public void tick() {
        volume = Mth.clamp(volume + (moving ? 0.025F : -0.03F), 0.0F, 0.32F);
        if (volume == 0.0F || Minecraft.getInstance().level != world) stop();
    }
}
