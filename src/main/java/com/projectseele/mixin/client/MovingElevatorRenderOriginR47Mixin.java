package com.projectseele.mixin.client;

import com.mojang.blaze3d.vertex.PoseStack;
import com.supermartijn642.movingelevators.elevator.ElevatorGroup;
import com.supermartijn642.movingelevators.elevator.ElevatorGroupRenderer;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.core.BlockPos;
import net.minecraft.util.Mth;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.ModifyVariable;

/** The renderer's virtual block/BE coordinates use the same floor rule as world blocks. */
@Mixin(value=ElevatorGroupRenderer.class,remap=false)
public abstract class MovingElevatorRenderOriginR47Mixin
{
    @ModifyVariable(method={"renderGroupBlocks","renderGroupBlockEntities"},
            at=@At("STORE"),ordinal=0,remap=false)
    private static BlockPos projectSeele$floorUndergroundRenderAnchor(BlockPos original,
            PoseStack poses,ElevatorGroup group,MultiBufferSource buffers,float partialTick)
    {
        double y=Mth.lerp(partialTick,group.getLastY(),group.getCurrentY());
        return BlockPos.containing(group.getCageAnchorPos(y));
    }
}
