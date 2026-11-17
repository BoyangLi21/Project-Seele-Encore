package com.projectseele.mixin;

import com.projectseele.world.SbwIdlePause;
import com.projectseele.world.SbwParkingTicketsR44;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.phys.Vec3;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/**
 * Pinned SBW short-ticket call, and the vehicle state {@link SbwIdlePause} reads.
 * Nothing is cancelled here but the ticket of a parked vehicle.
 */
@Pseudo
@Mixin(targets = "com.atsuishio.superbwarfare.entity.vehicle.base.VehicleEntity", remap = false)
public abstract class SbwParkingTicketsR44Mixin implements SbwIdlePause.Vehicle
{
    @Shadow public abstract boolean engineRunning();
    @Shadow public abstract boolean isFiring();
    @Shadow public abstract boolean fireInputDown();
    @Shadow public abstract String getAiTurretTargetUUID();
    @Shadow public abstract String getAiPassengerWeaponTargetUUID();
    @Shadow public abstract String getTowingUUID();
    @Shadow public abstract java.util.List<String> getTowingUUIDs();
    @Shadow public abstract float getHealth();
    @Shadow public abstract float getMaxHealth();
    @Shadow public abstract boolean isWreck();
    @Shadow public abstract void keepChunkLoaded(Vec3 position);

    /** Whether this vehicle's own tick has asked for its chunk ticket: SBW decides that per vehicle type. */
    @Unique private boolean seele$wantsTicket;

    @Override
    public boolean projectseele$atRest()
    {
        String turret = getAiTurretTargetUUID(), passenger = getAiPassengerWeaponTargetUUID(), towing = getTowingUUID();
        java.util.List<String> towed = getTowingUUIDs();
        // "undefined" is SBW's own value for no target; anything unknown counts as a target.
        return !engineRunning() && !isFiring() && !fireInputDown() && !isWreck() && getHealth() >= getMaxHealth()
                && turret != null && (turret.isBlank() || turret.equals("undefined"))
                && passenger != null && (passenger.isBlank() || passenger.equals("undefined"))
                && towing != null && towing.isBlank() && towed != null && towed.isEmpty();
    }

    @Override
    public void projectseele$holdChunk()
    {
        if (seele$wantsTicket) keepChunkLoaded(((Entity)(Object)this).position());
    }

    @Inject(method = "keepChunkLoaded(Lnet/minecraft/world/phys/Vec3;)V",
            at = @At("HEAD"), cancellable = true)
    private void seele$parkedSelfTicket(Vec3 position, CallbackInfo callback)
    {
        seele$wantsTicket = true;
        if(SbwParkingTicketsR44.disabled())return;
        try
        {
            if (SbwParkingTicketsR44.skip((Entity)(Object)this, engineRunning(), isFiring(), fireInputDown(),
                    getAiTurretTargetUUID(), getAiPassengerWeaponTargetUUID(), getTowingUUID(), getTowingUUIDs()))
            {
                callback.cancel();
            }
        }
        catch (RuntimeException | LinkageError error)
        {
            SbwParkingTicketsR44.unknownNativeState();
        }
    }
}
