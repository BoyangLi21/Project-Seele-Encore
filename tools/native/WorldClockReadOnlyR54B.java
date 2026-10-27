import java.lang.instrument.Instrumentation;
import java.nio.file.*;
import java.util.*;
public final class WorldClockReadOnlyR54B
{
    static Object c(Object owner,String names,Object...args)throws Exception{return DhRenderReadOnlyR54C.call(owner,names,args);}
    static Object f(Object owner,String...names)throws Exception{return DhRenderReadOnlyR54C.field(owner,names);}
    static Class<?> t(String name)throws Exception{return DhRenderReadOnlyR54C.type(name);}
    static Map<String,Object> level(Object level)throws Exception
    {
        var row=new LinkedHashMap<String,Object>();Object dimension=c(level,"dimensionType/m_6042_");
        long time=((Number)c(level,"getDayTime/m_46468_")).longValue();
        row.put("dimension",c(level,"dimension/m_46472_").toString());row.put("day_time",time);row.put("day_mod",Math.floorMod(time,24000));
        row.put("dimension_fixed_time",c(dimension,"fixedTime/f_63854_").toString());
        row.put("dimension_sun_phase",c(dimension,"timeOfDay/m_63904_",time));
        row.put("level_sun_phase",c(level,"getTimeOfDay/m_46942_",1F));
        return row;
    }
    public static void agentmain(String argument,Instrumentation instrumentation)throws Exception
    {
        String[] args=argument.split("\\|",-1);Path output=Path.of(args[0]);boolean server=args.length>1&&args[1].equals("server");
        if(Files.exists(output))throw new IllegalArgumentException("fresh output required");
        for(Class<?> type:instrumentation.getAllLoadedClasses())if(type.getName().equals("com.projectseele.ProjectSeele")){DhRenderReadOnlyR54C.loader=type.getClassLoader();break;}
        Object owner=server?c(t("net.minecraftforge.server.ServerLifecycleHooks"),"getCurrentServer"):c(t("net.minecraft.client.Minecraft"),"getInstance/m_91087_");
        Runnable read=()->{
            var out=new LinkedHashMap<String,Object>();out.put("read_only",true);out.put("server",server);out.put("utc_ms",System.currentTimeMillis());
            try
            {
                if(server){var rows=new ArrayList<Object>();for(Object l:(Iterable<?>)c(owner,"getAllLevels/m_129785_"))rows.add(level(l));out.put("levels",rows);}
                else
                {
                    Object l=f(owner,"level","f_91073_");out.put("level",level(l));
                    out.put("mission_night",c(t("com.projectseele.client.TvYashimaNightClientR54"),"surfaceNight",l));
                    out.put("iris_world_time",c(t("net.irisshaders.iris.uniforms.WorldTimeUniforms"),"getWorldDayTime"));
                    out.put("iris_dimension",c(t("net.irisshaders.iris.Iris"),"getCurrentDimension").toString());
                    Object camera=c(f(owner,"gameRenderer","f_91063_"),"getMainCamera/m_109153_");out.put("camera",c(camera,"getPosition/m_90583_").toString());
                    Object compat=c(t("net.irisshaders.iris.compat.dh.LodRendererEvents"),"getInstance");
                    Class<?> gl=t("org.lwjgl.opengl.GL20");var programs=new ArrayList<Object>();
                    for(String method:List.of("getSolidShader","getTranslucentShader"))
                    {
                        Object program=c(compat,method);if(program==null)continue;int id=((Number)f(program,"id")).intValue();var values=new LinkedHashMap<String,Object>();values.put("program",id);
                        for(String n:List.of("sunAngle","shadowAngle","rainStrength")){int at=((Number)c(gl,"glGetUniformLocation",id,n)).intValue();if(at>=0)values.put(n,c(gl,"glGetUniformf",id,at));}
                        int at=((Number)c(gl,"glGetUniformLocation",id,"worldTime")).intValue();if(at>=0)values.put("worldTime",c(gl,"glGetUniformi",id,at));programs.add(values);
                    }
                    out.put("gpu_uniforms",programs);
                }
            }catch(Throwable error){out.put("error",error.toString());}
            try{Object gson=t("com.google.gson.Gson").getConstructor().newInstance();Files.writeString(output,(String)c(gson,"toJson",out));}catch(Exception error){throw new RuntimeException(error);}
        };
        c(owner,server?"execute/m_18707_":"execute/m_6937_",read);
    }
}
