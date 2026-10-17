package com.projectseele.world;

import java.util.Set;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;

/** Natural copper ageing changes colour, not the closed seal's solid shape. */
public final class NervMechanicalMaterialR53
{
    private static final Set<Block> CUT_COPPER=Set.of(Blocks.CUT_COPPER,Blocks.EXPOSED_CUT_COPPER,
            Blocks.WEATHERED_CUT_COPPER,Blocks.OXIDIZED_CUT_COPPER,Blocks.WAXED_CUT_COPPER,
            Blocks.WAXED_EXPOSED_CUT_COPPER,Blocks.WAXED_WEATHERED_CUT_COPPER,Blocks.WAXED_OXIDIZED_CUT_COPPER);

    public static boolean fullCutCopper(BlockState state)
    {return CUT_COPPER.contains(state.getBlock());}

    public static boolean samePhase(BlockState actual,BlockState expected)
    {return actual.equals(expected)||fullCutCopper(actual)&&fullCutCopper(expected);}

    private NervMechanicalMaterialR53(){}
}
