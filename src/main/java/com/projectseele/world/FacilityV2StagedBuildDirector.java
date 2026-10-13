package com.projectseele.world;

import java.util.List;
import java.util.Map;
import java.util.WeakHashMap;

import com.projectseele.ProjectSeele;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;

/**
 * Executes the explicitly authorised build receipt staged beside a brand-new
 * S19 save.
 *
 * <p>This is not a repair loop. It never writes a legacy owner, never invents
 * a missing route and never reopens a completed owner. It only starts the
 * immutable v2 programmes in order; their individual directors still enforce
 * clean-world identity, owner bounds and durable completion receipts.</p>
 */
public final class FacilityV2StagedBuildDirector
{
    private static final int INTERVAL_TICKS = 20;
    private static final List<String> PUBLIC_ZONES = List.of(
            "TOKYO3_APRON", "SURFACE_TRANSIT", "PUBLIC_LIFT_SHAFT",
            "GEOFRONT_TRANSIT", "NERV_FOYER", "H01_CV_CONNECTOR",
            "COMMAND_VOLUME", "COMMAND_MODULE_CAP", "CMD_LIFT_SPINE",
            "COMMAND_SUITE", "STAFF_LIFT_SHAFT",
            "WEST_SERVICE_SPINE", "WEST_SUPPORT",
            "EAST_SERVICE_SPINE", "STAFF_SERVICE_CONNECTOR");
    private static final List<String> DOGMA_ZONES = List.of(
            "MAGI_CORE", "MAGI_DOGMA_SPINE", "DOGMA_LIFT_SHAFT",
            "DOGMA_SPINE", "LILITH_CHAMBER");
    private static final List<String> EVA_ZONES = List.of(
            "MECH_ACCESS_SPINE", "MECH_AIRLOCK_LINK",
            "MECH_PERSONNEL_TRUNK",
            "MECH_OBS_LINK_00", "UNIT00_CAGE", "UNIT00_CARRIER",
            "UNIT00_SWITCHYARD", "UNIT00_SILO", "UNIT00_SURFACE_HEAD",
            "MECH_OBS_LINK_01", "UNIT01_CAGE", "UNIT01_CARRIER",
            "UNIT01_SWITCHYARD", "UNIT01_SILO", "UNIT01_SURFACE_HEAD",
            "MECH_OBS_LINK_02", "UNIT02_CAGE", "UNIT02_CARRIER",
            "UNIT02_SWITCHYARD", "UNIT02_SILO", "UNIT02_SURFACE_HEAD");
    private static final Map<MinecraftServer, String> LAST_STAGE =
            new WeakHashMap<>();

    private FacilityV2StagedBuildDirector() {}

    public static void tick(MinecraftServer server)
    {
        if (NervLegacyGenerationGuardR52.retired(server)) return;
        if (server.getTickCount() % INTERVAL_TICKS != 0
                || !FacilityWorldPolicy.stagedBuildAuthorized(server))
        {
            return;
        }
        ServerLevel level = server.getLevel(FacilitySchemaV2.DIMENSION);
        if (level == null)
        {
            stage(server, "WAIT_GEOFRONT");
            return;
        }

        FacilityV2SavedData facility = FacilityV2SavedData.get(level);
        if (!facility.commissioned())
        {
            if (!FacilityV2BootstrapDirector.active(server))
            {
                FacilityV2BootstrapDirector.StartResult result =
                        FacilityV2BootstrapDirector.start(level);
                stage(server, result.accepted()
                        ? "PREFLIGHT" : "PREFLIGHT_BLOCKED "
                        + result.message());
            }
            return;
        }

        String failed = failedZone(facility);
        if (failed != null)
        {
            stage(server, "BLOCKED_ZONE " + failed);
            return;
        }
        FacilityV2ProgrammeSavedData programme =
                FacilityV2ProgrammeSavedData.get(level);
        if (facility.activeZone().isPresent() || programme.active())
        {
            stage(server, "BUILD " + programme.programme());
            return;
        }
        if (!complete(facility, PUBLIC_ZONES))
        {
            FacilityV2ProgrammeDirector.startPublicBackbone(level);
            stage(server, "PUBLIC_BACKBONE");
            return;
        }
        if (!complete(facility, DOGMA_ZONES))
        {
            FacilityV2ProgrammeDirector.startDogmaBackbone(level);
            stage(server, "DOGMA_BACKBONE");
            return;
        }
        if (!complete(facility, EVA_ZONES))
        {
            if(NervLegacyGenerationGuardR52.retired(level)){stage(server,"ROOT_R52_EVA_OWNER");return;}
            FacilityV2ProgrammeDirector.startEvaBackbone(level);
            stage(server, "EVA_BACKBONE");
            return;
        }
        if (!FacilityV2ArchitectureDirector.ready(level))
        {
            stage(server, "ARCHITECTURE_MIGRATION");
            return;
        }

        FacilityV2CommandInteriorSavedData interior =
                FacilityV2CommandInteriorSavedData.get(level);
        if (interior.appliedRevision()
                < FacilityV2CommandInteriorDirector.INTERIOR_REVISION)
        {
            stage(server, "COMMAND_ASSET_FUSION");
            return;
        }

        GeoFrontFabricSavedData fabric =
                GeoFrontFabricSavedData.get(level);
        if (fabric.lifecycle() == GeoFrontFabricSavedData.Lifecycle.DRAFT)
        {
            GeoFrontFabricDirector.commit(level);
            stage(server, "FABRIC_COMMITTED");
            return;
        }
        if (fabric.lifecycle() == GeoFrontFabricSavedData.Lifecycle.FAILED)
        {
            stage(server, "FABRIC_FAILED " + fabric.summary());
            return;
        }
        if (fabric.lifecycle() != GeoFrontFabricSavedData.Lifecycle.COMPLETE)
        {
            if (!fabric.programmeActive()
                    && fabric.activeFeature().isEmpty())
            {
                GeoFrontFabricDirector.startAll(level);
            }
            stage(server, "EXTERIOR_FABRIC");
            return;
        }
        stage(server, "READY_FOR_HUMAN_REVIEW");
    }

    private static boolean complete(FacilityV2SavedData facility,
                                    List<String> zones)
    {
        return zones.stream().allMatch(zone ->
        {
            FacilityV2SavedData.ZoneRecord receipt =
                    facility.requireZone(zone);
            return receipt.state()
                    == FacilityV2SavedData.ZoneState.COMPLETE
                    && !receipt.generatorVersion().isBlank()
                    && !receipt.buildPlanHash().isBlank();
        });
    }

    private static String failedZone(FacilityV2SavedData facility)
    {
        return facility.zones().entrySet().stream()
                .filter(entry -> entry.getValue().state()
                        == FacilityV2SavedData.ZoneState.FAILED)
                .map(Map.Entry::getKey)
                .findFirst()
                .orElse(null);
    }

    private static void stage(MinecraftServer server, String value)
    {
        String previous = LAST_STAGE.put(server, value);
        if (!value.equals(previous))
        {
            ProjectSeele.LOGGER.info(
                    "Facility S19 staged build: {}", value);
        }
    }
}
