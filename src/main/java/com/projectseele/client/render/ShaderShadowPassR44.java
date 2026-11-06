package com.projectseele.client.render;

import com.projectseele.ProjectSeele;
import java.lang.invoke.MethodHandle;
import java.lang.invoke.MethodHandles;
import java.lang.invoke.MethodType;
import net.minecraftforge.fml.ModList;

/** Optional Oculus/Iris API; a render-pass query must never be cached by game tick. */
public final class ShaderShadowPassR44
{
    private static boolean failed;

    /** Resolved on first use; constant handles let the JIT inline the per-draw query. */
    private static final class Api
    {
        static final Object INSTANCE;
        static final MethodHandle SHADOW_PASS;
        static final MethodHandle SHADER_PACK;

        static
        {
            Object instance = null;
            MethodHandle shadowPass = null, shaderPack = null;
            if (ModList.get().isLoaded("oculus") || ModList.get().isLoaded("iris"))
            {
                try
                {
                    Class<?> type = Class.forName("net.irisshaders.iris.api.v0.IrisApi");
                    MethodType query = MethodType.methodType(boolean.class, Object.class);
                    MethodHandles.Lookup lookup = MethodHandles.publicLookup();
                    instance = type.getMethod("getInstance").invoke(null);
                    shadowPass = lookup.findVirtual(type, "isRenderingShadowPass",
                            MethodType.methodType(boolean.class)).asType(query);
                    shaderPack = lookup.findVirtual(type, "isShaderPackInUse",
                            MethodType.methodType(boolean.class)).asType(query);
                }
                catch (ReflectiveOperationException | RuntimeException error)
                {
                    ProjectSeele.LOGGER.warn("Optional shader shadow-pass API unavailable", error);
                    instance = null;
                    shadowPass = null;
                    shaderPack = null;
                }
            }
            INSTANCE = instance;
            SHADOW_PASS = shadowPass;
            SHADER_PACK = shaderPack;
        }
    }

    public static boolean active()
    {
        if (failed || Api.SHADOW_PASS == null) return false;
        try
        {
            return (boolean) Api.SHADOW_PASS.invokeExact(Api.INSTANCE);
        }
        catch (Throwable error)
        {
            failed = true;
            ProjectSeele.LOGGER.warn("Shader shadow-pass query failed", error);
            return false;
        }
    }

    public static boolean enabled()
    {
        if (Api.SHADER_PACK == null) return false;
        try
        {
            return (boolean) Api.SHADER_PACK.invokeExact(Api.INSTANCE);
        }
        catch (Throwable error)
        {
            return false;
        }
    }

    private ShaderShadowPassR44() {}
}
