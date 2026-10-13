package com.projectseele.client;

import com.projectseele.registry.ModBlocks;
import com.projectseele.registry.ModItems;
import com.projectseele.world.EntryPlugBridgeDeckR48;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.RegisterColorHandlersEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Legacy bridge bounds are the installed R49 beds, whose R50 blocks lack a unit property. */
@Mod.EventBusSubscriber(modid="projectseele",bus=Mod.EventBusSubscriber.Bus.MOD,value=Dist.CLIENT)
public final class EntryPlugBridgeFinishR52
{
    private static final int[] COLOURS={0xDB9A32,0x8655BD,0xBC3932};
    private static int colour(net.minecraft.world.level.block.state.BlockState state,net.minecraft.core.BlockPos pos)
    {
        var level=net.minecraft.client.Minecraft.getInstance().level;
        if(level!=null&&pos!=null&&level.dimension().location().toString().equals("projectseele:geofront")
                &&(pos.getY()==-395||pos.getY()==-394)&&pos.getZ()>=-226&&pos.getZ()<=-216)
        {
            // Same finite bed coordinates certified by EntryPlugBridgeTopologyR49.fault.
            for(int unit=0;unit<3;unit++)if(Math.abs(pos.getX()-(-12+42*unit))<=16)return COLOURS[unit];
        }
        return COLOURS[state.getValue(EntryPlugBridgeDeckR48.UNIT_R52)];
    }
    @SubscribeEvent public static void blocks(RegisterColorHandlersEvent.Block event)
    {event.register((state,level,pos,tint)->tint==0?colour(state,pos):-1,ModBlocks.ENTRY_PLUG_BRIDGE_DECK_R48.get());}
    @SubscribeEvent public static void items(RegisterColorHandlersEvent.Item event)
    {event.register((stack,tint)->tint==0?COLOURS[1]:-1,ModItems.ENTRY_PLUG_BRIDGE_DECK_R48.get());}
    private EntryPlugBridgeFinishR52(){}
}
