package com.projectseele.client.render;

import com.projectseele.entity.NervHangarDoorEntity;
import com.projectseele.world.CarrierTransferRailsR53;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.client.renderer.LevelRenderer;
import net.minecraft.core.BlockPos;
import net.minecraft.world.phys.AABB;
import net.minecraftforge.client.event.RenderLevelStageEvent;

/** The bridge's actual source steel follows its original gate clock. */
final class CarrierTransferRailsRendererR53
{
    static void draw(RenderLevelStageEvent event, ClientLevel level)
    {
        var source = CarrierTransferRailsR53.selected();if (source == null) return;
        var camera = event.getCamera().getPosition();
        for (var gate : source.bridges().keySet())
        {
            if (camera.distanceToSqr(gate.frame().translation()) > com.projectseele.world.FacilityVisibilityR54.DISTANCE_SQUARED) continue;
            for (var door : level.getEntitiesOfClass(NervHangarDoorEntity.class,
                    new AABB(gate.frame().translation(), gate.frame().translation()).inflate(80), e -> e.getUUID().equals(gate.visual())))
                for (var part : CarrierTransferRailsR53.bridgeParts(door, door.actualOpenProgressR52()))
                    if (event.getFrustum().isVisible(part.bounds()))
                        NervLegacyCarrierRideRendererR52.drawFixed(part.steel(), camera, event.getPoseStack(),
                                TvFacilityMeshes.currentBuffers(), LevelRenderer.getLightColor(level, BlockPos.containing(part.bounds().getCenter())));
        }
    }
    private CarrierTransferRailsRendererR53() { }
}
