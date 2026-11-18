package com.projectseele.client;

import com.projectseele.ProjectSeele;
import com.projectseele.network.ClientboundEncounterObserverPacket;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import net.minecraft.client.Minecraft;
import net.minecraft.world.phys.Vec3;

/**
 * Where far terrain hides the distant Ramiel. Terrain past the vanilla render distance is drawn by Distant Horizons
 * into its own depth, which the main depth buffer never sees, so the far Angel would be drawn over ridges and over
 * the city in front of it. This keeps a horizon profile toward the Angel, read from Distant Horizons' own terrain
 * data with its raycast: for a fan of directions across the Angel's width, the lowest elevation above which the line
 * of sight to the Angel's axis is clear. The distant view then draws the body and drill only above that horizon.
 * Nothing here writes depth, so shader packs that read the depth buffer are unaffected; without Distant Horizons
 * there is no far terrain to hide anything and no profile is made.
 */
public final class RamielHorizonClipR64
{
    /** Directions across the Angel's width. */
    public static final int COLUMNS = 13;
    /** Horizon elevation (radians) per column; NaN = nothing hides that column, +Infinity = all of it is hidden. */
    public record Profile(Vec3 camera, Vec3 axis, double baseAzimuth, double halfAngle, double horizontal, double[] elevation)
    {
        public double azimuth(int column) {return baseAzimuth + (column / (double) (COLUMNS - 1) * 2 - 1) * halfAngle;}
        public boolean any() {for (double e : elevation) if (!Double.isNaN(e)) return true; return false;}
    }

    private static final ExecutorService WORKER = Executors.newSingleThreadExecutor(r -> {var t = new Thread(r, "SEELE Ramiel horizon"); t.setDaemon(true); return t;});
    private static volatile Profile current;
    private static CompletableFuture<Profile> pending;
    private static long lastRequest;
    private static Vec3 lastCamera = Vec3.ZERO, lastAxis = Vec3.ZERO;
    private static boolean dhMissing, reported;
    private static Object repo;
    private static Method raycast, levels, levelName, levelType;
    private static Object worldProxy;

    /** The profile for this frame, or null when none applies; a fresh one is asked for off the render thread. */
    public static Profile profile(Vec3 camera, ClientboundEncounterObserverPacket.Snapshot state)
    {
        if (dhMissing) return null;
        var mc = Minecraft.getInstance();
        if (mc.level == null) return null;
        long now = mc.level.getGameTime();
        Vec3 axis = state.position();
        if (pending != null && pending.isDone())
        {
            current = pending.getNow(null);
            pending = null;
        }
        boolean moved = camera.distanceToSqr(lastCamera) > 2.25 || axis.distanceToSqr(lastAxis) > 1;
        if (pending == null && (moved || now - lastRequest >= 10))
        {
            lastRequest = now;
            lastCamera = camera;
            lastAxis = axis;
            float scale = state.height() / 15F, center = state.height() * .5F;
            double top = axis.y + center + 8.5 * scale;
            double bottom = Math.min(axis.y + center - 8.5 * scale, axis.y + center - Math.max(0, state.drillDepth()));
            String dimension = mc.level.dimension().location().toString();
            pending = CompletableFuture.supplyAsync(() -> compute(dimension, camera, axis, 8.5 * scale + 4, top, bottom), WORKER);
        }
        Profile p = current;
        return p != null && p.camera.distanceToSqr(camera) < 64 && p.axis.distanceToSqr(axis) < 16 ? p : null;
    }

