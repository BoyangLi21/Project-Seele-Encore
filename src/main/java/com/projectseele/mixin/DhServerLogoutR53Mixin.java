package com.projectseele.mixin;

import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;

/** The plugin guards only the unloaded-level call and retains DH player cleanup. */
@Pseudo
@Mixin(targets = "com.seibel.distanthorizons.core.world.AbstractDhServerWorld", remap = false)
public abstract class DhServerLogoutR53Mixin {}
