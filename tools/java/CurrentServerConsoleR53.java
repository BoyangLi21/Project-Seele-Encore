import java.lang.instrument.Instrumentation;
import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;

/** Submits one ordinary console stop on the existing server thread after an exact World check. */
public final class CurrentServerConsoleR53
{
    private static ClassLoader loader;
    private static Class<?> type(String name) throws Exception { return Class.forName(name,true,loader); }
    private static Object invoke(Object owner,String[] names,Class<?>[] signature,Object...args) throws Exception
    {
        for(String name:names)try{return owner.getClass().getMethod(name,signature).invoke(owner,args);}catch(NoSuchMethodException absent){}
        throw new NoSuchMethodException(Arrays.toString(names));
    }
    private static Object staticField(Class<?> owner,String...names) throws Exception
    {
        for(String name:names)try{return owner.getField(name).get(null);}catch(NoSuchFieldException absent){}
        throw new NoSuchFieldException(Arrays.toString(names));
    }
    private static Path actualWorld(Object server) throws Exception
    {
        Class<?> resource=type("net.minecraft.world.level.storage.LevelResource");
        return ((Path)invoke(server,new String[]{"getWorldPath","m_129843_"},new Class<?>[]{resource},staticField(resource,"ROOT","f_78182_"))).toRealPath();
    }
    public static void agentmain(String argument,Instrumentation instrumentation) throws Exception
    {
        String[] args=argument.split("\\|",-1);
        if(args.length!=2)throw new IllegalArgumentException("exact_expected_world|fresh_external_receipt required");
        Path expected=Path.of(args[0]).toRealPath();
        Path authorized=Path.of("D:/eva/artifacts/map_complete_20261013/WORLD").toRealPath();
        if(!Files.isSameFile(expected,authorized))throw new IllegalArgumentException("Expected World differs from authorized Root World");
        Path output=Path.of(args[1]).toAbsolutePath().normalize();
        if(Files.exists(output))throw new IllegalArgumentException("Fresh external receipt required");
        for(Path p=output;p!=null;p=p.getParent())if(Files.exists(p.resolve("level.dat"))||Files.exists(p.resolve("session.lock")))throw new IllegalArgumentException("Receipt inside World");
        Files.createDirectories(output.getParent());
        if(output.getParent().toRealPath().startsWith(expected))throw new IllegalArgumentException("Resolved receipt inside World");
        for(Class<?> c:instrumentation.getAllLoadedClasses())if(c.getName().equals("com.projectseele.ProjectSeele")){loader=c.getClassLoader();break;}
        if(loader==null)throw new IllegalStateException("Actual existing Project SEELE server required");
        Object server=type("net.minecraftforge.server.ServerLifecycleHooks").getMethod("getCurrentServer").invoke(null);
        if(server==null||!Files.isSameFile(actualWorld(server),expected))throw new IllegalStateException("Actual server World mismatch");
        Object gson=type("com.google.gson.Gson").getConstructor().newInstance();Method json=gson.getClass().getMethod("toJson",Object.class);
        CompletableFuture<Void> completed=new CompletableFuture<>();
        Runnable ordinaryConsole=()->
        {
            var receipt=new LinkedHashMap<String,Object>();receipt.put("utc_ms",System.currentTimeMillis());receipt.put("pid",ProcessHandle.current().pid());
            receipt.put("thread",Thread.currentThread().getName());receipt.put("command","stop");receipt.put("expected_world",expected.toString());
            receipt.put("direct_state_actor_or_world_edit",false);receipt.put("direct_halt_or_force_kill",false);
            try
            {
                Path actual=actualWorld(server);receipt.put("actual_server_world",actual.toString());
                if(!Files.isSameFile(actual,expected))throw new IllegalStateException("Server-thread actual World mismatch");
                Object source=invoke(server,new String[]{"createCommandSourceStack","m_129893_"},new Class<?>[]{});
                Object commands=invoke(server,new String[]{"getCommands","m_129892_"},new Class<?>[]{});
                int result=((Number)invoke(commands,new String[]{"performPrefixedCommand","m_230957_"},new Class<?>[]{type("net.minecraft.commands.CommandSourceStack"),String.class},source,"stop")).intValue();
                receipt.put("command_result",result);receipt.put("state","ORDINARY_CONSOLE_STOP_SUBMITTED");
                receipt.put("shutdown_complete_claimed",false);
                Files.writeString(output,json.invoke(gson,receipt)+"\n",StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE);completed.complete(null);
            }
            catch(Throwable failure)
            {
                while(failure instanceof InvocationTargetException&&failure.getCause()!=null)failure=failure.getCause();
                receipt.put("state","FAILED");receipt.put("error",failure.toString());
                try{Files.writeString(output,json.invoke(gson,receipt)+"\n",StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE);}catch(Throwable ignored){}
                completed.completeExceptionally(failure);
            }
        };
        invoke(server,new String[]{"execute","m_18707_"},new Class<?>[]{Runnable.class},ordinaryConsole);
        completed.get(30,TimeUnit.SECONDS);
    }
}
