package com.projectseele.world;

import net.minecraft.world.level.block.GlassBlock;
import net.minecraft.world.level.block.RenderShape;
import net.minecraft.world.level.block.state.BlockState;

/** The native cage retains a solid door plane; its two leaves render separately. */
public final class LiftDoorInterlockR53 extends GlassBlock
{
    public LiftDoorInterlockR53(Properties properties) { super(properties); }
    @Override public RenderShape getRenderShape(BlockState state) { return RenderShape.INVISIBLE; }
}
