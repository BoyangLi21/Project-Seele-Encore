package com.projectseele.mixin;

import java.util.function.Predicate;
import java.util.stream.Stream;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.RamielEntity;
import com.projectseele.entity.SachielEntity;
import com.projectseele.physics.GiantMoveBlockQueryR53;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.level.block.state.BlockState;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Redirect;

@Mixin(Entity.class)
public abstract class GiantMoveBlockQueryR53Mixin
{
    @Redirect(method="move",at=@At(value="INVOKE",
            target="Ljava/util/stream/Stream;noneMatch(Ljava/util/function/Predicate;)Z",remap=false))
    private boolean seele$giantFireScan(Stream<BlockState> blocks,Predicate<BlockState> predicate)
    {
        Entity entity=(Entity)(Object)this;
        return entity instanceof EvaUnit01Entity||entity instanceof SachielEntity||entity instanceof RamielEntity
                ?GiantMoveBlockQueryR53.noneMatch(entity,blocks,predicate)
                :blocks.noneMatch(predicate);
    }
}
