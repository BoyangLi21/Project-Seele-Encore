package com.projectseele.mixin.client;

import com.projectseele.client.RamielTerrainDepthR64;
import org.joml.Matrix4fc;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** Keep the clip transform paired with the depth written by the optional Oculus DH program. */
@Pseudo
@Mixin(targets = "net.irisshaders.iris.compat.dh.IrisLodRenderProgram", remap = false)
public abstract class OculusDhDepthProjectionR65Mixin
{
    @Inject(method = "fillUniformData(Lorg/joml/Matrix4fc;Lorg/joml/Matrix4fc;IF)V",
            at = @At("TAIL"), require = 0)
    private void seele$rememberProjection(Matrix4fc projection, Matrix4fc view, int offset, float tick, CallbackInfo ci)
    {
        RamielTerrainDepthR64.observeShaderProjection(projection);
    }
}
