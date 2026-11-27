package com.projectseele.client.render;

import com.projectseele.ProjectSeele;
import net.minecraft.network.chat.Component;
import net.minecraft.server.packs.PackType;
import net.minecraft.server.packs.PathPackResources;
import net.minecraft.server.packs.repository.Pack;
import net.minecraft.server.packs.repository.PackSource;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.AddPackFindersEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.ModList;
import net.minecraftforge.fml.common.Mod;

/** MTR reads every resource pack's manifest at the same path, so publish ours as a separate pack. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, value = Dist.CLIENT, bus = Mod.EventBusSubscriber.Bus.MOD)
public final class AshiShipResources {
    @SubscribeEvent
    public static void findPack(AddPackFindersEvent event) {
        if (event.getPackType() != PackType.CLIENT_RESOURCES) return;
        var root = ModList.get().getModFileById(ProjectSeele.MODID).getFile().findResource("resourcepacks/ashi_ship");
        var pack = Pack.readMetaAndCreate("projectseele/ashi_ship", Component.literal("芦之湖観光船"), true,
                id -> new PathPackResources(id, root, true), PackType.CLIENT_RESOURCES, Pack.Position.TOP, PackSource.BUILT_IN);
        if (pack != null) event.addRepositorySource(consumer -> consumer.accept(pack));
    }
}
