package com.projectseele.world;

import net.minecraft.core.BlockPos;
import net.minecraft.util.StringRepresentable;
import net.minecraft.world.level.BlockGetter;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.StateDefinition;
import net.minecraft.world.level.block.state.properties.BooleanProperty;
import net.minecraft.world.level.block.state.properties.EnumProperty;
import net.minecraft.world.phys.shapes.CollisionContext;
import net.minecraft.world.phys.shapes.Shapes;
import net.minecraft.world.phys.shapes.VoxelShape;

/** Three-height actual I-girder: same bearing bottom and wheel-running top as the commissioned rail. */
public final class TvCraneGirderR44 extends Block
{
    public enum Segment implements StringRepresentable
    {
        BASE("base"), WEB("web"), TOP("top");
        private final String id;
        Segment(String id) { this.id=id; }
        @Override public String getSerializedName() { return id; }
    }
    public static final EnumProperty<Segment> SEGMENT=EnumProperty.create("segment",Segment.class);
    public static final BooleanProperty JOINT=BooleanProperty.create("joint");
    private static final VoxelShape[][] SHAPES=new VoxelShape[3][2];
    static
    {
        SHAPES[0][0]=Shapes.or(box(2.8,0,0,13.2,1.92,16),box(7.04,1.92,0,8.96,16,16));
        SHAPES[1][0]=box(7.04,0,0,8.96,16,16);
        SHAPES[2][0]=Shapes.or(box(7.04,0,0,8.96,13.44,16),box(2.24,13.44,0,13.76,16,16));
        for(int i=0;i<3;i++)
            SHAPES[i][1]=Shapes.or(SHAPES[i][0],box(5.36,0,6.88,10.64,i==2?13.44:16,9.12));
    }
    public TvCraneGirderR44(Properties properties)
    {
        super(properties);
        registerDefaultState(stateDefinition.any().setValue(SEGMENT,Segment.WEB).setValue(JOINT,false));
    }
    @Override protected void createBlockStateDefinition(StateDefinition.Builder<Block,BlockState> builder)
    {
        builder.add(SEGMENT,JOINT);
    }
    @Override public VoxelShape getShape(BlockState state,BlockGetter level,BlockPos position,CollisionContext context)
    {
        return SHAPES[state.getValue(SEGMENT).ordinal()][state.getValue(JOINT)?1:0];
    }
    @Override public VoxelShape getCollisionShape(BlockState state,BlockGetter level,BlockPos position,CollisionContext context)
    {
        return getShape(state,level,position,context);
    }
    @Override public VoxelShape getOcclusionShape(BlockState state,BlockGetter level,BlockPos position)
    {
        return Shapes.empty();
    }
}
