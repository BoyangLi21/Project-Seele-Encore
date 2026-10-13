package com.projectseele.mixin.client;

import com.projectseele.client.RamielDistantViewR52;
import net.minecraft.client.renderer.GameRenderer;
import org.joml.Matrix4f;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/** Distant actual observation uses the same extended depth projection as nearby world geometry. */
@Mixin(GameRenderer.class)
public abstract class RamielDistantProjectionR52Mixin
{
    @Inject(method="getProjectionMatrix",at=@At("RETURN"),cancellable=true)
    private void seele$remoteDepthR52(double fov,CallbackInfoReturnable<Matrix4f> result)
    {result.setReturnValue(RamielDistantViewR52.projection(result.getReturnValue()));}
}
