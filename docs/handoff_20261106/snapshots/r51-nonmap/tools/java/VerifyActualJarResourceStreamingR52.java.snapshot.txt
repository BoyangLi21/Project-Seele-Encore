package com.projectseele.world;

import com.google.gson.*;
import cpw.mods.niofs.union.*;
import java.io.*;
import java.lang.management.ManagementFactory;
import java.net.*;
import java.nio.*;
import java.nio.file.*;
import java.nio.file.spi.FileSystemProvider;
import java.security.*;
import java.util.*;
import java.util.concurrent.atomic.*;
import java.util.zip.*;

/** Isolated actual C10 resource/geometry comparison. No World or game. */
public final class VerifyActualJarResourceStreamingR52 {
 static int checks; static void need(boolean ok,String message){if(!ok)throw new IllegalStateException(message);checks++;}
 static String hex(byte[] b){return HexFormat.of().formatHex(b);}
 static String hash(InputStream input)throws Exception {try(input){var d=MessageDigest.getInstance("SHA-256");try(var checked=new DigestInputStream(input,d)){checked.transferTo(OutputStream.nullOutputStream());}return hex(d.digest());}}
 static URL unionURL(Path p)throws Exception {return new URL(null,p.toUri().toString(),new URLStreamHandler(){protected URLConnection openConnection(URL url){return new URLConnection(url){public void connect(){}public InputStream getInputStream()throws IOException{return ((UnionPath)p).buildInputStream();}};}});}
 static InputStream actualStream(URL u)throws Exception {return (InputStream)EvaOriginalMeshGeometryR52.class.getDeclaredMethod("resourceStreamR52",URL.class).invoke(null,u);}
 static void value(MessageDigest d,double v){d.update(ByteBuffer.allocate(8).order(ByteOrder.BIG_ENDIAN).putLong(Double.doubleToRawLongBits(v)).array());}
 static Map<String,Object> parts(Map<String,double[]> parts,MessageDigest total){var rows=new TreeMap<String,Object>();for(String name:new TreeSet<>(parts.keySet())){var xyz=parts.get(name);MessageDigest d; try{d=MessageDigest.getInstance("SHA-256");}catch(Exception e){throw new IllegalStateException(e);}for(double v:xyz){value(d,v);value(total,v);}String sha=hex(d.digest());total.update(name.getBytes(java.nio.charset.StandardCharsets.UTF_8));rows.put(name,Map.of("triangles",xyz.length/9,"raw_double_sha256",sha));}return rows;}
 public static void main(String[] args)throws Exception {
  if(args[0].equals("union-stream")){
   var fsProvider=(UnionFileSystemProvider)FileSystemProvider.installedProviders().stream().filter(p->p.getScheme().equals("union")).findFirst().orElseThrow();
   try(var actual=fsProvider.newFileSystem((java.util.function.BiPredicate<String,String>)null,Path.of(args[1]));var loader=new URLClassLoader(new URL[]{VerifyActualJarResourceStreamingR52.class.getProtectionDomain().getCodeSource().getLocation()},VerifyActualJarResourceStreamingR52.class.getClassLoader()){
    protected synchronized Class<?> loadClass(String name,boolean resolve)throws ClassNotFoundException{if(name.startsWith("com.projectseele.world.VerifyActualJarResourceStreamingR52")||name.startsWith("com.projectseele.world.EvaOriginalMeshGeometryR52")||name.startsWith("com.projectseele.world.FullAssemblyGeometryR52")){var found=findLoadedClass(name);if(found==null)found=findClass(name);if(resolve)resolveClass(found);return found;}return super.loadClass(name,resolve);}
    public URL getResource(String name){if(name.startsWith("assets/projectseele/")){try{return unionURL(actual.getPath(name));}catch(Exception failed){throw new IllegalStateException(failed);}}return super.getResource(name);}
   }){loader.loadClass(VerifyActualJarResourceStreamingR52.class.getName()).getMethod("main",String[].class).invoke(null,(Object)new String[]{"stream",args[1],args[2]});}return;
  }
  boolean stream=args[0].equals("stream");Path jar=Path.of(args[1]),out=Path.of(args[2]);
  var peak=new AtomicLong();var sampling=new AtomicBoolean(true);var sampler=new Thread(()->{while(sampling.get()){peak.accumulateAndGet(ManagementFactory.getMemoryMXBean().getHeapMemoryUsage().getUsed(),Math::max);try{Thread.sleep(2);}catch(InterruptedException e){return;}}},"resource-probe-heap");sampler.setDaemon(true);sampler.start();
  var report=new LinkedHashMap<String,Object>();var pfx="assets/projectseele/";var provider=(UnionFileSystemProvider)FileSystemProvider.installedProviders().stream().filter(p->p.getScheme().equals("union")).findFirst().orElseThrow();
  try(var union=provider.newFileSystem((java.util.function.BiPredicate<String,String>)null,jar);var zip=new ZipFile(jar.toFile())){
   var manifest=JsonParser.parseString(new String(zip.getInputStream(zip.getEntry(pfx+"eva/full_assembly_geometry_r52_sources.json")).readAllBytes(),java.nio.charset.StandardCharsets.UTF_8)).getAsJsonObject();var expected=new TreeMap<String,String>();manifest.getAsJsonObject("resources").entrySet().forEach(e->expected.put(e.getKey(),e.getValue().getAsString()));
   var reads=new AtomicInteger();var source=(EvaOriginalMeshGeometryR52.ByteSource)relative->{reads.incrementAndGet();try(var input=((UnionPath)union.getPath(pfx+relative)).buildInputStream()){return input.readAllBytes();}};
   long start=System.nanoTime();FullAssemblyGeometryR52.Provider selected;
   if(stream){FullAssemblyGeometryR52.installClasspath();selected=FullAssemblyGeometryR52.selectedClasspathProviderR52(expected);}else selected=FullAssemblyGeometryR52.load(source,expected);
   report.put("first_load_ms",(System.nanoTime()-start)/1e6);report.put("first_load_heap_peak_used_sampled_2ms_bytes",peak.get());report.put("actual_classpath_carrier_url",EvaOriginalMeshGeometryR52.class.getResource("/"+pfx+"mesh/tripo_carrier_r48.json").toString());report.put("source_fingerprint",selected.sourceFingerprint());report.put("heap_max_bytes",Runtime.getRuntime().maxMemory());
   var total=MessageDigest.getInstance("SHA-256");var geometry=new TreeMap<String,Object>();
   for(int v=0;v<3;v++){
    geometry.put("plug_"+v,parts(selected.closedPlugParts(v),total));
    for(double deck:new double[]{0,3,64})for(float rise:new float[]{0,.5F,1})for(float release:new float[]{0,1})geometry.put("carrier_"+v+"_deck"+deck+"_rise"+rise+"_release"+release,parts(selected.carrierParts(v,rise,deck==3,release,deck),total));
   }
   report.put("effective_parts",geometry);report.put("ordered_geometry_raw_double_sha256",hex(total.digest()));
   var resources=new TreeMap<String,Object>();long begin=System.nanoTime();var allSelected=new TreeMap<>(expected);
   var evaManifest=JsonParser.parseString(new String(zip.getInputStream(zip.getEntry(pfx+"eva/eva_original_mesh_geometry_r52_sources.json")).readAllBytes(),java.nio.charset.StandardCharsets.UTF_8)).getAsJsonObject();evaManifest.getAsJsonObject("resources").entrySet().forEach(e->allSelected.put(e.getKey(),e.getValue().getAsString()));
   for(var row:allSelected.entrySet()){
    String n=row.getKey();String old=hash(((UnionPath)union.getPath(pfx+n)).buildInputStream());String actual=stream?hash(actualStream(unionURL(union.getPath(pfx+n)))):old;
    need(old.equals(row.getValue())&&actual.equals(old),"Actual union/resource bytes changed: "+n);resources.put(n,Map.of("sha256",actual,"uncompressed_bytes",zip.getEntry(pfx+n).getSize()));
   }
   report.put("all_actual_resource_bytes",resources);report.put("resource_byte_comparison_ms",(System.nanoTime()-begin)/1e6);
   if(stream){
    begin=System.nanoTime();for(int i=0;i<100;i++){FullAssemblyGeometryR52.installClasspath();need(FullAssemblyGeometryR52.selectedClasspathProviderR52(expected)==selected,"Successful classpath provider not reused");}report.put("cached_100_install_ms",(System.nanoTime()-begin)/1e6);
    var changed=new HashMap<>(expected);changed.put("mesh/tripo_carrier_r48.json","0".repeat(64));boolean denied=false;try{FullAssemblyGeometryR52.selectedClasspathProviderR52(changed);}catch(IllegalStateException correct){denied=true;}need(denied,"Changed SHA accepted");need(FullAssemblyGeometryR52.selectedClasspathProviderR52(expected)==selected,"Failed selection replaced successful provider");need(FullAssemblyGeometryR52.classpathReadyR52(),"Nonblocking ready absent");
    var called=new AtomicInteger();denied=false;try{FullAssemblyGeometryR52.load(name->{called.incrementAndGet();throw new IOException("actual external source unavailable");},expected);}catch(IOException correct){denied=true;}need(denied&&called.get()==1,"External ByteSource was bypassed by classpath cache");
    denied=false;try{FullAssemblyGeometryR52.load(name->{if(name.equals("geo/entry_plug_carrier.geo.json"))return Files.readAllBytes(Path.of("C:/Users/liboy/.codex/worktrees/r51-nonmap/eva/src/main/resources/assets/projectseele/geo/entry_plug_carrier.geo.json"));try(var input=zip.getInputStream(zip.getEntry(pfx+name))){return input.readAllBytes();}},expected);}catch(IllegalStateException correct){denied=true;}need(denied,"Raw709 capsule GEO accepted against selected b472");need(FullAssemblyGeometryR52.selectedClasspathProviderR52(expected)==selected,"External failed provider polluted packaged selection");
    Path overlay=out.getParent().resolve("priority_fixture"),file=overlay.resolve(pfx+"geo/entry_plug_carrier.geo.json");Files.createDirectories(file.getParent());byte[] different="selected-overlay-byte-witness".getBytes(java.nio.charset.StandardCharsets.UTF_8);Files.write(file,different);
    try(var layered=provider.newFileSystem((java.util.function.BiPredicate<String,String>)null,jar,overlay)){need(hash(((UnionPath)layered.getPath(pfx+"geo/entry_plug_carrier.geo.json")).buildInputStream()).equals(hash(actualStream(unionURL(layered.getPath(pfx+"geo/entry_plug_carrier.geo.json"))))),"Union overlay priority changed");}
    try(var filtered=provider.newFileSystem((name,base)->!base.contains("priority_fixture"),jar,overlay)){need(hash(actualStream(unionURL(filtered.getPath(pfx+"geo/entry_plug_carrier.geo.json")))).equals(expected.get("geo/entry_plug_carrier.geo.json")),"Union filesystem filter changed");}
   }
   report.put("old_union_full_load_reads",reads.get());report.put("checks",checks);
  }finally{sampling.set(false);sampler.join();}
  report.put("heap_peak_used_sampled_2ms_bytes",peak.get());report.put("mode",args[0]);report.put("world_written",false);report.put("game_started",false);report.put("scope","One isolated cold selected-resource load and exact effective-parts comparison; no complete-game performance claim.");Files.writeString(out,new GsonBuilder().setPrettyPrinting().create().toJson(report));System.out.println(new Gson().toJson(Map.of("mode",args[0],"checks",checks,"output",out.toString(),"first_load_ms",report.get("first_load_ms"),"geometry",report.get("ordered_geometry_raw_double_sha256"),"heap_peak",peak.get())));
 }
}
