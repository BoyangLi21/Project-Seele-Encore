package com.projectseele.mixin;

import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.gen.Accessor;

/** MTR stores the inherited service name on this generated base class. */
@Pseudo
@Mixin(targets="org.mtr.core.generated.data.NameColorDataBaseSchema",remap=false)
public interface MtrNameAccessor
{
    @Accessor(value="name",remap=false)
    String projectSeele$nativeName();
}
