import java.lang.instrument.*;
import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;

/** QA-only normal original button use. No direct light/state, grants or chunk loads. */
public final class R52PhotoRoomLightAgent {
    static ClassLoader loader;
    static Class<?> type(String name)throws Exception{return Class.forName(name,false,loader);}
    static Object call(Object o,String[] names,Class<?>[] signature,Object...args)throws Exception{
        for(var name:names)try{return o.getClass().getMethod(name,signature).invoke(o,args);}catch(NoSuchMethodException ignored){}
        throw new NoSuchMethodException(Arrays.toString(names));
    }
    static Object call(Object o,String...names)throws Exception{return call(o,names,new Class<?>[0]);}
    static Object field(Object o,String...names)throws Exception{
        for(Class<?> c=o.getClass();c!=null;c=c.getSuperclass())for(var name:names)try{var f=c.getDeclaredField(name);f.setAccessible(true);return f.get(o);}catch(NoSuchFieldException ignored){}
        throw new NoSuchFieldException(Arrays.toString(names));
    }
    static Object enumeration(String name,String constant)throws Exception{return Enum.valueOf((Class)type(name),constant);}
    static void execute(Object o,Runnable action)throws Exception{call(o,new String[]{"execute"},new Class<?>[]{Runnable.class},action);}
    static double number(Object value){double v=((Number)value).doubleValue();if(!Double.isFinite(v))throw new IllegalArgumentException("Finite source coordinate required");return v;}
    static int integer(Object value){double d=number(value);if(d!=Math.rint(d)||Math.abs(d)>30000000)throw new IllegalArgumentException("Exact bounded button coordinate required");return (int)d;}
    public static void agentmain(String arg,Instrumentation ins)throws Exception{
        var args=arg.split("\\|",-1);if(args.length!=2)throw new IllegalArgumentException("plan|output required");
        Path root=Path.of("D:/eva/artifacts/r52_fresh_from_r51_20261009/runtime_directory/candidate").toRealPath(),plan=Path.of(args[0]).toRealPath(),out=Path.of(args[1]).toAbsolutePath().normalize();
        if(!plan.startsWith(root)||!out.startsWith(root)||Files.exists(out)||!out.getParent().toRealPath().startsWith(root)||Files.size(plan)>100000)throw new IllegalArgumentException("Fresh bounded candidate-only output required");
        for(var c:ins.getAllLoadedClasses())if(c.getName().equals("com.projectseele.ProjectSeele")){loader=c.getClassLoader();break;}
        if(loader==null)throw new IllegalStateException("Actual existing client required");
        Object gson=type("com.google.gson.Gson").getConstructor().newInstance();var p=(Map<?,?>)gson.getClass().getMethod("fromJson",String.class,Class.class).invoke(gson,Files.readString(plan),Map.class);
        if(!(p.get("seele_meeting_mode")instanceof Boolean wanted)||!(p.get("seele_button")instanceof List<?> xyz)||xyz.size()!=3||!(p.get("seele_use_stand")instanceof List<?> stand)||stand.size()!=3)throw new IllegalArgumentException("Actual button, stand and explicit mode required");
        int x=integer(xyz.get(0)),y=integer(xyz.get(1)),z=integer(xyz.get(2));
        Object mc=type("net.minecraft.client.Minecraft").getMethod("m_91087_").invoke(null),server=call(mc,"getSingleplayerServer","m_91092_");
        if(server==null)throw new IllegalStateException("Actual integrated QA server required");
        UUID id=(UUID)call(field(mc,"player","f_91074_"),"getUUID","m_20148_");
        var thread=new Thread(()->{
            var report=new LinkedHashMap<String,Object>();report.put("world_source_written",false);report.put("direct_geometry_or_state_written",false);report.put("interaction_path","Actual vanilla ServerPlayerGameMode.useItemOn and original SEELE circuit");
            try{
                long deadline=System.nanoTime()+15_000_000_000L;boolean complete=false;
                while(!complete&&System.nanoTime()<deadline){
                    var done=new CompletableFuture<Boolean>();execute(server,()->{
                        try{
                            var resource=type("net.minecraft.world.level.storage.LevelResource").getField("f_78182_").get(null);
                            Path world=((Path)call(server,new String[]{"getWorldPath","m_129843_"},new Class<?>[]{type("net.minecraft.world.level.storage.LevelResource")},resource)).toRealPath();
                            if(!world.equals(Path.of("D:/eva/artifacts/r51_nonmap_release/native_r51/game/saves/SEELE_R52_REVIEW").toRealPath()))throw new IllegalStateException("Used QA only");
                            Object player=call(call(server,"getPlayerList","m_6846_"),new String[]{"getPlayer","m_11259_"},new Class<?>[]{UUID.class},id),level=call(player,"serverLevel","m_284548_");
                            Object position=call(player,"position","m_20182_");double distance=0;
                            for(int i=0;i<3;i++)distance+=Math.pow(number(field(position,new String[]{"x","y","z"}[i],new String[]{"f_82479_","f_82480_","f_82481_"}[i]))-number(stand.get(i)),2);
                            report.put("actual_stand_distance_m",Math.sqrt(distance));
                            if(distance>.25*.25||(boolean)call(player,"isSpectator","m_5833_")){done.complete(false);return;}
                            String dimension=call(call(level,"dimension","m_46472_"),"location","m_135782_").toString();
                            if(!dimension.equals("projectseele:geofront"))throw new IllegalStateException("Actual current room dimension required");
                            boolean before=(boolean)type("com.projectseele.world.SeeleLightingR48").getMethod("meetingModeR48",type("net.minecraft.server.level.ServerLevel")).invoke(null,level);report.put("before_meeting_mode",before);
                            if(before!=wanted){
                                Object at=type("net.minecraft.core.BlockPos").getConstructor(int.class,int.class,int.class).newInstance(x,y,z),target=type("net.minecraft.world.phys.Vec3").getConstructor(double.class,double.class,double.class).newInstance(x+.8,y+.5,z+.5),eye=call(player,"getEyePosition","m_146892_");
                                Object context=type("net.minecraft.world.level.ClipContext").getConstructor(type("net.minecraft.world.phys.Vec3"),type("net.minecraft.world.phys.Vec3"),type("net.minecraft.world.level.ClipContext$Block"),type("net.minecraft.world.level.ClipContext$Fluid"),type("net.minecraft.world.entity.Entity")).newInstance(eye,target,enumeration("net.minecraft.world.level.ClipContext$Block","OUTLINE"),enumeration("net.minecraft.world.level.ClipContext$Fluid","NONE"),player);
                                Object hit=call(level,new String[]{"clip","m_45547_"},new Class<?>[]{type("net.minecraft.world.level.ClipContext")},context);
                                if(!call(hit,"getBlockPos","m_82425_").equals(at))throw new IllegalStateException("Actual outline ray misses original button");
                                Object hand=enumeration("net.minecraft.world.InteractionHand","MAIN_HAND"),stack=call(player,new String[]{"getItemInHand","m_21120_"},new Class<?>[]{type("net.minecraft.world.InteractionHand")},hand);
                                Object used=call(field(player,"gameMode","f_8941_"),new String[]{"useItemOn","m_7179_"},new Class<?>[]{type("net.minecraft.server.level.ServerPlayer"),type("net.minecraft.world.level.Level"),type("net.minecraft.world.item.ItemStack"),type("net.minecraft.world.InteractionHand"),type("net.minecraft.world.phys.BlockHitResult")},player,level,stack,hand,hit);report.put("vanilla_use_result",used.toString());
                            }
                            boolean after=(boolean)type("com.projectseele.world.SeeleLightingR48").getMethod("meetingModeR48",type("net.minecraft.server.level.ServerLevel")).invoke(null,level);report.put("actual_meeting_mode",after);
                            if(after!=wanted)throw new IllegalStateException("Original permission/circuit did not reach requested mode");
                            report.put("status","PASS");done.complete(true);
                        }catch(Throwable failure){done.completeExceptionally(failure);}
                    });complete=done.get(5,TimeUnit.SECONDS);if(!complete)Thread.sleep(200);
                }
                if(!complete)throw new IllegalStateException("Actual current-room stand and non-spectator player never arrived");
            }catch(Throwable error){report.put("status","HOLD");report.put("error",error.toString());}
            try{String json=(String)gson.getClass().getMethod("toJson",Object.class).invoke(gson,report);Files.writeString(out,json+"\n");}catch(Exception error){error.printStackTrace();}
        },"r52-normal-QA-light-button");thread.setDaemon(true);thread.start();
    }
}
