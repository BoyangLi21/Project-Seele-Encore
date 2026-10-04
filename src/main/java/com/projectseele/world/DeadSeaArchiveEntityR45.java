package com.projectseele.world;

import com.projectseele.registry.ModBlockEntities;
import net.minecraft.core.BlockPos;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.AABB;

public final class DeadSeaArchiveEntityR45 extends BlockEntity
{
    public DeadSeaArchiveEntityR45(BlockPos pos,BlockState state){super(ModBlockEntities.DEAD_SEA_ARCHIVE.get(),pos,state);}
    @Override public AABB getRenderBoundingBox(){return new AABB(worldPosition).expandTowards(0,.32,0);}
}
