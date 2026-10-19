package com.projectseele.mixin.client;

import com.projectseele.client.SparseByteCacheResetR53;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Pseudo
@Mixin(targets = "org.mtr.libraries.com.logisticscraft.occlusionculling.cache.ArrayOcclusionCache", remap = false)
public abstract class MtrOcclusionCacheR53Mixin
{
    @Shadow @Final private byte[] cache;
    @Shadow private int entry;
    @Unique private SparseByteCacheResetR53 seele$dirtyPages;

    @Inject(method = "<init>", at = @At("RETURN"))
    private void seele$createPages(int reach, CallbackInfo ci)
    {
        seele$dirtyPages = new SparseByteCacheResetR53(cache.length);
    }

    @Inject(method = {"setVisible", "setHidden"}, at = @At("RETURN"))
    private void seele$markWrittenPage(int x, int y, int z, CallbackInfo ci)
    {
        seele$dirtyPages.mark(entry);
    }

    @Inject(method = "resetCache", at = @At("HEAD"), cancellable = true)
    private void seele$clearWrittenPages(CallbackInfo ci)
    {
        seele$dirtyPages.clear(cache);
        ci.cancel();
    }
}
