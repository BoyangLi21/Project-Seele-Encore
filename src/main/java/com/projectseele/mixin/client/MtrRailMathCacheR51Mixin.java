package com.projectseele.mixin.client;

import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;

/** Optional producer hook; the compatibility plugin validates and changes only
 * the four immutable RailMath allocation sites, retaining both Rail bodies. */
@Pseudo
@Mixin(targets="org.mtr.core.data.Rail",remap=false)
public abstract class MtrRailMathCacheR51Mixin{}
