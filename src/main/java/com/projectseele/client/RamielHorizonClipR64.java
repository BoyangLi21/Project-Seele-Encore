package com.projectseele.client;

import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import com.projectseele.network.ClientboundEncounterObserverPacket;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import net.minecraft.client.Minecraft;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.phys.Vec3;

/**
 * Where far terrain hides the distant Ramiel. Terrain past the vanilla render distance is drawn by Distant Horizons
 * into its own depth, which the main depth buffer never sees, so the far Angel would be drawn over the ridges and the
 * city in front of it. From the Yashima emplacement a ridge 1.4 km out hides everything below about y 163 at the
 * Angel's axis.
 *
 * The terrain between the emplacement and the Angel is fixed, so its profile is measured offline
 * (tools/map_buildings/ramiel_horizon.py) and shipped as yashima/ramiel_horizon_r64.json: the top of the terrain every
 * eight blocks along azimuths around the line to the Angel, lift towers at their raised height (the far view is baked
 * with the city raised). While the camera is near the emplacement (seat, cannon sight, third person) this gives, for
 * a fan of directions across the Angel, the elevation below which it is hidden; the distant view draws the body and
 * drill only above it. No terrain is read at run time and nothing writes depth, so it costs nothing and behaves the
 * same with and without a shader pack. Away from the emplacement nothing changes; near terrain is in the main depth
 * buffer anyway. Rerun the tool after terrain or skyline changes on that line.
 */
public final class RamielHorizonClipR64
{
    /** Directions across the Angel's width. */
    public static final int COLUMNS = 13;
    private static final ResourceLocation PROFILE = new ResourceLocation("projectseele", "yashima/ramiel_horizon_r64.json");
    /** Horizon elevation (radians) per column; NaN = nothing hides that column, +Infinity = all of it is hidden. */
    public record Profile(Vec3 camera, Vec3 axis, double baseAzimuth, double halfAngle, double horizontal, double[] elevation)
    {
        public double azimuth(int column) {return baseAzimuth + (column / (double) (COLUMNS - 1) * 2 - 1) * halfAngle;}
        public boolean any() {for (double e : elevation) if (!Double.isNaN(e)) return true; return false;}
    }
    private record Terrain(double ax, double ay, double az, double axisX, double axisZ, int step, double azimuth0, double azimuthStep, short[][] tops) {}

    private static Terrain terrain;
    private static boolean loaded;
    private static Profile cached;
    private static float cachedHeight, cachedDrill;

    public static void reload()
    {
        terrain = null;
        loaded = false;
        cached = null;
    }

    /** The clip for this frame, or null when the camera is not at the emplacement or no profile is installed. */
    public static Profile profile(Vec3 camera, ClientboundEncounterObserverPacket.Snapshot state)
    {
        Terrain t = terrain();
        if (t == null) return null;
        Vec3 axis = state.position();
        if (Math.abs(axis.x - t.axisX) > 4 || Math.abs(axis.z - t.axisZ) > 4) return null;
        if (Math.hypot(camera.x - t.ax, camera.z - t.az) > 96 || Math.abs(camera.y - t.ay) > 96) return null;
        if (cached != null && cached.camera.distanceToSqr(camera) < .25 && cached.axis.distanceToSqr(axis) < .25
                && cachedHeight == state.height() && Math.abs(cachedDrill - state.drillDepth()) < 1) return cached;
        float scale = state.height() / 15F, center = state.height() * .5F;
        double top = axis.y + center + 8.5 * scale;
        double bottom = Math.min(axis.y + center - 8.5 * scale, axis.y + center - Math.max(0, state.drillDepth()));
        double dx = axis.x - camera.x, dz = axis.z - camera.z, horizontal = Math.sqrt(dx * dx + dz * dz);
        double base = Math.atan2(dz, dx), half = Math.atan((8.5 * scale + 4) / horizontal);
        double low = Math.atan2(bottom - camera.y, horizontal), high = Math.atan2(top - camera.y, horizontal);
        var profile = new Profile(camera, axis, base, half, horizontal, new double[COLUMNS]);
        for (int i = 0; i < COLUMNS; i++)
        {
            double e = horizon(t, camera, profile.azimuth(i), horizontal);
            profile.elevation[i] = e <= low ? Double.NaN : e >= high ? Double.POSITIVE_INFINITY : e;
        }
        cached = profile;
        cachedHeight = state.height();
        cachedDrill = state.drillDepth();
        return profile;
    }

    /** Highest elevation of the terrain, seen from the camera, along the stored line nearest this azimuth. */
    private static double horizon(Terrain t, Vec3 camera, double azimuth, double horizontal)
    {
        int line = (int) Math.round((Math.toDegrees(azimuth) - t.azimuth0) / t.azimuthStep);
        if (line < 0 || line >= t.tops.length) return Double.NEGATIVE_INFINITY;
        double a = Math.toRadians(t.azimuth0 + line * t.azimuthStep), cx = Math.cos(a), cz = Math.sin(a);
        double best = Double.NEGATIVE_INFINITY;
        short[] tops = t.tops[line];
        for (int k = 0; k < tops.length; k++)
        {
            double d = (k + 1) * t.step, x = t.ax + cx * d, z = t.az + cz * d;
            double from = Math.hypot(x - camera.x, z - camera.z);
            if (from < 4) continue;
            if (from >= horizontal - 8) break;
            best = Math.max(best, Math.atan2(tops[k] - camera.y, from));
        }
        return best;
    }

    private static Terrain terrain()
    {
        if (loaded) return terrain;
        loaded = true;
        try
        {
            var resource = Minecraft.getInstance().getResourceManager().getResource(PROFILE);
            if (resource.isEmpty()) return null;
            try (var reader = new InputStreamReader(resource.get().open(), StandardCharsets.UTF_8))
            {
                var root = JsonParser.parseReader(reader).getAsJsonObject();
                if (root.get("schema").getAsInt() != 1) return null;
                var anchor = root.getAsJsonArray("anchor");
                var axis = root.getAsJsonArray("axis");
                var rows = root.getAsJsonArray("tops");
                short[][] tops = new short[rows.size()][];
                for (int i = 0; i < tops.length; i++)
                {
                    var row = rows.get(i).getAsJsonArray();
                    tops[i] = new short[row.size()];
                    for (int k = 0; k < tops[i].length; k++) tops[i][k] = row.get(k).getAsShort();
                }
                terrain = new Terrain(anchor.get(0).getAsDouble(), anchor.get(1).getAsDouble(), anchor.get(2).getAsDouble(),
                        axis.get(0).getAsDouble(), axis.get(1).getAsDouble(), root.get("step").getAsInt(),
                        root.get("azimuth_start_deg").getAsDouble(), root.get("azimuth_step_deg").getAsDouble(), tops);
            }
        }
        catch (Exception failure)
        {
            ProjectSeele.LOGGER.warn("Ramiel far horizon profile unreadable: {}", failure.toString());
            terrain = null;
        }
        return terrain;
    }

    private RamielHorizonClipR64() {}
}
