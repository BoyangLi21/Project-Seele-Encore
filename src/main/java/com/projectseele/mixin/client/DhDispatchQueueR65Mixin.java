package com.projectseele.mixin.client;

import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.ModifyArg;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.LinkedBlockingQueue;

/** DH throttles dispatch with occupiedThreads. A second, smaller handoff limit drops
 * already-polled tasks when a completing worker schedules its successor before returning. */
@Pseudo
@Mixin(targets = "com.seibel.distanthorizons.core.util.threading.PriorityTaskPicker", remap = false)
public abstract class DhDispatchQueueR65Mixin
{
    @ModifyArg(method = "<init>", index = 2, at = @At(value = "INVOKE",
            target = "Lcom/seibel/distanthorizons/core/util/threading/RateLimitedThreadPoolExecutor;<init>(ILjava/util/concurrent/ThreadFactory;Ljava/util/concurrent/BlockingQueue;)V"))
    private BlockingQueue<Runnable> projectSeele$acceptDispatchedTasks(BlockingQueue<Runnable> original)
    {
        return new LinkedBlockingQueue<>();
    }
}
