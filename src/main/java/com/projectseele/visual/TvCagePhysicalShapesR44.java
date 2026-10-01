package com.projectseele.visual;

import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.NervCarrierPlatformEntity;
import com.projectseele.world.FacilitySchemaV2;
import com.projectseele.world.TvCageCollisionR44;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.AABB;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.Files;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.List;

/** Current-state native shape outlet for QA/navigation; never generates world blocks. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID)
public final class TvCagePhysicalShapesR44
{
    private static boolean written;
    private static int age;

    @SubscribeEvent
    public static void tick(TickEvent.ServerTickEvent event)
    {
        if (!Boolean.getBoolean("projectseele.r44TvCageShapeExport") || written
                || event.phase != TickEvent.Phase.END || ++age < 60) return;
        if (!TvCageCollisionR44.enabled())
            throw new IllegalStateException("Native cage export requires the same review geometry/physics flag");
        var server = event.getServer();
        var root = server.getWorldPath(LevelResource.ROOT).normalize();
        if (!root.getFileName().toString().equals("SEELE_FIELD_R44_REVIEW"))
            throw new IllegalStateException("Cage shape export refuses another world");
        var level = server.getLevel(FacilitySchemaV2.DIMENSION);
        if (level == null) return;
        var rows = new JsonArray();
        for (int variant = 0; variant < 3; variant++)
        {
            final int identity = variant;
            double x = new double[] {-11.5, 30.5, 72.5}[variant];
            var gantries = level.getEntitiesOfClass(NervCarrierPlatformEntity.class,
                    new AABB(x - 1, -444, -240.5, x + 1, -440, -238.5),
                    e -> e.isAlive() && e.isRestraintGantry() && e.getUnitVariant() == identity);
            if (gantries.size() != 1) return;
            var gantry = gantries.get(0);
            var shapes = TvCageCollisionR44.append(level, null,
                    new AABB(x - 20.5, -445, -268, x + 20.5, -355, -213), List.of());
            if (shapes.isEmpty()) throw new IllegalStateException("Visible cage has no physical assembly");
            var row = new JsonObject();
            row.addProperty("variant", variant);
            row.addProperty("gantry_uuid", gantry.getStringUUID());
            row.addProperty("closed", gantry.getRestraintProgress());
            row.addProperty("server_game_time", level.getGameTime());
            row.addProperty("blocked_actor_uuid", gantry.getPersistentData().getString("TvCageBlockedR44"));
            var boxes = new JsonArray();
            for (var shape : shapes)
                for (var box : shape.toAabbs())
                {
                    var values = new JsonArray();
                    for (double value : new double[] {box.minX, box.minY, box.minZ, box.maxX, box.maxY, box.maxZ})
                        values.add(value);
                    boxes.add(values);
                }
            row.add("world_aabbs", boxes);
            rows.add(row);
        }
        try (var stream = TvCagePhysicalShapesR44.class.getResourceAsStream("/assets/projectseele/mesh/tv_shoulder_shells_r44.json"))
        {
            if (stream == null) throw new IllegalStateException("Actual cage resource missing");
            var report = new JsonObject();
            report.addProperty("schema", 44);
            report.addProperty("world", root.toAbsolutePath().toString());
            report.addProperty("dimension", level.dimension().location().toString());
            report.addProperty("resource_sha256", HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(stream.readAllBytes())));
            report.addProperty("geometry_enabled", true);
            report.add("actual_gantries", rows);
            report.add("actual_collision_query_metrics",TvCageCollisionR44.actualQueryMetricsR44());
            report.addProperty("native_query", "The same TvCageCollisionR44.append output actually supplied to Entity.collide's vanilla solver; shape existence alone does not pass movement");
            report.addProperty("cache_identity", "Invalidate on any gantry UUID, closed progress or resource SHA change; this snapshot is never an all-state floor");
            report.addProperty("coverage_limit", "Entity.collide walking/step/landing only. Other Level.getEntityCollisions callers, block raycast and NPC pathfinding remain separate consumers");
            report.addProperty("navigation_role", "Mechanical service aprons are physical equipment surfaces; no new public route/doorway is inferred from their AABBs. Existing crew topology stays separately measured");
            report.addProperty("native_walk", "UNVERIFIED");
            report.addProperty("occupied_stop", "UNVERIFIED");
            report.addProperty("cold_reload", "UNVERIFIED");
            Files.writeString(root.resolve("r44_tv_cage_collision_shapes.json"), new GsonBuilder().setPrettyPrinting().create().toJson(report));
            written = true;
            ProjectSeele.LOGGER.info("R44 actual three-cage physical snapshot exported; no blocks/entities mutated");
        }
        catch (Exception failure)
        {
            written = true;
            throw new IllegalStateException("Actual cage shapes could not be exported", failure);
        }
    }

    private TvCagePhysicalShapesR44() { }
}
