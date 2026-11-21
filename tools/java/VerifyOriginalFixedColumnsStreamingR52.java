package com.projectseele.world;
import com.google.gson.*;
import java.nio.*;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.security.*;
import java.lang.management.*;
import java.util.*;
import java.util.concurrent.atomic.*;
/** Isolated cold-method benchmark; old literal predicate is test code only. */
public final class VerifyOriginalFixedColumnsStreamingR52 {
 private static double[] old()throws Exception {
  byte[] bytes=EvaOriginalMeshGeometryR52.classpathBytes("mesh/tv_shoulder_shells_r44.json");var root=JsonParser.parseString(new String(bytes,StandardCharsets.UTF_8)).getAsJsonObject();if(root.get("stride").getAsInt()!=6||!root.get("frame").getAsString().equals("fixed_gantry_local_metres_world_axes"))throw new IllegalStateException("Actual original gantry frame source changed");
  var values=root.getAsJsonObject("parts").getAsJsonArray("cage_frame_lower_r44");var boxes=root.getAsJsonObject("collision_parts").getAsJsonArray("cage_frame_lower_r44");var points=new ArrayList<Double>();
  for(int i=0;i<values.size();i+=18){boolean lowerBar=false;double top=Math.max(values.get(i+1).getAsFloat(),Math.max(values.get(i+7).getAsFloat(),values.get(i+13).getAsFloat()));if(top<=-.61999)for(int b=boxes.size()-3;b<boxes.size();b++){var pair=boxes.get(b).getAsJsonArray();var lo=pair.get(0).getAsJsonArray();var hi=pair.get(1).getAsJsonArray();boolean inside=true;for(int c=0;c<18;c+=6)for(int axis=0;axis<3;axis++){double p=values.get(i+c+axis).getAsFloat();inside&=p>=lo.get(axis).getAsDouble()-1e-5&&p<=hi.get(axis).getAsDouble()+1e-5;}lowerBar|=inside;}if(!lowerBar)for(int c=0;c<18;c+=6)for(int axis=0;axis<3;axis++)points.add((double)values.get(i+c+axis).getAsFloat());}
  if(points.size()/9!=4912)throw new IllegalStateException("Complete actual columns including all eight bottom triangles required");return new NervRigidMeshSweepR52(points.stream().mapToDouble(x->x).toArray()).triangles();
 }
 public static void main(String[] a)throws Exception {
  var memory=ManagementFactory.getMemoryMXBean();var peak=new AtomicLong(memory.getHeapMemoryUsage().getUsed());var done=new AtomicBoolean(false);var monitor=new Thread(()->{while(!done.get()){peak.accumulateAndGet(memory.getHeapMemoryUsage().getUsed(),Math::max);try{Thread.sleep(2);}catch(InterruptedException ignored){}}});monitor.setDaemon(true);monitor.start();
  long begin=System.nanoTime();double[] values=a[0].equals("old")?old():NervPlantMotionR52.originalFixedColumnsR52().triangles();long elapsed=System.nanoTime()-begin;peak.accumulateAndGet(memory.getHeapMemoryUsage().getUsed(),Math::max);done.set(true);monitor.join();
  var bytes=ByteBuffer.allocate(values.length*8).order(ByteOrder.BIG_ENDIAN);for(double v:values)bytes.putLong(Double.doubleToRawLongBits(v));var raw=bytes.array();Files.write(Path.of(a[2]),raw);
  var result=new LinkedHashMap<String,Object>();result.put("mode",a[0]);result.put("triangles",values.length/9);result.put("double_values",values.length);result.put("output_raw_double_sha256",HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(raw)));result.put("elapsed_milliseconds",elapsed/1e6);result.put("heap_max_bytes",Runtime.getRuntime().maxMemory());result.put("heap_peak_used_sampled_2ms_bytes",peak.get());result.put("heap_pool_peak_used_sum_bytes",ManagementFactory.getMemoryPoolMXBeans().stream().filter(p->p.getType()==MemoryType.HEAP).mapToLong(p->p.getPeakUsage().getUsed()).sum());result.put("scope","One isolated first call against actual immutable resource; includes mesh construction. No World or complete-game speed/peak claim.");
  Files.writeString(Path.of(a[1]),new GsonBuilder().setPrettyPrinting().create().toJson(result));System.out.println(new Gson().toJson(result));
 }
}
