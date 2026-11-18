package com.projectseele.mixin.client;

import com.projectseele.client.YashimaBlackoutR64;
import net.minecraft.client.renderer.entity.EntityRenderer;
import net.minecraft.core.BlockPos;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.level.LightLayer;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/** R64, the Yashima blackout: whatever stands where it is dark is not lit by the lamps there either (unless it burns). */
@Mixin(EntityRenderer.class)
public abstract class YashimaBlackoutEntityR64Mixin
{
    @Inject(method = "getBlockLightLevel", at = @At("RETURN"), cancellable = true)
    private void seele$blackout(Entity entity, BlockPos pos, CallbackInfoReturnable<Integer> result)
    {
        if (result.getReturnValueI() > 0 && !entity.isOnFire() && YashimaBlackoutR64.zone(pos.getX(), pos.getY(), pos.getZ())
                && entity.level().getBrightness(LightLayer.SKY, pos) > 0)
        {
            result.setReturnValue(0); YashimaBlackoutR64.told(1);
        }
    }
}
