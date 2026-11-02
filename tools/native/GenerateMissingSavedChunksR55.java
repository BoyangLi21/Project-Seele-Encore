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
        Map<?,?> plan = (Map<?,?>) call(gson, "fromJson", Files.readString(directory.resolve("plan.json")), Map.class);
        if (chunks.isEmpty() || chunks.size() > 65536 || new HashSet<>(chunks).size() != chunks.size())
            throw new IllegalArgumentException("A finite, nonempty set of distinct source chunks is required");
        if (!chunks.equals(plan.get("chunks")))
            throw new IllegalArgumentException("Native target list differs from the reviewed plan");
        for (Object value : chunks)
        {
            if (!(value instanceof List<?> pair) || pair.size() != 2)
                throw new IllegalArgumentException("Invalid native target coordinate");
            for (Object coordinate : pair)
                if (!(coordinate instanceof Number number) || !Double.isFinite(number.doubleValue())
                        || number.doubleValue() != number.intValue() || Math.abs(number.longValue()) > 1874999)
                    throw new IllegalArgumentException("Native target coordinates must be bounded integers");
        }
        if (((Number) call(targetLevel, "getSeed/m_7328_")).longValue()
                != Long.parseLong(Files.readString(directory.resolve("seed.txt")).strip()))
            throw new IllegalStateException("Authoring seed differs from the actual save");
        Object generator = call(call(targetLevel, "getChunkSource/m_7726_"), "getGenerator/m_8481_");
        if (!generator.getClass().getName().equals("com.projectseele.world.GeoFrontBoundedChunkGenerator"))
            throw new IllegalStateException("Unexpected native terrain generator");
        var bindings = type("com.projectseele.world.CityRigidGenerationR45").getDeclaredField("BINDINGS");
        bindings.setAccessible(true);
        Object binding = ((Map<?,?>) bindings.get(null)).get(generator);
        if (binding == null || !call(binding, "world").equals(plan.get("world_uuid")))
            throw new IllegalStateException("Actual future-generation authority is not bound");
        for (String name : List.of("hakone_surface.bin.gz", "hakone_surface_blend.bin.gz"))
            try (var input = loader.getResourceAsStream("data/projectseele/worldgen/" + name))
            {
                if (input == null || !Arrays.equals(input.readAllBytes(), Files.readAllBytes(directory.resolve("terrain-inputs").resolve(name))))
                    throw new IllegalStateException("Native generator has different terrain input: " + name);
            }
        Object players = call(server, "getPlayerList/m_6846_");
        if (((Number) call(players, "getPlayerCount/m_11309_")).intValue() != 0)
            throw new IllegalStateException("Isolated generation requires zero connected players");
        Map<String,Object> preflight = new LinkedHashMap<>();
        preflight.put("cache_only", true);
        preflight.put("cache_world", expected.toString());
        preflight.put("seed_matches", true);
        preflight.put("seed", Files.readString(directory.resolve("seed.txt")).strip());
        preflight.put("terrain_matches", true);
        preflight.put("generator", generator.getClass().getName());
        preflight.put("recipe_directory", String.valueOf(call(binding, "recipe")));
        preflight.put("world_uuid", plan.get("world_uuid"));
        preflight.put("requested_chunks", chunks.size());
        preflight.put("pid", ProcessHandle.current().pid());
        Files.writeString(directory.resolve("native-preflight.json"), (String) call(gson, "toJson", preflight));
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
                // caller then merges only these exact originally unfinished
                // slots, after comparing their full original saved payloads.
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