    private static Profile compute(String dimension, Vec3 camera, Vec3 axis, double halfWidth, double top, double bottom)
    {
        try
        {
            if (!bind()) return null;
            Object level = level(dimension);
            if (level == null) return null;
            Object cache = cache();
            double dx = axis.x - camera.x, dz = axis.z - camera.z, horizontal = Math.sqrt(dx * dx + dz * dz);
            if (horizontal < 384) return null;
            double base = Math.atan2(dz, dx), half = Math.atan(halfWidth / horizontal);
            double low = Math.atan2(bottom - camera.y, horizontal), high = Math.atan2(top - camera.y, horizontal);
            var profile = new Profile(camera, axis, base, half, horizontal, new double[COLUMNS]);
            for (int i = 0; i < COLUMNS; i++)
            {
                double az = profile.azimuth(i);
                if (!hits(level, cache, camera, az, low, horizontal)) {profile.elevation[i] = Double.NaN; continue;}
                if (hits(level, cache, camera, az, high, horizontal)) {profile.elevation[i] = Double.POSITIVE_INFINITY; continue;}
                double a = low, b = high;
                for (int step = 0; step < 9; step++)
                {
                    double m = (a + b) * .5;
                    if (hits(level, cache, camera, az, m, horizontal)) a = m; else b = m;
                }
                profile.elevation[i] = b;
            }
            return profile;
        }
        catch (Throwable failure)
        {
            if (!reported) {reported = true; ProjectSeele.LOGGER.warn("Ramiel far horizon unavailable: {}", failure.toString());}
            return null;
        }
    }

    /** Does far terrain stop the line at this azimuth and elevation before it reaches the Angel's axis? */
    private static boolean hits(Object level, Object cache, Vec3 camera, double azimuth, double elevation, double horizontal) throws Exception
    {
        double c = Math.cos(elevation);
        float x = (float) (c * Math.cos(azimuth)), y = (float) Math.sin(elevation), z = (float) (c * Math.sin(azimuth));
        int reach = (int) ((horizontal - 8) / Math.max(.05, c));
        Object result = raycast.invoke(repo, level, camera.x + x * 2, camera.y + y * 2, camera.z + z * 2, x, y, z, reach, cache);
        if (result == null) return false;
        Field success = result.getClass().getField("success"), payload = result.getClass().getField("payload");
        return success.getBoolean(result) && payload.get(result) != null;
    }

    private static boolean bind()
    {
        if (raycast != null) return true;
        try
        {
            Class<?> delayed = Class.forName("com.seibel.distanthorizons.api.DhApi$Delayed");
            repo = delayed.getField("terrainRepo").get(null);
            worldProxy = delayed.getField("worldProxy").get(null);
            if (repo == null || worldProxy == null) return false;
            Class<?> level = Class.forName("com.seibel.distanthorizons.api.interfaces.world.IDhApiLevelWrapper");
            Class<?> cache = Class.forName("com.seibel.distanthorizons.api.interfaces.data.IDhApiTerrainDataCache");
            raycast = Class.forName("com.seibel.distanthorizons.api.interfaces.data.IDhApiTerrainDataRepo")
                    .getMethod("raycast", level, double.class, double.class, double.class, float.class, float.class, float.class, int.class, cache);
            levels = Class.forName("com.seibel.distanthorizons.api.interfaces.world.IDhApiWorldProxy").getMethod("getAllLoadedLevelWrappers");
            levelName = level.getMethod("getDimensionName");
            levelType = level.getMethod("getLevelType");
            return true;
        }
        catch (ClassNotFoundException absent)
        {
            dhMissing = true;
            return false;
        }
        catch (ReflectiveOperationException failure)
        {
            dhMissing = true;
            ProjectSeele.LOGGER.warn("Ramiel far horizon: Distant Horizons API not as expected: {}", failure.toString());
            return false;
        }
    }

    /** The client-side DH level of this dimension, else any DH level of it. */
    private static Object level(String dimension) throws Exception
    {
        Object chosen = null;
        for (Object candidate : (Iterable<?>) levels.invoke(worldProxy))
        {
            if (!dimension.equals(levelName.invoke(candidate))) continue;
            if (String.valueOf(levelType.invoke(candidate)).contains("CLIENT")) return candidate;
            if (chosen == null) chosen = candidate;
        }
        return chosen;
    }

    private static Object cache()
    {
        for (String name : new String[] {"createSoftCache", "getSoftCache"})
            try {return Class.forName("com.seibel.distanthorizons.api.interfaces.data.IDhApiTerrainDataRepo").getMethod(name).invoke(repo);}
            catch (ReflectiveOperationException ignored) {}
        return null;
    }

    private RamielHorizonClipR64() {}
}
