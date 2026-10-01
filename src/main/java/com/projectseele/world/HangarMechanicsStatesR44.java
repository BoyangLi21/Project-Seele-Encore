package com.projectseele.world;

import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.projectseele.ProjectSeele;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

import java.nio.file.Files;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

/** Actual server phase/rack timeline; client rows cite this server context. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID)
public final class HangarMechanicsStatesR44
{
    public record Context(String phase, int lclLayers, int phaseTicks, long serverTime) {}
    private static volatile Map<UUID, Context> current = Map.of();
    private static final JsonArray snapshots = new JsonArray();
    private static final Map<String, JsonObject> phases = new HashMap<>();

    public static Context context(UUID uuid)
    {
        return current.get(uuid);
    }

    @SubscribeEvent
    public static void tick(TickEvent.ServerTickEvent event)
    {
        if (!(Boolean.getBoolean("projectseele.r44HangarContacts")
                || Boolean.getBoolean("projectseele.r44HangarMeshWitness"))
                || event.phase != TickEvent.Phase.END || event.getServer().getTickCount() % 20 != 0)
        {
            return;
        }
        var server = event.getServer();
        var root = server.getWorldPath(LevelResource.ROOT).normalize();
        if (!root.getFileName().toString().equals("SEELE_FIELD_R44_REVIEW"))
        {
            throw new IllegalStateException("Actual hangar state timeline refuses another world");
        }
        var level = server.getLevel(FacilitySchemaV2.DIMENSION);
        if (level == null)
        {
            return;
        }
        var contexts = new HashMap<UUID, Context>();
        var rows = new JsonArray();
        for (int variant = 0; variant < 3; variant++)
        {
            var state = EvaLogisticsDirector.status(level, variant);
            var row = new JsonObject();
            row.addProperty("variant", variant);
            row.addProperty("s20_phase", state.phase());
            row.addProperty("lcl_layers", state.lclLayers());
            row.addProperty("phase_ticks", state.ticks());
            row.addProperty("canonical_uuid", state.canonicalId() == null ? "UNREGISTERED" : state.canonicalId().toString());
            row.addProperty("loaded", state.loaded());
            var unit = EvaLogisticsDirector.canonicalUnit(level, variant);
            if (unit != null)
            {
                row.addProperty("actual_entity_uuid", unit.getUUID().toString());
                row.addProperty("carrier_rise", unit.carrierRiseProgress(1F));
                row.addProperty("launch_phase", unit.getLaunchPhase());
                row.addProperty("active_carrier_motion", unit.hasActiveCarrierMotion());
                row.addProperty("recovery_rack", unit.recoveryRackR39());
                row.addProperty("logistics_locked", unit.isNervLogisticsLocked());
                row.addProperty("carrier_power_connected", unit.isCarrierPowerConnected());
                row.addProperty("position", unit.position().toString());
                contexts.put(unit.getUUID(), new Context(state.phase(), state.lclLayers(), state.ticks(), level.getGameTime()));
                phases.put(variant + "/" + state.phase(), row.deepCopy());
            }
            rows.add(row);
        }
        current = Map.copyOf(contexts);
        var snapshot = new JsonObject();
        snapshot.addProperty("server_game_time", level.getGameTime());
        snapshot.add("actual_units", rows);
        snapshots.add(snapshot);
        if (snapshots.size() > 600)
        {
            snapshots.remove(0);
        }
        var report = new JsonObject();
        report.add("latest_snapshots", snapshots.deepCopy());
        report.add("latest_observation_per_actual_variant_phase", new GsonBuilder().create().toJsonTree(phases));
        report.addProperty("status", "Actual server state only; carrier rack and fixed wet restraints are different assemblies. Complete operating/visible eight-state experience still requires actual frames.");
        try
        {
            Files.writeString(root.resolve("r44_hangar_mechanics_states_server.json"), new GsonBuilder().setPrettyPrinting().create().toJson(report));
        }
        catch (Exception failure)
        {
            throw new IllegalStateException("Could not save actual hangar state timeline", failure);
        }
    }

    private HangarMechanicsStatesR44() {}
}
