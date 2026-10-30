package com.projectseele.mixin;

import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.injection.Constant;
import org.spongepowered.asm.mixin.injection.ModifyConstant;

/** The two Hakone services use a quieter native departure cadence. */
@Pseudo
@Mixin(targets="org.mtr.core.data.Siding",remap=false)
public abstract class HakoneRopewayHeadwayMixin
{
    @ModifyConstant(method="getRepeatInterval(J)J",constant=@Constant(longValue=8000L),remap=false)
    private long projectSeele$hakoneCabinInterval(long original)
    {
        String name=((MtrNameAccessor)(Object)this).projectSeele$nativeName();
        return "HRW 車庫".equals(name)||"HRE 車庫".equals(name)?45000L:original;
    }
}
