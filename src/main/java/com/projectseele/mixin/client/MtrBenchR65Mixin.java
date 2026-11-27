package com.projectseele.mixin.client;

import com.projectseele.client.RailSeatsR65;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Coerce;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Pseudo
@Mixin(targets = "org.mtr.mod.client.VehicleRidingMovement", remap = false)
public abstract class MtrBenchR65Mixin
{
    @Shadow private static double ridingVehicleX, ridingVehicleY, ridingVehicleZ;
    @Shadow private static long ridingVehicleId;
    @Shadow private static int ridingVehicleCarNumber;
    @Shadow private static boolean isOnGangway;
    @Shadow private static void sendUpdate(boolean dismount) { throw new AssertionError(); }

    @Inject(method = "movePlayer(JJILorg/mtr/libraries/it/unimi/dsi/fastutil/objects/ObjectArrayList;Lorg/mtr/mod/client/GangwayMovementPositions;Lorg/mtr/mod/client/GangwayMovementPositions;Lorg/mtr/mod/client/GangwayMovementPositions;Lorg/mtr/mod/render/PositionAndRotation;)V", at = @At("HEAD"))
    private static void projectSeele$aisle(long elapsed, long id, int car, @Coerce Object floors,
            @Coerce Object previous, @Coerce Object first, @Coerce Object second, @Coerce Object pose, CallbackInfo ci)
    {
        if (id != ridingVehicleId || car != ridingVehicleCarNumber) return;
        if (isOnGangway) { RailSeatsR65.leave(); return; }
        RailSeatsR65.frame(id, car, ridingVehicleX, ridingVehicleY, ridingVehicleZ, pose);
        if (RailSeatsR65.seated() || RailSeatsR65.changed())
        {
            ridingVehicleX = RailSeatsR65.aisleX();
            ridingVehicleY = RailSeatsR65.floor();
            ridingVehicleZ = RailSeatsR65.seatZ();
        }
    }

    @Inject(method = "movePlayer(JJILorg/mtr/libraries/it/unimi/dsi/fastutil/objects/ObjectArrayList;Lorg/mtr/mod/client/GangwayMovementPositions;Lorg/mtr/mod/client/GangwayMovementPositions;Lorg/mtr/mod/client/GangwayMovementPositions;Lorg/mtr/mod/render/PositionAndRotation;)V",
            at = @At(value = "NEW", target = "org/mtr/mapping/holder/Vector3d", ordinal = 2))
    private static void projectSeele$seatAnchor(CallbackInfo ci)
    {
        if (RailSeatsR65.seated())
        {
            ridingVehicleX = RailSeatsR65.seatX(); ridingVehicleZ = RailSeatsR65.seatZ();
            ridingVehicleY = RailSeatsR65.floor() - .36;
        }
        if (RailSeatsR65.changed()) { sendUpdate(false); RailSeatsR65.sent(); }
    }

    @Inject(method = "tick", at = @At("RETURN"))
    private static void projectSeele$clearAfterDismount(CallbackInfo ci)
    {
        if (ridingVehicleId == 0) RailSeatsR65.leave();
    }
}
