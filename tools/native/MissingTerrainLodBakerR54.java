import java.lang.instrument.Instrumentation;
import java.nio.file.*;import java.util.*;import java.util.concurrent.*;import java.util.concurrent.atomic.*;import java.util.function.Consumer;
public final class MissingTerrainLodBakerR54 {
 static ClassLoader loader;
 static Class<?> t(String name)throws Exception{return Class.forName(name,false,loader);}
 static Object c(Object owner,String names,Object...args)throws Exception {
  Class<?> type=owner instanceof Class<?>?(Class<?>)owner:owner.getClass();
  for(String name:names.split("/")) {
   for(var m:type.getMethods())if(m.getName().equals(name)&&m.getParameterCount()==args.length)try{return m.invoke(owner instanceof Class<?>?null:owner,args);}catch(IllegalArgumentException mismatch){}
   for(Class<?> k=type;k!=null;k=k.getSuperclass())for(var m:k.getDeclaredMethods())if(m.getName().equals(name)&&m.getParameterCount()==args.length){m.setAccessible(true);try{return m.invoke(owner instanceof Class<?>?null:owner,args);}catch(IllegalArgumentException mismatch){}}
  }
  throw new NoSuchMethodException(names);
 }
 static volatile boolean stop;
 public static void agentmain(String arg,Instrumentation ins)throws Exception {
  if(arg.equals("stop")){stop=true;return;}
  for(Class<?> q:ins.getAllLoadedClasses())if(q.getName().equals("com.projectseele.ProjectSeele"))loader=q.getClassLoader();
  Path root=Path.of(arg);int workers=Files.exists(root.resolve("workers.txt"))?Integer.parseInt(Files.readString(root.resolve("workers.txt")).strip()):4;if(workers<1||workers>12)throw new IllegalArgumentException("workers must be 1..12");Object gson=t("com.google.gson.Gson").getConstructor().newInstance();
  new Thread(()->{Object generator=null;ExecutorService executor=Executors.newFixedThreadPool(workers);int completed=0;AtomicInteger chunks=new AtomicInteger();long start=System.nanoTime();try{
   Object world=c(t("com.seibel.distanthorizons.core.api.internal.SharedApi"),"getAbstractDhWorld"),level=null;
   for(Object l:(Iterable<?>)c(world,"getAllLoadedLevels"))if(String.valueOf(c(l,"getLevelWrapper")).contains("projectseele:geofront"))level=l;
   if(level==null)throw new IllegalStateException("GeoFront not loaded");Object provider=c(level,"getFullDataProvider");
   generator=t("com.seibel.distanthorizons.core.generation.BatchGenerator").getConstructor(t("com.seibel.distanthorizons.core.level.IDhLevel")).newInstance(level);
   Object mode=Enum.valueOf((Class)t("com.seibel.distanthorizons.api.enums.worldGeneration.EDhApiDistantGeneratorMode"),Files.exists(root.resolve("mode.txt"))?Files.readString(root.resolve("mode.txt")).strip():"FEATURES");
   List<?> list=(List<?>)c(gson,"fromJson",Files.readString(root.resolve("tiles.json")),List.class);
   var pending=new java.util.ArrayDeque<java.util.Map.Entry<java.util.concurrent.CompletableFuture<?>,List<?>>>();int next=0;
   while(next<list.size()||!pending.isEmpty()) {
    if(stop||Files.exists(root.resolve("STOP")))break;
    while(next<list.size()&&pending.size()<workers) {
     List<?> tile=(List<?>)list.get(next++);int x=((Number)tile.get(0)).intValue(),z=((Number)tile.get(1)).intValue();
     Consumer<Object[]> save=objects->{try{Object data=c(t("com.seibel.distanthorizons.core.dataObjects.fullData.sources.FullDataSourceV2"),"createFromChunk",objects[0]);try{c(t("com.seibel.distanthorizons.core.generation.DhLightingEngine").getField("INSTANCE").get(null),"bakeDataSourceSkyLight",data,15);((CompletableFuture<?>)c(provider,"updateDataSourceAsync",data)).get(60,TimeUnit.SECONDS);chunks.incrementAndGet();}finally{c(data,"close");}}catch(Exception e){throw new RuntimeException(e);}};
     c(generator,"preGeneratorTaskStart");var future=(CompletableFuture<?>)c(generator,"generateChunks",x*4,z*4,4,(byte)0,mode,executor,save);pending.add(Map.entry(future,tile));
    }
    var done=pending.remove();done.getKey().get(180,TimeUnit.SECONDS);completed++;
    Files.writeString(root.resolve("progress.json"),(String)c(gson,"toJson",Map.of("completed",completed,"total",list.size(),"chunks",chunks.get(),"seconds",(System.nanoTime()-start)/1000000000,"last",done.getValue(),"done",completed==list.size())));
   }
  }catch(Throwable e){try{var sw=new java.io.StringWriter();e.printStackTrace(new java.io.PrintWriter(sw));Files.writeString(root.resolve("error.txt"),sw.toString());}catch(Exception ignored){}}finally{executor.shutdownNow();if(generator!=null)try{c(generator,"close");}catch(Exception ignored){}}},"SEELE native missing-background bake").start();
 }
}
