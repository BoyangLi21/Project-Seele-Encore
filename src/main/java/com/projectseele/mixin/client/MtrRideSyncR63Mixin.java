package com.projectseele.mixin.client;

import com.projectseele.ProjectSeele;
import java.lang.reflect.Field;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.ModifyArg;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/**
 * Keeps a fast train in view for the passenger riding it.
 * <p>
 * MTR's client asks the server for rails and vehicles only 500 ms after a chunk loads, and only
 * within its render distance (12 chunks: 192 blocks). The server then pushes vehicle updates
 * around the position of that last request. At 700 km/h a train covers 194 blocks a second, and
 * on the spiral line the rider stays inside chunks that are already loaded, so no new request
 * goes out: the train ran past the rails the client knew, stood still for one to two seconds and
 * then jumped forward (45 times on one descent). The request now reaches at least 512 blocks,
 * and while the player rides a vehicle one goes out every half second.
 */
@Pseudo
@Mixin(targets="org.mtr.mod.InitClient",remap=false)
public abstract class MtrRideSyncR63Mixin
{
    @Unique private static final long PROJECTSEELE$MIN_RADIUS=512L;
    @Unique private static final long PROJECTSEELE$RIDING_INTERVAL_MILLIS=500L;
    @Unique private static long projectSeele$lastRidingRequest;
    @Unique private static Field projectSeele$ridingVehicleId;
    @Unique private static boolean projectSeele$ridingUnreadable;
    @Unique private static boolean projectSeele$announced;

    @Shadow(remap=false) private static long gameMillis;
    @Shadow(remap=false) private static long lastUpdatePacketMillis;

    @ModifyArg(method="lambda$init$34()V",at=@At(value="INVOKE",target="Lorg/mtr/core/operation/DataRequest;<init>(Ljava/util/UUID;Lorg/mtr/core/data/Position;J)V",remap=false),index=2,remap=false,require=0)
    private static long projectSeele$requestRadius(long radius)
    {
        if(!projectSeele$announced)
        {
            projectSeele$announced=true;
            ProjectSeele.LOGGER.info("R63 MTR ride sync active: request radius {} -> {} blocks",radius,Math.max(radius,PROJECTSEELE$MIN_RADIUS));
        }
        return Math.max(radius,PROJECTSEELE$MIN_RADIUS);
    }

    /** No request pending and the player on a vehicle: schedule one, at most every half second. */
    @Inject(method="lambda$init$34()V",at=@At("HEAD"),remap=false,require=0)
    private static void projectSeele$ridingCadence(CallbackInfo callback)
    {
        if(lastUpdatePacketMillis!=0L||gameMillis-projectSeele$lastRidingRequest<PROJECTSEELE$RIDING_INTERVAL_MILLIS||!projectSeele$riding())return;
        projectSeele$lastRidingRequest=gameMillis;
        // The tick sends once the game clock has passed this mark; it advances later in the same tick.
        lastUpdatePacketMillis=Math.max(1L,gameMillis);
    }

    @Unique
    private static boolean projectSeele$riding()
    {
        if(projectSeele$ridingUnreadable)return false;
        try
        {
            if(projectSeele$ridingVehicleId==null)
            {
                Field field=Class.forName("org.mtr.mod.client.VehicleRidingMovement").getDeclaredField("ridingVehicleId");
                field.setAccessible(true);
                projectSeele$ridingVehicleId=field;
            }
            return projectSeele$ridingVehicleId.getLong(null)!=0L;
        }
        catch(ReflectiveOperationException|RuntimeException|LinkageError failure)
        {
            projectSeele$ridingUnreadable=true;
            ProjectSeele.LOGGER.warn("R63 MTR ride sync: riding state unreadable, half-second requests off",failure);
            return false;
        }
    }
}
