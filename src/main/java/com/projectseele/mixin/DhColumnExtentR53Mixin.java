package com.projectseele.mixin;

import com.projectseele.compat.DhColumnExtentR53;
import it.unimi.dsi.fastutil.longs.LongArrayList;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Coerce;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

@Pseudo
@Mixin(targets = "com.seibel.distanthorizons.core.dataObjects.fullData.sources.FullDataSourceV2", remap = false)
public abstract class DhColumnExtentR53Mixin
{
    // DH 2.3.4 notices exhausted cursors on the next loop iteration, after
    // already emitting one sample with palette ID zero above the source data.
    @Inject(method = "mergeInputTwoByTwoDataColumn", at = @At("RETURN"))
    private static void seele$respectSourceExtent(@Coerce Object source, int x, int z,
                                                  CallbackInfoReturnable<LongArrayList> result)
    {
        DhColumnExtentR53.trimMerged(source, x, z, result.getReturnValue());
    }
}
