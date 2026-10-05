package com.projectseele.mixin.client;

import com.projectseele.client.LclWaterResourcesR47;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.packs.resources.MultiPackResourceManager;
import net.minecraft.server.packs.resources.Resource;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;
import java.util.List;
import java.util.Optional;

/** Both vanilla/Forge atlas and Oculus PBR lookups see aliases from the current resource reload. */
@Mixin(MultiPackResourceManager.class)
public abstract class LclWaterResourceReloadR47Mixin
{
    @Inject(method = "getResource", at = @At("HEAD"), cancellable = true)
    private void projectseele$lclResource(ResourceLocation requested, CallbackInfoReturnable<Optional<Resource>> callback)
    {
        ResourceLocation source = LclWaterResourcesR47.waterSource(requested);
        if (source == null) return;
        var manager = (MultiPackResourceManager) (Object) this;
        callback.setReturnValue(manager.getResource(source).map(resource -> LclWaterResourcesR47.alias(manager, source, resource)));
    }
    @Inject(method = "getResourceStack", at = @At("HEAD"), cancellable = true)
    private void projectseele$lclResourceStack(ResourceLocation requested, CallbackInfoReturnable<List<Resource>> callback)
    {
        ResourceLocation source = LclWaterResourcesR47.waterSource(requested);
        if (source == null) return;
        var manager = (MultiPackResourceManager) (Object) this;
        callback.setReturnValue(manager.getResourceStack(source).stream()
                .map(resource -> LclWaterResourcesR47.alias(manager, source, resource)).toList());
    }
}
