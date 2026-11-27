package com.projectseele.world;

import java.util.Locale;
import net.minecraft.core.BlockPos;
import net.minecraft.util.StringRepresentable;
import net.minecraft.world.level.BlockGetter;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.state.BlockBehaviour;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.StateDefinition;
import net.minecraft.world.level.block.state.properties.EnumProperty;
import net.minecraft.world.phys.shapes.CollisionContext;
import net.minecraft.world.phys.shapes.Shapes;
import net.minecraft.world.phys.shapes.VoxelShape;

/** Fitted furniture for apartment 402 and its preserved First Laboratory counterpart. */
public final class ReiRoomFixture extends Block {
    public enum Kind implements StringRepresentable {
        EYEGLASS_CABINET, MEDICINE_FRIDGE, ENTRANCE_SINK, FOLDING_CHAIR, BLIND_TOP, BLIND_BOTTOM;

        @Override
        public String getSerializedName() {
            return name().toLowerCase(Locale.ROOT);
        }
    }

    public static final EnumProperty<Kind> KIND = EnumProperty.create("kind", Kind.class);
    private static final VoxelShape CABINET = box(1, 0, 1, 15, 11, 15);
    private static final VoxelShape FRIDGE = box(1, 0, 1, 15, 14, 15);
    private static final VoxelShape SINK = Shapes.or(box(1, 0, 1, 15, 12, 13), box(6, 12, 3, 10, 16, 7));
    private static final VoxelShape CHAIR = Shapes.or(box(2, 0, 3, 14, 8, 14), box(2, 8, 3, 14, 15, 5));
    private static final VoxelShape BLIND = box(0, 0, 11, 16, 16, 15);

    public ReiRoomFixture(BlockBehaviour.Properties properties) {
        super(properties);
        registerDefaultState(stateDefinition.any().setValue(KIND, Kind.EYEGLASS_CABINET));
    }

    @Override
    protected void createBlockStateDefinition(StateDefinition.Builder<Block, BlockState> builder) {
        builder.add(KIND);
    }

    @Override
    public VoxelShape getShape(BlockState state, BlockGetter level, BlockPos pos, CollisionContext context) {
        return switch (state.getValue(KIND)) {
            case EYEGLASS_CABINET -> CABINET;
            case MEDICINE_FRIDGE -> FRIDGE;
            case ENTRANCE_SINK -> SINK;
            case FOLDING_CHAIR -> CHAIR;
            case BLIND_TOP, BLIND_BOTTOM -> BLIND;
        };
    }
}
