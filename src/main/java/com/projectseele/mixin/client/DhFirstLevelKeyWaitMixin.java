package com.projectseele.mixin.client;

import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.injection.Constant;
import org.spongepowered.asm.mixin.injection.ModifyConstant;

/**
 * DH opens the first level of a connection a second after joining unless the server's level key
 * has been handled by then. When the render thread handles the key just as that timer fires, both
 * build a level, the second one fails to start its renderer, and no LOD is drawn all session.
 * Every SEELE server sends keys, so the timer only has to cover a server that never answers.
 */
@Pseudo
@Mixin(targets = "com.seibel.distanthorizons.core.api.internal.ClientApi", remap = false)
public abstract class DhFirstLevelKeyWaitMixin
{
    @ModifyConstant(method = "clientLevelLoadEvent", constant = @Constant(longValue = 1000L), require = 0)
    private long seele$waitForServerLevelKey(long delayMillis)
    {
        return 30_000L;
    }
}
