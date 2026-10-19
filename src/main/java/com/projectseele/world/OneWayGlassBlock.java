package com.projectseele.world;

import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.world.item.context.BlockPlaceContext;
import net.minecraft.world.level.block.HorizontalDirectionalBlock;
import net.minecraft.world.level.block.EntityBlock;
import net.minecraft.world.level.block.RenderShape;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.Mirror;
import net.minecraft.world.level.block.Rotation;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.StateDefinition;
import net.minecraft.world.level.BlockGetter;
import net.minecraft.world.level.block.state.properties.BooleanProperty;

/**
 * Directional glazing whose outward face uses the pyramid's black skin.
 *
 * <p>{@link #FACING} always points out of the room.  The block model renders
 * the normal exterior cladding outside; the room-side view remains optically
 * empty while the full block keeps its structural collision.</p>
 */
public final class OneWayGlassBlock extends HorizontalDirectionalBlock implements EntityBlock
{
    public static final BooleanProperty PYRAMID=BooleanProperty.create("pyramid");
    public OneWayGlassBlock(Properties properties)
    {
        super(properties);
        registerDefaultState(stateDefinition.any()
                .setValue(FACING, Direction.NORTH).setValue(PYRAMID,false));
    }

    @Override
    public BlockState getStateForPlacement(BlockPlaceContext context)
    {
        return defaultBlockState().setValue(FACING,
                context.getHorizontalDirection().getOpposite());
    }

    @Override
    public BlockState rotate(BlockState state, Rotation rotation)
    {
        return state.setValue(FACING, rotation.rotate(state.getValue(FACING)));
    }

    @Override
    public BlockState mirror(BlockState state, Mirror mirror)
    {
        return rotate(state, mirror.getRotation(state.getValue(FACING)));
    }

    // Old saves have no block-entity NBT for the original directional pane.
    // Keep that state on its original baked-model path instead of hiding it.
    @Override public RenderShape getRenderShape(BlockState state)
    {
        return RenderShape.MODEL;
    }
    @Override public BlockEntity newBlockEntity(BlockPos pos,BlockState state)
    {
        return state.getValue(PYRAMID)?new OneWayGlassBlockEntity(pos,state):null;
    }

    @Override public int getLightBlock(BlockState state,BlockGetter level,BlockPos pos)
    {
        // Optical visibility is directional, but the opaque exterior must not
        // advertise the lit room as a glowing window in the dark pyramid skin.
        return state.getValue(PYRAMID)?15:0;
    }

    @Override public boolean propagatesSkylightDown(BlockState state,BlockGetter level,BlockPos pos)
    {
        return !state.getValue(PYRAMID);
    }

    @Override
    protected void createBlockStateDefinition(
            StateDefinition.Builder<net.minecraft.world.level.block.Block,
                    BlockState> builder)
    {
        builder.add(FACING,PYRAMID);
    }
}
