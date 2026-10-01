package com.projectseele.mixin;

import java.lang.reflect.Proxy;
import com.projectseele.world.NativeEcologyFeatureProtectionR44;
import com.projectseele.world.RegionalEcologyBiomeSourceR44;
import net.minecraft.core.BlockPos;
import net.minecraft.util.RandomSource;
import net.minecraft.world.level.WorldGenLevel;
import net.minecraft.world.level.chunk.ChunkGenerator;
import net.minecraft.world.level.levelgen.placement.PlacedFeature;
import net.minecraft.world.level.levelgen.Heightmap;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

@Mixin(PlacedFeature.class)
public abstract class EcologyPlacedFeatureR44Mixin
{
    @Inject(method="placeWithBiomeCheck",at=@At("HEAD"),cancellable=true)
    private void seele$guardCompleteFeature(WorldGenLevel world,ChunkGenerator generator,RandomSource random,BlockPos origin,CallbackInfoReturnable<Boolean> result)
    {
        if(Proxy.isProxyClass(world.getClass())||!(generator.getBiomeSource() instanceof RegionalEcologyBiomeSourceR44 source))return;
        int floor=NativeEcologyFeatureProtectionR44.surfaceGround(origin.getX(),origin.getZ(),
                world.getHeight(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES,origin.getX(),origin.getZ())-1,world::getBlockState,source);
        BlockPos projected=new BlockPos(origin.getX(),floor==Integer.MIN_VALUE?world.getMinBuildHeight():floor+1,origin.getZ());
        result.setReturnValue(NativeEcologyFeatureProtectionR44.place((PlacedFeature)(Object)this,world,generator,random,projected,source,null));
    }
}
