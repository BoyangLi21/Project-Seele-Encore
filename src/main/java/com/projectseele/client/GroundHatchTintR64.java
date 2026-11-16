package com.projectseele.client;

import com.projectseele.ProjectSeele;
import com.projectseele.registry.ModBlocks;
import net.minecraft.client.renderer.BiomeColors;
import net.minecraft.world.level.GrassColor;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.RegisterColorHandlersEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** A ground hatch's cover takes the grass colour of the biome it lies in, as the terrain beside it does. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, bus = Mod.EventBusSubscriber.Bus.MOD, value = Dist.CLIENT)
public final class GroundHatchTintR64
{
    @SubscribeEvent
    public static void blockColors(RegisterColorHandlersEvent.Block event)
    {
        event.register((state, level, pos, index) -> level != null && pos != null
                ? BiomeColors.getAverageGrassColor(level, pos) : GrassColor.getDefaultColor(), ModBlocks.NERV_GROUND_HATCH.get());
    }

    private GroundHatchTintR64() {}
}
