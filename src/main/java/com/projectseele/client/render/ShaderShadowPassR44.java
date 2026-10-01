package com.projectseele.client.render;

import com.projectseele.ProjectSeele;
import net.minecraftforge.fml.ModList;
import java.lang.reflect.Method;

/** Optional Oculus/Iris API; a render-pass query must never be cached by game tick. */
public final class ShaderShadowPassR44
{
    private static boolean resolved;
    private static Object api;
    private static Method shadowPass;
    private static Method shaderPack;

    public static boolean active()
    {
        if (!resolved)
        {
            resolved = true;
            if (!ModList.get().isLoaded("oculus") && !ModList.get().isLoaded("iris")) return false;
            try
            {
                Class<?> type = Class.forName("net.irisshaders.iris.api.v0.IrisApi");
                api = type.getMethod("getInstance").invoke(null);
                shadowPass = type.getMethod("isRenderingShadowPass");
                shaderPack = type.getMethod("isShaderPackInUse");
            }
            catch (ReflectiveOperationException error)
            {
                ProjectSeele.LOGGER.warn("Optional shader shadow-pass API unavailable", error);
            }
        }
        if (shadowPass == null) return false;
        try
        {
            return Boolean.TRUE.equals(shadowPass.invoke(api));
        }
        catch (ReflectiveOperationException error)
        {
            shadowPass = null;
            ProjectSeele.LOGGER.warn("Shader shadow-pass query failed", error);
            return false;
        }
    }

    public static boolean enabled()
    {
        active();
        if(shaderPack==null)return false;
        try{return Boolean.TRUE.equals(shaderPack.invoke(api));}
        catch(ReflectiveOperationException error){return false;}
    }

    private ShaderShadowPassR44() {}
}
