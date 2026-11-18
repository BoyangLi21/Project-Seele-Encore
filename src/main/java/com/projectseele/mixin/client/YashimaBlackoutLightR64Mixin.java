package com.projectseele.mixin.client;

import com.projectseele.client.YashimaBlackoutR64;
import net.minecraft.client.renderer.LevelRenderer;
import net.minecraft.core.BlockPos;
import net.minecraft.world.level.BlockAndTintGetter;
import net.minecraft.world.level.LightLayer;
import net.minecraft.world.level.block.state.BlockState;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/**
 * R64, the Yashima blackout: where the sky reaches, a block is drawn by the sky's light alone, with neither the
 * light that reaches it from lamps nor its own. (The game's meshing, block entities and particles all come through
 * here, and so does most of Embeddium's.) A solid lamp, which the sky does not reach itself, is out when the sky
 * reaches a block beside it.
 */
@Mixin(LevelRenderer.class)
public abstract class YashimaBlackoutLightR64Mixin
{
    @Inject(method = "getLightColor(Lnet/minecraft/world/level/BlockAndTintGetter;Lnet/minecraft/world/level/block/state/BlockState;Lnet/minecraft/core/BlockPos;)I",
            at = @At("HEAD"), cancellable = true)
    private static void seele$blackout(BlockAndTintGetter level, BlockState state, BlockPos pos, CallbackInfoReturnable<Integer> result)
    {
        if (!YashimaBlackoutR64.zone(pos.getX(), pos.getY(), pos.getZ())) return;
        int sky = level.getBrightness(LightLayer.SKY, pos);
        if (sky > 0) result.setReturnValue(sky << 20);
        else if (state.getLightEmission(level, pos) > 0 && YashimaBlackoutR64.skyBeside(level, pos.getX(), pos.getY(), pos.getZ())) result.setReturnValue(0);
        else return;
        YashimaBlackoutR64.told(0);
    }
}
