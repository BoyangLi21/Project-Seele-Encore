import java.lang.instrument.Instrumentation;
import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.io.*;
import java.util.zip.GZIPOutputStream;

/** Read already generated chunks on the isolated server thread for candidates.
 * Never loads an uncompleted target, writes a save, or publishes a world patch.
 */
public final class ExportCompletedTerrainR55B {
    private static ClassLoader loader;
    private static Class<?> type(String s)throws Exception{return Class.forName(s,false,loader);}
    private static Object call(Object owner,String names,Object...args)throws Exception{
        for(String name:names.split("/"))for(Class<?> k=owner instanceof Class<?>?(Class<?>)owner:owner.getClass();k!=null;k=k.getSuperclass())
            for(var m:k.getDeclaredMethods())if(m.getName().equals(name)&&m.getParameterCount()==args.length){
                m.setAccessible(true);try{return m.invoke(owner instanceof Class<?>?null:owner,args);}catch(IllegalArgumentException wrong){}
            }
        throw new NoSuchMethodException(names);
    }
    public static void agentmain(String argument,Instrumentation instrumentation)throws Exception{
        for(Class<?> c:instrumentation.getAllLoadedClasses())if(c.getName().equals("com.projectseele.ProjectSeele"))loader=c.getClassLoader();
        Path out=Path.of(argument),bake=Path.of(Files.readString(out.resolve("bake-directory.txt")).strip());
        Object gson=type("com.google.gson.Gson").getConstructor().newInstance();
        Map<?,?> plan=(Map<?,?>)call(gson,"fromJson",Files.readString(bake.resolve("plan.json")),Map.class);
        Map<?,?> progress=(Map<?,?>)call(gson,"fromJson",Files.readString(bake.resolve("progress.json")),Map.class);
        List<?> all=(List<?>)plan.get("chunks");int completed=((Number)progress.get("completed")).intValue();
        Set<?> finished=new HashSet<>(all.subList(0,completed));
        List<?> requested=(List<?>)call(gson,"fromJson",Files.readString(out.resolve("chunks.json")),List.class);
        if(requested.isEmpty()||requested.size()>4096||new HashSet<>(requested).size()!=requested.size()||!finished.containsAll(requested))
            throw new IllegalStateException("Only a finite subset of the attested completed prefix can be exported");
        Object server=call(type("net.minecraftforge.server.ServerLifecycleHooks"),"getCurrentServer");
        Class<?> resourceType=type("net.minecraft.world.level.storage.LevelResource");var ctor=resourceType.getDeclaredConstructor(String.class);ctor.setAccessible(true);
        Object resource=ctor.newInstance(".");Path actual=null;
        for(var m:server.getClass().getMethods())if(m.getReturnType()==Path.class&&Arrays.equals(m.getParameterTypes(),new Class<?>[]{resourceType}))actual=((Path)m.invoke(server,resource)).toRealPath();
        Path expected=Path.of((String)plan.get("cache_world")).toRealPath();
        if(actual==null||!actual.equals(expected)||!expected.toString().replace('\\','/').contains("/cache-server/"))throw new IllegalStateException("Isolated authoring save required");
        if(((Number)call(call(server,"getPlayerList/m_6846_"),"getPlayerCount/m_11309_")).intValue()!=0)throw new IllegalStateException("Players connected");
        Object level=null;for(Object q:(Iterable<?>)call(server,"getAllLevels/m_129785_"))
            if(String.valueOf(call(call(q,"dimension/m_46472_"),"location/m_135782_")).equals("projectseele:geofront"))level=q;
        if(level==null||((Number)call(level,"getSeed/m_7328_")).longValue()!=Long.parseLong(Files.readString(bake.resolve("seed.txt")).strip()))throw new IllegalStateException("Missing/mismatched geofront");
        Object generator=call(call(level,"getChunkSource/m_7726_"),"getGenerator/m_8481_");
        if(!generator.getClass().getName().equals("com.projectseele.world.GeoFrontBoundedChunkGenerator"))throw new IllegalStateException("Wrong generator");
        var bindings=type("com.projectseele.world.CityRigidGenerationR45").getDeclaredField("BINDINGS");bindings.setAccessible(true);
        Object binding=((Map<?,?>)bindings.get(null)).get(generator);
        if(binding==null||!call(binding,"world").equals(plan.get("world_uuid")))throw new IllegalStateException("Different world binding");
        for(String name:List.of("hakone_surface.bin.gz","hakone_surface_blend.bin.gz"))try(var in=loader.getResourceAsStream("data/projectseele/worldgen/"+name)){
            if(in==null||!Arrays.equals(in.readAllBytes(),Files.readAllBytes(bake.resolve("terrain-inputs").resolve(name))))throw new IllegalStateException("Terrain input changed");
        }
        Object target=level;Files.createDirectories(out.resolve("chunks"));
        new Thread(()->{
            int done=0;
            try{
                for(Object raw:requested){
                    List<?> q=(List<?>)raw;int x=((Number)q.get(0)).intValue(),z=((Number)q.get(1)).intValue();CompletableFuture<byte[]> ready=new CompletableFuture<>();
                    ((Executor)server).execute(()->{
                        try{
                            Object chunk=call(target,"getChunk/m_6325_",x,z),tag=null;
                            for(var m:type("net.minecraft.world.level.chunk.storage.ChunkSerializer").getDeclaredMethods())
                                if(Modifier.isStatic(m.getModifiers())&&m.getParameterCount()==2&&m.getReturnType()==type("net.minecraft.nbt.CompoundTag")
                                    &&m.getParameterTypes()[0].isInstance(target)&&m.getParameterTypes()[1].isInstance(chunk)){
                                    if(tag!=null)throw new IllegalStateException("Ambiguous chunk serialization");m.setAccessible(true);tag=m.invoke(null,target,chunk);
                                }
                            if(tag==null)throw new IllegalStateException("Chunk serialization unavailable");
                            var buffer=new ByteArrayOutputStream();
                            try(var data=new DataOutputStream(new GZIPOutputStream(buffer))){
                                data.writeByte(10);data.writeUTF("");boolean written=false;
                                for(var m:tag.getClass().getDeclaredMethods())if(m.getReturnType()==void.class&&Arrays.equals(m.getParameterTypes(),new Class<?>[]{DataOutput.class})){
                                    if(written)throw new IllegalStateException("Ambiguous NBT serialization");m.setAccessible(true);m.invoke(tag,data);written=true;
                                }
                                if(!written)throw new IllegalStateException("NBT serialization unavailable");
                            }
                            ready.complete(buffer.toByteArray());
                        }catch(Throwable error){ready.completeExceptionally(error);}
                    });
                    byte[] bytes=ready.get(120,TimeUnit.SECONDS);Files.write(out.resolve("chunks").resolve(x+"_"+z+".dat"),bytes);done++;
                    if(done%16==0||done==requested.size())Files.writeString(out.resolve("progress.json"),(String)call(gson,"toJson",Map.of("completed",done,"total",requested.size(),"exported",done==requested.size(),"actual_world_written",false,"cache_saved",false)));
                    Thread.sleep(50);
                }
                Files.writeString(out.resolve("receipt.json"),(String)call(gson,"toJson",Map.of("cache_world",expected.toString(),"bake",bake.toString(),"completed_prefix_at_start",completed,"exported_chunks",done,"pid",ProcessHandle.current().pid(),"actual_world_written",false,"candidate_only",true)));
            }catch(Throwable error){try{var sw=new StringWriter();error.printStackTrace(new PrintWriter(sw));Files.writeString(out.resolve("error.txt"),sw.toString());}catch(Exception ignored){}}
        },"SEELE completed native terrain candidate export").start();
    }
}
