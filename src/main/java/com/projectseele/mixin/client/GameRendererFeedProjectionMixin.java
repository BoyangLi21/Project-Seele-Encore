package com.projectseele.mixin.client;

import com.projectseele.client.EvaCommandFeedClient;
import net.minecraft.client.renderer.GameRenderer;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.ModifyArg;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;
import com.mojang.blaze3d.vertex.PoseStack;

/** Preserve the optical target's aspect when the pilot uses a different display ratio. */
@Mixin(GameRenderer.class)
public abstract class GameRendererFeedProjectionMixin
{
    @Inject(method="getFov",at=@At("RETURN"))
    private void projectseele$observeReviewLens(net.minecraft.client.Camera camera,float partial,boolean useSetting,
            CallbackInfoReturnable<Double> callback)
    {
        if(useSetting && EvaCommandFeedClient.captureTargetOverride()==null)
            com.projectseele.client.visual.RegionalStationPhoto.observeEffectiveFov(callback.getReturnValue());
    }
    @Inject(method="renderLevel",at=@At("HEAD"))
    private void projectseele$beginOpticalPass(float partial,long finishTime,PoseStack pose,CallbackInfo callback)
    {
        com.projectseele.client.EvaPilotBodyRenderBridge.beginPass();
    }
    @Inject(method="renderLevel",at=@At("TAIL"))
    private void projectseele$captureBeforeGui(float partial,long finishTime,PoseStack pose,CallbackInfo callback)
    {
        EvaCommandFeedClient.opticalWorldRendered(partial);
    }
    @ModifyArg(method="getProjectionMatrix",at=@At(value="INVOKE",
            target="Lorg/joml/Matrix4f;setPerspective(FFFF)Lorg/joml/Matrix4f;",remap=false),index=1)
    private float projectseele$opticalAspect(float original)
    {
        var target=EvaCommandFeedClient.captureTargetOverride();
        return target==null?original:target.viewWidth/(float)target.viewHeight;
    }
}
