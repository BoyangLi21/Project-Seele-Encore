package com.projectseele.mixin.client;

import net.minecraft.client.Timer;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/**
 * The frame's partial tick from the nanosecond clock instead of whole
 * milliseconds. At sixty frames a second the millisecond clock alternates 16
 * and 17 ms frames, so every interpolated position moved about 6% too far or
 * too short every third frame; a giant crossing 20 to 110 blocks a second
 * with the camera behind it made the near ground shimmer by up to a tenth of
 * a block.
 */
@Mixin(Timer.class)
public abstract class TimerPrecisionMixin
{
    @Shadow public float partialTick;
    @Shadow public float tickDelta;
    @Shadow private long lastMs;
    @Shadow @Final private float msPerTick;
    @Unique private long projectseele$lastNanos = Long.MIN_VALUE;

    @Inject(method = "advanceTime", at = @At("HEAD"), cancellable = true)
    private void projectseele$advancePrecisely(long millis, CallbackInfoReturnable<Integer> callback)
    {
        long now = System.nanoTime();
        long last = this.projectseele$lastNanos;
        this.projectseele$lastNanos = now;
        // The first frame, and any frame after a clock reset, keeps vanilla's step.
        if (last == Long.MIN_VALUE || now < last || millis - this.lastMs > 1000L)
        {
            return;
        }
        this.tickDelta = (float)((now - last) / 1.0E6D / this.msPerTick);
        this.lastMs = millis;
        this.partialTick += this.tickDelta;
        int ticks = (int)this.partialTick;
        this.partialTick -= (float)ticks;
        callback.setReturnValue(ticks);
    }
}
