package com.projectseele.mixin.client;

import com.projectseele.client.YashimaBlackoutR64;
import net.minecraft.world.level.BlockAndTintGetter;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/**
 * R64, the Yashima blackout in Embeddium's meshing (0.3.31). Its light word for a block packs, beside the light
 * that reaches the block, the block's own emission and whether it is drawn full bright: a lamp's own faces are lit
 * by those two whatever LevelRenderer.getLightColor answered. Where the sky reaches (the word has its light too),
 * all three are taken out of the word; the sky's light, the occlusion and the shape flags stay. A solid lamp, which
 * the sky does not reach itself, loses them when the sky reaches a block beside it.
 */
@Pseudo
@Mixin(targets = "me.jellysquid.mods.sodium.client.model.light.data.LightDataAccess", remap = false)
public abstract class YashimaBlackoutEmbeddiumR64Mixin
{
    @Shadow protected BlockAndTintGetter world;

    @Shadow public static int packBL(int light) { throw new AssertionError(); }
    @Shadow public static int unpackBL(int word) { throw new AssertionError(); }
    @Shadow public static int unpackSL(int word) { throw new AssertionError(); }
    @Shadow public static int packLU(int emission) { throw new AssertionError(); }
    @Shadow public static int unpackLU(int word) { throw new AssertionError(); }
    @Shadow public static int packEM(boolean emissive) { throw new AssertionError(); }
    @Shadow public static boolean unpackEM(int word) { throw new AssertionError(); }

    @Inject(method = "compute(III)I", at = @At("RETURN"), cancellable = true, require = 0)
    private void seele$blackout(int x, int y, int z, CallbackInfoReturnable<Integer> result)
    {
        if (!YashimaBlackoutR64.zone(x, y, z)) return;
        int word = result.getReturnValueI();
        YashimaBlackoutR64.told(2);
        if (unpackSL(word) == 0 && !(unpackLU(word) > 0 && this.world != null && YashimaBlackoutR64.skyBeside(this.world, x, y, z))) return;
        int dark = word - packBL(unpackBL(word)) - packLU(unpackLU(word)) - packEM(unpackEM(word));
        if (dark == word) return;
        YashimaBlackoutR64.told(3);
        result.setReturnValue(dark);
    }
}
