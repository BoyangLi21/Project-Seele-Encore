import java.lang.instrument.Instrumentation;
import java.lang.reflect.InvocationTargetException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;

/** Generate explicitly listed terrain only in an isolated, named authoring save. */
public final class GenerateMissingSavedChunksR55
{
    private static ClassLoader loader;
    private static Class<?> type(String name) throws Exception { return Class.forName(name, false, loader); }
    private static Object call(Object owner, String names, Object... args) throws Exception
    {
        for (String name : names.split("/"))
            for (Class<?> k = owner instanceof Class<?> ? (Class<?>) owner : owner.getClass(); k != null; k = k.getSuperclass())
                for (var method : k.getDeclaredMethods())
                    if (method.getName().equals(name) && method.getParameterCount() == args.length)
                    {
                        method.setAccessible(true);
                        try { return method.invoke(owner instanceof Class<?> ? null : owner, args); }
                        catch (IllegalArgumentException wrongOverload) { }
                    }
        throw new NoSuchMethodException(names);
    }

    public static void agentmain(String argument, Instrumentation instrumentation) throws Exception
    {
        for (Class<?> c : instrumentation.getAllLoadedClasses())
            if (c.getName().equals("com.projectseele.ProjectSeele")) loader = c.getClassLoader();
        Path directory = Path.of(argument);
        Object server = call(type("net.minecraftforge.server.ServerLifecycleHooks"), "getCurrentServer");
        Class<?> resourceType = type("net.minecraft.world.level.storage.LevelResource");
        var constructor = resourceType.getDeclaredConstructor(String.class); constructor.setAccessible(true);
        Object resource = constructor.newInstance(".");
        Path actual = null;
        for (var method : server.getClass().getMethods())
            if (method.getReturnType() == Path.class && Arrays.equals(method.getParameterTypes(), new Class<?>[]{resourceType}))
                actual = ((Path) method.invoke(server, resource)).toRealPath();
        Path expected = Path.of(Files.readString(directory.resolve("server-world.txt")).strip()).toRealPath();
        if (actual == null || !actual.equals(expected) || !expected.toString().replace('\\','/').contains("/cache-server/"))
            throw new IllegalStateException("Only the explicitly named isolated cache-server save may be generated");
        Object level = null;
        for (Object candidate : (Iterable<?>) call(server, "getAllLevels/m_129785_"))
            if (String.valueOf(call(call(candidate, "dimension/m_46472_"), "location/m_135782_")).equals("projectseele:geofront")) level = candidate;
        if (level == null) throw new IllegalStateException("GeoFront is not loaded");
        Object targetLevel = level;
        Object gson = type("com.google.gson.Gson").getConstructor().newInstance();
        List<?> chunks = (List<?>) call(gson, "fromJson", Files.readString(directory.resolve("chunks.json")), List.class);
        new Thread(() -> {
            int completed = 0;
            try
            {
                for (Object value : chunks)
                {
                    List<?> pair = (List<?>) value; int x = ((Number) pair.get(0)).intValue(), z = ((Number) pair.get(1)).intValue();
                    CompletableFuture<Void> ready = new CompletableFuture<>();
                    ((Executor) server).execute(() -> {
                        try { call(targetLevel, "getChunk/m_6325_", x, z); ready.complete(null); }
                        catch (Throwable error) { ready.completeExceptionally(error); }
                    });
                    ready.get(180, TimeUnit.SECONDS); completed++;
                    if (completed % 16 == 0 || completed == chunks.size())
                        Files.writeString(directory.resolve("progress.json"), (String) call(gson, "toJson",
                            Map.of("completed", completed, "total", chunks.size(), "generated", completed == chunks.size(), "save_required", true)));
                }
                // Normal server shutdown flushes these native FULL chunks. The
                // caller then merges only originally absent chunk slots.
            }
            catch (Throwable error)
            {
                while (error instanceof InvocationTargetException && error.getCause() != null) error = error.getCause();
                try { var text = new java.io.StringWriter(); error.printStackTrace(new java.io.PrintWriter(text)); Files.writeString(directory.resolve("error.txt"), text.toString()); }
                catch (Exception ignored) { }
            }
        }, "SEELE isolated lake chunk generation").start();
    }
}
