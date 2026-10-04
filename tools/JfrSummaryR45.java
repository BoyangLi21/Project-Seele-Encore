import jdk.jfr.consumer.*;
import java.nio.file.*;
import java.util.*;

/** Stream real JFR events; never recursively serialize JFR class-loader graphs. */
class JfrSummaryR45 {
    static Map<String,Long> events=new TreeMap<>(),threads=new TreeMap<>(),tops=new HashMap<>(),owners=new HashMap<>(),stacks=new HashMap<>();
    static Map<String,Long> allocationWeights=new HashMap<>(),allocationOwnerWeights=new HashMap<>();
    static void increment(Map<String,Long> map,String key){map.merge(key,1L,Long::sum);}
    static Object top(Map<String,Long> map,int limit){return map.entrySet().stream().sorted(Map.Entry.<String,Long>comparingByValue().reversed()).limit(limit).map(e->Map.of("key",e.getKey(),"samples",e.getValue())).toList();}
    static Object allocated(Map<String,Long> map,int limit){return map.entrySet().stream().sorted(Map.Entry.<String,Long>comparingByValue().reversed()).limit(limit).map(e->Map.of("key",e.getKey(),"estimated_allocation_bytes",e.getValue())).toList();}
    static String json(Object value){
        if(value==null)return "null";
        if(value instanceof String s)return "\""+s.replace("\\","\\\\").replace("\"","\\\"").replace("\n","\\n").replace("\r","\\r").replace("\t","\\t")+"\"";
        if(value instanceof Number||value instanceof Boolean)return value.toString();
        if(value instanceof Map<?,?> map)return "{"+String.join(",",map.entrySet().stream().map(e->json(e.getKey().toString())+":"+json(e.getValue())).toList())+"}";
        if(value instanceof Collection<?> items)return "["+String.join(",",items.stream().map(JfrSummaryR45::json).toList())+"]";
        throw new IllegalArgumentException(value.getClass().toString());
    }
    public static void main(String[] args)throws Exception{
        Path input=Path.of(args[0]),output=Path.of(args[1]);if(Files.exists(output))throw new IllegalArgumentException("Fresh output required");
        long samples=0,gcCount=0;double gcMs=0,gcMax=0;String first="",last="";
        List<Map<String,Object>> longPauses=new ArrayList<>();
        try(RecordingFile file=new RecordingFile(input)){
            while(file.hasMoreEvents()){
                var event=file.readEvent();String type=event.getEventType().getName();increment(events,type);
                if(first.isEmpty())first=event.getStartTime().toString();last=event.getStartTime().toString();
                if(type.equals("jdk.GCPhasePause")){
                    double ms=event.getDuration().toNanos()/1e6;gcMs+=ms;gcMax=Math.max(gcMax,ms);gcCount++;
                    if(ms>=100)longPauses.add(Map.of("time",event.getStartTime().toString(),"ms",ms));
                }
                if(type.equals("jdk.ObjectAllocationSample")){
                    String allocated=event.getClass("objectClass").getName();long weight=event.getLong("weight");
                    allocationWeights.merge(allocated,weight,Long::sum);
                    var allocationTrace=event.getStackTrace();
                    if(allocationTrace!=null)for(var frame:allocationTrace.getFrames()){
                        var method=frame.getMethod();String name=method.getType().getName()+"."+method.getName();
                        if(name.startsWith("com.projectseele.")||name.startsWith("com.simibubi.create.")){
                            allocationOwnerWeights.merge(name+" | "+allocated,weight,Long::sum);break;
                        }
                    }
                }
                if(!type.equals("jdk.ExecutionSample")&&!type.equals("jdk.NativeMethodSample"))continue;
                samples++;RecordedThread thread=event.hasField("sampledThread")?event.getThread("sampledThread"):event.getThread();
                String who=thread==null?"unknown":thread.getJavaName();increment(threads,who);
                RecordedStackTrace trace=event.getStackTrace();if(trace==null)continue;
                List<String> frames=new ArrayList<>();String owner="";
                for(var frame:trace.getFrames()){
                    var method=frame.getMethod();String name=method.getType().getName()+"."+method.getName();
                    frames.add(name+":"+frame.getLineNumber());
                    if(owner.isEmpty()&&(name.startsWith("com.projectseele.")||name.startsWith("com.simibubi.create.")))owner=name;
                }
                if(!frames.isEmpty())increment(tops,who+" | "+frames.get(0));
                if(!owner.isEmpty())increment(owners,who+" | "+owner);
                increment(stacks,who+" | "+String.join(" <- ",frames.subList(0,Math.min(frames.size(),24))));
            }
        }
        Map<String,Object> result=new LinkedHashMap<>();result.put("source",input.toAbsolutePath().toString());
        result.put("event_counts",events);result.put("sample_count",samples);result.put("threads",threads);
        result.put("top_frames",top(tops,100));result.put("first_project_or_create_frames",top(owners,100));result.put("stacks",top(stacks,80));
        result.put("gc_phase_pause",Map.of("count",gcCount,"total_ms",gcMs,"maximum_ms",gcMax,"at_least_100ms",longPauses));
        result.put("sampled_allocation_weight_bytes_by_class",allocated(allocationWeights,60));
        result.put("sampled_allocation_weight_bytes_by_project_owner",allocated(allocationOwnerWeights,80));
        result.put("allocation_caveat","Allocation weights estimate traffic, not retained/live heap size.");
        result.put("first_event_time",first);result.put("last_event_time",last);
        result.put("scope","Actual statistical samples, not exact wall-time attribution. The separate diagnostic PrintThreads safepoint must not count as application GC.");
        Files.writeString(output,json(result));System.out.println("Parsed "+samples+" actual samples; compact bytes="+Files.size(output));
    }
}
