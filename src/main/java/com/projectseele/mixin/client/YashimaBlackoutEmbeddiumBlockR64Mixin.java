package com.projectseele.mixin.client;

import com.projectseele.client.YashimaBlackoutR64;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.client.resources.model.BakedModel;
import net.minecraft.core.BlockPos;
import net.minecraft.world.level.BlockAndTintGetter;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraftforge.client.model.data.ModelData;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/**
 * R64, the Yashima blackout under a shader pack: the moment Embeddium (0.3.31) has a block's model ready to mesh,
 * with the block's place in the world known, and after Oculus has noted the block for the pack. A block that gives
 * light and stands where the blackout reaches is passed to the blackout, which has the pack told nothing of a lamp
 * that is out (YashimaBlackoutOculusR64Mixin).
 */
@Pseudo
@Mixin(targets = "me.jellysquid.mods.sodium.client.render.chunk.compile.pipeline.BlockRenderContext", remap = false)
public abstract class YashimaBlackoutEmbeddiumBlockR64Mixin
{
    @Shadow @Final private BlockAndTintGetter localSlice;

    @Inject(method = "update", at = @At("RETURN"), require = 0)
    private void seele$blackout(BlockPos pos, BlockPos origin, BlockState state, BakedModel model, long seed, ModelData data, RenderType layer, CallbackInfo info)
    {
        if (state.getLightEmission() > 0 && YashimaBlackoutR64.zone(pos.getX(), pos.getY(), pos.getZ())) YashimaBlackoutR64.lampOut(this.localSlice, pos);
    }
}
