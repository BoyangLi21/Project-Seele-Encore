import java.lang.instrument.Instrumentation;
import java.nio.file.*;
import java.util.*;

/** Read the actual render camera and fog state without changing the view or shader. */
public final class FogReadOnlyR54
{
    interface Read { Object get() throws Exception; }
    static void add(Map<String,Object> map,String key,Read read)
    {try{map.put(key,read.get());}catch(Exception error){map.put(key+"_error",error.toString());}}
    static Object c(Object owner,String names,Object...args)throws Exception{return DhRenderReadOnlyR54C.call(owner,names,args);}
    static Object f(Object owner,String...names)throws Exception{return DhRenderReadOnlyR54C.field(owner,names);}
    static Class<?> t(String name)throws Exception{return DhRenderReadOnlyR54C.type(name);}
    static Map<String,Object> uniforms(Object program)throws Exception
    {
        var out=new LinkedHashMap<String,Object>();if(program==null)return out;
        int id=((Number)f(program,"id")).intValue();out.put("program",id);Class<?> gl=t("org.lwjgl.opengl.GL20");
        for(String name:List.of("isEyeInWater","worldTime"))
        {int at=((Number)c(gl,"glGetUniformLocation",id,name)).intValue();if(at>=0)out.put(name,c(gl,"glGetUniformi",id,at));}
        for(String name:List.of("fogColor","skyColor","cameraPosition"))
        {int at=((Number)c(gl,"glGetUniformLocation",id,name)).intValue();if(at>=0){float[] values=new float[3];c(gl,"glGetUniformfv",id,at,values);out.put(name,values);}}
        return out;
    }
    public static void agentmain(String argument,Instrumentation instrumentation)throws Exception
    {
        Path output=Path.of(argument.split("\\|",-1)[0]);if(Files.exists(output))throw new IllegalArgumentException("Fresh output required");
        for(Class<?> type:instrumentation.getAllLoadedClasses())if(type.getName().equals("com.projectseele.ProjectSeele")){DhRenderReadOnlyR54C.loader=type.getClassLoader();break;}
        Object mc=c(t("net.minecraft.client.Minecraft"),"getInstance/m_91087_");
        Runnable snapshot=()->{
            var out=new LinkedHashMap<String,Object>();out.put("read_only",true);out.put("utc_ms",System.currentTimeMillis());
            try
            {
                Object level=f(mc,"level","f_91073_"),player=f(mc,"player","f_91074_");
                Object camera=c(f(mc,"gameRenderer","f_91063_"),"getMainCamera/m_109153_");
                Object pos=c(camera,"getBlockPosition/m_90588_"),subject=c(camera,"getEntity/m_90592_");
                add(out,"fps",()->c(mc,"getFps/m_260875_"));
                add(out,"player_position",()->c(player,"position/m_20182_").toString());
                add(out,"camera_position",()->c(camera,"getPosition/m_90583_").toString());
                add(out,"camera_block_position",()->pos.toString());
                add(out,"camera_subject_type",()->subject==null?null:subject.getClass().getSimpleName());
                add(out,"camera_subject_position",()->subject==null?null:c(subject,"position/m_20182_").toString());
                add(out,"camera_fluid",()->c(camera,"getFluidInCamera/m_167685_").toString());
                add(out,"camera_block",()->c(camera,"getBlockAtCamera").toString());
                add(out,"camera_fluid_state",()->c(level,"getFluidState/m_6425_",pos).toString());
                add(out,"camera_fluid_type",()->c(c(level,"getFluidState/m_6425_",pos),"getFluidType").toString());
                add(out,"subject_eye_fluid_type",()->c(subject,"getEyeInFluidType").toString());
                add(out,"computed_isEyeInWater",()->c(t("net.irisshaders.iris.uniforms.CommonUniforms"),"isEyeInWater"));
                add(out,"camera_biome",()->c(level,"getBiome/m_204166_",pos).toString());
                add(out,"biome_fog_rgb",()->c(c(c(level,"getBiome/m_204166_",pos),"value/m_203334_"),"getFogColor/m_47539_"));
                add(out,"biome_water_fog_rgb",()->c(c(c(level,"getBiome/m_204166_",pos),"value/m_203334_"),"getWaterFogColor/m_47561_"));
                Class<?> render=t("com.mojang.blaze3d.systems.RenderSystem");
                add(out,"render_fog_rgb",()->c(render,"getShaderFogColor"));
                add(out,"render_fog_start",()->c(render,"getShaderFogStart"));
                add(out,"render_fog_end",()->c(render,"getShaderFogEnd"));
                Object iris=f(t("net.irisshaders.iris.uniforms.CapturedRenderingState"),"INSTANCE");
                add(out,"iris_captured_fog_rgb",()->c(iris,"getFogColor").toString());
                Object compat=c(t("net.irisshaders.iris.compat.dh.LodRendererEvents"),"getInstance");
                add(out,"dh_solid_uniforms",()->uniforms(c(compat,"getSolidShader")));
                add(out,"dh_water_uniforms",()->uniforms(c(compat,"getTranslucentShader")));
                add(out,"camera_debug_properties",()->{var flags=new TreeMap<String,String>();for(String key:System.getProperties().stringPropertyNames())if(key.startsWith("projectseele.")&&(key.toLowerCase().contains("camera")||key.toLowerCase().contains("fog")||key.toLowerCase().contains("review")))flags.put(key,System.getProperty(key));return flags;});
            }
            catch(Throwable error){out.put("error",error.toString());}
            try{Object gson=t("com.google.gson.Gson").getConstructor().newInstance();Files.writeString(output,(String)c(gson,"toJson",out));}catch(Exception error){throw new RuntimeException(error);}
        };
        c(mc,"execute/m_6937_",snapshot);
    }
}
