package com.projectseele.world;

import com.projectseele.registry.ModBlockEntities;
import net.minecraft.core.*;
import net.minecraft.util.StringRepresentable;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.context.BlockPlaceContext;
import net.minecraft.world.level.*;
import net.minecraft.world.level.block.*;
import net.minecraft.world.level.block.entity.*;
import net.minecraft.world.level.block.state.*;
import net.minecraft.world.level.block.state.properties.EnumProperty;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraft.world.phys.shapes.*;
import java.util.*;

/** Human-scale period fixtures; collision follows the entire model envelope. */
public final class PeriodFixtureBlock extends HorizontalDirectionalBlock implements EntityBlock
{
    public enum Kind implements StringRepresentable
    {
        PUBLIC_PHONE, NOTICE_BOARD, UTILITY_BOX, PIPE_RUN, BOLLARD, HYDRANT, WALL_CLOCK, DRINKING_FOUNTAIN,
        CAFE_COUNTER, CAFE_TABLE, CAFE_STOOL, NEWSPAPER_RACK, COFFEE_MACHINE, SHOP_SIGN, DOCUMENT_CART, TECH_BENCH, PARKED_BICYCLE, VENDING_MACHINE, LETTER_BOX;
        @Override public String getSerializedName() { return name().toLowerCase(Locale.ROOT); }
    }
    public static final EnumProperty<Kind> KIND = EnumProperty.create("kind", Kind.class);
    private static final Map<Kind, Map<Direction, VoxelShape>> SHAPES = shapes();
    public PeriodFixtureBlock(Properties properties)
    {
        super(properties); registerDefaultState(stateDefinition.any().setValue(FACING, Direction.SOUTH).setValue(KIND, Kind.PUBLIC_PHONE));
    }
    @Override protected void createBlockStateDefinition(StateDefinition.Builder<Block, BlockState> builder) { builder.add(FACING, KIND); }
    @Override public BlockState getStateForPlacement(BlockPlaceContext context)
    {
        Kind kind=Kind.PUBLIC_PHONE;var tag=context.getItemInHand().getTagElement("BlockStateTag");
        if(tag!=null)try{kind=Kind.valueOf(tag.getString("kind").toUpperCase(Locale.ROOT));}catch(IllegalArgumentException ignored){}
        var state=defaultBlockState().setValue(FACING,context.getHorizontalDirection().getOpposite()).setValue(KIND,kind);
        return canSurvive(state,context.getLevel(),context.getClickedPos())?state:null;
    }
    public static int upperCells(Kind kind)
    {return switch(kind){case PUBLIC_PHONE->2;case NOTICE_BOARD,NEWSPAPER_RACK,COFFEE_MACHINE,TECH_BENCH,PARKED_BICYCLE,VENDING_MACHINE,LETTER_BOX->1;default->0;};}
    public static VoxelShape fullShape(BlockState state){return SHAPES.get(state.getValue(KIND)).get(state.getValue(FACING));}
    public static VoxelShape slice(VoxelShape shape){return Shapes.joinUnoptimized(shape,Shapes.box(-16,0,-16,16,1,16),BooleanOp.AND);}
    @Override public boolean canSurvive(BlockState state,LevelReader level,BlockPos pos)
    {
        for(int offset=1;offset<=upperCells(state.getValue(KIND));offset++)
        {
            var upper=level.getBlockState(pos.above(offset));
            if(!upper.isAir()&&!(upper.getBlock() instanceof PeriodFixturePartBlock&&upper.getValue(PeriodFixturePartBlock.OFFSET)==offset))return false;
        }
        return true;
    }
    @Override public void setPlacedBy(Level level,BlockPos pos,BlockState state,net.minecraft.world.entity.LivingEntity placer,net.minecraft.world.item.ItemStack stack)
    {
        super.setPlacedBy(level,pos,state,placer,stack);
        for(int offset=1;offset<=upperCells(state.getValue(KIND));offset++)
            level.setBlock(pos.above(offset),com.projectseele.registry.ModBlocks.PERIOD_FIXTURE_PART.get().defaultBlockState().setValue(PeriodFixturePartBlock.OFFSET,offset),3);
    }
    @Override public void onRemove(BlockState state,Level level,BlockPos pos,BlockState replacement,boolean moving)
    {
        if(!level.isClientSide&&replacement.getBlock()!=this)
            for(int offset=1;offset<=upperCells(state.getValue(KIND));offset++)
            {
                var upper=level.getBlockState(pos.above(offset));
                if(upper.getBlock() instanceof PeriodFixturePartBlock&&upper.getValue(PeriodFixturePartBlock.OFFSET)==offset)level.removeBlock(pos.above(offset),moving);
            }
        super.onRemove(state,level,pos,replacement,moving);
    }
    @Override public net.minecraft.world.item.ItemStack getCloneItemStack(BlockGetter level,BlockPos pos,BlockState state)
    {
        var stack=new net.minecraft.world.item.ItemStack(com.projectseele.registry.ModItems.PERIOD_FIXTURE.get());
        stack.getOrCreateTagElement("BlockStateTag").putString("kind",state.getValue(KIND).getSerializedName());return stack;
    }
    @Override public BlockState rotate(BlockState state, Rotation rotation) { return state.setValue(FACING, rotation.rotate(state.getValue(FACING))); }
    @Override public BlockState mirror(BlockState state, Mirror mirror) { return rotate(state, mirror.getRotation(state.getValue(FACING))); }
    @Override public VoxelShape getShape(BlockState state, BlockGetter level, BlockPos pos, CollisionContext context) { return slice(fullShape(state)); }
    @Override public RenderShape getRenderShape(BlockState state) { return RenderShape.INVISIBLE; }
    @Override public BlockEntity newBlockEntity(BlockPos pos, BlockState state) { return new PeriodFixtureBlockEntity(pos, state); }
    @Override public <T extends BlockEntity> BlockEntityTicker<T> getTicker(Level level, BlockState state, BlockEntityType<T> type)
    {
        return !level.isClientSide && state.getValue(KIND) == Kind.WALL_CLOCK && type == ModBlockEntities.PERIOD_FIXTURE.get()
                ? (world, pos, block, entity) -> ((PeriodFixtureBlockEntity) entity).updateClock() : null;
    }
    @Override public InteractionResult use(BlockState state, Level level, BlockPos pos, Player player, InteractionHand hand, BlockHitResult hit)
    {
        if (hand != InteractionHand.MAIN_HAND) return InteractionResult.PASS;
        if(state.getValue(KIND)==Kind.CAFE_STOOL)return NervOfficeChairBlock.sit(level,pos,player,state.getValue(FACING),-.25);
        if(!level.isClientSide&&state.getValue(KIND)==Kind.TECH_BENCH&&player instanceof net.minecraft.server.level.ServerPlayer operator)
            operator.sendSystemMessage(net.minecraft.network.chat.Component.literal("设施监视终端\n初号机："+NervStaffDialogue.readinessHint(operator.serverLevel(),1,"query")));
        if (!level.isClientSide && state.getValue(KIND) == Kind.PUBLIC_PHONE)
        {
            if(player instanceof net.minecraft.server.level.ServerPlayer caller
                    &&PilotRestroomServicesR47.handlePhoneR47(caller,pos))return InteractionResult.CONSUME;
            player.displayClientMessage(net.minecraft.network.chat.Component.literal("线路处于紧急管制。请按站内导向牌前往 NERV 接驳设施。"), false);
            level.playSound(null, pos, com.projectseele.registry.ModSounds.PERIOD_PHONE_BUSY.get(), net.minecraft.sounds.SoundSource.BLOCKS, .55F, 1);
        }
        else if (!level.isClientSide && state.getValue(KIND) == Kind.NOTICE_BOARD && level.getBlockEntity(pos) instanceof PeriodFixtureBlockEntity board)
            player.displayClientMessage(net.minecraft.network.chat.Component.literal(board.title()+"\n"+String.join("\n",board.lines())), false);
        return InteractionResult.sidedSuccess(level.isClientSide);
    }
    private static Map<Kind, Map<Direction, VoxelShape>> shapes()
    {
        Map<Kind, Map<Direction, VoxelShape>> result = new EnumMap<>(Kind.class);
        for (Kind kind : Kind.values())
        {
            VoxelShape shape = switch (kind)
            {
                case PUBLIC_PHONE -> Shapes.or(box(.4,0,.4,1.3,35.5,1.3),box(14.7,0,.4,15.6,35.5,1.3),
                        box(.4,0,13.3,1.3,35.5,14.3),box(14.7,0,13.3,15.6,35.5,14.3),
                        box(.4,34.8,.4,15.6,36.7,15.2),box(1.2,9.2,1.2,14.8,10.4,12.8),box(3.1,10.4,2,12.4,22.5,8.9),
                        box(1,10.3,1.3,1.3,34.5,13.7),box(14.7,10.3,1.3,15,34.5,13.7),box(1.2,10.3,1.1,14.8,34.5,1.4));
                case NOTICE_BOARD -> Shapes.or(box(.8,10,6.6,15.2,30,9.2),box(1.7,0,6.7,2.7,31,7.7),box(13.3,0,6.7,14.3,31,7.7));
                case UTILITY_BOX -> box(1.6,0,.8,14.4,15,5.5);
                case PIPE_RUN -> box(2,0,.3,13,16,3.8);
                case BOLLARD -> box(6.8,0,6.8,9.2,12.6,9.2);
                case HYDRANT -> box(4.5,0,5.4,11.5,11.7,10.6);
                case WALL_CLOCK -> box(1.2,1.2,.8,14.8,14.8,3.3);
                case DRINKING_FOUNTAIN -> box(2.2,0,2.7,13.8,14.5,13);
                case CAFE_COUNTER -> box(.1,0,.4,15.9,14.7,15.6);
                case CAFE_TABLE -> Shapes.or(box(6.9,0,6.9,9.1,11.2,9.1),box(.9,11.2,1.2,15.1,12.3,14.8));
                case CAFE_STOOL -> box(4,0,4,12,8.8,12);
                case NEWSPAPER_RACK -> box(1.2,0,2.2,14.8,28.3,13.8);
                case COFFEE_MACHINE -> Shapes.or(box(.4,0,1.2,15.6,13.1,15),box(1.9,13.1,3.2,13.2,20.5,11.2));
                case SHOP_SIGN -> box(-15.1,.5,.7,31.1,12.8,2.4);
                case DOCUMENT_CART -> box(1.6,0,1.6,14.4,15,14.4);
                case TECH_BENCH -> Shapes.or(box(.4,0,.8,15.6,13.3,15.2),box(2.5,13.3,2.8,13.4,21,11.7));
                case PARKED_BICYCLE -> box(-7.3,0,4,23.3,17.4,12);
                case VENDING_MACHINE -> box(.7,0,.9,15.3,31.1,16.8);
                case LETTER_BOX -> Shapes.or(box(6.2,0,6.3,9.8,8,9.7),box(3,8,3.7,13,20.4,12.6));
            };
            Map<Direction, VoxelShape> rotations = new EnumMap<>(Direction.class);
            for (Direction direction : Direction.Plane.HORIZONTAL)
            {
                VoxelShape rotated = shape;
                for (int i = 0; i < direction.get2DDataValue(); i++)
                {
                    final VoxelShape[] next = {Shapes.empty()};
                    rotated.forAllBoxes((a,b,c,d,e,f) -> next[0] = Shapes.or(next[0], Shapes.box(1-f,b,a,1-c,e,d)));
                    rotated = next[0];
                }
                rotations.put(direction, rotated.optimize());
            }
            result.put(kind, Map.copyOf(rotations));
        }
        return Map.copyOf(result);
    }
}
