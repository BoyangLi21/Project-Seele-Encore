package com.projectseele.mixin;

import com.projectseele.world.SbwParkingTicketsR44;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.phys.Vec3;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** Pinned SBW short-ticket call; no vehicle tick, AI or motion is cancelled. */
@Pseudo
@Mixin(targets = "com.atsuishio.superbwarfare.entity.vehicle.base.VehicleEntity", remap = false)
public abstract class SbwParkingTicketsR44Mixin
{
    @Shadow public abstract boolean engineRunning();
    @Shadow public abstract boolean isFiring();
    @Shadow public abstract boolean fireInputDown();
    @Shadow public abstract String getAiTurretTargetUUID();
    @Shadow public abstract String getAiPassengerWeaponTargetUUID();
    @Shadow public abstract String getTowingUUID();
    @Shadow public abstract java.util.List<String> getTowingUUIDs();

    @Inject(method = "keepChunkLoaded(Lnet/minecraft/world/phys/Vec3;)V",
            at = @At("HEAD"), cancellable = true)
    private void seele$parkedSelfTicket(Vec3 position, CallbackInfo callback)
    {
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
