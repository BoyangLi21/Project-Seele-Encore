package com.projectseele.mixin;

import com.projectseele.physics.GiantInsideBlocks;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.level.block.state.BlockState;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** Gives this mod's giants the section walk of {@link GiantInsideBlocks} in place of vanilla's cell by cell one. */
@Mixin(Entity.class)
public abstract class GiantInsideBlocksMixin implements GiantInsideBlocks.Host
{
    @Shadow protected abstract void onInsideBlock(BlockState state);

    @Override
    public void projectseele$insideBlock(BlockState state)
    {
        this.onInsideBlock(state);
    }

    @Inject(method = "checkInsideBlocks", at = @At("HEAD"), cancellable = true)
    private void projectseele$giantInsideBlocks(CallbackInfo callback)
    {
        Entity entity = (Entity) (Object) this;
        if (GiantInsideBlocks.applies(entity) && GiantInsideBlocks.scan(entity, this)) callback.cancel();
    }
}
