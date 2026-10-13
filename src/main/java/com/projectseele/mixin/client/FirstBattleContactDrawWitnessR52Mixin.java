package com.projectseele.mixin.client;

import com.mojang.blaze3d.vertex.VertexBuffer;
import com.projectseele.client.render.EvaContactShadowsR24;
import net.minecraft.client.renderer.ShaderInstance;
import org.joml.Matrix4f;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** The opt-in contact receipt observes the applied shader at the actual draw boundary. */
@Mixin(VertexBuffer.class)
public abstract class FirstBattleContactDrawWitnessR52Mixin
{
    @Inject(method="_drawWithShader",at=@At(value="INVOKE",
            target="Lnet/minecraft/client/renderer/ShaderInstance;apply()V",shift=At.Shift.AFTER))
    private void projectseele$contactDraw(Matrix4f modelView,Matrix4f projection,ShaderInstance shader,CallbackInfo callback)
    {
        if(EvaContactShadowsR24.tracingDrawR52())EvaContactShadowsR24.actualDrawR52(shader,modelView,projection);
    }
}
