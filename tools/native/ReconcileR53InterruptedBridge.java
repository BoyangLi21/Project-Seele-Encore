import java.lang.instrument.Instrumentation;
import java.lang.reflect.Method;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Collection;
import java.util.Map;

/** One-shot repair of the witnessed Unit 00 interrupted save; never a runtime fallback. */
public final class ReconcileR53InterruptedBridge
{
    private static ClassLoader loader;
    private static Class<?> type(String name) throws Exception { return Class.forName(name, false, loader); }
    private static Object field(Object value, String name) throws Exception
    {
        Class<?> cls = value instanceof Class<?> c ? c : value.getClass();
        var field = cls.getDeclaredField(name); field.setAccessible(true);
        return field.get(value instanceof Class<?> ? null : value);
    }
    private static Object call(Object value, String names, Object... args) throws Exception
    {
        for (String name : names.split("/"))
            for (Class<?> cls = value instanceof Class<?> c ? c : value.getClass(); cls != null; cls = cls.getSuperclass())
                for (Method method : cls.getDeclaredMethods())
                    if (method.getName().equals(name) && method.getParameterCount() == args.length)
                    {
                        method.setAccessible(true);
                        try { return method.invoke(value instanceof Class<?> ? null : value, args); }
                        catch (IllegalArgumentException wrongOverload) { }
                    }
        throw new NoSuchMethodException(names);
    }
    private static void require(boolean condition, String message)
    { if (!condition) throw new IllegalStateException(message); }
    public static void agentmain(String output, Instrumentation instrumentation) throws Exception
    {
        Path report = Path.of(output);
        require(!Files.exists(report), "Fresh repair receipt required");
        for (Class<?> cls : instrumentation.getAllLoadedClasses())
            if (cls.getName().equals("com.projectseele.ProjectSeele")) loader = cls.getClassLoader();
        Object server = call(type("net.minecraftforge.server.ServerLifecycleHooks"), "getCurrentServer");
        call(server, "execute/m_18707_", (Runnable) () -> {
            try
            {
                Object level = null;
                for (Object candidate : (Iterable<?>) call(server, "getAllLevels/m_129785_"))
                    if (call(candidate, "dimension/m_46472_").toString().contains("projectseele:geofront")) level = candidate;
                Object controller = ((Map<?, ?>) field(type("com.projectseele.world.NervRouteRuntimeR52"), "LIVE")).get(level);
                Object owner = field(controller, "owner"), saved = field(controller, "saved");
                Object plant = ((Map<?, ?>) field(owner, "units")).get(0), job = null;
                require(call(plant, "eva").toString().equals("fbe61635-4d0e-42e7-b3d4-f08cf2061f74"), "Original EVA differs");
                for (Object candidate : (Collection<?>) call(saved, "jobs"))
                    if ((Integer) call(call(call(candidate, "snapshot"), "original"), "variant") == 0) job = candidate;
                Object snapshot = call(job, "snapshot"), data = call(job, "ownerData");
                require(call(job, "phase").toString().equals("FINISHING")
                        && call(snapshot, "route").equals("unit0/recovery/1")
                        && ((Number) call(snapshot, "fraction")).doubleValue() == 1, "Recovery has not reached its bay");
                require(call(data, "getString/m_128461_", "Finish").equals("BRIDGE")
                        && (Integer) call(data, "getInt/m_128451_", "FilledLayers") == 44
                        && (Integer) call(data, "getInt/m_128451_", "BridgeAmount") == 0, "Witnessed phase differs");
                require((Boolean) call(owner, "savedBridgeProvenance", data, field(owner, "epoch"),
                        call(field(owner, "directory"), "fingerprint")), "Saved bridge ownership differs");
                for (int amount = 0; amount <= 9; amount++)
                    require((Boolean) call(owner, "bridgeMatches", level, plant, amount) == (amount == 9), "Actual full bridge differs");
                Object before = call(data, "copy/m_6426_");
                Files.writeString(Path.of(output + ".before.snbt"), before.toString());
                call(owner, "rememberBridge", data, 9);
                Object inverse = call(data, "copy/m_6426_");
                call(inverse, "putInt/m_128405_", "BridgeAmount", 0);
                require(inverse.equals(before), "Unexpected change outside BridgeAmount");
                call(saved, "setDirty/m_77762_");
                Files.writeString(report, "Original bridge matches complete state 9; BridgeAmount 0 -> 9. No blocks, actors, task phases or clocks changed.");
            }
            catch (Throwable error)
            {
                try { Files.writeString(report, "REJECTED: " + error); } catch (Exception ignored) { }
                error.printStackTrace();
            }
        });
    }
}
