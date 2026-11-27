package com.projectseele.mixin.client;

import com.projectseele.client.CitySkylineR66;
import it.unimi.dsi.fastutil.longs.LongArrayList;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Coerce;
import org.spongepowered.asm.mixin.injection.ModifyVariable;

/** Filter only the render copy of DH's source column, before reduction into its screen LOD. */
@Pseudo
@Mixin(targets="com.seibel.distanthorizons.core.dataObjects.transformers.FullDataToRenderDataTransformer",remap=false)
public abstract class DhCitySkylineR66Mixin {
    @ModifyVariable(method="updateOrReplaceRenderDataViewColumnWithFullDataColumn",at=@At("HEAD"),argsOnly=true,ordinal=0,require=0)
    private static LongArrayList seele$cityGeometry(LongArrayList original,@Coerce Object level,@Coerce Object map,
            int worldX,int worldZ,@Coerce Object column,LongArrayList source) {
        return CitySkylineR66.surveyColumn(level,worldX,worldZ,original);
    }
}
