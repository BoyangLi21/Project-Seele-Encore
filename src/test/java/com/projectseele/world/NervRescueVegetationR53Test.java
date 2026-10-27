package com.projectseele.world;

import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.LeavesBlock;

/** Material classification only; native destruction still applies the world's protection hooks. */
public final class NervRescueVegetationR53Test
{
    public static void main(String[] args)
    {
        net.minecraft.SharedConstants.tryDetectVersion();
        net.minecraftforge.fml.loading.FMLPaths.loadAbsolutePaths(java.nio.file.Path.of(".Codex/vegetation-test").toAbsolutePath());
        try{net.minecraft.server.Bootstrap.bootStrap();}catch(ExceptionInInitializerError e)
        {if(java.util.Arrays.stream(e.getStackTrace()).noneMatch(f->f.getClassName().equals("net.minecraftforge.network.NetworkHooks"))||net.minecraft.core.registries.BuiltInRegistries.BLOCK.size()<1000)throw e;}
        var leaf=Blocks.OAK_LEAVES.defaultBlockState();
        check(NervRescueVegetationR53.vanillaLeaf(leaf.setValue(LeavesBlock.PERSISTENT,true)),"Planted leaf rejected");
        check(NervRescueVegetationR53.vanillaLeaf(leaf.setValue(LeavesBlock.PERSISTENT,false)),"Natural leaf rejected");
        check(!NervRescueVegetationR53.vanillaLeaf(Blocks.OAK_LOG.defaultBlockState()),"Trunk admitted");
        check(!NervRescueVegetationR53.vanillaLeaf(Blocks.STONE.defaultBlockState()),"Building material admitted");
        check(!NervRescueVegetationR53.vanillaLeaf(Blocks.AIR.defaultBlockState()),"Air admitted");
    }
    private static void check(boolean condition,String why){if(!condition)throw new AssertionError(why);}
    private NervRescueVegetationR53Test(){}
}
