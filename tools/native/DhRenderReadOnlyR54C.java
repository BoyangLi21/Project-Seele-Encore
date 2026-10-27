import java.lang.instrument.Instrumentation;
import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;

/** One render-thread snapshot; no inputs, configuration changes or cache writes. */
public final class DhRenderReadOnlyR54C
{
    static ClassLoader loader;
    static Class<?> type(String name) throws Exception {return Class.forName(name,false,loader);}
    static Object field(Object owner,String...names) throws Exception
    {
        for(String name:names)for(Class<?> c=owner instanceof Class<?>?(Class<?>)owner:owner.getClass();c!=null;c=c.getSuperclass())
            try{Field f=c.getDeclaredField(name);f.setAccessible(true);return f.get(owner instanceof Class<?>?null:owner);}catch(NoSuchFieldException absent){}
        throw new NoSuchFieldException(Arrays.toString(names));
    }
    static Object call(Object owner,String names,Object...args) throws Exception
    {
        Class<?> start=owner instanceof Class<?>?(Class<?>)owner:owner.getClass();
        for(String name:names.split("/"))for(Method m:start.getMethods())
            if(m.getName().equals(name)&&m.getParameterCount()==args.length)
                try{return m.invoke(owner instanceof Class<?>?null:owner,args);}catch(IllegalArgumentException mismatch){}
        for(String name:names.split("/"))for(Class<?> c=owner instanceof Class<?>?(Class<?>)owner:owner.getClass();c!=null;c=c.getSuperclass())
            for(Method m:c.getDeclaredMethods())if(m.getName().equals(name)&&m.getParameterCount()==args.length)
                try{m.setAccessible(true);return m.invoke(owner instanceof Class<?>?null:owner,args);}catch(IllegalArgumentException mismatch){}
        throw new NoSuchMethodException(names);
    }
    static Map<String,Object> matrix(Object matrix) throws Exception
    {
        var row=new LinkedHashMap<String,Object>();float[] values=new float[16];call(matrix,"get",values);row.put("column_major",values);
        float m22=((Number)call(matrix,"m22")).floatValue(),m32=((Number)call(matrix,"m32")).floatValue();
        row.put("projection_near",m32/(m22-1));row.put("projection_far",m32/(m22+1));return row;
    }
    static Map<String,Object> shader(Object program) throws Exception
    {
        var row=new LinkedHashMap<String,Object>();if(program==null){row.put("present",false);return row;}
        int id=((Number)field(program,"id")).intValue();row.put("id",id);Class<?> gl=type("org.lwjgl.opengl.GL20");
        for(String name:List.of("dhProjection","gbufferProjection","dhProjectionInverse","gbufferProjectionInverse"))
        {
            int location=((Number)call(gl,"glGetUniformLocation",id,name)).intValue();
            if(location<0)continue;float[] values=new float[16];call(gl,"glGetUniformfv",id,location,values);row.put(name,values);
        }
        for(String name:List.of("far","near","dhNearPlane","dhFarPlane"))
        {
            int location=((Number)call(gl,"glGetUniformLocation",id,name)).intValue();
            if(location>=0)row.put(name,call(gl,"glGetUniformf",id,location));
        }
        return row;
    }
    public static void agentmain(String argument,Instrumentation instrumentation) throws Exception
    {
        Path output=Path.of(argument.split("\\|",-1)[0]).toAbsolutePath().normalize();
        if(Files.exists(output))throw new IllegalArgumentException("Use a fresh snapshot output");
        for(Class<?> c:instrumentation.getAllLoadedClasses())if(c.getName().equals("com.projectseele.ProjectSeele")){loader=c.getClassLoader();break;}
        if(loader==null)throw new IllegalStateException("Project SEELE is not loaded");
        Object mc=call(type("net.minecraft.client.Minecraft"),"getInstance/m_91087_");
        Runnable snapshot=()->{
            var result=new LinkedHashMap<String,Object>();result.put("scope","Read-only current rendering snapshot; GPU uniforms reflect their last upload, not a newly rendered frame");
            result.put("utc_ms",System.currentTimeMillis());
            try
            {
                result.put("fps",call(mc,"getFps/m_260875_"));
                Object level=field(mc,"level","f_91073_");
                result.put("mc_min_y",call(level,"getMinBuildHeight/m_141937_"));result.put("mc_height",call(level,"getHeight/m_141928_"));
                Object dh=call(type("com.seibel.distanthorizons.core.api.internal.SharedApi"),"getIDhClientWorld");
                result.put("dh_world_mode",dh==null?null:dh.getClass().getSimpleName());
                var levels=new ArrayList<Object>();
                if(dh!=null)for(Object l:(Iterable<?>)call(dh,"getAllLoadedLevels"))
                {
                    var row=new LinkedHashMap<String,Object>();Object wrapper=call(l,"getLevelWrapper");
                    row.put("level",wrapper.toString());row.put("min_height",call(wrapper,"getMinHeight"));row.put("dh_min_y",call(l,"getMinY"));
                    Object network = field(l, "networkState");
                    row.put("server_support_ready", network != null && (Boolean)call(network, "isReady"));
                    if (network != null && (Boolean)call(network, "isReady"))
                    {
                        Object config = field(network, "sessionConfig");
                        row.put("server_realtime_updates", call(config, "isRealTimeUpdatesEnabled"));
                        row.put("server_update_radius_chunks", call(config, "getMaxUpdateDistanceRadius"));
                        row.put("server_distant_generation", call(config, "isDistantGenerationEnabled"));
                    }
                    Object client=field(l,"clientside");row.put("rendering",call(client,"isRendering"));
                    Object state=call(field(client,"ClientRenderStateRef"),"get");
                    if(state!=null){Object renderer=field(state,"lodRenderer");row.put("setup_complete",field(renderer,"isSetupComplete"));row.put("closed",field(renderer,"rendererClosed"));}
                    levels.add(row);
                }
                result.put("dh_levels",levels);
                Object proxy=field(type("com.seibel.distanthorizons.api.DhApi$Delayed"),"renderProxy");
                result.put("defer_transparent",call(proxy,"getDeferTransparentRendering"));
                Object iris=field(type("net.irisshaders.iris.uniforms.CapturedRenderingState"),"INSTANCE");
                result.put("captured_gbuffer_projection",matrix(call(iris,"getGbufferProjection")));
                float[] mv=new float[16];call(call(iris,"getGbufferModelView"),"get",mv);result.put("captured_gbuffer_modelview",mv);
                Object compatibility=call(type("net.irisshaders.iris.compat.dh.LodRendererEvents"),"getInstance");
                result.put("oculus_override",field(compatibility,"shouldOverride"));
                result.put("dh_solid_gpu",shader(call(compatibility,"getSolidShader")));
                result.put("dh_translucent_gpu",shader(call(compatibility,"getTranslucentShader")));
            }
            catch(Throwable error){result.put("error",error.toString());}
            try{Object gson=type("com.google.gson.Gson").getConstructor().newInstance();Files.writeString(output,(String)call(gson,"toJson",result));}
            catch(Exception error){throw new RuntimeException(error);}
        };
        call(mc,"execute/m_6937_",snapshot);
    }
}
