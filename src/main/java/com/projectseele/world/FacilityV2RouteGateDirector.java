package com.projectseele.world;

import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;

/**
 * Applies the physical boundary state of registered FacilitySchema ports.
 *
 * <p>A completed owner never exposes an unfinished destination. Public lift
 * landing doors are excluded because their runtime interlock is owned by the
 * persistent elevator controller.</p>
 */
public final class FacilityV2RouteGateDirector
{
    private static BlockState structuralClosed()
    {
        return com.projectseele.world.NervMaterials.structuralBlock().defaultBlockState();
    }
    private static final BlockState OPEN = Blocks.AIR.defaultBlockState();

    private FacilityV2RouteGateDirector() {}

    public static void refresh(ServerLevel level, FacilityV2SavedData data)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return;
        if (!FacilityWorldPolicy.isCleanRebuild(level.getServer())
                || !data.commissioned())
        {
            return;
        }
        FacilitySchemaV2.ResolvedManifest manifest = data.manifest();
        for (FacilitySchemaV2.PortSpec port : manifest.ports())
        {
            if(NervLegacyGenerationGuardR52.evaPort(level,port))continue;
            if (!isManagedProfile(port) || isPublicLiftLanding(port))
            {
                continue;
            }
            if (!complete(data, port.zoneId()))
            {
                continue;
            }
            boolean open = reciprocalCompletionReceiptsPresent(
                    data, manifest, port)
                    && routeUnlocked(data, port);
            setAperture(level, port.aperture(), open ? OPEN : structuralClosed());
        }
    }

    /**
     * The command-room MAGI view is part of the first public slice, but the
     * nearby personnel descent remains a locked blast boundary until the
     * restricted MAGI/Dogma spine itself has a completion receipt.
     */
    private static boolean routeUnlocked(
            FacilityV2SavedData data, FacilitySchemaV2.PortSpec port)
    {
        if ("CV-MAGI-SECURE".equals(port.id())
                || "MAGI-CV-SECURE".equals(port.id()))
        {
            return complete(data, "MAGI_DOGMA_SPINE");
        }
        return true;
    }

    /**
     * Facility-side authority for the only approved exterior seam. Fabric
     * constructs the outside landing but never deletes a block inside the
     * WEST_SUPPORT owner.
     */
    public static void openWestExteriorSeamIfReady(
            ServerLevel level, FacilityV2SavedData facility,
            GeoFrontFabricSavedData fabric)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return;
        if (!FacilityWorldPolicy.isCleanRebuild(level.getServer())
                || fabric.westSeamOpen()
                || !complete(facility, "WEST_SUPPORT")
                || fabric.requireFeature(
                GeoFrontFabricPlan.Feature.WEST_SEAM).state()
                != GeoFrontFabricSavedData.FeatureState.COMPLETE
                || fabric.requireFeature(
                GeoFrontFabricPlan.Feature.ROAD_NETWORK).state()
                != GeoFrontFabricSavedData.FeatureState.COMPLETE)
        {
            return;
        }

        BlockPos centre = facility.manifest().centre();
        FacilitySchemaV2.IntBox opening =
                new FacilitySchemaV2.IntBox(
                        centre.getX() - 208, -360,
                        centre.getZ() + 28,
                        centre.getX() - 207, -354,
                        centre.getZ() + 36);
        setAperture(level, opening, OPEN);
        fabric.markWestSeamOpen();
    }

    private static boolean isManagedProfile(FacilitySchemaV2.PortSpec port)
    {
        return port.clearProfile().startsWith("H")
                || port.clearProfile().startsWith("V")
                || port.clearProfile().startsWith("EVA2X_");
    }

    private static boolean isPublicLiftLanding(
            FacilitySchemaV2.PortSpec port)
    {
        return "PUBLIC_LIFT_SHAFT".equals(port.zoneId())
                || "PUBLIC_LIFT_SHAFT".equals(port.peerZoneId());
    }

    private static boolean complete(FacilityV2SavedData data, String zoneId)
    {
        FacilityV2SavedData.ZoneRecord receipt =
                data.requireZone(zoneId);
        return receipt.state() == FacilityV2SavedData.ZoneState.COMPLETE
                && !receipt.generatorVersion().isBlank()
                && !receipt.buildPlanHash().isBlank();
    }

    /**
     * A lease plane opens only after both owners produced durable completion
     * receipts and the peer declaration points back to this exact port.
     */
    private static boolean reciprocalCompletionReceiptsPresent(
            FacilityV2SavedData data,
            FacilitySchemaV2.ResolvedManifest manifest,
            FacilitySchemaV2.PortSpec port)
    {
        if (!complete(data, port.zoneId())
                || !complete(data, port.peerZoneId()))
        {
            return false;
        }
        return manifest.ports().stream().anyMatch(peer ->
                peer.id().equals(port.peerPortId())
                        && peer.zoneId().equals(port.peerZoneId())
                        && peer.peerPortId().equals(port.id())
                        && peer.peerZoneId().equals(port.zoneId()));
    }

    private static void setAperture(ServerLevel level,
                                    FacilitySchemaV2.IntBox aperture,
                                    BlockState target)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return;
        for (int y = aperture.minY(); y < aperture.maxY(); y++)
        {
            for (int z = aperture.minZ(); z < aperture.maxZ(); z++)
            {
                for (int x = aperture.minX(); x < aperture.maxX(); x++)
                {
                    BlockPos position = new BlockPos(x, y, z);
                    if (!level.getBlockState(position).equals(target))
                    {
                        level.setBlock(position, target,
                                Block.UPDATE_CLIENTS);
                    }
                }
            }
        }
    }
}
