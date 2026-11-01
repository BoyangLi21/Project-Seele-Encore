import java.lang.instrument.*;
import java.nio.file.*;
import java.lang.reflect.*;
import java.util.*;

/** Use exported saved columns as the only new LOD input in the isolated cache JVM. */
public final class IsolateCacheLodInputR55 {
    static Object call(Object target, String names, Object... args) throws Exception {
        Class<?> type = target instanceof Class<?> c ? c : target.getClass();
        for (String name : names.split("/")) for (Method method : type.getMethods())
            if (method.getName().equals(name) && method.getParameterCount() == args.length)
                try { return method.invoke(target instanceof Class<?> ? null : target, args); }
                catch (IllegalArgumentException mismatch) {}
        throw new NoSuchMethodException(names);
    }
    public static void agentmain(String output, Instrumentation instrumentation) throws Exception {
        Class<?> shared = null, project = null;
        for (Class<?> type : instrumentation.getAllLoadedClasses()) {
            if (type.getName().equals("com.projectseele.ProjectSeele")) project = type;
            if (type.getName().equals("com.seibel.distanthorizons.core.api.internal.SharedApi")) shared = type;
        }
        if (project == null || shared == null) throw new IllegalStateException("Cache provider not ready");
        ClassLoader loader = project.getClassLoader();
        Object server = call(Class.forName("net.minecraftforge.server.ServerLifecycleHooks", true, loader), "getCurrentServer");
        Class<?> resource = Class.forName("net.minecraft.world.level.storage.LevelResource", true, loader);
        Object root;
        try { root = resource.getField("ROOT").get(null); }
        catch (NoSuchFieldException mapped) { root = resource.getField("f_78182_").get(null); }
        Path actual = ((Path)call(server, "getWorldPath/m_129843_", root)).toRealPath();
        Path allowed = Path.of("F:/eva/artifacts/r55_map_20261029/cache-server/SEELE_R53_WORLD").toRealPath();
        if (!Files.isSameFile(actual, allowed)) throw new IllegalStateException("Only the isolated cache world is allowed");
        Object players = call(server, "getPlayerList/m_6846_");
        if (((Number)call(players, "getPlayerCount/m_11309_")).intValue() != 0)
            throw new IllegalStateException("Cache server must have no players");
        Path receipt = Path.of(output).toAbsolutePath().normalize();
        if (receipt.startsWith(allowed) || Files.exists(receipt)) throw new IllegalArgumentException("Fresh external receipt required");
        Class<?> readerType = Class.forName("org.objectweb.asm.ClassReader", true, loader);
        Class<?> nodeType = Class.forName("org.objectweb.asm.tree.ClassNode", true, loader);
        Class<?> writerType = Class.forName("org.objectweb.asm.ClassWriter", true, loader);
        byte[] original;
        try (var stream = shared.getResourceAsStream("SharedApi.class")) { original = stream.readAllBytes(); }
        Object reader = readerType.getConstructor(byte[].class).newInstance((Object)original);
        Object node = nodeType.getConstructor().newInstance();
        call(reader, "accept", node, 0);
        int changed = 0;
        for (Object method : (List<?>)nodeType.getField("methods").get(node)) {
            Class<?> mt = method.getClass();
            String name = (String)mt.getField("name").get(method);
            String descriptor = (String)mt.getField("desc").get(method);
            if (!Set.of("chunkLoadEvent", "chunkBlockChangedEvent").contains(name)) continue;
            if (!descriptor.equals("(Lcom/seibel/distanthorizons/core/wrapperInterfaces/chunk/IChunkWrapper;Lcom/seibel/distanthorizons/core/wrapperInterfaces/world/ILevelWrapper;)V"))
                throw new IllegalStateException("Unexpected DH event signature");
            Object instructions = mt.getField("instructions").get(method);
            call(instructions, "clear");
            Object ret = Class.forName("org.objectweb.asm.tree.InsnNode", true, loader).getConstructor(int.class).newInstance(177);
            call(instructions, "add", ret);
            ((List<?>)mt.getField("tryCatchBlocks").get(method)).clear();
            mt.getField("localVariables").set(method, null);
            mt.getField("visibleLocalVariableAnnotations").set(method, null);
            mt.getField("invisibleLocalVariableAnnotations").set(method, null);
            mt.getField("maxStack").setInt(method, 0);
            mt.getField("maxLocals").setInt(method, 3);
            changed++;
        }
        if (changed != 2) throw new IllegalStateException("Expected exactly two event adapters");
        Object writer = writerType.getConstructor(int.class).newInstance(0);
        call(node, "accept", writer);
        instrumentation.redefineClasses(new ClassDefinition(shared, (byte[])call(writer, "toByteArray")));
        call(shared.getField("INSTANCE").get(null), "clearQueuedChunkUpdates");
        Files.writeString(receipt, "{\"cache_only\":true,\"saved_columns_only\":true,\"event_adapters_disabled\":2,\"disk_mods_changed\":false,\"world_blocks_written\":false}\n", StandardOpenOption.CREATE_NEW);
    }
}
