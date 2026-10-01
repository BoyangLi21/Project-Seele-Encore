import java.lang.instrument.Instrumentation;
import java.lang.reflect.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.function.Predicate;

/** Snapshot existing production guards on the server thread. No world edits or entity changes. */
public final class R44TokyoInspectAgent
{
    private static Map<String,Class<?>> classes;
    private static Class<?> c(String name){Class<?> found=classes.get(name);if(found==null)throw new IllegalStateException("Required loaded class missing: "+name);return found;}
    private static Object field(Class<?> type,String name,Object owner)throws Exception{var f=type.getDeclaredField(name);f.setAccessible(true);return f.get(owner);}
    private static Object call(Object owner,String name,Object...args)throws Exception
    {
        Class<?> type=owner instanceof Class<?>?(Class<?>)owner:owner.getClass();
        List<Method> methods=new ArrayList<>(Arrays.asList(type.getMethods()));
        for(Class<?> at=type;at!=null;at=at.getSuperclass())methods.addAll(Arrays.asList(at.getDeclaredMethods()));
        for(Method m:methods)
        {
            if(!m.getName().equals(name)||m.getParameterCount()!=args.length)continue;
            Class<?>[] p=m.getParameterTypes();boolean match=true;
            for(int i=0;i<p.length;i++)if(args[i]!=null&&!box(p[i]).isInstance(args[i]))match=false;
            if(!match)continue;m.setAccessible(true);return m.invoke(owner instanceof Class<?>?null:owner,args);
        }
        throw new NoSuchMethodException(type.getName()+"."+name+"/"+args.length);
    }
    private static Class<?> box(Class<?> p){if(!p.isPrimitive())return p;if(p==int.class)return Integer.class;if(p==long.class)return Long.class;if(p==boolean.class)return Boolean.class;if(p==double.class)return Double.class;if(p==float.class)return Float.class;return p;}
    private static int n(Object owner,String method)throws Exception{return ((Number)call(owner,method)).intValue();}
    private static Map<String,Object> row(Object... pairs){Map<String,Object> r=new LinkedHashMap<>();for(int i=0;i<pairs.length;i+=2)r.put((String)pairs[i],pairs[i+1]);return r;}
    private static String text(Object owner,String method)throws Exception{return String.valueOf(call(owner,method));}
    public static void agentmain(String arguments,Instrumentation instrumentation)throws Exception
    {
        String[] args=arguments.split("\\|",-1);if(args.length!=4)throw new IllegalArgumentException("mode|expectedJob|expectedWorld|output");
        boolean halt=args[0].equals("inspect-and-halt");if(!halt&&!args[0].equals("inspect"))throw new IllegalArgumentException("Unknown operation");
        Path expectedJob=Path.of(args[1]).toAbsolutePath().normalize(),expectedWorld=Path.of(args[2]).toAbsolutePath().normalize(),output=Path.of(args[3]).toAbsolutePath().normalize();
        if(!expectedWorld.getFileName().toString().equals("SEELE_FIELD_R44_REVIEW"))throw new IllegalStateException("Wrong expected world");
        if(!Path.of(System.getProperty("projectseele.r44TokyoQualityJob","")).toAbsolutePath().normalize().equals(expectedJob))throw new IllegalStateException("Wrong actual quality job");
        if(Files.exists(output))throw new IllegalStateException("Preserve previous diagnostic: "+output);
        classes=new HashMap<>();for(Class<?> type:instrumentation.getAllLoadedClasses())classes.put(type.getName(),type);
        Object server=call(c("net.minecraftforge.server.ServerLifecycleHooks"),"getCurrentServer");if(server==null)throw new IllegalStateException("No active server");
        Object root=field(c("net.minecraft.world.level.storage.LevelResource"),"ROOT",null);
        Path actual=((Path)call(server,"getWorldPath",root)).toAbsolutePath().normalize();if(!actual.equals(expectedWorld))throw new IllegalStateException("Wrong actual world: "+actual);
        Runnable inspect=()->
        {
            try
            {
                Map<String,Object> report=sample(server,expectedJob,expectedWorld);report.put("normal_halt_requested",halt);
                Files.createDirectories(output.getParent());Files.writeString(output,json(report),StandardCharsets.UTF_8,StandardOpenOption.CREATE_NEW);
                System.out.println("R44 TOKYO INSPECT wrote "+output);
                if(halt)call(server,"halt",false);
            }
            catch(Throwable error){System.err.println("R44 TOKYO INSPECT failed; no halt requested after error");error.printStackTrace();}
        };
        call(server,"execute",inspect);
    }
    private static Map<String,Object> sample(Object server,Path job,Path world)throws Exception
    {
        Class<?> fixture=c("com.projectseele.world.Tokyo3BuildingQualityR44"),director=c("com.projectseele.world.Tokyo3RetractionDirector"),builder=c("com.projectseele.world.ThirdTokyoSurfaceBuilder");
        Object input=field(fixture,"input",null);if(input==null)throw new IllegalStateException("Quality fixture not initialised");
        long expectedSeed=((Number)call(call(input,"get","world_seed"),"getAsLong")).longValue();
        if(!Path.of(text(call(input,"get","world"),"getAsString")).toAbsolutePath().normalize().equals(world))throw new IllegalStateException("Fixture input world mismatch");
        Object level=null;for(Object candidate:(Iterable<?>)call(server,"getAllLevels"))if(text(call(candidate,"dimension"),"location").equals("projectseele:geofront"))level=candidate;
        if(level==null||((Number)call(level,"getSeed")).longValue()!=expectedSeed)throw new IllegalStateException("Dimension/seed mismatch");
        Object origin=call(c("com.projectseele.world.IntegratedNervMapBuilder"),"tokyo3Origin",level),data=call(c("com.projectseele.world.Tokyo3RetractionSavedData"),"get",level);
        Object district=((Optional<?>)call(data,"get",origin)).orElseThrow();int depth=n(district,"depth"),target=n(district,"targetDepth"),next=depth+Integer.signum(target-depth);
        Map<String,Object> result=row("read_only",true,"world",world.toString(),"job",job.toString(),"seed",expectedSeed,"game_time",call(level,"getGameTime"),"origin",origin.toString(),"depth",depth,"target",target,"next_depth",next,"cursor",call(district,"cursor"),"voxel_cursor",call(district,"voxelCursor"),"queued_target",call(district,"queuedTargetDepth"),"next_step_at",call(district,"nextStepAt"),"fault",call(district,"fault"));
        for(String name:List.of("age","index","phase","timer","mode","requested","done","requestedEndpointDepth"))result.put("fixture_"+name,field(fixture,name,null));
        result.put("production_district_loaded",call(director,"districtLoaded",level,origin));result.put("production_travel_occupied",call(director,"travelOccupied",level,origin,depth,next));
        Object key=call(director,"travelKey",level,origin);result.put("claimed_ticket_cursor",((Map<?,?>)field(director,"TICKET_CURSOR",null)).get(key));
        List<Object> chunkRows=new ArrayList<>();Object source=call(level,"getChunkSource");
        for(long packed:(long[])call(director,"travelChunks",level,origin))
        {
            int x=(int)packed,z=(int)(packed>>32);Object full=call(source,"getChunkNow",x,z);
            chunkRows.add(row("x",x,"z",z,"has_chunk",call(level,"hasChunk",x,z),"full_chunk_now",full!=null));
        }
        result.put("travel_chunks",chunkRows);List<Object> envelopes=new ArrayList<>();int towerIndex=0;
        for(Object tower:(Iterable<?>)call(builder,"movableBuildings",level))
        {
            int half=n(tower,"halfSize"),height=n(tower,"height"),cx=n(origin,"getX")+n(tower,"x"),cz=n(origin,"getZ")+n(tower,"z"),oy=n(origin,"getY");
            int visible=Math.max(Math.max(0,height-depth),Math.max(0,height-next));
            envelopes.add(envelope(level,towerIndex,"generated_surface",cx-half,oy,cz-half,cx+half+1,oy+visible+5,cz+half+1,false));
            int roof=oy+((Number)call(builder,"ceilingRoofRelativeY",tower,origin)).intValue(),travel=Math.max(height,oy-roof),below=Math.max(0,Math.min(height,Math.max(depth,next)-travel));
            if(below>0)envelopes.add(envelope(level,towerIndex,"generated_underground",cx-half,roof-below-2,cz-half,cx+half+1,roof+4,cz+half+1,false));
            towerIndex++;
        }
        Class<?> loader=c("com.projectseele.world.LocalMapAssetLoader");int importedIndex=0;
        Object templateSize=field(loader,"SKYSCRAPER_TEMPLATE_SIZE",null);
        for(Object placement:(Object[])field(loader,"SKYSCRAPERS",null))
        {
            Object rotation=call(placement,"rotation"),size=call(loader,"rotatedSkyscraperSize",rotation),bounds=call(loader,"skyscraperBounds",rotation),base=call(origin,"offset",call(placement,"offset"));
            int oldDrop=((Number)call(loader,"skyscraperDrop",placement,size,depth,origin,level)).intValue(),newDrop=((Number)call(loader,"skyscraperDrop",placement,size,next,origin,level)).intValue();
            int x=n(base,"getX"),y=n(base,"getY"),z=n(base,"getZ");
            envelopes.add(envelope(level,importedIndex++,"imported_player_or_eva",x+n(bounds,"minimumX"),y-Math.max(oldDrop,newDrop),z+n(bounds,"minimumZ"),x+n(bounds,"maximumX")+1,y-Math.min(oldDrop,newDrop)+n(templateSize,"getY"),z+n(bounds,"maximumZ")+1,true));
        }
        result.put("production_envelopes",envelopes);result.put("entity_identity_preserved",true);return result;
    }
    private static Map<String,Object> envelope(Object level,int tower,String kind,double x0,double y0,double z0,double x1,double y1,double z1,boolean imported)throws Exception
    {
        Object aabb=c("net.minecraft.world.phys.AABB").getConstructor(double.class,double.class,double.class,double.class,double.class,double.class).newInstance(x0,y0,z0,x1,y1,z1);
        Predicate<Object> eligible=entity->{try{return (Boolean)call(entity,"isAlive")&&!(Boolean)call(entity,"isSpectator")&&(!imported||c("net.minecraft.world.entity.player.Player").isInstance(entity)||c("com.projectseele.entity.EvaUnit01Entity").isInstance(entity));}catch(Exception e){throw new RuntimeException(e);}};
        List<Object> blockers=new ArrayList<>();for(Object entity:(Iterable<?>)call(level,"getEntitiesOfClass",c("net.minecraft.world.entity.LivingEntity"),aabb,eligible))
        {
            Object tags=call(entity,"getTags");boolean probe=((Set<?>)tags).stream().anyMatch(t->t.toString().startsWith("r44_city_quality/"));
            blockers.add(row("uuid",text(entity,"getUUID"),"entity_type",text(entity,"getType"),"java_type",entity.getClass().getName(),"position",text(entity,"position"),"aabb",text(entity,"getBoundingBox"),"tags",tags,"quality_probe",probe,"original_actor",!probe,"alive",call(entity,"isAlive"),"spectator",call(entity,"isSpectator")));
        }
        return row("tower",tower,"kind",kind,"aabb",List.of(x0,y0,z0,x1,y1,z1),"blockers",blockers);
    }
    private static String json(Object value)
    {
        if(value==null)return "null";if(value instanceof Number||value instanceof Boolean)return value.toString();
        if(value instanceof Map<?,?> map){StringJoiner out=new StringJoiner(",","{","}");for(var e:map.entrySet())out.add(json(e.getKey().toString())+":"+json(e.getValue()));return out.toString();}
        if(value instanceof Iterable<?> list){StringJoiner out=new StringJoiner(",","[","]");for(Object v:list)out.add(json(v));return out.toString();}
        return "\""+value.toString().replace("\\","\\\\").replace("\"","\\\"").replace("\n","\\n").replace("\r","\\r").replace("\t","\\t")+"\"";
    }
}
