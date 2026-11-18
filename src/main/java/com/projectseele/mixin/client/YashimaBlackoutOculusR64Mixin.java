package com.projectseele.mixin.client;

import com.projectseele.client.YashimaBlackoutR64;
import net.minecraft.world.level.block.state.BlockState;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/**
 * R64, the Yashima blackout under a shader pack (Oculus 1.8.0 with Embeddium). Before a block's model is meshed
 * Oculus notes the block's number in the pack's table and its emission here, and writes both with every vertex of
 * the block: by these a pack makes a lamp glow whatever light it has. A block that gives light is reported to the
 * blackout as it is noted, and the blackout has both taken back (no known block, no emission) for a lamp that is
 * out, just before its model is meshed (YashimaBlackoutEmbeddiumBlockR64Mixin).
 */
@Pseudo
@Mixin(targets = "net.irisshaders.iris.compat.sodium.impl.block_context.BlockContextHolder", remap = false)
public abstract class YashimaBlackoutOculusR64Mixin implements YashimaBlackoutR64.Lamp
{
    @Shadow public short blockId;
    @Shadow public byte lightValue;

    @Inject(method = "set(Lnet/minecraft/world/level/block/state/BlockState;SB)V", at = @At("RETURN"), require = 0)
    private void seele$lamp(BlockState state, short renderType, byte emission, CallbackInfo info)
    {
        if (emission > 0) YashimaBlackoutR64.lamp(this);
    }

    @Override
    public void seele$lampOut()
    {
        this.blockId = -1;
        this.lightValue = 0;
    }
}
