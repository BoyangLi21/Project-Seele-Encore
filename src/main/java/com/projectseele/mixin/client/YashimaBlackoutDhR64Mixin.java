package com.projectseele.mixin.client;

import com.projectseele.client.YashimaBlackoutR64;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.ModifyVariable;

/**
 * R64, the Yashima blackout in Distant Horizons' far view (2.3.4). Every quad of the far view is given its
 * material, its sky light and its block light as three bytes, in that order; during the blackout the block light
 * is nothing and the "illuminated" material (15, which a shader pack makes glow) is the plain one (0). The far
 * view is built again when the blackout begins and ends (YashimaBlackoutR64).
 */
@Pseudo
@Mixin(targets = "com.seibel.distanthorizons.core.dataObjects.render.bufferBuilding.LodQuadBuilder", remap = false)
public abstract class YashimaBlackoutDhR64Mixin
{
    @ModifyVariable(method = {"addQuadUp", "addQuadDown", "addQuadAdj"}, at = @At("HEAD"), ordinal = 2, argsOnly = true, require = 0)
    private byte seele$blackoutLight(byte blockLight)
    {
        return YashimaBlackoutR64.far() ? 0 : blockLight;
    }

    @ModifyVariable(method = {"addQuadUp", "addQuadDown", "addQuadAdj"}, at = @At("HEAD"), ordinal = 0, argsOnly = true, require = 0)
    private byte seele$blackoutMaterial(byte material)
    {
        return YashimaBlackoutR64.far() && material == 15 ? 0 : material;
    }
}
