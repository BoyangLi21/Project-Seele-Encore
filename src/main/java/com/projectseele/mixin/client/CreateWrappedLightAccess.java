package com.projectseele.mixin.client;

import net.minecraft.world.level.BlockAndTintGetter;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.gen.Accessor;

@Pseudo
@Mixin(targets = "com.simibubi.create.foundation.utility.worldWrappers.WrappedBlockAndTintGetter", remap = false)
public interface CreateWrappedLightAccess
{
    @Accessor(value = "wrapped", remap = false)
    BlockAndTintGetter projectSeele$wrappedView();
}
