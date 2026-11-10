package com.projectseele.mixin.client;

import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

import net.minecraft.client.renderer.LightTexture;
import net.minecraft.core.BlockPos;
import net.minecraft.world.level.LightLayer;
import net.minecraftforge.fml.ModList;

/**
 * Starlight cannot light Create's render-only virtual world: its chunks were never loaded through
 * Starlight, so relighting throws in initNibble and reading light dereferences missing nibble arrays.
 * Either one crashed the client the moment a moving city block (a Create contraption) was drawn.
 * Under Starlight the virtual relight is skipped and its light reads use only the light Create
 * samples from the real world at the contraption (externalPackedLight); light emitted inside a
 * moving contraption is lost until it lands.
 * Create's methods keep their SRG names in the release jar, so targets are written as such.
 */
@Pseudo
@Mixin(targets = "com.simibubi.create.foundation.virtualWorld.VirtualRenderWorld", remap = false)
public abstract class CreateVirtualLightStarlightGuardMixin
{
    @Unique
    private static final boolean PROJECTSEELE$STARLIGHT = ModList.get().isLoaded("starlight");

    @Shadow(remap = false)
    private int externalPackedLight;

    @Inject(method = "runLightEngine", at = @At("HEAD"), cancellable = true, remap = false)
    private void projectSeele$skipVirtualRelightUnderStarlight(CallbackInfo callback)
    {
        if (PROJECTSEELE$STARLIGHT)
        {
            callback.cancel();
        }
    }

    @Inject(method = "m_45517_(Lnet/minecraft/world/level/LightLayer;Lnet/minecraft/core/BlockPos;)I",
            at = @At("HEAD"), cancellable = true, remap = false)
    private void projectSeele$realWorldLightUnderStarlight(LightLayer layer, BlockPos pos, CallbackInfoReturnable<Integer> callback)
    {
        if (PROJECTSEELE$STARLIGHT)
        {
            callback.setReturnValue(layer == LightLayer.SKY
                    ? LightTexture.sky(this.externalPackedLight)
                    : LightTexture.block(this.externalPackedLight));
        }
    }
}
