package com.projectseele.visual;

import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.NervCarrierPlatformEntity;
import com.projectseele.world.EvaLogisticsDirector;
import com.projectseele.world.FacilitySchemaV2;
import com.projectseele.world.TvCageCollisionR44;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.MoverType;
import net.minecraft.world.entity.decoration.ArmorStand;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.Files;
import java.util.List;

/** Optional actual vanilla clipping and occupied-stop probes, never a player/art approval. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID)
public final class TvCagePhysicalReviewR44
{
    private static int age;
    private static boolean completed;

    @SubscribeEvent
    public static void tick(TickEvent.ServerTickEvent event)
    {
        if (!Boolean.getBoolean("projectseele.r44TvCagePhysicalReview") || completed
                || event.phase != TickEvent.Phase.END || ++age < 100) return;
        if (!TvCageCollisionR44.enabled()) throw new IllegalStateException("Physical review requires the same cage flag");
        var server = event.getServer();
        var root = server.getWorldPath(LevelResource.ROOT).normalize();
        if (!root.getFileName().toString().equals(com.projectseele.visual.NativeReviewWorldsR45.expectedName()))
            throw new IllegalStateException("Cage physical review refuses another world");
        var level = server.getLevel(FacilitySchemaV2.DIMENSION);
        if (level == null) return;
        var gantries = new NervCarrierPlatformEntity[3];
        for (int variant = 0; variant < 3; variant++)
        {
            int identity = variant;
            double x = new double[] {-11.5, 30.5, 72.5}[variant];
            var candidates = level.getEntitiesOfClass(NervCarrierPlatformEntity.class,
                    new AABB(x - 1, -444, -240.5, x + 1, -440, -238.5),
                    e -> e.isAlive() && e.isRestraintGantry() && e.getUnitVariant() == identity);
            if (candidates.size() != 1 || EvaLogisticsDirector.canonicalUnit(level, variant) == null) return;
            gantries[variant] = candidates.get(0);
            if (Math.abs(gantries[variant].getRestraintProgress() - 1) > .001) return;
        }
        completed = true;
        var rows = new JsonArray();
        boolean passed = true;
        for (int variant = 0; variant < 3; variant++)
        {
            var gantry = gantries[variant];
            var owner = EvaLogisticsDirector.canonicalUnit(level, variant);
            var row = new JsonObject();
            row.addProperty("variant", variant);
            row.addProperty("gantry_uuid", gantry.getStringUUID());
            row.addProperty("actual_owner_uuid", owner.getStringUUID());
            row.addProperty("closed_before", gantry.getRestraintProgress());
            boolean emptyBefore = TvCageCollisionR44.canMove(level, owner, gantry, 0);
            row.addProperty("unoccupied_release_before", emptyBefore);
            ArmorStand probe = null;
            try
            {
                // A normal .5m-wide living body consumes the vanilla solver;
                // it is explicitly not claimed to be a real player's walk.
                probe = new ArmorStand(level, gantry.getX() + 1.1, gantry.getY() + 49.46, gantry.getZ() - 19.34);
                probe.setInvisible(true);
                probe.setInvulnerable(true);
                probe.setNoGravity(true);
                probe.noPhysics = false;
                probe.setMaxUpStep(.6F);
                probe.getPersistentData().putBoolean("R44TvCageProbe", true);
                if (!level.addFreshEntity(probe)) throw new IllegalStateException("Probe body rejected");
                boolean occupied = TvCageCollisionR44.canMove(level, owner, gantry, 0);
                row.addProperty("occupied_release_refused", !occupied);
                row.addProperty("occupied_refusal_actor_uuid", gantry.getPersistentData().getString("TvCageBlockedR44"));
                passed &= emptyBefore && !occupied;

                Vec3 before = new Vec3(gantry.getX() + 1.1, gantry.getY() + 49.46, gantry.getZ() - 20.0);
                probe.setPos(before.x, before.y, before.z);
                probe.move(MoverType.SELF, new Vec3(0, 0, 2));
                double travel = probe.getZ() - before.z;
                boolean blocked = travel >= -.0001 && travel < .50;
                row.addProperty("actual_vanilla_beam_horizontal_travel_m", travel);
                row.addProperty("actual_vanilla_beam_clip", blocked);
                passed &= blocked;

                double rampX = gantry.getX() + 10.05;
                double rampZ = gantry.getZ() - 12;
                double localTop = 48.96 + (8.50 / 13.92) * 3.74;
                probe.setPos(rampX, gantry.getY() + localTop + 1, rampZ);
                probe.move(MoverType.SELF, new Vec3(0, -2, 0));
                double nativeSupport = footprintSupport(level, probe, gantry.getY() + localTop);
                double footprintPlane = gantry.getY() + 48.96
                        + ((probe.getBoundingBox().maxZ - gantry.getZ() + 20.50) / 13.92) * 3.74;
                double error = Math.abs(probe.getY() - nativeSupport);
                row.addProperty("actual_body_footprint_front_z", probe.getBoundingBox().maxZ);
                row.addProperty("centre_plane_y", gantry.getY() + localTop);
                row.addProperty("highest_footprint_plane_y", footprintPlane);
                row.addProperty("native_highest_footprint_support_y", nativeSupport);
                row.addProperty("native_stair_to_footprint_plane_error_m", Math.abs(nativeSupport - footprintPlane));
                row.addProperty("native_ramp_on_ground", probe.onGround());
                row.addProperty("actual_vanilla_ramp_support_error_m", error);
                row.addProperty("actual_vanilla_ramp_landing", error < .001 && probe.onGround());
                passed &= error < .001 && probe.onGround();
                double startZ = probe.getZ();
                for (int step = 0; step < 16; step++) probe.move(MoverType.SELF, new Vec3(0, -.08, .125));
                double stepTravel = probe.getZ() - startZ;
                double stepTop = 48.96 + (10.50 / 13.92) * 3.74;
                double stepSupport = footprintSupport(level, probe, gantry.getY() + stepTop);
                double stepError = Math.abs(probe.getY() - stepSupport);
                row.addProperty("actual_vanilla_ramp_step_travel_m", stepTravel);
                row.addProperty("actual_vanilla_ramp_step_support_error_m", stepError);
                row.addProperty("actual_vanilla_ramp_step_highest_footprint_support_y", stepSupport);
                row.addProperty("actual_vanilla_ramp_step", stepTravel > 1.95 && stepError < .001);
                passed &= stepTravel > 1.95 && stepError < .001;
            }
            catch (Exception failure)
            {
                passed = false;
                row.addProperty("failure", failure.toString());
            }
            finally
            {
                if (probe != null) probe.discard();
                boolean emptyAfter = TvCageCollisionR44.canMove(level, owner, gantry, 0);
                row.addProperty("unoccupied_release_after_cleanup", emptyAfter);
                row.addProperty("closed_after", gantry.getRestraintProgress());
                passed &= emptyAfter && Math.abs(gantry.getRestraintProgress() - 1) < .001;
            }
            rows.add(row);
        }
        var report = new JsonObject();
        report.addProperty("server_game_time", level.getGameTime());
        report.addProperty("diagnostic_native_passed", passed);
        report.add("actual_three_bay_cases", rows);
        report.add("actual_collision_query_metrics",TvCageCollisionR44.actualQueryMetricsR44());
        report.addProperty("canonical_progress_changed", false);
        report.addProperty("scope", "Actual Entity.move -> Entity.collide walking/landing/step and occupied sweep refusal using a transient normal ArmorStand body; not real player, all meshes, NPC routing or art acceptance");
        report.addProperty("fixture_cleanup", "finally discards every created body; no canonical unit/gantry transform, phase, progress or world blocks changed");
        report.addProperty("remaining", "Real player/body width, active logistics clock freeze, collision-resource load rejection, all opening states, operator actions, return/cancel, cold reload, multiplayer and artistic review remain UNVERIFIED");
        try
        {
            Files.writeString(root.resolve("r44_tv_cage_physical_review.json"), new GsonBuilder().setPrettyPrinting().create().toJson(report));
        }
        catch (Exception failure)
        {
            throw new IllegalStateException("Cage native physical probe could not write its receipt", failure);
        }
    }

    private static double footprintSupport(ServerLevel level, ArmorStand actor, double expectedCentre)
    {
        var feet = actor.getBoundingBox();
        var query = new AABB(feet.minX, expectedCentre - 1.5, feet.minZ,
                feet.maxX, expectedCentre + .20, feet.maxZ);
        // The vanilla body has a horizontal foot rectangle, so support is the
        // highest actual surface under that rectangle, not under its centre.
        double result = Double.NEGATIVE_INFINITY;
        for (var shape : TvCageCollisionR44.append(level, actor, query, List.of()))
            for (var box : shape.toAabbs())
                if (box.maxX > feet.minX && box.minX < feet.maxX
                        && box.maxZ > feet.minZ && box.minZ < feet.maxZ
                        && box.maxY <= expectedCentre + .20) result = Math.max(result, box.maxY);
        return result;
    }

    private TvCagePhysicalReviewR44() { }
}
