package com.projectseele.client.render;

import com.projectseele.registry.ModBlocks;
import net.minecraft.client.Minecraft;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.client.renderer.LightTexture;
import net.minecraft.core.BlockPos;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.RenderLevelStageEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.util.Map;
import java.util.WeakHashMap;

/** Fixed guide machinery has a world lifetime, independent of tracked cage entities. */
@Mod.EventBusSubscriber(modid="projectseele",value=Dist.CLIENT)
public final class TransferGuidewayR20Renderer
{
    private static final Map<ClientLevel,Boolean> VERIFIED=new WeakHashMap<>();
    private static final BlockPos[] ANCHORS={new BlockPos(30,-443,-213),new BlockPos(9,-438,-204),new BlockPos(9,-425,-140),new BlockPos(9,-412,-76)};
    @SubscribeEvent public static void draw(RenderLevelStageEvent event)
    {
        if(event.getStage()!=RenderLevelStageEvent.Stage.AFTER_ENTITIES)return;
        var level=Minecraft.getInstance().level;if(level==null||!level.dimension().location().toString().equals("projectseele:geofront"))return;
        if(R52FixedGuideRenderer.draw(event,level))return;
        var camera=event.getCamera().getPosition();if(camera.y> -260||camera.y< -510||Math.abs(camera.x-30)>260||Math.abs(camera.z+140)>310)return;
        if(!VERIFIED.containsKey(level))
        {
            for(var p:ANCHORS)if(level.hasChunkAt(p)&&level.getBlockState(p).is(ModBlocks.NERV_MACHINE_HAZARD.get())){VERIFIED.put(level,true);break;}
            if(!VERIFIED.containsKey(level))return;
        }
        var poses=event.getPoseStack();poses.pushPose();poses.translate(30.5-camera.x,-442.96-camera.y,-239.5-camera.z);
        TvFacilityMeshes.draw("r20_transfer_guide",poses,LightTexture.FULL_BRIGHT);poses.popPose();
    }
    private TransferGuidewayR20Renderer(){}
}
