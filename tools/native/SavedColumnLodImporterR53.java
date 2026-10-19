import java.lang.instrument.*;import java.lang.reflect.*;import java.nio.file.*;import java.util.*;import java.util.concurrent.*;import java.io.*;import java.util.zip.*;
public final class SavedColumnLodImporterR53 {
 static ClassLoader loader;
 static Object c(Object owner,String names,Object...args)throws Exception {
  for(String name:names.split("/"))for(Class<?> type=owner instanceof Class<?>?(Class<?>)owner:owner.getClass();type!=null;type=type.getSuperclass())
   for(var method:type.getDeclaredMethods())if(method.getName().equals(name)&&method.getParameterCount()==args.length){method.setAccessible(true);try{return method.invoke(owner instanceof Class<?>?null:owner,args);}catch(IllegalArgumentException mismatch){}}
  throw new NoSuchMethodException(names);
 }
 static Class<?> t(String name)throws Exception{return Class.forName(name,false,loader);}
 static Object f(Object o,String n)throws Exception{for(Class<?> q=o.getClass();q!=null;q=q.getSuperclass())try{var v=q.getDeclaredField(n);v.setAccessible(true);return v.get(o);}catch(NoSuchFieldException e){}throw new NoSuchFieldException(n);}
 static volatile boolean stopped;
 static final String ROOT="com.seibel.distanthorizons.core.",WRAP="loaderCommon.forge.com.seibel.distanthorizons.common.wrappers.block.";
 public static void agentmain(String arg,Instrumentation ins)throws Exception{
  if(arg.equals("stop")){stopped=true;return;}for(Class<?> q:ins.getAllLoadedClasses())if(q.getName().equals("com.projectseele.ProjectSeele"))loader=q.getClassLoader();
  new Thread(()->{Path directory=Path.of(arg),output=directory.resolve("native-import.json");int completed=0;long start=System.currentTimeMillis();try{
   Object gson=t("com.google.gson.Gson").getConstructor().newInstance();Object world=c(t(ROOT+"api.internal.SharedApi"),"getDhClientServerWorld"),provider=null,wrapper=null;
   for(Object l:(Set<?>)f(world,"dhLevels"))if(String.valueOf(c(l,"getLevelWrapper")).contains("projectseele:geofront")){wrapper=c(l,"getLevelWrapper");provider=c(l,"getFullDataProvider");}
   if(provider==null)throw new IllegalStateException("GeoFront provider not ready");
   var blockCache=new HashMap<String,Object>();var biomeCache=new HashMap<String,Object>();Class<?> lists=t("it.unimi.dsi.fastutil.longs.LongArrayList");
   byte generation=((Number)f(t("com.seibel.distanthorizons.api.enums.worldGeneration.EDhApiWorldGenerationStep").getField("LIGHT").get(null),"value")).byteValue();
   byte compression=((Number)f(t("com.seibel.distanthorizons.api.enums.config.EDhApiWorldCompressionMode").getField("MERGE_SAME_BLOCKS").get(null),"value")).byteValue();
   List<Path> files;try(var paths=Files.list(directory)){files=paths.filter(p->p.toString().endsWith(".columns.gz")).sorted().toList();}
   for(Path file:files){if(stopped)break;Object source;
    try(var stream=new DataInputStream(new BufferedInputStream(new GZIPInputStream(Files.newInputStream(file))))){
     Map<?,?> header=(Map<?,?>)c(gson,"fromJson",new String(stream.readNBytes(stream.readInt()),java.nio.charset.StandardCharsets.UTF_8),Map.class);List<?> tile=(List<?>)header.get("tile"),pairs=(List<?>)header.get("pairs");
     long pos=(Long)c(t(ROOT+"pos.DhSectionPos"),"encode",(byte)6,((Number)tile.get(0)).intValue(),((Number)tile.get(1)).intValue());Object map=t(ROOT+"dataObjects.fullData.FullDataPointIdMap").getConstructor(long.class).newInstance(pos);int[] ids=new int[pairs.size()],emission=new int[pairs.size()];
     for(int i=0;i<pairs.size();i++){List<?> pair=(List<?>)pairs.get(i);String biome=(String)pair.get(0),state=(String)pair.get(1);Object bw=biomeCache.get(biome);if(bw==null){bw=c(t(WRAP+"BiomeWrapper"),"deserialize",biome,wrapper);biomeCache.put(biome,bw);}Object sw=blockCache.get(state);
      if(sw==null){
       int bracket=state.indexOf('[');String name=bracket<0?state:state.substring(0,bracket);
       Object registry=t("net.minecraftforge.registries.ForgeRegistries").getField("BLOCKS").get(null);
       String[] namespace=name.split(":",2);Object key=t("net.minecraft.resources.ResourceLocation").getConstructor(String.class,String.class).newInstance(namespace[0],namespace[1]);
       Object block=c(registry,"getValue",key);if(block==null)throw new IllegalStateException("Unknown source block "+name);
       Object nativeState=c(block,"defaultBlockState/m_49966_"),definition=c(block,"getStateDefinition/m_49965_");
       if(bracket>=0)for(String property:state.substring(bracket+1,state.length()-1).split(",")){
        String[] entry=property.split("=",2);Object prop=c(definition,"getProperty/m_61081_",entry[0]);if(prop==null)throw new IllegalStateException("Unknown source property "+property);
        Optional<?> value=(Optional<?>)c(prop,"getValue/m_6215_",entry[1]);if(value.isEmpty())throw new IllegalStateException("Unknown source value "+property);
        nativeState=c(nativeState,"setValue/m_61124_",prop,value.get());
        if(!c(nativeState,"getValue/m_61143_",prop).equals(value.get()))throw new IllegalStateException("Property round trip failed "+property);
       }
       sw=c(t(WRAP+"BlockStateWrapper"),"fromBlockState",nativeState,wrapper);blockCache.put(state,sw);
      }
      ids[i]=((Number)c(map,"addIfNotPresentAndGetId",bw,sw)).intValue();emission[i]=((Number)c(sw,"getLightEmission")).intValue();
     }
     Object columns=Array.newInstance(lists,4096);byte[] gen=new byte[4096],mode=new byte[4096];Arrays.fill(gen,generation);Arrays.fill(mode,compression);
     for(int i=0;i<4096;i++){int n=stream.readUnsignedShort();long[] spans=new long[n];int previous=1665;for(int k=0;k<n;k++){long value=stream.readLong();int id=(int)(value&0x7fffffff),bottom=(int)((value>>44)&4095),height=(int)((value>>32)&4095);if(bottom+height!=previous)throw new IllegalStateException("Gap/overlap in exact column");previous=bottom;int light=Math.max((int)((value>>>60)&15),emission[id]);spans[k]=(value&0x00ffffff00000000L)|ids[id]|((long)light<<60);}if(previous!=0)throw new IllegalStateException("Incomplete source column");Array.set(columns,i,lists.getConstructor(long[].class).newInstance((Object)spans));}
     if(stream.read()!=-1)throw new IllegalStateException("Trailing column data");source=c(t(ROOT+"dataObjects.fullData.sources.FullDataSourceV2"),"createWithData",pos,map,columns,gen,mode);source.getClass().getField("applyToParent").set(source,true);
     c(t(ROOT+"generation.DhLightingEngine").getField("INSTANCE").get(null),"bakeDataSourceSkyLight",source,15);
    }
    ((CompletableFuture<?>)c(provider,"updateDataSourceAsync",source)).get(60,TimeUnit.SECONDS);c(source,"close");completed++;
    Runtime vm=Runtime.getRuntime();Files.writeString(output,(String)c(gson,"toJson",Map.of("completed",completed,"total",files.size(),"done",completed==files.size(),"heap_mb",(vm.totalMemory()-vm.freeMemory())/1048576,"elapsed_seconds",(System.currentTimeMillis()-start)/1000,"last",file.getFileName().toString())));Thread.sleep(200);
   }
   var serials=new TreeMap<String,Object>();for(var entry:blockCache.entrySet())serials.put(entry.getKey(),c(entry.getValue(),"getSerialString"));
   Files.writeString(directory.resolve("native-palette.json"),(String)c(gson,"toJson",serials));
  }catch(Throwable e){while(e instanceof InvocationTargetException&&e.getCause()!=null)e=e.getCause();try{var trace=new StringWriter();e.printStackTrace(new PrintWriter(trace));Files.writeString(output,"completed="+completed+"\n"+trace);}catch(Exception ignored){}}},"SEELE saved-column native cache import").start();
 }
}
