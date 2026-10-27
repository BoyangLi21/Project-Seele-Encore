package com.projectseele.client;

import com.projectseele.ProjectSeele;

/** Refresh Oculus' cached DH switch before it chooses shader preprocessor defines. */
public final class DhShaderReloadR53
{
    public static void synchronizeRenderPass(boolean shaderOverride)
    {
        try
        {
            var delayed = Class.forName("com.seibel.distanthorizons.api.DhApi$Delayed");
            Object proxy = delayed.getField("renderProxy").get(null);
            if (proxy == null) return;
            proxy.getClass().getMethod("setDeferTransparentRendering", boolean.class)
                    .invoke(proxy, shaderOverride);
        }
        catch (ClassNotFoundException absent) { }
        catch (ReflectiveOperationException failure)
        {
            ProjectSeele.LOGGER.warn("Could not synchronize the pinned Oculus/DH render pass", failure);
        }
    }

    public static void synchronize()
    {
        try
        {
            var delayed = Class.forName("com.seibel.distanthorizons.api.DhApi$Delayed");
            Object config = delayed.getField("configs").get(null);
            if (config == null) return;
            var configType = Class.forName("com.seibel.distanthorizons.api.interfaces.config.IDhApiConfig");
            Object graphics = configType.getMethod("graphics").invoke(config);
            var graphicsType = Class.forName("com.seibel.distanthorizons.api.interfaces.config.client.IDhApiGraphicsConfig");
            Object value = graphicsType.getMethod("renderingEnabled").invoke(graphics);
            var valueType = Class.forName("com.seibel.distanthorizons.api.interfaces.config.IDhApiConfigValue");
            boolean enabled = (Boolean) valueType.getMethod("getValue").invoke(value);
            var cached = Class.forName("net.irisshaders.iris.compat.dh.DHCompatInternal").getDeclaredField("dhEnabled");
            cached.setAccessible(true);
            // Oculus 1.8 only refreshes this flag when a shader pipeline already
            // exists. With shaders off, a DH toggle otherwise poisons reload.
            if (cached.getBoolean(null) != enabled)
            {
                cached.setBoolean(null, enabled);
                ProjectSeele.LOGGER.info("Synchronized DH rendering switch before shader reload: {}", enabled);
            }
        }
        catch (ClassNotFoundException absent) { }
        catch (ReflectiveOperationException failure)
        {
            ProjectSeele.LOGGER.warn("Could not synchronize the pinned Oculus/DH reload state", failure);
        }
    }

    private DhShaderReloadR53() { }
}
