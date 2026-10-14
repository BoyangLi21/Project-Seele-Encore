import java.lang.instrument.Instrumentation;
import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;

/** Explicit native client input: normal vanilla block use or an existing UI button. */
public final class CurrentClientInputAgentV5R53
{
    private static ClassLoader loader;
    private static Class<?> type(String n) throws Exception {return Class.forName(n,true,loader);}
    private static Object invoke(Object o,String[] names,Class<?>[] sig,Object... args) throws Exception
    {for(String n:names)try{return o.getClass().getMethod(n,sig).invoke(o,args);}catch(NoSuchMethodException absent){}throw new NoSuchMethodException(Arrays.toString(names));}
    private static Object field(Object o,String... names) throws Exception
    {for(String n:names)try{return o.getClass().getField(n).get(o);}catch(NoSuchFieldException absent){}throw new NoSuchFieldException(Arrays.toString(names));}
    private static Object call(Object o,String... names) throws Exception{return invoke(o,names,new Class<?>[0]);}
    private static Map<String,Object> playerState(Object player) throws Exception
    {
        var row=new LinkedHashMap<String,Object>();
        row.put("uuid",call(player,"getUUID","m_20148_").toString());
        row.put("position",call(player,"position","m_20182_").toString());
        row.put("velocity",call(player,"getDeltaMovement","m_20184_").toString());
        row.put("yaw",call(player,"getYRot","m_146908_"));
        row.put("pitch",call(player,"getXRot","m_146909_"));
        row.put("on_ground",call(player,"onGround","m_20096_"));
        row.put("passenger",call(player,"isPassenger","m_20159_"));
        Object abilities=call(player,"getAbilities","m_150110_");
        row.put("flying",field(abilities,"flying","f_35935_"));
        return row;
    }
    private static List<Object> movementKeys(Object client) throws Exception
    {
        Object options=field(client,"options","f_91066_");var keys=new ArrayList<Object>();
        for(Field f:options.getClass().getFields())if(f.getType().getName().equals("net.minecraft.client.KeyMapping"))
        {
            Object key=f.get(options);
            if(key!=null&&List.of("key.forward","key.back","key.left","key.right","key.jump","key.sneak","key.sprint").contains(call(key,"getName","m_90860_")))keys.add(key);
        }
        if(keys.size()!=7)throw new IllegalStateException("Actual seven vanilla movement bindings required");
        return keys;
    }
    private static void key(Object key,boolean down) throws Exception
    {invoke(key,new String[]{"setDown","m_7249_"},new Class<?>[]{boolean.class},down);}
    public static void agentmain(String argument,Instrumentation instrumentation) throws Exception
    {
        String[] args=argument.split("\\|",-1);if(args.length<3)throw new IllegalArgumentException("action|output|values required");
        Path output=Path.of(args[1]).toAbsolutePath().normalize();if(Files.exists(output))throw new IllegalArgumentException("Fresh input receipt required");
        for(Path at=output;at!=null;at=at.getParent())if(Files.exists(at.resolve("level.dat"))||Files.exists(at.resolve("session.lock")))throw new IllegalArgumentException("Output inside World");
        for(Class<?> c:instrumentation.getAllLoadedClasses())if(c.getName().equals("com.projectseele.ProjectSeele")){loader=c.getClassLoader();break;}
        if(loader==null)throw new IllegalStateException("Actual mod not loaded");
        Object mc;
        try{mc=type("net.minecraft.client.Minecraft").getMethod("getInstance").invoke(null);}
        catch(NoSuchMethodException absent){mc=type("net.minecraft.client.Minecraft").getMethod("m_91087_").invoke(null);}
        final Object client=mc;
        Runnable input=()->
        {
            var report=new LinkedHashMap<String,Object>();report.put("action",args[0]);report.put("utc_ms",System.currentTimeMillis());report.put("input_submitted_not_functional_pass",true);
            try
            {
                Object player=field(client,"player","f_91074_");if(player==null)throw new IllegalStateException("Actual local player required");
                report.put("player_uuid",call(player,"getUUID","m_20148_").toString());
                if(args[0].equals("snapshot"))
                {
                    report.put("fps",call(client,"getFps","m_260875_"));
                    report.put("rigid_machinery_gpu",type("com.projectseele.client.render.RigidMachineryGpuR44").getMethod("snapshot").invoke(null).toString());
                    report.put("player",playerState(player));
                    Object screen=field(client,"screen","f_91080_");
                    report.put("screen",screen==null?"":screen.getClass().getName());
                    if(screen!=null)
                    {
                        var labels=new ArrayList<String>();
                        for(Object child:(List<?>)call(screen,"children","m_6702_"))if(type("net.minecraft.client.gui.components.Button").isInstance(child))
                            labels.add(call(call(child,"getMessage","m_93669_"),"getString","m_130150_").toString());
                        report.put("actual_button_labels",labels);
                    }
                }
                else if(args[0].equals("look")||args[0].equals("walk"))
                {
                    if(args.length<4)throw new IllegalArgumentException("look/walk|output|yaw|pitch[|milliseconds] required");
                    float yaw=Float.parseFloat(args[2]),pitch=Float.parseFloat(args[3]);
                    if(!Float.isFinite(yaw)||!Float.isFinite(pitch)||Math.abs(pitch)>90)throw new IllegalArgumentException("Finite ordinary look required");
                    report.put("before",playerState(player));
                    invoke(player,new String[]{"setYRot","m_146922_"},new Class<?>[]{float.class},yaw);
                    invoke(player,new String[]{"setXRot","m_146926_"},new Class<?>[]{float.class},pitch);
                    if(args[0].equals("walk"))
                    {
                        int millis=Integer.parseInt(args[4]);if(millis<50||millis>10000)throw new IllegalArgumentException("Bounded50..10000ms ordinary walk required");
                        if(field(client,"screen","f_91080_")!=null)throw new IllegalStateException("Close the actual screen before walking");
                        List<Object> keys=movementKeys(client);
                        for(Object binding:keys)key(binding,call(binding,"getName","m_90860_").equals("key.forward"));
                        report.put("ordinary_forward_key_duration_ms",millis);report.put("direct_position_write",false);
                        Thread release=new Thread(()->
                        {
                            try{Thread.sleep(millis);invoke(client,new String[]{"execute","m_18707_"},new Class<?>[]{Runnable.class},(Runnable)()->
                            {try{for(Object binding:keys)key(binding,false);var end=new LinkedHashMap<String,Object>();end.put("after",playerState(player));end.put("direct_position_write",false);end.put("input_submitted_not_functional_pass",true);end.put("utc_ms",System.currentTimeMillis());Object gson=type("com.google.gson.Gson").getConstructor().newInstance();Files.writeString(output.resolveSibling(output.getFileName()+".end.json"),gson.getClass().getMethod("toJson",Object.class).invoke(gson,end)+"\n");}catch(Throwable failure){throw new RuntimeException(failure);}});}
                            catch(Throwable failure){throw new RuntimeException(failure);}
                        },"SEELE-ordinary-key-release");release.setDaemon(true);release.start();
                    }
                    report.put("after_look",playerState(player));
                }
                else if(args[0].equals("close_screen"))
                {
                    Object screen=field(client,"screen","f_91080_");if(screen==null)throw new IllegalStateException("No actual screen to close");
                    invoke(screen,new String[]{"keyPressed","m_7933_"},new Class<?>[]{int.class,int.class,int.class},256,0,0);
                    report.put("ordinary_escape_key_submitted",true);
                }
                else if(args[0].equals("radio"))
                {
                    if(field(client,"screen","f_91080_")!=null)throw new IllegalStateException("Close the actual screen before pressing radio");
                    Object binding=type("com.projectseele.client.Keybinds").getField("COMMAND_RADIO").get(null);
                    Object boundKey=call(binding,"getKey");
                    Method click;
                    try{click=type("net.minecraft.client.KeyMapping").getMethod("click",type("com.mojang.blaze3d.platform.InputConstants$Key"));}
                    catch(NoSuchMethodException absent){click=type("net.minecraft.client.KeyMapping").getMethod("m_90835_",type("com.mojang.blaze3d.platform.InputConstants$Key"));}
                    click.invoke(null,boundKey);report.put("ordinary_radio_key_clicked",true);
                }
                else if(args[0].equals("stop_flying"))
                {
                    if(field(client,"screen","f_91080_")!=null)throw new IllegalStateException("Close the actual screen before ordinary flight toggle");
                    Object abilities=call(player,"getAbilities","m_150110_");
                    if(!Boolean.TRUE.equals(field(abilities,"flying","f_35935_")))throw new IllegalStateException("Actual player is already in walking mode");
                    Object jump=null;for(Object binding:movementKeys(client))if(call(binding,"getName","m_90860_").equals("key.jump"))jump=binding;
                    if(jump==null)throw new IllegalStateException("Actual jump binding required");final Object jumpKey=jump;
                    report.put("before",playerState(player));
                    for(Object binding:movementKeys(client))key(binding,false);
                    Object bus=type("net.minecraftforge.common.MinecraftForge").getField("EVENT_BUS").get(null);
                    Class<?> tick=type("net.minecraftforge.event.TickEvent$ClientTickEvent");
                    Object priority=Enum.valueOf((Class)type("net.minecraftforge.eventbus.api.EventPriority"),"LOWEST");
                    final int[] step={0};final java.util.function.Consumer<Object>[] listener=new java.util.function.Consumer[1];
                    listener[0]=event->
                    {
                        try
                        {
                            if(!field(event,"phase").toString().equals("START"))return;
                            int current=step[0]++;
                            if(current<=4)key(jumpKey,current==1||current==3);
                            else
                            {
                                invoke(bus,new String[]{"unregister"},new Class<?>[]{Object.class},listener[0]);
                                var end=new LinkedHashMap<String,Object>();end.put("after",playerState(player));
                                end.put("ordinary_double_jump_key",true);end.put("ordinary_client_tick_steps",step[0]);
                                end.put("ability_direct_write",false);end.put("utc_ms",System.currentTimeMillis());
                                Object gson=type("com.google.gson.Gson").getConstructor().newInstance();
                                Files.writeString(output.resolveSibling(output.getFileName()+".end.json"),gson.getClass().getMethod("toJson",Object.class).invoke(gson,end)+"\n");
                            }
                        }
                        catch(Throwable failure)
                        {
                            try{key(jumpKey,false);invoke(bus,new String[]{"unregister"},new Class<?>[]{Object.class},listener[0]);}catch(Throwable ignored){}
                            throw new RuntimeException(failure);
                        }
                    };
                    invoke(bus,new String[]{"addListener"},new Class<?>[]{type("net.minecraftforge.eventbus.api.EventPriority"),boolean.class,Class.class,java.util.function.Consumer.class},priority,false,tick,listener[0]);
                    report.put("ability_direct_write",false);report.put("ordinary_double_jump_key_submitted",true);
                }
                else if(args[0].equals("ui_text"))
                {
                    Object screen=field(client,"screen","f_91080_");if(screen==null)throw new IllegalStateException("No actual open native screen");
                    int index=Integer.parseInt(args[2]);var boxes=new ArrayList<Object>();
                    for(Object child:(List<?>)call(screen,"children","m_6702_"))if(type("net.minecraft.client.gui.components.EditBox").isInstance(child))boxes.add(child);
                    if(index<0||index>=boxes.size())throw new IllegalStateException("Actual text box index absent: "+index);
                    if(args[3].length()>128)throw new IllegalArgumentException("Bounded normal UI text required");
                    invoke(boxes.get(index),new String[]{"setValue","m_94144_"},new Class<?>[]{String.class},args[3]);
                    report.put("actual_text_box_count",boxes.size());report.put("edited_actual_box_index",index);report.put("value",args[3]);
                }
                else if(args[0].equals("use_block"))
                {
                    if(args.length!=6)throw new IllegalArgumentException("use_block|output|x|y|z|face required");
                    int x=Integer.parseInt(args[2]),y=Integer.parseInt(args[3]),z=Integer.parseInt(args[4]);
                    Object eye=call(player,"getEyePosition","m_146892_");Class<?> vec=type("net.minecraft.world.phys.Vec3");
                    Object hit=vec.getConstructor(double.class,double.class,double.class).newInstance(x+.5,y+.5,z+.5);
                    double distance=(double)invoke(eye,new String[]{"distanceTo","m_82554_"},new Class<?>[]{vec},hit);
                    Object gameMode=field(client,"gameMode","f_91072_");double reach=((Number)call(gameMode,"getPickRange","m_105286_")).doubleValue();
                    if(distance>reach)throw new IllegalStateException("Actual block outside current native reach: "+distance+" > "+reach);
                    Class<?> pos=type("net.minecraft.core.BlockPos"),direction=type("net.minecraft.core.Direction"),hand=type("net.minecraft.world.InteractionHand"),result=type("net.minecraft.world.phys.BlockHitResult");
                    Object block=pos.getConstructor(int.class,int.class,int.class).newInstance(x,y,z);
                    Object face=Enum.valueOf((Class)direction,args[5]);Object main=Enum.valueOf((Class)hand,"MAIN_HAND");
                    Class<?> clip=type("net.minecraft.world.level.ClipContext"),blockMode=type("net.minecraft.world.level.ClipContext$Block"),fluidMode=type("net.minecraft.world.level.ClipContext$Fluid");
                    Object context=clip.getConstructor(vec,vec,blockMode,fluidMode,type("net.minecraft.world.entity.Entity")).newInstance(eye,hit,Enum.valueOf((Class)blockMode,"OUTLINE"),Enum.valueOf((Class)fluidMode,"NONE"),player);
                    Object level=field(client,"level","f_91073_");Object blockHit=invoke(level,new String[]{"clip","m_45547_"},new Class<?>[]{clip},context);
                    if(!call(blockHit,"getBlockPos","m_82425_").equals(block)||!call(blockHit,"getType","m_6662_").toString().equals("BLOCK"))throw new IllegalStateException("Actual vanilla line of sight does not reach this block");
                    String actualFace=call(blockHit,"getDirection","m_82434_").toString();if(!actualFace.equalsIgnoreCase(args[5]))throw new IllegalStateException("Actual vanilla hit face is "+actualFace+", expected "+args[5]);
                    report.put("actual_vanilla_ray_hit",blockHit.toString());
                    report.put("native_use_result",invoke(gameMode,new String[]{"useItemOn","m_105259_"},new Class<?>[]{type("net.minecraft.client.player.LocalPlayer"),hand,result},player,main,blockHit).toString());
                    report.put("block",List.of(x,y,z));report.put("distance",distance);report.put("native_reach",reach);
                }
                else if(args[0].equals("ui_button"))
                {
                    Object screen=field(client,"screen","f_91080_");if(screen==null)throw new IllegalStateException("No actual open native screen");
                    report.put("screen",screen.getClass().getName());var labels=new ArrayList<String>();Object selected=null;
                    for(Object child:(List<?>)call(screen,"children","m_6702_"))if(type("net.minecraft.client.gui.components.Button").isInstance(child))
                    {
                        String text=call(call(child,"getMessage","m_93669_"),"getString","m_130150_").toString();labels.add(text);
                        if(text.equals(args[2])){if(selected!=null)throw new IllegalStateException("Ambiguous native button label");selected=child;}
                    }
                    report.put("actual_button_labels",labels);if(selected==null)throw new IllegalStateException("Exact native button label absent: "+args[2]);
                    if(!Boolean.TRUE.equals(field(selected,"active","f_93623_"))||!Boolean.TRUE.equals(field(selected,"visible","f_93624_")))throw new IllegalStateException("Actual native button disabled or hidden");
                    call(selected,"onPress","m_5691_");report.put("pressed_actual_button",args[2]);
                }
                else throw new IllegalArgumentException("Unsupported ordinary input");
            }
            catch(Throwable failure){while(failure instanceof InvocationTargetException&&failure.getCause()!=null)failure=failure.getCause();report.put("error",failure.toString());}
            try{Object gson=type("com.google.gson.Gson").getConstructor().newInstance();Files.createDirectories(output.getParent());Files.writeString(output,gson.getClass().getMethod("toJson",Object.class).invoke(gson,report)+"\n");}
            catch(Throwable failure){throw new RuntimeException(failure);}
        };
        invoke(mc,new String[]{"execute","m_18707_"},new Class<?>[]{Runnable.class},input);
    }
}
