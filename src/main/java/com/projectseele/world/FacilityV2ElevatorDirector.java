package com.projectseele.world;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.NervCarrierPlatformEntity;
import com.projectseele.registry.ModEntities;
import com.projectseele.world.FacilityV2LiftSavedData.InstallationState;
import net.minecraft.ChatFormatting;
import net.minecraft.core.BlockPos;
import net.minecraft.network.chat.Component;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.sounds.SoundSource;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.AABB;

/**
 * Runtime authority for permanent FacilitySchema v2 lift cabins.
 *
 * <p>Construction plans own shafts and landings. This director owns only
 * cabin identity, call controls and door interlocks. A button never creates a
 * disposable cabin and a rider is never teleported between floors.</p>
 */
public final class FacilityV2ElevatorDirector
{
    private static final String PUBLIC_LIFT_ID = "public-h01";
    private static final String COMMAND_LIFT_ID = "command-secure";
    private static final String STAFF_LIFT_ID = "staff-command";
    private static final String DOGMA_LIFT_ID = "dogma-secure";
    private static final String WEST_SUPPORT_LIFT_ID =
            "west-support-service";
    private static final int PUBLIC_X = 0;
    private static final int PUBLIC_Z = 232;
    private static final double PUBLIC_LOWER_Y = -352.0D;
    private static final int NEARBY_RADIUS = 768;
    private static final int RESCUE_RECOVERY_REVISION = 1;
    private static final int STAFF_LANDING_ARCHITECTURE_REVISION = 2;
    private static final BlockState CLOSED_DOOR =
            Blocks.IRON_BLOCK.defaultBlockState();
    private static final BlockState OPEN_DOOR =
            Blocks.AIR.defaultBlockState();

    private FacilityV2ElevatorDirector() {}

