package com.projectseele.mixin;

import com.projectseele.world.CityEntitySaveFence;
import net.minecraft.util.thread.ProcessorMailbox;
import net.minecraft.world.level.chunk.storage.EntityStorage;
import net.minecraft.world.level.chunk.storage.IOWorker;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(EntityStorage.class)
abstract class CityEntityStorageFenceMixin
{
    @Shadow @Final private IOWorker worker;
    @Shadow @Final private ProcessorMailbox<Runnable> entityDeserializerQueue;

    @Inject(method = "flush", at = @At("HEAD"), cancellable = true)
    private void seele$deferCityFlush(boolean force, CallbackInfo ci)
    {
        if (force && CityEntitySaveFence.deferFinalFlush(this, worker, entityDeserializerQueue)) ci.cancel();
    }
}
