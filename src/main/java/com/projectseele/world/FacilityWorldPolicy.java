package com.projectseele.world;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.Map;
import java.util.WeakHashMap;
import java.util.Objects;
import com.projectseele.ProjectSeele;
import net.minecraftforge.event.server.ServerStoppedEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.storage.LevelResource;

/**
 * Single authority for deciding which facility generation pipeline may write
 * to the current save.
 *
 * <p>The clean rebuild intentionally starts without legacy chunks. A save
 * name check alone is too weak because a local world can be renamed, so the
 * staging marker is authoritative and stable names are diagnostic fallbacks.</p>
 */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID)
public final class FacilityWorldPolicy
{
    public static final String CLEAN_DIRECTORY = "SEELE_S19_CLEAN";
    public static final String CLEAN_LEVEL_NAME =
            "Project SEELE - S19 Clean";
    public static final String CLEAN_MARKER =
            ".projectseele_s19_clean.json";
    public static final String CLEAN_BUILD_AUTHORIZATION =
            ".projectseele_s19_build_authorized.json";
    public static final String S20_DIRECTORY = "SEELE_S20_REBUILD";
    public static final String S20_LEVEL_NAME =
            "Project SEELE - S20 Rebuild";
    public static final String S20_MARKER =
            ".projectseele_s20_rebuild.json";
    public static final String S22_COASTAL_MARKER =
            ".projectseele_s22_coastal.json";
    public static final String S22_MIGRATION_FREEZE_MARKER =
            ".projectseele_s22_migration_frozen.json";
    public static final String S22_FLEET_PARKED_RECEIPT =
            ".projectseele_s22_fleet_parked_v1.json";
    public static final String SPATIAL_PREVIEW_FREEZE_MARKER =
            ".projectseele_spatial_preview_read_only.json";
    public static final String S20_R10_R12_APPROVAL_RECEIPT =
            ".projectseele_approved_semantic_repairs_r10_r12.json";
    public static final String S20_R14_R16_APPROVAL_RECEIPT =
            ".projectseele_approved_semantic_repairs_r14_r16.json";
    public static final String S20_R28_APPROVAL_RECEIPT =
            ".projectseele_approved_semantic_repairs_r28.json";
    public static final String BROKEN_ARCHIVE_DIRECTORY =
            "SEELE_FULL_REBUILD";
    public static final String BROKEN_ARCHIVE_MARKER =
            ".projectseele_full_rebuild";
    public static final String CONTAMINATED_ARCHIVE_DIRECTORY =
            "SEELE_CLEAN_REBUILD";
    public static final String CONTAMINATED_ARCHIVE_LEVEL_NAME =
            "Project SEELE - Clean Rebuild";
    public static final String CONTAMINATED_ARCHIVE_MARKER =
            ".projectseele_clean_rebuild.json";

    private FacilityWorldPolicy() {}

    private static final Map<MinecraftServer, MarkerSnapshot> MARKERS = new WeakHashMap<>();
    private record MarkerSnapshot(int tick, Path root, String levelName, Map<String, Boolean> present) {}

    /** One real marker stat per server/world/tick, including negative results.
     * Native Windows missing-file stats allocate an exception stack; repeated
     * door synchronization must not repeat that work for the same decision.
     * External changes are observed on the next tick, and explicit same-tick
     * policy changes can call invalidate instead of weakening writer guards. */
    public static boolean markerPresent(MinecraftServer server, String marker)
    {
        Path root = server.getWorldPath(LevelResource.ROOT).toAbsolutePath().normalize();
        String name = server.getWorldData().getLevelName();
        int tick = server.getTickCount();
        synchronized (MARKERS)
        {
            MarkerSnapshot cached = MARKERS.get(server);
            if (cached == null || cached.tick() != tick || !cached.root().equals(root) || !Objects.equals(cached.levelName(), name))
            {
                cached = new MarkerSnapshot(tick, root, name, new HashMap<>());
                MARKERS.put(server, cached);
            }
            return cached.present().computeIfAbsent(marker, value -> Files.isRegularFile(root.resolve(value)));
        }
    }

    public static void invalidate(MinecraftServer server)
    {
        synchronized (MARKERS) { MARKERS.remove(server); }
        S20PhysicalElevatorDirector.invalidateLiftSpecs(server);
    }

    @SubscribeEvent
    public static void onServerStopped(ServerStoppedEvent event)
    {
        invalidate(event.getServer());
    }

    public static boolean isCleanRebuild(MinecraftServer server)
    {
        Path root = server.getWorldPath(LevelResource.ROOT);
        Path name = root.getFileName();
        return markerPresent(server, CLEAN_MARKER)
                || CLEAN_LEVEL_NAME.equals(
                        server.getWorldData().getLevelName())
                || name != null
                && CLEAN_DIRECTORY.equals(name.toString());
    }

