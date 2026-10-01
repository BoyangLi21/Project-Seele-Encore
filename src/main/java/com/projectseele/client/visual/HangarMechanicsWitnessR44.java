package com.projectseele.client.visual;

import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.projectseele.entity.NervCarrierPlatformEntity;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.world.HangarMechanicsStatesR44;
import net.minecraft.client.Minecraft;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

import java.nio.file.Files;

/** Real client-tracked entity IDs/poses, independent of a body or bounding outline. */
@Mod.EventBusSubscriber(modid = "projectseele", value = Dist.CLIENT)
public final class HangarMechanicsWitnessR44
{
    private static int ticks;
    private static final JsonArray snapshots = new JsonArray();

    @SubscribeEvent
    public static void tick(TickEvent.ClientTickEvent event)
    {
        if (!(Boolean.getBoolean("projectseele.r44HangarContacts")
                || Boolean.getBoolean("projectseele.r44HangarMeshWitness"))
                || event.phase != TickEvent.Phase.END || ++ticks < 80 || ticks % 20 != 0)
        {
            return;
        }
        var mc = Minecraft.getInstance();
        if (mc.level == null || mc.player == null || mc.getSingleplayerServer() == null)
        {
            return;
        }
        var root = mc.getSingleplayerServer().getWorldPath(LevelResource.ROOT).normalize();
        if (!root.getFileName().toString().equals("SEELE_FIELD_R44_REVIEW"))
        {
            throw new IllegalStateException("Client hangar mechanics witness refuses another world");
        }
        var rows = new JsonArray();var units = new JsonArray();int[] gantries = new int[3];
        for (var entity : mc.level.entitiesForRendering())
        {
            if (entity instanceof EvaUnit01Entity unit && !unit.isExperimentalUnit())
            {
                var row = new JsonObject();
                row.addProperty("uuid", unit.getUUID().toString());
                row.addProperty("variant", unit.getUnitVariant());
                row.addProperty("actual_client_carrier_rise", unit.carrierRiseProgress(1F));
                row.addProperty("actual_client_launch_phase", unit.getLaunchPhase());
                row.addProperty("actual_client_active_carrier_motion", unit.hasActiveCarrierMotion());
                row.addProperty("actual_client_recovery_rack", unit.recoveryRackR39());
                row.addProperty("actual_client_logistics_locked", unit.isNervLogisticsLocked());
                row.addProperty("original_origin_section_compiled", mc.levelRenderer.isChunkCompiled(unit.blockPosition()));
                row.addProperty("actualbodyFrameKind", unit.hasActiveCarrierMotion() ? "carrier_analytic_root" : "tracked_entity_interpolated_root");
                row.addProperty("position", unit.position().toString());
                var context = HangarMechanicsStatesR44.context(unit.getUUID());
                if (context != null)
                {
                    row.addProperty("s20_phase", context.phase());
                    row.addProperty("lcl_layers", context.lclLayers());
                    row.addProperty("phase_ticks", context.phaseTicks());
                    row.addProperty("server_context_game_time", context.serverTime());
                    row.addProperty("phase_lcl_source", "Paired actual integrated-server context by identical UUID; not claimed as client-synced phase fields");
                }
                units.add(row);
            }
            if (!(entity instanceof NervCarrierPlatformEntity visual)
                    || !(visual.isRestraintGantry() || visual.isPlugCrane()))
            {
                continue;
            }
            var row = new JsonObject();
            row.addProperty("uuid", visual.getUUID().toString());row.addProperty("entity_id", visual.getId());
            row.addProperty("variant", visual.getUnitVariant());row.addProperty("alive", visual.isAlive());
            row.addProperty("kind", visual.isRestraintGantry() ? "fixed_wet_gantry" : "plug_crane");
            row.addProperty("position", visual.position().toString());row.addProperty("actual_client_box", visual.getBoundingBox().toString());
            row.addProperty("restraint_progress", visual.getRestraintProgress());row.addProperty("ticks", visual.tickCount);
            // This direct call is outside renderLevel's selective redirect:
            // it records the original terrain-section condition independently
            // of a large-entity visibility bypass in the actual draw loop.
            row.addProperty("original_origin_section_compiled", mc.levelRenderer.isChunkCompiled(visual.blockPosition()));
            row.addProperty("actualbodyFrameKind", visual.isRestraintGantry() ? "fixed_world_gantry_anchor" : "interpolated_crane_trolley_anchor");
            if (visual.isRestraintGantry() && visual.getUnitVariant() >= 0 && visual.getUnitVariant() < 3)
            {
                gantries[visual.getUnitVariant()]++;
            }
            rows.add(row);
        }
        var snapshot = new JsonObject();snapshot.addProperty("client_tick", ticks);
        snapshot.addProperty("camera_player", mc.player.position().toString());
        snapshot.add("actual_client_tracked_mechanics", rows);
        snapshot.add("actual_client_units_with_paired_server_phase", units);
        snapshot.addProperty("exactly_one_each_of_three", gantries[0] == 1 && gantries[1] == 1 && gantries[2] == 1);
        snapshots.add(snapshot);
        if (snapshots.size() > 600) snapshots.remove(0);
        var report = new JsonObject();report.add("snapshots", snapshots);
        report.addProperty("status", "ACTUAL_CLIENT_TRACKING only. Visible complete machinery, six surface contacts and full operating sequences still require native frames.");
        try
        {
            Files.writeString(root.resolve("r44_hangar_mechanics_client.json"),
                    new GsonBuilder().setPrettyPrinting().create().toJson(report));
        }
        catch (Exception failure)
        {
            throw new IllegalStateException("Could not save actual client hangar mechanics", failure);
        }
    }

    private HangarMechanicsWitnessR44() {}
}
