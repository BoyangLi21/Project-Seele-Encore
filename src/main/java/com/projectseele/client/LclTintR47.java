package com.projectseele.client;

import com.projectseele.ProjectSeele;
import com.projectseele.fluid.LclFluidType;
import com.projectseele.registry.ModBlocks;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.RegisterColorHandlersEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Block/particle colour only; actual fluid meshes use LclFluidType's Forge extension. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, bus = Mod.EventBusSubscriber.Bus.MOD, value = Dist.CLIENT)
public final class LclTintR47
{
    @SubscribeEvent
    public static void blockColors(RegisterColorHandlersEvent.Block event)
    {
        event.register((state, level, pos, index) -> LclFluidType.TINT, ModBlocks.LCL_BLOCK.get());
    }

    private LclTintR47() {}
}
