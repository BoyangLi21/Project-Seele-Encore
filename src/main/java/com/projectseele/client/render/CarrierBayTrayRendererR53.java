package com.projectseele.client.render;

import com.projectseele.world.CarrierBayTrayR53;
import com.projectseele.world.CarrierMountProfileR53;
import com.projectseele.world.NervOriginalCarrierR52;
import com.projectseele.world.NervAirTransportManifestR52;
import com.projectseele.entity.NervCarrierPlatformEntity;
import java.util.*;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.client.renderer.LevelRenderer;
import net.minecraft.core.BlockPos;
import net.minecraftforge.client.event.RenderLevelStageEvent;

/** Tray bridge bearings use the owner's exact source split and interpolated clock. */
final class CarrierBayTrayRendererR53
{
    private record Ready(long next, boolean value, int owner) { }
    private static final Map<Integer,Ready> readiness = new HashMap<>();
    static void clear() { readiness.clear(); }
    static void draw(RenderLevelStageEvent event, ClientLevel level)
    {
        var camera = event.getCamera().getPosition();long now = level.getGameTime();
        for (var bay : CarrierBayTrayR53.selected())
        {
            if (camera.distanceToSqr(bay.root().translation()) > com.projectseele.world.FacilityVisibilityR54.DISTANCE_SQUARED) continue;
            NervCarrierPlatformEntity owner = null;
            if (com.projectseele.client.FacilityFrameClientR52.claimed(level))
                for (var actor : level.entitiesForRendering())
                    if (actor instanceof NervCarrierPlatformEntity carrier && CarrierBayTrayR53.bay(carrier) == bay
                            && CarrierMountProfileR53.read(carrier, event.getPartialTick()).shallowBay()
                            && NervAirTransportManifestR52.same(NervOriginalCarrierR52.actualRoot(carrier, event.getPartialTick()), bay.root()))
                    { owner = carrier; break; }
            int ownerId = owner == null ? -1 : owner.getId();
            var ready = readiness.get(bay.variant());
            if (ready == null || now >= ready.next() || ready.owner() != ownerId)
            { ready = new Ready(now + 20, CarrierBayTrayR53.readyForRender(level, bay, owner), ownerId);readiness.put(bay.variant(), ready); }
            if (!ready.value()) continue;
            float rise = owner == null ? 1 : NervOriginalCarrierR52.progress(owner, event.getPartialTick());
            for (var part : CarrierBayTrayR53.railsAt(bay,rise))
            {
                var bounds = part.mesh().envelope(part.frame(), part.frame());
                if (!event.getFrustum().isVisible(bounds)) continue;
                NervLegacyCarrierRideRendererR52.drawFixed(part, camera, event.getPoseStack(),
                        TvFacilityMeshes.currentBuffers(), LevelRenderer.getLightColor(level, BlockPos.containing(bounds.getCenter())));
            }
        }
    }
    private CarrierBayTrayRendererR53() { }
}
