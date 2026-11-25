package com.projectseele.compat;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.lang.reflect.Method;

/**
 * MTR's oversized text images (MtrClampedTextLeakR65Mixin): which ones MTR copies into a smaller texture instead of
 * using, and closing those originals. MTR is not on the compile classpath, so its image and config are read by
 * reflection; if they cannot be, the originals stay open as before and nothing else changes.
 */
public final class MtrClampedTextR65
{
    private static final Logger LOGGER = LoggerFactory.getLogger("projectseele/mtr-text");
    /** MTR's size limit for one side of a dynamic texture before its resolution setting doubles it. */
    public static final int BASE_LIMIT = 2048;
    private static Method width, height, close, client, resolution;
    private static boolean unavailable;
    private static long closed, closedBytes;

    private MtrClampedTextR65() {}

    /** The longest side MTR keeps for a dynamic texture at a given dynamic texture resolution setting. */
    public static int limit(int resolution)
    {
        return BASE_LIMIT * (int) Math.pow(2, resolution);
    }

    /** Whether MTR copies an image of this size into a smaller one (the same test MTR makes) instead of using it. */
    public static boolean clamped(int width, int height, int resolution)
    {
        int limit = limit(resolution);
        return width > limit || height > limit;
    }

    /** Closes an MTR image that MTR has just copied into a smaller texture; any other image is left alone. */
    public static void closeIfClamped(Object image)
    {
        if (image == null || unavailable) return;
        try
        {
            if (client == null)
            {
                Class<?> config = Class.forName("org.mtr.mod.config.Config", false, image.getClass().getClassLoader());
                Method getClient = config.getMethod("getClient");
                resolution = getClient.getReturnType().getMethod("getDynamicTextureResolution");
                client = getClient;
            }
            closeIfClamped(image, (int) resolution.invoke(client.invoke(null)));
        }
        catch (ReflectiveOperationException | RuntimeException | LinkageError missing)
        {
            give(missing);
        }
    }

    /** The same, with the resolution setting given. */
    public static void closeIfClamped(Object image, int resolutionSetting)
    {
        if (image == null || unavailable) return;
        try
        {
            if (close == null)
            {
                Class<?> type = image.getClass();
                width = type.getMethod("getWidth");
                height = type.getMethod("getHeight");
                close = type.getMethod("close");
            }
            int w = (int) width.invoke(image), h = (int) height.invoke(image);
            if (!clamped(w, h, resolutionSetting)) return;
            close.invoke(image);
            closed++;
            closedBytes += 4L * w * h;
            if (closed == 1 || closed % 500 == 0)
                LOGGER.info("Closed {} oversized MTR text images ({} MB) that MTR had copied and left open; latest {}x{}", closed, closedBytes >> 20, w, h);
        }
        catch (ReflectiveOperationException | RuntimeException | LinkageError missing)
        {
            give(missing);
        }
    }

    /** How many originals have been closed (for checks). */
    public static long closedCount()
    {
        return closed;
    }

    private static void give(Throwable missing)
    {
        unavailable = true;
        LOGGER.warn("MTR text images unreadable; MTR's oversized originals stay open", missing);
    }
}
