package com.projectseele.mixin;

import com.projectseele.world.FacilitySchemaV2;
import com.projectseele.world.PeriodicEntitySave;
import net.minecraft.server.MinecraftServer;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Redirect;

@Mixin(MinecraftServer.class)
abstract class PeriodicSaveScopeMixin
{
    @Redirect(method = "tickServer", at = @At(value = "INVOKE",
            target = "Lnet/minecraft/server/MinecraftServer;saveEverything(ZZZ)Z"))
    private boolean seele$scheduleGeoFrontEntities(MinecraftServer server, boolean quiet, boolean flush, boolean force)
    {
        var level = server.getLevel(FacilitySchemaV2.DIMENSION);
        if (level == null || flush) return server.saveEverything(quiet, flush, force);
        var manager = (PeriodicEntitySave)((ServiceAircraftWorldR32Accessor) level).seele$entityManagerR32();
        manager.seele$periodicSave(true);
        try { return server.saveEverything(quiet, false, force); }
        finally { manager.seele$periodicSave(false); }
    }
}