    /** Installs a cabin as part of shaft completion, never from a button. */
    public static void onZoneCompleted(
            ServerLevel level, FacilitySchemaV2.ResolvedManifest manifest,
            String zoneId)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return;
        if (!FacilityWorldPolicy.isCleanRebuild(level.getServer()))
        {
            return;
        }
        switch (zoneId)
        {
            case "PUBLIC_LIFT_SHAFT" -> commissionAndInstallCabin(
                    level, manifest, PUBLIC_LIFT_ID, zoneId,
                    PUBLIC_X, PUBLIC_LOWER_Y, PUBLIC_Z, 2, 0.0F);
            case "CMD_LIFT_SPINE" -> commissionAndInstallCabin(
                    level, manifest, COMMAND_LIFT_ID, zoneId,
                    68, -332.0D, 49, 4, 90.0F);
            case "STAFF_LIFT_SHAFT" -> commissionAndInstallCabin(
                    level, manifest, STAFF_LIFT_ID, zoneId,
                    64, -408.0D, 64, 1, 90.0F);
            case "DOGMA_LIFT_SHAFT" -> commissionAndInstallCabin(
                    level, manifest, DOGMA_LIFT_ID, zoneId,
                    32, -395.0D, 172, 3, 0.0F);
            case "WEST_SUPPORT" -> commissionAndInstallCabin(
                    level, manifest, WEST_SUPPORT_LIFT_ID, zoneId,
                    -184, -408.0D, 64, 1, 90.0F);
            default ->
            {
                // Most facility zones have no movable architectural specimen.
            }
        }
    }

    public static void tick(MinecraftServer server)
    {
        if (NervLegacyGenerationGuardR52.retired(server)) return;
        if (!FacilityWorldPolicy.isCleanRebuild(server))
        {
            return;
        }
        ServerLevel level = server.getLevel(FacilitySchemaV2.DIMENSION);
        if (level == null)
        {
            return;
        }
        FacilityV2SavedData facility = FacilityV2SavedData.get(level);
        if (!facility.commissioned())
        {
            return;
        }
        FacilitySchemaV2.ResolvedManifest manifest = facility.manifest();
        BlockPos centre = manifest.centre();
        serviceArchitectureMigrations(level, manifest, facility);
        if (!hasNearbyPlayer(level, centre))
        {
            return;
        }

        serviceRescueRecommissioning(level, manifest, facility);
        servicePendingCommissioning(level, manifest, facility);
        if (publicLiftReady(facility))
        {
            tickPublicLift(level, manifest);
        }
        if (commandLiftReady(facility))
        {
            tickCommandLift(level, manifest);
        }
        if (staffLiftReady(facility))
        {
            tickStaffLift(level, manifest);
        }
        if (dogmaLiftReady(facility))
        {
            tickDogmaLift(level, manifest);
        }
        if (westSupportLiftReady(facility))
        {
            tickWestSupportLift(level, manifest);
        }
    }

    private static void tickCommandLift(
            ServerLevel level, FacilitySchemaV2.ResolvedManifest manifest)
    {
        if (!liftChunkReady(level, manifest, 68, -332, 49))
        {
            return;
        }
        NervCarrierPlatformEntity cabin = findExistingCabin(
                level, manifest, COMMAND_LIFT_ID, "CMD_LIFT_SPINE");
        if (cabin == null)
        {
            BlockPos centre = manifest.centre();
            setLandingDoorX(level, centre, 64, -332, 46, false);
            setLandingDoorX(level, centre, 64, -324, 46, false);
            return;
        }
        BlockPos centre = manifest.centre();
        setLandingDoorX(level, centre, 64, -332, 46,
                cabin.canOpenLandingDoorAt(-332.0D));
        setLandingDoorX(level, centre, 64, -324, 46,
                cabin.canOpenLandingDoorAt(-324.0D));
        serviceSafetyInterlock(level, manifest, cabin, COMMAND_LIFT_ID,
                "CMD_LIFT_SPINE",
                landingDoorXClosed(level, centre, 64, -332, 46)
                        && landingDoorXClosed(
                                level, centre, 64, -324, 46),
                -332.0D, -324.0D);
    }

    private static void tickPublicLift(
            ServerLevel level, FacilitySchemaV2.ResolvedManifest manifest)
    {
        if (!liftChunkReady(level, manifest, PUBLIC_X,
                (int) PUBLIC_LOWER_Y, PUBLIC_Z))
        {
            return;
        }
        NervCarrierPlatformEntity cabin = findExistingCabin(
                level, manifest, PUBLIC_LIFT_ID, "PUBLIC_LIFT_SHAFT");
        if (cabin == null)
        {
            BlockPos centre = manifest.centre();
            setPublicLandingDoor(level, centre, -352, 226, false);
            setPublicLandingDoor(level, centre, manifest.surfaceY(),
                    237, false);
            return;
        }
        BlockPos centre = manifest.centre();
        double upperY = manifest.surfaceY();
        boolean lowerOpen =
                cabin.canOpenLandingDoorAt(PUBLIC_LOWER_Y);
        boolean upperOpen = cabin.canOpenLandingDoorAt(upperY);
        setPublicLandingDoor(level, centre, -352, 226, lowerOpen);
        setPublicLandingDoor(level, centre, manifest.surfaceY(),
                237, upperOpen);
        serviceSafetyInterlock(level, manifest, cabin, PUBLIC_LIFT_ID,
                "PUBLIC_LIFT_SHAFT",
                publicLandingDoorClosed(level, centre, -352, 226)
                        && publicLandingDoorClosed(level, centre,
                                manifest.surfaceY(), 237),
                PUBLIC_LOWER_Y, upperY);
    }

    private static void tickStaffLift(
            ServerLevel level, FacilitySchemaV2.ResolvedManifest manifest)
    {
        if (!liftChunkReady(level, manifest, 64, -408, 64))
        {
            return;
        }
        NervCarrierPlatformEntity cabin = findExistingCabin(
                level, manifest, STAFF_LIFT_ID, "STAFF_LIFT_SHAFT");
        retireObsoleteStaffLanding(level, manifest.centre());
        if (cabin == null)
        {
            BlockPos centre = manifest.centre();
            setLandingDoorX(level, centre, 60, -408, 61, false);
            setLandingDoorX(level, centre, 60, -348, 61, false);
            setLandingDoorX(level, centre, 68, -348, 61, false);
            setLandingDoorX(level, centre, 60, -332, 61, false);
            return;
        }
        BlockPos centre = manifest.centre();
        setLandingDoorX(level, centre, 60, -408, 61,
                cabin.canOpenLandingDoorAt(-408.0D));
        setLandingDoorX(level, centre, 60, -348, 61,
                cabin.canOpenLandingDoorAt(-348.0D));
        setLandingDoorX(level, centre, 68, -348, 61,
                cabin.canOpenLandingDoorAt(-348.0D));
        setLandingDoorX(level, centre, 60, -332, 61,
                cabin.canOpenLandingDoorAt(-332.0D));
        serviceSafetyInterlock(level, manifest, cabin, STAFF_LIFT_ID,
                "STAFF_LIFT_SHAFT",
                landingDoorXClosed(level, centre, 60, -408, 61)
                        && landingDoorXClosed(
                                level, centre, 60, -348, 61)
                        && landingDoorXClosed(
                                level, centre, 68, -348, 61)
                        && landingDoorXClosed(
                                level, centre, 60, -332, 61),
                -408.0D, -348.0D, -332.0D);
    }

    private static void tickDogmaLift(
            ServerLevel level, FacilitySchemaV2.ResolvedManifest manifest)
    {
        if (!liftChunkReady(level, manifest, 32, -395, 172))
        {
            return;
        }
        NervCarrierPlatformEntity cabin = findExistingCabin(
                level, manifest, DOGMA_LIFT_ID, "DOGMA_LIFT_SHAFT");
        if (cabin == null)
        {
            BlockPos centre = manifest.centre();
            setLandingDoorZ(level, centre, 29, -395, 168, false);
            setLandingDoorZ(level, centre, 29, -576, 176, false);
            return;
        }
        BlockPos centre = manifest.centre();
        setLandingDoorZ(level, centre, 29, -395, 168,
                cabin.canOpenLandingDoorAt(-395.0D));
        setLandingDoorZ(level, centre, 29, -576, 176,
                cabin.canOpenLandingDoorAt(-576.0D));
        serviceSafetyInterlock(level, manifest, cabin, DOGMA_LIFT_ID,
                "DOGMA_LIFT_SHAFT",
                landingDoorZClosed(level, centre, 29, -395, 168)
                        && landingDoorZClosed(
                                level, centre, 29, -576, 176),
                -395.0D, -576.0D);
    }

    private static void tickWestSupportLift(
            ServerLevel level, FacilitySchemaV2.ResolvedManifest manifest)
    {
        if (!liftChunkReady(level, manifest, -184, -408, 64))
        {
            return;
        }
        NervCarrierPlatformEntity cabin = findExistingCabin(
                level, manifest, WEST_SUPPORT_LIFT_ID, "WEST_SUPPORT");
        if (cabin == null)
        {
            BlockPos centre = manifest.centre();
            setLandingDoorX(level, centre, -177, -408, 61, false);
            setLandingDoorX(level, centre, -177, -360, 61, false);
            return;
        }
        BlockPos centre = manifest.centre();
        setLandingDoorX(level, centre, -177, -408, 61,
                cabin.canOpenLandingDoorAt(-408.0D));
        setLandingDoorX(level, centre, -177, -360, 61,
                cabin.canOpenLandingDoorAt(-360.0D));
        serviceSafetyInterlock(level, manifest, cabin,
                WEST_SUPPORT_LIFT_ID, "WEST_SUPPORT",
                landingDoorXClosed(
                        level, centre, -177, -408, 61)
                        && landingDoorXClosed(
                                level, centre, -177, -360, 61),
                -408.0D, -360.0D);
    }

    public static boolean handleUse(ServerPlayer player, BlockPos position)
    {
        if (NervLegacyGenerationGuardR52.retired(player.serverLevel())) return false;
        ServerLevel level = player.serverLevel();
        if (!FacilityWorldPolicy.isCleanRebuild(level.getServer())
                || !level.dimension().equals(FacilitySchemaV2.DIMENSION))
        {
            return false;
        }
        FacilityV2SavedData facility = FacilityV2SavedData.get(level);
        if (!facility.commissioned())
        {
            return false;
        }
        FacilitySchemaV2.ResolvedManifest manifest = facility.manifest();
        if (publicLiftReady(facility)
                && handlePublicUse(player, position, manifest))
        {
            return true;
        }
        if (commandLiftReady(facility)
                && handleCommandUse(player, position, manifest))
        {
            return true;
        }
        if (staffLiftReady(facility)
                && handleStaffUse(player, position, manifest))
        {
            return true;
        }
        if (westSupportLiftReady(facility)
                && handleWestSupportUse(player, position, manifest))
        {
            return true;
        }
        return dogmaLiftReady(facility)
                && handleDogmaUse(player, position, manifest);
    }

    private static boolean handleCommandUse(
            ServerPlayer player, BlockPos position,
            FacilitySchemaV2.ResolvedManifest manifest)
    {
        BlockPos centre = manifest.centre();
        BlockPos l2Call = centre.offset(63, -330, 45);
        BlockPos l2Destination = centre.offset(63, -329, 45);
        BlockPos l3Call = centre.offset(63, -322, 45);
        BlockPos l3Destination = centre.offset(63, -321, 45);
        if (!position.equals(l2Call)
                && !position.equals(l2Destination)
                && !position.equals(l3Call)
                && !position.equals(l3Destination))
        {
            return false;
        }
        double targetY = position.equals(l2Call)
                || position.equals(l3Destination)
                ? -332.0D : -324.0D;
        NervCarrierPlatformEntity cabin = findExistingCabin(
                player.serverLevel(), manifest, COMMAND_LIFT_ID,
                "CMD_LIFT_SPINE");
        return requestTravel(player, cabin, targetY,
                "COMMAND LIFT",
                targetY == -332.0D ? "L2 SECURE SPINE"
                        : "L3 HIGH COMMAND");
    }

    private static boolean handlePublicUse(
            ServerPlayer player, BlockPos position,
            FacilitySchemaV2.ResolvedManifest manifest)
    {
        ServerLevel level = player.serverLevel();
        BlockPos centre = manifest.centre();
        BlockPos lowerControl = centre.offset(-9, -350, 223);
        BlockPos lowerDestination = centre.offset(-9, -349, 223);
        BlockPos upperControl = centre.offset(
                8, manifest.surfaceY() + 2, 240);
        BlockPos upperDestination = centre.offset(
                8, manifest.surfaceY() + 3, 240);
        boolean lowerPressed = position.equals(lowerControl);
        boolean lowerDestinationPressed =
                position.equals(lowerDestination);
        boolean upperPressed = position.equals(upperControl);
        boolean upperDestinationPressed =
                position.equals(upperDestination);
        if (!lowerPressed && !lowerDestinationPressed
                && !upperPressed && !upperDestinationPressed)
        {
            return false;
        }

        NervCarrierPlatformEntity cabin = findExistingCabin(
                level, manifest, PUBLIC_LIFT_ID, "PUBLIC_LIFT_SHAFT");
        if (cabin == null)
        {
            player.displayClientMessage(Component.literal(
                    "H-01 LIFT  CABIN IDENTITY UNAVAILABLE")
                    .withStyle(ChatFormatting.RED), true);
            return true;
        }
        if (!cabin.isPersistentLiftIdle())
        {
            player.displayClientMessage(Component.literal(
                    "H-01 LIFT  IN TRANSIT")
                    .withStyle(ChatFormatting.GOLD), true);
            return true;
        }

        double requestedY;
        String operation;
        if (lowerPressed)
        {
            requestedY = PUBLIC_LOWER_Y;
            operation = "CALL GEOFRONT";
        }
        else if (lowerDestinationPressed)
        {
            requestedY = manifest.surfaceY();
            operation = "SELECT TOKYO-3";
        }
        else if (upperPressed)
        {
            requestedY = manifest.surfaceY();
            operation = "CALL TOKYO-3";
        }
        else
        {
            requestedY = PUBLIC_LOWER_Y;
            operation = "SELECT GEOFRONT";
        }

        if (!cabin.beginPersistentLiftTravel(requestedY))
        {
            player.displayClientMessage(Component.literal(
                    "H-01 LIFT  CABIN READY AT THIS LANDING")
                    .withStyle(ChatFormatting.YELLOW), true);
            return true;
        }
        level.playSound(null, position,
                SoundEvents.NOTE_BLOCK_PLING.value(),
                SoundSource.BLOCKS, 0.8F, 0.72F);
        player.displayClientMessage(Component.literal(
                "H-01 LIFT  " + operation
                        + " / DOORS CLOSE IN 3 SECONDS")
                .withStyle(ChatFormatting.AQUA), true);
        return true;
    }

    private static boolean handleStaffUse(
            ServerPlayer player, BlockPos position,
            FacilitySchemaV2.ResolvedManifest manifest)
    {
        BlockPos centre = manifest.centre();
        int relativeX = position.getX() - centre.getX();
        int relativeY = position.getY();
        int relativeZ = position.getZ() - centre.getZ();
        if (relativeX != 58 || relativeZ < 58 || relativeZ > 60
                || (relativeY != -406
                && relativeY != -346
                && relativeY != -330))
        {
            return false;
        }
        double targetY = switch (relativeZ)
        {
            case 58 -> -408.0D;
            case 59 -> -348.0D;
            default -> -332.0D;
        };
        NervCarrierPlatformEntity cabin = findExistingCabin(
                player.serverLevel(), manifest, STAFF_LIFT_ID,
                "STAFF_LIFT_SHAFT");
        return requestTravel(player, cabin, targetY,
                "STAFF LIFT", switch (relativeZ)
                {
                    case 58 -> "B4 EVA WET CAGES";
                    case 59 -> "L0 TECHNICAL";
                    default -> "L2 COMMAND";
                });
    }

    /**
     * Revision 1 of the runtime mistakenly opened a fourth door at the
     * retired rescue-map wet-cage Y=-385. S19 has no owner or landing there;
     * restore the shaft wall so the cabin never appears to stop at an
     * unconnected phantom floor.
     */
    private static void retireObsoleteStaffLanding(
            ServerLevel level, BlockPos centre)
    {
        BlockState wall = Blocks.DEEPSLATE_TILES.defaultBlockState();
        for (int z = 61; z <= 66; z++)
        {
            for (int y = -385; y <= -381; y++)
            {
                BlockPos position = centre.offset(60, y, z);
                BlockState current = level.getBlockState(position);
                if (current.is(Blocks.IRON_BLOCK) || current.isAir())
                {
                    level.setBlock(position, wall, Block.UPDATE_CLIENTS);
                }
            }
        }
    }

    private static boolean handleDogmaUse(
            ServerPlayer player, BlockPos position,
            FacilitySchemaV2.ResolvedManifest manifest)
    {
        BlockPos centre = manifest.centre();
        BlockPos upperCall = centre.offset(26, -393, 162);
        BlockPos upperDestination = centre.offset(26, -392, 162);
        BlockPos lowerCall = centre.offset(37, -574, 181);
        BlockPos lowerDestination = centre.offset(37, -573, 181);
        if (!position.equals(upperCall)
                && !position.equals(upperDestination)
                && !position.equals(lowerCall)
                && !position.equals(lowerDestination))
        {
            return false;
        }
        double targetY = position.equals(upperCall)
                || position.equals(lowerDestination)
                ? -395.0D : -576.0D;
        NervCarrierPlatformEntity cabin = findExistingCabin(
                player.serverLevel(), manifest, DOGMA_LIFT_ID,
                "DOGMA_LIFT_SHAFT");
        return requestTravel(player, cabin, targetY,
                "DOGMA LIFT",
                targetY == -395.0D ? "MAGI SECURE" : "CENTRAL DOGMA");
    }

    private static boolean handleWestSupportUse(
            ServerPlayer player, BlockPos position,
            FacilitySchemaV2.ResolvedManifest manifest)
    {
        BlockPos centre = manifest.centre();
        BlockPos lowerCall = centre.offset(-174, -406, 58);
        BlockPos lowerDestination = centre.offset(-174, -405, 58);
        BlockPos upperCall = centre.offset(-174, -358, 58);
        BlockPos upperDestination = centre.offset(-174, -357, 58);
        if (!position.equals(lowerCall)
                && !position.equals(lowerDestination)
                && !position.equals(upperCall)
                && !position.equals(upperDestination))
        {
            return false;
        }
        double targetY = position.equals(lowerCall)
                || position.equals(upperDestination)
                ? -408.0D : -360.0D;
        NervCarrierPlatformEntity cabin = findExistingCabin(
                player.serverLevel(), manifest, WEST_SUPPORT_LIFT_ID,
                "WEST_SUPPORT");
        return requestTravel(player, cabin, targetY,
                "WEST SUPPORT LIFT",
                targetY == -408.0D ? "B4 MAINTENANCE"
                        : "GEOFRONT EXTERIOR");
    }

    private static boolean requestTravel(
            ServerPlayer player, NervCarrierPlatformEntity cabin,
            double targetY, String liftName, String destination)
    {
        if (cabin == null)
        {
            player.displayClientMessage(Component.literal(
                    liftName + "  CABIN IDENTITY UNAVAILABLE")
                    .withStyle(ChatFormatting.RED), true);
            return true;
        }
        if (!cabin.isPersistentLiftIdle())
        {
            player.displayClientMessage(Component.literal(
                    liftName + "  IN TRANSIT")
                    .withStyle(ChatFormatting.GOLD), true);
            return true;
        }
        if (!cabin.beginPersistentLiftTravel(targetY))
        {
            player.displayClientMessage(Component.literal(
                    liftName + "  CABIN READY / " + destination)
                    .withStyle(ChatFormatting.YELLOW), true);
            return true;
        }
        player.serverLevel().playSound(null, player.blockPosition(),
                SoundEvents.NOTE_BLOCK_PLING.value(),
                SoundSource.BLOCKS, 0.8F, 0.72F);
        player.displayClientMessage(Component.literal(
                liftName + "  " + destination
                        + " / DOORS CLOSE IN 3 SECONDS")
                .withStyle(ChatFormatting.AQUA), true);
        return true;
    }

    private static boolean publicLiftReady(FacilityV2SavedData data)
    {
        return data.commissioned()
                && complete(data, "PUBLIC_LIFT_SHAFT")
                && complete(data, "GEOFRONT_TRANSIT")
                && complete(data, "SURFACE_TRANSIT");
    }

    private static boolean staffLiftReady(FacilityV2SavedData data)
    {
        return data.commissioned()
                && complete(data, "STAFF_LIFT_SHAFT")
                && complete(data, "COMMAND_VOLUME")
                && complete(data, "STAFF_SERVICE_CONNECTOR")
                && complete(data, "EAST_SERVICE_SPINE");
    }

    private static boolean commandLiftReady(FacilityV2SavedData data)
    {
        return data.commissioned()
                && complete(data, "CMD_LIFT_SPINE")
                && complete(data, "COMMAND_VOLUME");
    }

    private static boolean dogmaLiftReady(FacilityV2SavedData data)
    {
        return data.commissioned()
                && complete(data, "DOGMA_LIFT_SHAFT")
                && complete(data, "MAGI_DOGMA_SPINE")
                && complete(data, "DOGMA_SPINE");
    }

    private static boolean westSupportLiftReady(FacilityV2SavedData data)
    {
        return data.commissioned()
                && complete(data, "WEST_SUPPORT")
                && complete(data, "STAFF_SERVICE_CONNECTOR");
    }

    private static boolean complete(FacilityV2SavedData data, String zoneId)
    {
        return data.requireZone(zoneId).state()
                == FacilityV2SavedData.ZoneState.COMPLETE;
    }

    private static boolean hasNearbyPlayer(ServerLevel level, BlockPos centre)
    {
        double maxDistanceSquared = NEARBY_RADIUS * NEARBY_RADIUS;
        for (ServerPlayer player : level.players())
        {
            double dx = player.getX() - centre.getX();
            double dz = player.getZ() - centre.getZ();
            if (dx * dx + dz * dz <= maxDistanceSquared)
            {
                return true;
            }
        }
        return false;
    }

    private static void commissionAndInstallCabin(
            ServerLevel level, FacilitySchemaV2.ResolvedManifest manifest,
            String liftId, String shaftZoneId,
            int relativeX, double initialY, int relativeZ,
            int accent, float yaw)
    {
        FacilityV2LiftSavedData identities =
                FacilityV2LiftSavedData.get(level);
        identities.requestCommissioning(liftId);
        installPendingCabin(level, manifest, liftId, shaftZoneId,
                relativeX, initialY, relativeZ, accent, yaw);
    }

    /**
     * Completes a commissioning request after its shaft chunk becomes ready.
     * This path runs from the facility lifecycle, never from a call button.
     */
    private static void servicePendingCommissioning(
            ServerLevel level, FacilitySchemaV2.ResolvedManifest manifest,
            FacilityV2SavedData facility)
    {
        if (publicLiftReady(facility))
        {
            installPendingCabin(level, manifest, PUBLIC_LIFT_ID,
                    "PUBLIC_LIFT_SHAFT", PUBLIC_X, PUBLIC_LOWER_Y,
                    PUBLIC_Z, 2, 0.0F);
        }
        if (commandLiftReady(facility))
        {
            installPendingCabin(level, manifest, COMMAND_LIFT_ID,
                    "CMD_LIFT_SPINE", 68, -332.0D, 49, 4, 90.0F);
        }
        if (staffLiftReady(facility))
        {
            installPendingCabin(level, manifest, STAFF_LIFT_ID,
                    "STAFF_LIFT_SHAFT", 64, -408.0D, 64, 1, 90.0F);
        }
        if (dogmaLiftReady(facility))
        {
            installPendingCabin(level, manifest, DOGMA_LIFT_ID,
                    "DOGMA_LIFT_SHAFT", 32, -395.0D, 172, 3, 0.0F);
        }
        if (westSupportLiftReady(facility))
        {
            installPendingCabin(level, manifest, WEST_SUPPORT_LIFT_ID,
                    "WEST_SUPPORT", -184, -408.0D, 64, 1, 90.0F);
        }
    }

    /**
     * Applies small, owner-bounded corrections to completed lift
     * architecture without rebuilding a shaft around a live cabin.
     */
    private static void serviceArchitectureMigrations(
            ServerLevel level, FacilitySchemaV2.ResolvedManifest manifest,
            FacilityV2SavedData facility)
    {
        if (!staffLiftReady(facility))
        {
            return;
        }
        FacilityV2LiftSavedData identities =
                FacilityV2LiftSavedData.get(level);
        if (!identities.needsArchitectureRevision(STAFF_LIFT_ID,
                STAFF_LANDING_ARCHITECTURE_REVISION))
        {
            return;
        }

        BlockPos centre = manifest.centre();
        BlockPos anchor = centre.offset(64, -409, 70);
        level.getChunkAt(anchor);
        FacilitySchemaV2.IntBox owner =
                manifest.requireZone("STAFF_LIFT_SHAFT").owner();
        StaffLiftShaftV2Plan plan = new StaffLiftShaftV2Plan(manifest);
        int writes = 0;
        for (int x = 57; x <= 70; x++)
        {
            for (int z = 69; z <= 71; z++)
            {
                BlockPos position = centre.offset(x, -409, z);
                if (!contains(owner, position))
                {
                    throw new IllegalStateException(
                            "Staff landing migration escaped its owner at "
                                    + position);
                }
                BlockState target = plan.blockAt(position);
                if (!level.getBlockState(position).equals(target))
                {
                    level.setBlock(position, target, Block.UPDATE_CLIENTS);
                    writes++;
                }
            }
        }
        identities.markArchitectureRevisionApplied(STAFF_LIFT_ID,
                STAFF_LANDING_ARCHITECTURE_REVISION);
        ProjectSeele.LOGGER.info(
                "Facility v2 staff-to-mechanical landing revision {} "
                        + "installed: writes={}",
                STAFF_LANDING_ARCHITECTURE_REVISION, writes);
    }

    /**
     * One-time migration for the local rescue world whose old lift UUIDs were
     * saved after their entity chunks had already been replaced. It first
     * adopts a matching physical cabin if one survives; otherwise it clears
     * only that stale FAULT identity so normal lifecycle commissioning can
     * install exactly one replacement. Call buttons remain interaction-only.
     */
    private static void serviceRescueRecommissioning(
            ServerLevel level, FacilitySchemaV2.ResolvedManifest manifest,
            FacilityV2SavedData facility)
    {
        if (!FacilityV2RescueDirector.isTargetWorld(level.getServer()))
        {
            return;
        }
        recoverLiftIfNeeded(level, manifest, facility,
                PUBLIC_LIFT_ID, "PUBLIC_LIFT_SHAFT",
                PUBLIC_X, (int) PUBLIC_LOWER_Y, PUBLIC_Z);
        recoverLiftIfNeeded(level, manifest, facility,
                COMMAND_LIFT_ID, "CMD_LIFT_SPINE",
                68, -332, 49);
        recoverLiftIfNeeded(level, manifest, facility,
                STAFF_LIFT_ID, "STAFF_LIFT_SHAFT",
                64, -408, 64);
        recoverLiftIfNeeded(level, manifest, facility,
                DOGMA_LIFT_ID, "DOGMA_LIFT_SHAFT",
                32, -395, 172);
        recoverLiftIfNeeded(level, manifest, facility,
                WEST_SUPPORT_LIFT_ID, "WEST_SUPPORT",
                -184, -408, 64);
    }

    private static void recoverLiftIfNeeded(
            ServerLevel level, FacilitySchemaV2.ResolvedManifest manifest,
            FacilityV2SavedData facility, String liftId,
            String shaftZoneId, int relativeX, int y, int relativeZ)
    {
        FacilityV2LiftSavedData identities =
                FacilityV2LiftSavedData.get(level);
        if (!identities.needsRescueRecovery(
                liftId, RESCUE_RECOVERY_REVISION)
                || !complete(facility, shaftZoneId))
        {
            return;
        }

        /*
         * This is a one-time save migration, not a call-button hot path.
         * Loading the five already-authored shaft anchors once guarantees a
         * stale lift cannot remain permanently FAULT simply because nobody
         * happened to stand close enough to load its cabin chunk.
         */
        BlockPos shaftAnchor = manifest.centre().offset(
                relativeX, y, relativeZ);
        level.getChunkAt(shaftAnchor);

        FacilitySchemaV2.IntBox owner =
                manifest.requireZone(shaftZoneId).owner();
        List<NervCarrierPlatformEntity> matches =
                level.getEntitiesOfClass(
                        NervCarrierPlatformEntity.class, owner.toAabb(),
                        candidate -> candidate.isAlive()
                                && candidate.isPersistentLift()
                                && liftId.equals(candidate.getLiftId()));
        if (!matches.isEmpty())
        {
            identities.register(liftId, matches.get(0).getUUID());
            identities.markRescueRecoveryApplied(
                    liftId, RESCUE_RECOVERY_REVISION);
            ProjectSeele.LOGGER.info(
                    "Facility v2 rescue adopted surviving lift cabin {}",
                    liftId);
            return;
        }

        if (identities.installationState(liftId)
                == InstallationState.FAULT)
        {
            identities.requestRescueRecommissioning(liftId);
            ProjectSeele.LOGGER.info(
                    "Facility v2 rescue recommissioned stale lift {}",
                    liftId);
        }
        identities.markRescueRecoveryApplied(
                liftId, RESCUE_RECOVERY_REVISION);
    }

    private static boolean liftChunkReady(
            ServerLevel level, FacilitySchemaV2.ResolvedManifest manifest,
            int relativeX, int y, int relativeZ)
    {
        return level.hasChunkAt(manifest.centre().offset(
                relativeX, y, relativeZ));
    }

    private static NervCarrierPlatformEntity installPendingCabin(
            ServerLevel level, FacilitySchemaV2.ResolvedManifest manifest,
            String liftId, String shaftZoneId,
            int relativeX, double initialY, int relativeZ,
            int accent, float yaw)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return null;
        BlockPos centre = manifest.centre();
        BlockPos shaft = centre.offset(relativeX, (int) initialY, relativeZ);
        if (!level.hasChunkAt(shaft))
        {
            return null;
        }

        FacilityV2LiftSavedData identities =
                FacilityV2LiftSavedData.get(level);
        InstallationState state = identities.installationState(liftId);
        Optional<UUID> known = identities.cabin(liftId);
        if (known.isPresent())
        {
            Entity entity = level.getEntity(known.get());
            if (entity instanceof NervCarrierPlatformEntity cabin
                    && cabin.isAlive() && cabin.isPersistentLift()
                    && liftId.equals(cabin.getLiftId()))
            {
                return cabin;
            }
            if (state == InstallationState.INSTALLED)
            {
                identities.markFault(liftId);
                return null;
            }
        }

        if (state == InstallationState.PENDING)
        {
            FacilitySchemaV2.IntBox owner = manifest.requireZone(
                    shaftZoneId).owner();
            List<NervCarrierPlatformEntity> matches =
                    level.getEntitiesOfClass(
                            NervCarrierPlatformEntity.class, owner.toAabb(),
                            candidate -> candidate.isPersistentLift()
                                    && liftId.equals(candidate.getLiftId()));
            if (!matches.isEmpty())
            {
                NervCarrierPlatformEntity cabin = matches.get(0);
                identities.register(liftId, cabin.getUUID());
                return cabin;
            }
        }

        // Once a commissioned identity existed, its disappearance is a
        // service fault. Never create a replacement with a second UUID.
        if (state != InstallationState.PENDING)
        {
            return null;
        }

        NervCarrierPlatformEntity cabin =
                ModEntities.NERV_LIFT_CABIN.get().create(level);
        if (cabin == null)
        {
            return null;
        }
        cabin.setPos(centre.getX() + relativeX + 0.5D,
                initialY,
                centre.getZ() + relativeZ + 0.5D);
        cabin.setYRot(yaw);
        cabin.configurePersistentLift(liftId, accent);
        if (!level.addFreshEntity(cabin))
        {
            return null;
        }
        identities.register(liftId, cabin.getUUID());
        return cabin;
    }

    /**
     * Interaction and runtime polling may enqueue requests, but never create a
     * cabin. Installation occurs exactly once when the shaft owner receives
     * its COMPLETE construction receipt.
     */
    private static NervCarrierPlatformEntity findExistingCabin(
            ServerLevel level, FacilitySchemaV2.ResolvedManifest manifest,
            String liftId, String shaftZoneId)
    {
        FacilityV2LiftSavedData identities =
                FacilityV2LiftSavedData.get(level);
        Optional<UUID> known = identities.cabin(liftId);
        if (known.isPresent())
        {
            Entity entity = level.getEntity(known.get());
            if (entity instanceof NervCarrierPlatformEntity cabin
                    && cabin.isAlive() && cabin.isPersistentLift()
                    && liftId.equals(cabin.getLiftId()))
            {
                return cabin;
            }
            identities.markFault(liftId);
            return null;
        }
        if (identities.installationState(liftId)
                == InstallationState.INSTALLED)
        {
            identities.markFault(liftId);
            return null;
        }
        return null;
    }

    /**
     * One authority grants a short motion heartbeat only after the durable
     * identity, completed shaft and every physical door agree. Recovery never
     * resumes a saved velocity: it starts from rest toward the nearest audited
     * landing.
     */
    private static void serviceSafetyInterlock(
            ServerLevel level, FacilitySchemaV2.ResolvedManifest manifest,
            NervCarrierPlatformEntity cabin, String liftId,
            String shaftZoneId, boolean allLandingDoorsClosed,
            double... stableFloors)
    {
        FacilityV2LiftSavedData identities =
                FacilityV2LiftSavedData.get(level);
        FacilityV2SavedData facility = FacilityV2SavedData.get(level);
        boolean identityValid =
                identities.installationState(liftId)
                        == InstallationState.INSTALLED
                        && identities.cabin(liftId)
                        .filter(cabin.getUUID()::equals).isPresent()
                        && liftId.equals(cabin.getLiftId());
        boolean shaftComplete = facility.commissioned()
                && complete(facility, shaftZoneId);
        boolean insideShaft = contains(
                manifest.requireZone(shaftZoneId).owner().toAabb(),
                cabin.getBoundingBox());
        if (!identityValid || !shaftComplete || !insideShaft)
        {
            identities.markFault(liftId);
            cabin.forcePersistentLiftFault();
            return;
        }

        boolean motionAllowed = !cabin.isLiftDoorOpen()
                && allLandingDoorsClosed
                && doorwayObstructionClear(level, cabin);
        cabin.authorizePersistentLiftMotion(motionAllowed);
        if (motionAllowed && cabin.isPersistentLiftRecoveryHold()
                && stableFloors.length > 0)
        {
            cabin.recoverPersistentLiftTo(
                    nearestStableFloor(cabin.getY(), stableFloors));
        }
    }

    private static boolean contains(AABB outer, AABB inner)
    {
        double tolerance = 0.05D;
        return inner.minX >= outer.minX - tolerance
                && inner.minY >= outer.minY - tolerance
                && inner.minZ >= outer.minZ - tolerance
                && inner.maxX <= outer.maxX + tolerance
                && inner.maxY <= outer.maxY + tolerance
                && inner.maxZ <= outer.maxZ + tolerance;
    }

    private static boolean contains(
            FacilitySchemaV2.IntBox box, BlockPos position)
    {
        return position.getX() >= box.minX()
                && position.getX() < box.maxX()
                && position.getY() >= box.minY()
                && position.getY() < box.maxY()
                && position.getZ() >= box.minZ()
                && position.getZ() < box.maxZ();
    }

    private static boolean doorwayObstructionClear(
            ServerLevel level, NervCarrierPlatformEntity cabin)
    {
        AABB safetyEnvelope = cabin.getBoundingBox()
                .inflate(0.8D, 0.25D, 0.8D);
        return level.getEntities(cabin, safetyEnvelope,
                candidate -> candidate.isAlive()
                        && candidate.getRootVehicle() != cabin
                        && (candidate instanceof ServerPlayer
                        || candidate instanceof net.minecraft.world.entity
                        .LivingEntity)).isEmpty();
    }

    private static double nearestStableFloor(
            double currentY, double[] stableFloors)
    {
        double nearest = stableFloors[0];
        double distance = Math.abs(currentY - nearest);
        for (int index = 1; index < stableFloors.length; index++)
        {
            double candidateDistance =
                    Math.abs(currentY - stableFloors[index]);
            if (candidateDistance < distance)
            {
                nearest = stableFloors[index];
                distance = candidateDistance;
            }
        }
        return nearest;
    }

    private static boolean publicLandingDoorClosed(
            ServerLevel level, BlockPos centre,
            int bottomY, int relativeZ)
    {
        for (int x = -3; x <= 2; x++)
        {
            for (int y = bottomY; y <= bottomY + 4; y++)
            {
                if (!level.getBlockState(
                        centre.offset(x, y, relativeZ))
                        .is(Blocks.IRON_BLOCK))
                {
                    return false;
                }
            }
        }
        return true;
    }

    private static boolean landingDoorXClosed(
            ServerLevel level, BlockPos centre, int relativeX,
            int bottomY, int minRelativeZ)
    {
        for (int z = minRelativeZ; z < minRelativeZ + 6; z++)
        {
            for (int y = bottomY; y <= bottomY + 4; y++)
            {
                if (!level.getBlockState(
                        centre.offset(relativeX, y, z))
                        .is(Blocks.IRON_BLOCK))
                {
                    return false;
                }
            }
        }
        return true;
    }

    private static boolean landingDoorZClosed(
            ServerLevel level, BlockPos centre, int minRelativeX,
            int bottomY, int relativeZ)
    {
        for (int x = minRelativeX; x < minRelativeX + 6; x++)
        {
            for (int y = bottomY; y <= bottomY + 4; y++)
            {
                if (!level.getBlockState(
                        centre.offset(x, y, relativeZ))
                        .is(Blocks.IRON_BLOCK))
                {
                    return false;
                }
            }
        }
        return true;
    }

    private static void setPublicLandingDoor(ServerLevel level,
                                             BlockPos centre,
                                             int bottomY, int relativeZ,
                                             boolean open)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return;
        BlockState target = open ? OPEN_DOOR : CLOSED_DOOR;
        for (int x = -3; x <= 2; x++)
        {
            for (int y = bottomY; y <= bottomY + 4; y++)
            {
                BlockPos position = centre.offset(x, y, relativeZ);
                if (!level.getBlockState(position).equals(target))
                {
                    level.setBlock(position, target,
                            Block.UPDATE_CLIENTS);
                }
            }
        }
    }

    private static void setLandingDoorX(ServerLevel level,
                                        BlockPos centre, int relativeX,
                                        int bottomY, int minRelativeZ,
                                        boolean open)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return;
        BlockState target = open ? OPEN_DOOR : CLOSED_DOOR;
        for (int z = minRelativeZ; z < minRelativeZ + 6; z++)
        {
            for (int y = bottomY; y <= bottomY + 4; y++)
            {
                BlockPos position = centre.offset(relativeX, y, z);
                if (!level.getBlockState(position).equals(target))
                {
                    level.setBlock(position, target,
                            Block.UPDATE_CLIENTS);
                }
            }
        }
    }

    private static void setLandingDoorZ(ServerLevel level,
                                        BlockPos centre, int minRelativeX,
                                        int bottomY, int relativeZ,
                                        boolean open)
    {
        if (NervLegacyGenerationGuardR52.retired(level)) return;
        BlockState target = open ? OPEN_DOOR : CLOSED_DOOR;
        for (int x = minRelativeX; x < minRelativeX + 6; x++)
        {
            for (int y = bottomY; y <= bottomY + 4; y++)
            {
                BlockPos position = centre.offset(x, y, relativeZ);
                if (!level.getBlockState(position).equals(target))
                {
                    level.setBlock(position, target,
                            Block.UPDATE_CLIENTS);
                }
            }
        }
    }
}