    /**
     * True where the bounded S20 additions are authorised.
     *
     * <p>S20 starts from the last coherent human-approved block layout. It is
     * intentionally not a Facility-v2 clean world: none of the S19 staged
     * builders may run against it.</p>
     *
     */
    public static boolean isS20Rebuild(MinecraftServer server)
    {
        Path root = server.getWorldPath(LevelResource.ROOT);
        Path name = root.getFileName();
        return markerPresent(server, S20_MARKER)
                || markerPresent(server, S22_COASTAL_MARKER)
                || S20_LEVEL_NAME.equals(
                        server.getWorldData().getLevelName())
                || name != null && S20_DIRECTORY.equals(name.toString());
    }

    /**
     * True for forensic and recovery-preview saves where every automatic S20
     * world writer is frozen while the authored geometry is surveyed.
     */
    public static boolean isSpatialPreviewFrozen(MinecraftServer server)
    {
        Path root = server.getWorldPath(LevelResource.ROOT);
        return markerPresent(server, SPATIAL_PREVIEW_FREEZE_MARKER);
    }

    /** True only for the separate-seed coastal migration world. */
    public static boolean isS22Coastal(MinecraftServer server)
    {
        Path root = server.getWorldPath(LevelResource.ROOT);
        return markerPresent(server, S22_COASTAL_MARKER);
    }

    /** No S20 map writer may run while approved R28 volumes are in transit. */
    public static boolean isS22MigrationFrozen(MinecraftServer server)
    {
        Path root = server.getWorldPath(LevelResource.ROOT);
        return markerPresent(server, S22_MIGRATION_FREEZE_MARKER);
    }

    /**
     * True only after the exact R10/R11/R12 packets have been applied and
     * read back by the offline fail-closed applicator.
     */
    public static boolean isR10R12Approved(MinecraftServer server)
    {
        Path root = server.getWorldPath(LevelResource.ROOT);
        return markerPresent(server, S20_R10_R12_APPROVAL_RECEIPT);
    }

    /** Correct observation lift, wrong-lift rollback and launch-well deck. */
    public static boolean isR14R16Approved(MinecraftServer server)
    {
        Path root = server.getWorldPath(LevelResource.ROOT);
        return markerPresent(server, S20_R14_R16_APPROVAL_RECEIPT);
    }

    /** Duplicate deep MAGI sculptures were removed by the approved R28 packet. */
    public static boolean isR28Approved(MinecraftServer server)
    {
        Path root = server.getWorldPath(LevelResource.ROOT);
        return markerPresent(server, S20_R28_APPROVAL_RECEIPT);
    }

    public static boolean stagedBuildAuthorized(MinecraftServer server)
    {
        if (!isCleanRebuild(server))
        {
            return false;
        }
        Path root = server.getWorldPath(LevelResource.ROOT);
        return markerPresent(server, CLEAN_BUILD_AUTHORIZATION);
    }

    public static boolean isReadOnlyBrokenArchive(MinecraftServer server)
    {
        Path root = server.getWorldPath(LevelResource.ROOT);
        Path name = root.getFileName();
        return isCleanRebuild(server)
                || BROKEN_ARCHIVE_DIRECTORY.equals(
                server.getWorldData().getLevelName())
                || CONTAMINATED_ARCHIVE_LEVEL_NAME.equals(
                server.getWorldData().getLevelName())
                || name != null
                && (BROKEN_ARCHIVE_DIRECTORY.equals(name.toString())
                || CONTAMINATED_ARCHIVE_DIRECTORY.equals(name.toString()))
                || markerPresent(server, BROKEN_ARCHIVE_MARKER)
                || markerPresent(server, CONTAMINATED_ARCHIVE_MARKER);
    }

    public static void requireCleanRebuild(
            MinecraftServer server, String operation)
    {
        if (!isCleanRebuild(server))
        {
            throw new IllegalStateException(
                    "Facility v2 writer '" + operation
                            + "' is authorised only in "
                            + CLEAN_DIRECTORY + ".");
        }
    }

    public static boolean legacyGenerationAllowed(MinecraftServer server)
    {
        return !isCleanRebuild(server)
                && !isS20Rebuild(server)
                && !isReadOnlyBrokenArchive(server)
                && !isSpatialPreviewFrozen(server)
                && !isS22MigrationFrozen(server);
    }

    /** Regional receipts retire the original S20 civil templates as a whole. */
    public static boolean unmigratedS20CivilGenerationAllowed(ServerLevel level)
    {
        MinecraftServer server = level.getServer();
        return isS20Rebuild(server)
                && !isSpatialPreviewFrozen(server)
                && !isS22MigrationFrozen(server)
                && !FacilityLayoutR20.active(server)
                && !RegionalFacilityLayout.migrated(server);
    }

    public static void requireLegacyGenerationAllowed(
            MinecraftServer server, String operation)
    {
        if (!legacyGenerationAllowed(server))
        {
            throw new IllegalStateException(
                    "Retired facility generator '" + operation
                            + "' is disabled for this world role. Use the "
                            + "clean FacilitySchema command path.");
        }
    }
}
