import java.lang.instrument.Instrumentation;
import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;
import java.util.function.Consumer;

/** Drives only vanilla movement keys along an explicitly named input path. */
public final class CurrentOrdinaryWalkingAgentR53
{
    private static ClassLoader loader;
    private static Class<?> type(String n)throws Exception{return Class.forName(n,true,loader);}
    private static Object field(Object o,String... names)throws Exception{for(String n:names)try{return o.getClass().getField(n).get(o);}catch(NoSuchFieldException missing){}throw new NoSuchFieldException(Arrays.toString(names));}
    private static Object invoke(Object o,String[] names,Class<?>[] sig,Object... args)throws Exception{for(String n:names)try{return o.getClass().getMethod(n,sig).invoke(o,args);}catch(NoSuchMethodException missing){}throw new NoSuchMethodException(Arrays.toString(names));}
    private static Object call(Object o,String... names)throws Exception{return invoke(o,names,new Class<?>[0]);}
    private static void key(Object o,boolean down)throws Exception{invoke(o,new String[]{"setDown","m_7249_"},new Class<?>[]{boolean.class},down);}
    private static double[] position(Object player)throws Exception{Object p=call(player,"position","m_20182_");return new double[]{((Number)field(p,"x","f_82479_")).doubleValue(),((Number)field(p,"y","f_82480_")).doubleValue(),((Number)field(p,"z","f_82481_")).doubleValue()};}
    private static Map<String,Object> state(Object player)throws Exception{var r=new LinkedHashMap<String,Object>();r.put("position",position(player));r.put("uuid",call(player,"getUUID","m_20148_").toString());r.put("on_ground",call(player,"onGround","m_20096_"));r.put("velocity",call(player,"getDeltaMovement","m_20184_").toString());r.put("flying",field(call(player,"getAbilities","m_150110_"),"flying","f_35935_"));r.put("passenger",call(player,"isPassenger","m_20159_"));return r;}
    private static void write(Path p,Map<String,Object> value)throws Exception{Object gson=type("com.google.gson.Gson").getConstructor().newInstance();Files.createDirectories(p.getParent());Files.writeString(p,gson.getClass().getMethod("toJson",Object.class).invoke(gson,value)+"\n",StandardOpenOption.CREATE,StandardOpenOption.APPEND);}
    public static void agentmain(String argument,Instrumentation inst)throws Exception
    {
        String[] args=argument.split("\\|",-1);if(args.length!=2)throw new IllegalArgumentException("plan|fresh_output required");
        Path plan=Path.of(args[0]).toAbsolutePath().normalize(),output=Path.of(args[1]).toAbsolutePath().normalize();
        if(Files.exists(output)||Files.size(plan)>16000000)throw new IllegalArgumentException("Fresh bounded path input required");
        for(Path at=output;at!=null;at=at.getParent())if(Files.exists(at.resolve("level.dat"))||Files.exists(at.resolve("session.lock")))throw new IllegalArgumentException("Output inside World");
        for(Class<?> c:inst.getAllLoadedClasses())if(c.getName().equals("com.projectseele.ProjectSeele")){loader=c.getClassLoader();break;}if(loader==null)throw new IllegalStateException("Actual mod required");
        Object gson=type("com.google.gson.Gson").getConstructor().newInstance();Object decoded=gson.getClass().getMethod("fromJson",String.class,Class.class).invoke(gson,Files.readString(plan),Map.class);
        Map<?,?> document=(Map<?,?>)decoded;if(!"projectseele.r53.ordinary-named-walk-input.v1".equals(document.get("schema")))throw new IllegalArgumentException("Explicit named walking input schema required");
        var targets=new ArrayList<double[]>();for(Object raw:(List<?>)document.get("feet_targets")){List<?> p=(List<?>)raw;if(p.size()!=3)throw new IllegalArgumentException("XYZ feet target required");double[] v=new double[3];for(int i=0;i<3;i++){v[i]=((Number)p.get(i)).doubleValue();if(!Double.isFinite(v[i]))throw new IllegalArgumentException("Finite path required");}targets.add(v);}
        if(targets.isEmpty()||targets.size()>50000)throw new IllegalArgumentException("Bounded named path required");
        Object mc;try{mc=type("net.minecraft.client.Minecraft").getMethod("getInstance").invoke(null);}catch(NoSuchMethodException e){mc=type("net.minecraft.client.Minecraft").getMethod("m_91087_").invoke(null);}final Object client=mc;
        Runnable start=()->
        {
            try
            {
                Object player=field(client,"player","f_91074_");if(player==null||field(client,"screen","f_91080_")!=null)throw new IllegalStateException("Actual player with closed screen required");
                Map<String,Object> initial=state(player);if(Boolean.TRUE.equals(initial.get("flying"))||Boolean.TRUE.equals(initial.get("passenger")))throw new IllegalStateException("Actual walking mode required");
                double[] at=position(player),first=targets.get(0);if(Math.hypot(at[0]-first[0],at[2]-first[2])>1.5||Math.abs(at[1]-first[1])>1.5)throw new IllegalStateException("Player must already reach the named starting point");
                var keys=new LinkedHashMap<String,Object>();Object options=field(client,"options","f_91066_");for(Field f:options.getClass().getFields())if(f.getType().getName().equals("net.minecraft.client.KeyMapping")){Object k=f.get(options);if(k!=null){String name=call(k,"getName","m_90860_").toString();if(List.of("key.forward","key.back","key.left","key.right","key.jump","key.sneak","key.sprint").contains(name))keys.put(name,k);}}
                if(keys.size()!=7)throw new IllegalStateException("Seven actual normal movement bindings required");for(Object k:keys.values())key(k,false);
                Object bus=type("net.minecraftforge.common.MinecraftForge").getField("EVENT_BUS").get(null),priority=Enum.valueOf((Class)type("net.minecraftforge.eventbus.api.EventPriority"),"LOWEST");
                int[] index={0},ticks={0},lastAdvance={0};long deadline=System.nanoTime()+7200000000000L;Consumer<Object>[] listener=new Consumer[1];
                Map<String,Object> begin=new LinkedHashMap<>();begin.put("event","START");begin.put("utc_ms",System.currentTimeMillis());begin.put("plan",plan.toString());begin.put("input_named_path_id",document.get("named_path_id"));begin.put("planned_waypoints",targets.size());begin.put("initial",initial);begin.put("direct_position_or_ability_write",false);begin.put("global_functional_pass_claimed",false);write(output,begin);
                listener[0]=event->
                {
                    boolean end=false;String failure="";
                    try
                    {
                        if(!field(event,"phase").toString().equals("START"))return;ticks[0]++;
                        Map<String,Object> actual=state(player);double[] p=(double[])actual.get("position");
                        if(field(client,"screen","f_91080_")!=null||Boolean.TRUE.equals(actual.get("flying"))||Boolean.TRUE.equals(actual.get("passenger")))throw new IllegalStateException("Actual walking mode or screen changed");
                        while(index[0]<targets.size())
                        {
                            double[] target=targets.get(index[0]);double distance=Math.hypot(p[0]-target[0],p[2]-target[2]);
                            if(distance>.34||Math.abs(p[1]-target[1])>.60)break;
                            var hit=new LinkedHashMap<String,Object>();hit.put("event","WAYPOINT_REACHED");hit.put("index",index[0]);hit.put("target",target);hit.put("actual",actual);hit.put("client_tick",ticks[0]);hit.put("utc_ms",System.currentTimeMillis());write(output,hit);index[0]++;lastAdvance[0]=ticks[0];
                        }
                        if(index[0]>=targets.size())end=true;
                        else
                        {
                            double[] target=targets.get(index[0]);if(Math.abs(p[1]-target[1])>2.5)throw new IllegalStateException("Unexpected actual vertical position");
                            if(ticks[0]-lastAdvance[0]>300||System.nanoTime()>deadline||Files.exists(output.resolveSibling(output.getFileName()+".stop")))throw new IllegalStateException("Ordinary walking blocked, timed out, or stopped");
                            float yaw=(float)Math.toDegrees(Math.atan2(-(target[0]-p[0]),target[2]-p[2]));invoke(player,new String[]{"setYRot","m_146922_"},new Class<?>[]{float.class},yaw);invoke(player,new String[]{"setXRot","m_146926_"},new Class<?>[]{float.class},0F);
                            key(keys.get("key.forward"),true);key(keys.get("key.jump"),target[1]-p[1]>.60);
                        }
                    }
                    catch(Throwable error){while(error instanceof InvocationTargetException&&error.getCause()!=null)error=error.getCause();failure=error.toString();end=true;}
                    if(end)
                    {
                        try
                        {
                            for(Object k:keys.values())key(k,false);invoke(bus,new String[]{"unregister"},new Class<?>[]{Object.class},listener[0]);
                            var result=new LinkedHashMap<String,Object>();result.put("event",failure.isEmpty()?"COMPLETE":"FAILED");result.put("utc_ms",System.currentTimeMillis());result.put("reached_waypoints",index[0]);result.put("planned_waypoints",targets.size());result.put("actual",state(player));result.put("failure",failure);result.put("direct_position_or_ability_write",false);result.put("global_functional_pass_claimed",false);write(output,result);
                        }catch(Throwable error){throw new RuntimeException(error);}
                    }
                };
                invoke(bus,new String[]{"addListener"},new Class<?>[]{type("net.minecraftforge.eventbus.api.EventPriority"),boolean.class,Class.class,Consumer.class},priority,false,type("net.minecraftforge.event.TickEvent$ClientTickEvent"),listener[0]);
            }
            catch(Throwable error){try{write(output,Map.of("event","FAILED_BEFORE_INPUT","error",error.toString(),"utc_ms",System.currentTimeMillis(),"direct_position_or_ability_write",false));}catch(Throwable fatal){throw new RuntimeException(fatal);}}
        };
        invoke(client,new String[]{"execute","m_18707_"},new Class<?>[]{Runnable.class},start);
    }
}
