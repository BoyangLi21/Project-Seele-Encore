package com.projectseele.client.render;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.mojang.math.Axis;
import com.projectseele.ProjectSeele;
import com.projectseele.registry.ModBlocks;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import net.minecraft.client.Minecraft;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.client.renderer.LevelRenderer;
import net.minecraft.core.BlockPos;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.client.event.RenderLevelStageEvent;

/** Installed static guide geometry; never authorizes a carrier movement. */
final class R52FixedGuideRenderer
{
    private record Segment(Vec3 origin, double length) {}
    private record FixedDraw(com.projectseele.world.NervLegacyCarrierRideR52.Piece part,net.minecraft.world.phys.AABB bounds,BlockPos centre){}
    private static List<FixedDraw> fixedDraws;
    private static boolean attempted;
    private static BlockPos marker;
    private static Vec3 incline;
    private static float inclineYaw;
    private static List<Segment> segments = List.of();
    private static RigidMachineryPartR44 mesh;

    static void clearCache()
    {
        attempted = false; mesh = null; segments = List.of();
        fixedDraws = null;
        NervFixedFootGuideRendererR52.clear();
        NervUprightGuideRendererR52.clear();
        CarrierRearGuideRendererR53.clear();
        CarrierBayTrayRendererR53.clear();
    }

    private static Vec3 point(com.google.gson.JsonArray a)
    {
        if (a.size() != 3) throw new IllegalArgumentException("Three coordinates required");
        var result = new Vec3(a.get(0).getAsDouble(), a.get(1).getAsDouble(), a.get(2).getAsDouble());
        if (!Double.isFinite(result.lengthSqr())) throw new IllegalArgumentException("Finite guide point required");
        return result;
    }

    private static JsonObject read(String path) throws Exception
    {
        try (var stream = Minecraft.getInstance().getResourceManager().open(new ResourceLocation(ProjectSeele.MODID, path));
             var reader = new InputStreamReader(stream, StandardCharsets.UTF_8))
        { return JsonParser.parseReader(reader).getAsJsonObject(); }
    }

    private static void load()
    {
        if (attempted) return;
        attempted = true;
        try
        {
            var data = read("facility/r52_fixed_guides.json");
            if (!data.get("schema").getAsString().equals("projectseele.r52.fixed-guides.v1"))
                throw new IllegalArgumentException("Unknown fixed guide schema");
            var required = data.getAsJsonObject("required_marker");
            if (!required.get("block").getAsString().equals("projectseele:nerv_machine_hazard"))
                throw new IllegalArgumentException("Unknown installed marker");
            marker = BlockPos.containing(point(required.getAsJsonArray("pos")));
            var original = data.getAsJsonObject("original_incline");
            incline = point(original.getAsJsonArray("origin"));
            inclineYaw = original.get("yaw_degrees").getAsFloat();
            if (!Float.isFinite(inclineYaw)) throw new IllegalArgumentException("Finite yaw required");
            var rows = data.getAsJsonArray("level_segments");
            if (rows.size() > 128) throw new IllegalArgumentException("Guide instance limit exceeded");
            var result = new ArrayList<Segment>();
            for (var row : rows)
            {
                var o = row.getAsJsonObject();double length = o.get("length").getAsDouble();
                if (!Double.isFinite(length) || length <= 0 || length > 16) throw new IllegalArgumentException("Guide segment length invalid");
                result.add(new Segment(point(o.getAsJsonArray("origin")), length));
            }
            mesh = RigidMachineryPartR44.triangles(read("mesh/tv_guide_r52.json").getAsJsonArray("part"));
            segments = List.copyOf(result);
        }
        catch (Exception e) { mesh = null; ProjectSeele.LOGGER.error("R52 fixed guide geometry rejected", e); }
    }

    /** True suppresses the old absolute anchor only in the installed R52 world. */
    static boolean draw(RenderLevelStageEvent event, ClientLevel level)
    {
        if(!com.projectseele.client.FacilityFrameClientR52.claimed(level))return false;
        CarrierRearGuideRendererR53.drawFixed(event,level);
        CarrierBayTrayRendererR53.draw(event,level);
        CarrierTransferRailsRendererR53.draw(event,level);
        if(com.projectseele.client.FacilityFrameClientR52.continuousUprightR52(level))NervUprightGuideRendererR52.draw(event,level);
        else NervFixedFootGuideRendererR52.draw(event,level);
        if(TripoMachineryR48.selectedRunningDeckR52())
        {
            var camera=event.getCamera().getPosition();var poses=event.getPoseStack();
            try
            {
                if(fixedDraws==null)
                {
                    var rows=new ArrayList<FixedDraw>();
                    for(var part:com.projectseele.world.NervLegacyCarrierRideR52.fixedPartsR52())
                    {
                        // Duplicate contact-only top faces are already in the
                        // visible original head source.
                        if(part.name().equals("legacy_heads_only"))continue;
                        var bounds=part.mesh().envelope(part.frame(),part.frame());
                        rows.add(new FixedDraw(part,bounds.inflate(240),BlockPos.containing(bounds.getCenter())));
                    }
                    fixedDraws=List.copyOf(rows);
                }
                for(var draw:fixedDraws)
                {
                    if(!draw.bounds().contains(camera)||!level.hasChunkAt(draw.centre()))continue;
                    NervLegacyCarrierRideRendererR52.drawFixed(draw.part(),camera,poses,TvFacilityMeshes.currentBuffers(),LevelRenderer.getLightColor(level,draw.centre()));
                }
            }
            catch(java.io.IOException missing){throw new IllegalStateException("Selected running-head source unavailable",missing);}
            return true;
        }
        load();
        // A resource/remote-chunk delay must never resurrect demolished R50
        // machinery at the old absolute anchor in an authoritative R52 map.
        if (mesh == null) return true;
        var camera = event.getCamera().getPosition();var poses = event.getPoseStack();
        if (camera.y < -760 || camera.y > -500) return true;
        if (Math.abs(camera.x - incline.x) < 260 && Math.abs(camera.z - (incline.z - 100)) < 340)
        {
            poses.pushPose();poses.translate(incline.x-camera.x, incline.y-camera.y, incline.z-camera.z);
            poses.mulPose(Axis.YP.rotationDegrees(inclineYaw));
            TvFacilityMeshes.draw("r20_transfer_guide", poses, LevelRenderer.getLightColor(level, BlockPos.containing(camera)));poses.popPose();
        }
        for (var segment : segments)
        {
            var origin=segment.origin();
            if (Math.abs(camera.x-origin.x)>240 || Math.abs(camera.z-origin.z)>260 || !level.hasChunkAt(BlockPos.containing(origin))) continue;
            poses.pushPose();poses.translate(origin.x-camera.x, origin.y-camera.y, origin.z-camera.z);
            poses.scale(1,1,(float)(segment.length()/16));
            mesh.draw(poses,TvFacilityMeshes.currentBuffers(),LevelRenderer.getLightColor(level,BlockPos.containing(origin).above(4)));
            poses.popPose();
        }
        return true;
    }
    private R52FixedGuideRenderer() {}
}
