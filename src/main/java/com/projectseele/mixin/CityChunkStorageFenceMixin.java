package com.projectseele.mixin;

import com.projectseele.world.CityEntitySaveFence;
import net.minecraft.world.level.chunk.storage.ChunkStorage;
import net.minecraft.world.level.chunk.storage.IOWorker;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(ChunkStorage.class)
abstract class CityChunkStorageFenceMixin
{
    @Shadow @Final private IOWorker worker;

    @Inject(method = "flushWorker", at = @At("HEAD"), cancellable = true)
    private void seele$deferCityChunkFlush(CallbackInfo ci)
    {
        if (CityEntitySaveFence.deferChunkFlush(this, worker)) ci.cancel();
    }
}
