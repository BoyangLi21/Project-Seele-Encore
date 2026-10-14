import java.lang.instrument.Instrumentation;
import java.lang.reflect.*;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import java.util.concurrent.*;

/** Observe only existing loaded chunks on the server thread. Never load chunks,
 * move actors, operate devices, allocate SavedData, or claim actual traversal. */
public final class NamedPersonnelReadOnlyAgentR53
{
    private static ClassLoader loader;
    private static Object gson, context;
    private static Method json;
    private static Class<?> type(String name) throws Exception
    {
        return Class.forName(name, false, loader);
    }
    private static Object invoke(Object target, String[] names, Class<?>[] signature, Object... args) throws Exception
    {
        for (String name : names)
        {
            try { return target.getClass().getMethod(name, signature).invoke(target, args); }
            catch (NoSuchMethodException absent) { }
        }
        throw new NoSuchMethodException(Arrays.toString(names));
    }
    private static Object zero(Object target, String... names) throws Exception
    {
        return invoke(target, names, new Class<?>[0]);
    }
    private static Object field(Class<?> owner, String... names) throws Exception
    {
        for (String name : names)
        {
            try { return owner.getField(name).get(null); }
            catch (NoSuchFieldException absent) { }
        }
        throw new NoSuchFieldException(Arrays.toString(names));
    }
    private static double coordinate(Object object, String name, String srg) throws Exception
    {
        try { return object.getClass().getField(name).getDouble(object); }
        catch (NoSuchFieldException absent) { return object.getClass().getField(srg).getDouble(object); }
    }
    private static String sha(byte[] bytes) throws Exception
    {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
    }
    @SuppressWarnings("unchecked")
    private static Map<String, Object> read(Path path) throws Exception
    {
        return (Map<String, Object>) gson.getClass().getMethod("fromJson", String.class, Class.class)
            .invoke(gson, Files.readString(path), Map.class);
    }
    @SuppressWarnings("unchecked")
    private static List<Map<String, Object>> rows(Map<String, Object> plan, String key)
    {
        return (List<Map<String, Object>>) plan.get(key);
    }
    private static double number(Map<String, Object> row, String key)
    {
        return ((Number) row.get(key)).doubleValue();
    }
    private static double[] point(Map<String, Object> row, String key)
    {
        List<?> values = (List<?>) row.get(key);
        return values.stream().mapToDouble(v -> ((Number) v).doubleValue()).toArray();
    }
    private static Object pos(int x, int y, int z) throws Exception
    {
        return type("net.minecraft.core.BlockPos").getConstructor(int.class, int.class, int.class).newInstance(x, y, z);
    }
    private static Object vector(double x, double y, double z) throws Exception
    {
        return type("net.minecraft.world.phys.Vec3").getConstructor(double.class, double.class, double.class).newInstance(x, y, z);
    }
    private static Object block(Object level, Object p) throws Exception
    {
        return invoke(level, new String[]{"getBlockState", "m_8055_"}, new Class<?>[]{type("net.minecraft.core.BlockPos")}, p);
    }
    private static String canonical(Object state)
    {
        return state.toString().replaceFirst("^Block\\{([^}]+)\\}", "$1");
    }
    private static Object shape(Object state, Object level, Object p) throws Exception
    {
        return invoke(state, new String[]{"getCollisionShape", "m_60742_"},
            new Class<?>[]{type("net.minecraft.world.level.BlockGetter"), type("net.minecraft.core.BlockPos"), type("net.minecraft.world.phys.shapes.CollisionContext")}, level, p, context);
    }
    private static boolean loaded(Object level, int x0, int z0, int x1, int z1) throws Exception
    {
        Object source = zero(level, "getChunkSource", "m_7726_");
        for (int x = x0 >> 4; x <= (x1 >> 4); x++)
        {
            for (int z = z0 >> 4; z <= (z1 >> 4); z++)
            {
                if (invoke(source, new String[]{"getChunkNow", "m_7131_"}, new Class<?>[]{int.class, int.class}, x, z) == null) return false;
            }
        }
        return true;
    }
    private static boolean overlaps(Object box, int x, int y, int z, double[] body) throws Exception
    {
        return coordinate(box, "minX", "f_82288_") + x < body[3] - 1e-7 && coordinate(box, "maxX", "f_82291_") + x > body[0] + 1e-7
            && coordinate(box, "minY", "f_82289_") + y < body[4] - 1e-7 && coordinate(box, "maxY", "f_82292_") + y > body[1] + 1e-7
            && coordinate(box, "minZ", "f_82290_") + z < body[5] - 1e-7 && coordinate(box, "maxZ", "f_82293_") + z > body[2] + 1e-7;
    }
    @SuppressWarnings({"unchecked", "rawtypes"})
    private static Map<String, Object> body(Object level, Map<String, Object> row) throws Exception
    {
        double[] feet = point(row, "feet");
        double r = number(row, "body_radius"), h = number(row, "body_height");
        double[] bounds = {feet[0] - r, feet[1] + 1e-7, feet[2] - r, feet[0] + r, feet[1] + h, feet[2] + r};
        var out = new LinkedHashMap<String, Object>(); out.put("id", row.get("id")); out.put("feet", feet); out.put("roles", row.get("roles")); out.put("condition", row.get("condition"));
        int x0 = (int) Math.floor(bounds[0]) - 1, x1 = (int) Math.floor(bounds[3]) + 1;
        int z0 = (int) Math.floor(bounds[2]) - 1, z1 = (int) Math.floor(bounds[5]) + 1;
        if (!loaded(level, x0, z0, x1, z1)) { out.put("status", "NOT_LOADED"); return out; }
        var collisions = new ArrayList<Map<String, Object>>();
        for (int x = x0; x <= x1; x++) for (int y = (int) Math.floor(bounds[1]) - 1; y <= (int) Math.floor(bounds[4]); y++) for (int z = z0; z <= z1; z++)
        {
            Object p = pos(x, y, z), state = block(level, p);
            for (Object box : (List<?>) zero(shape(state, level, p), "toAabbs", "m_83299_"))
            {
                if (overlaps(box, x, y, z, bounds)) collisions.add(Map.of("pos", List.of(x, y, z), "state", canonical(state), "local_aabb", box.toString()));
            }
        }
        out.put("body_clear", collisions.isEmpty()); out.put("collisions", collisions);
        Map<String, Object> rays = (Map<String, Object>) row.get("floor9rays");
        double from = feet[1] + number(rays, "ray_from_y_offset"), to = feet[1] + number(rays, "ray_to_y_offset");
        double maximum = number(rays, "max_drop"); boolean support = true;
        var hits = new ArrayList<Map<String, Object>>();
        Class<?> clip = type("net.minecraft.world.level.ClipContext"), v = type("net.minecraft.world.phys.Vec3");
        Object collider = Enum.valueOf((Class) type("net.minecraft.world.level.ClipContext$Block"), "COLLIDER");
        Object none = Enum.valueOf((Class) type("net.minecraft.world.level.ClipContext$Fluid"), "NONE");
        for (Object ox : (List<?>) rays.get("offset_xz")) for (Object oz : (List<?>) rays.get("offset_xz"))
        {
            double dx = ((Number) ox).doubleValue(), dz = ((Number) oz).doubleValue();
            Object nativeRay = clip.getConstructor(v, v, collider.getClass(), none.getClass(), type("net.minecraft.world.entity.Entity"))
                .newInstance(vector(feet[0] + dx, from, feet[2] + dz), vector(feet[0] + dx, to, feet[2] + dz), collider, none, null);
            Object hit = invoke(level, new String[]{"clip", "m_45547_"}, new Class<?>[]{clip}, nativeRay);
            var ray = new LinkedHashMap<String, Object>(); ray.put("offset", List.of(dx, dz));
            String result = zero(hit, "getType", "m_6662_").toString(); ray.put("hit_type", result);
            boolean valid = false;
            if (result.equals("BLOCK"))
            {
                Object location = zero(hit, "getLocation", "m_82450_");
                double y = coordinate(location, "y", "f_82480_");
                String face = zero(hit, "getDirection", "m_82434_").toString();
                double drop = feet[1] - y;
                valid = face.equalsIgnoreCase("UP") && drop >= -0.020001 && drop <= maximum + 1e-7;
                ray.put("block_pos", zero(hit, "getBlockPos", "m_82425_").toString()); ray.put("hit_y", y); ray.put("face", face); ray.put("drop", drop);
            }
            ray.put("support_valid", valid); support &= valid; hits.add(ray);
        }
        out.put("floor9rays", hits); out.put("all9_supported", support);
        boolean geometry = collisions.isEmpty() == Boolean.TRUE.equals(row.get("expected_body_clear")) && support;
        out.put("status", geometry ? "GEOMETRY_MATCH" : "GEOMETRY_MISMATCH");
        out.put("actual_traversal_verified", false); return out;
    }
    private static Map<String, Object> barrier(Object level, Map<String, Object> row) throws Exception
    {
        double[] q = point(row, "pos"); int x = (int) q[0], y = (int) q[1], z = (int) q[2];
        var out = new LinkedHashMap<String, Object>(); out.put("pos", row.get("pos")); out.put("role", row.get("role"));
        if (!loaded(level, x - 1, z - 1, x + 1, z + 1)) { out.put("status", "NOT_LOADED"); return out; }
        Object p = pos(x, y, z), state = block(level, p), collision = shape(state, level, p);
        boolean nonempty = !Boolean.TRUE.equals(zero(collision, "isEmpty", "m_83281_"));
        out.put("state", canonical(state)); out.put("collision_aabbs", zero(collision, "toAabbs", "m_83299_").toString());
        out.put("status", nonempty && canonical(state).equals(row.get("expected_state")) ? "GEOMETRY_MATCH" : "GEOMETRY_MISMATCH");
        out.put("not_an_entry_or_walk_target", true); return out;
    }
    private static Object nbtField(Object tag, String name, Object expected) throws Exception
    {
        for (String part : name.split("\\."))
        {
            if (!part.equals(name.substring(name.lastIndexOf('.') + 1)))
            {
                tag = invoke(tag, new String[]{"getCompound", "m_128469_"}, new Class<?>[]{String.class}, part);
            }
        }
        String last = name.substring(name.lastIndexOf('.') + 1);
        if (!Boolean.TRUE.equals(invoke(tag, new String[]{"contains", "m_128441_"}, new Class<?>[]{String.class}, last))) return null;
        if (expected instanceof Boolean) return invoke(tag, new String[]{"getBoolean", "m_128471_"}, new Class<?>[]{String.class}, last);
        if (expected instanceof Number) return invoke(tag, new String[]{"getLong", "m_128454_"}, new Class<?>[]{String.class}, last);
        return invoke(tag, new String[]{"getString", "m_128461_"}, new Class<?>[]{String.class}, last);
    }
    @SuppressWarnings("unchecked")
    private static Map<String, Object> blockEntity(Object level, Map<String, Object> row) throws Exception
    {
        double[] q = point(row, "pos"); int x = (int) q[0], y = (int) q[1], z = (int) q[2];
        var out = new LinkedHashMap<String, Object>(); out.put("pos", row.get("pos")); out.put("role", row.get("role"));
        if (!loaded(level, x, z, x, z)) { out.put("status", "NOT_LOADED"); return out; }
        Object p = pos(x, y, z), actual = invoke(level, new String[]{"getBlockEntity", "m_7702_"}, new Class<?>[]{type("net.minecraft.core.BlockPos")}, p);
        out.put("state", canonical(block(level, p)));
        if (actual == null) { out.put("status", "MISSING_BE"); return out; }
        Object tag = zero(actual, "saveWithFullMetadata", "m_187480_"); out.put("native_nbt", tag.toString());
        boolean match = true;
        if (row.get("expected_state") != null) match &= out.get("state").equals(row.get("expected_state"));
        if (row.get("expected_id") != null) match &= row.get("expected_id").equals(nbtField(tag, "id", row.get("expected_id")));
        var observed = new LinkedHashMap<String, Object>();
        if (row.get("expected_fields") instanceof Map)
        {
            for (var e : ((Map<String, Object>) row.get("expected_fields")).entrySet())
            {
                Object value = nbtField(tag, e.getKey(), e.getValue()); observed.put(e.getKey(), value);
                match &= value instanceof Number && e.getValue() instanceof Number ? ((Number) value).longValue() == ((Number) e.getValue()).longValue() : Objects.equals(value, e.getValue());
            }
        }
        out.put("observed_fields", observed);
        if (row.get("expected_complete_nbt") != null)
        {
            Object expected = null; Class<?> parser = type("net.minecraft.nbt.TagParser");
            for (String name : List.of("parseTag", "m_129359_"))
            {
                try { expected = parser.getMethod(name, String.class).invoke(null, row.get("expected_complete_nbt")); break; }
                catch (NoSuchMethodException absent) { }
            }
            if (expected == null) throw new NoSuchMethodException("Native TagParser.parseTag");
            boolean exact = tag.equals(expected); out.put("complete_nbt_equal_at_observation", exact); match &= exact;
        }
        out.put("status", match ? "BE_MATCH" : "BE_MISMATCH"); return out;
    }
    private static Throwable cause(Throwable error)
    {
        while (error instanceof InvocationTargetException && error.getCause() != null) error = error.getCause();
        return error;
    }
    private static void append(Path output, Object row) throws Exception
    {
        Files.writeString(output, json.invoke(gson, row) + "\n", StandardOpenOption.CREATE, StandardOpenOption.APPEND);
    }
    public static void agentmain(String argument, Instrumentation instrumentation) throws Exception
    {
        String[] args = argument.split("\\|", -1);
        if (args.length != 4) throw new IllegalArgumentException("plan|freshOutputDirectory|actualLiveWorldPath|groupPrefix required");
        Path planPath = Path.of(args[0]).toRealPath(), output = Path.of(args[1]).toAbsolutePath().normalize(), allowedWorld = Path.of(args[2]).toRealPath();
        if (Files.exists(output)) throw new IllegalArgumentException("Fresh output directory required");
        for (Path at = output; at != null; at = at.getParent())
        {
            if (Files.exists(at.resolve("level.dat")) || Files.exists(at.resolve("session.lock"))) throw new IllegalArgumentException("Output cannot be inside World");
            if (Files.isSymbolicLink(at)) throw new IllegalArgumentException("Output cannot redirect through a link");
        }
        for (Class<?> c : instrumentation.getAllLoadedClasses()) if (c.getName().equals("com.projectseele.ProjectSeele")) { loader = c.getClassLoader(); break; }
        if (loader == null) throw new IllegalStateException("Root's actual mod must already be loaded");
        gson = type("com.google.gson.Gson").getConstructor().newInstance(); json = gson.getClass().getMethod("toJson", Object.class);
        Map<String, Object> plan = read(planPath);
        if (!"projectseele.r53.named-personnel-native-sampling.v1".equals(plan.get("schema"))) throw new IllegalArgumentException("Exact named sampling plan required");
        Object server = type("net.minecraftforge.server.ServerLifecycleHooks").getMethod("getCurrentServer").invoke(null);
        if (server == null) throw new IllegalStateException("Attach to Root's existing actual server only");
        Class<?> resource = type("net.minecraft.world.level.storage.LevelResource");
        Path actualWorld = ((Path) invoke(server, new String[]{"getWorldPath", "m_129843_"}, new Class<?>[]{resource}, field(resource, "ROOT", "f_78182_"))).toRealPath();
        if (!actualWorld.equals(allowedWorld)) throw new IllegalStateException("Explicit actual World path does not match running server");
        if (!sha(Files.readAllBytes(actualWorld.resolve("nerv_routes_r24.json.gz"))).equals(plan.get("navigation_sha256"))) throw new IllegalStateException("Live navigation differs from plan");
        if (!sha(Files.readAllBytes(actualWorld.resolve("personnel_lifts_r52.json"))).equals(plan.get("personnel_manifest_sha256"))) throw new IllegalStateException("Live lift manifest differs from plan");
        context = null;
        for (String name : List.of("empty", "m_82749_"))
        {
            try { context = type("net.minecraft.world.phys.shapes.CollisionContext").getMethod(name).invoke(null); break; }
            catch (NoSuchMethodException absent) { }
        }
        if (context == null) throw new NoSuchMethodException("Native CollisionContext.empty");
        Object level = null;
        for (Object candidate : (Iterable<?>) zero(server, "getAllLevels", "m_129785_"))
        {
            if (zero(candidate, "dimension", "m_46472_").toString().contains(plan.get("dimension").toString())) level = candidate;
        }
        if (level == null) throw new IllegalStateException("Named dimension is not actually loaded");
        final Object nativeLevel = level;
        var selected = new ArrayList<Map<String, Object>>();
        for (Map<String, Object> row : rows(plan, "body_probes"))
        {
            boolean include = args[3].equals("-");
            for (Object role : (List<?>) row.get("roles")) include |= role.toString().startsWith(args[3]);
            if (include) selected.add(row);
        }
        if (selected.isEmpty()) throw new IllegalArgumentException("No named point matches group prefix");
        Files.createDirectories(output);
        var header = new LinkedHashMap<String, Object>(); header.put("world_written", false); header.put("actual_world", actualWorld.toString()); header.put("plan_sha256", sha(Files.readAllBytes(planPath))); header.put("navigation_sha256", plan.get("navigation_sha256")); header.put("directory_fingerprint", plan.get("directory_fingerprint")); header.put("selected_body_points", selected.size()); header.put("group_prefix", args[3]); header.put("actual_traversal_verified", false); header.put("chunk_loading_allowed", false);
        append(output.resolve("HEADER.jsonl"), header);
        Thread worker = new Thread(() ->
        {
            var counts = new LinkedHashMap<String, Integer>(); long start = System.currentTimeMillis();
            var work = new ArrayList<Map.Entry<String, Map<String, Object>>>();
            for (Map<String, Object> row : selected) work.add(Map.entry("body", row));
            for (Map<String, Object> row : rows(plan, "barrier_probes")) if (args[3].equals("-") || row.get("role").toString().startsWith(args[3]) || args[3].startsWith("pyramid/")) work.add(Map.entry("barrier", row));
            for (Map<String, Object> row : rows(plan, "block_entity_probes")) work.add(Map.entry("be", row));
            try
            {
                for (int from = 0; from < work.size(); from += 32)
                {
                    if (Files.exists(output.resolve("STOP"))) break;
                    int low = from, high = Math.min(work.size(), from + 32); var done = new CompletableFuture<Void>();
                    Runnable capture = () ->
                    {
                        try
                        {
                            for (int i = low; i < high; i++)
                            {
                                var entry = work.get(i); Map<String, Object> result;
                                try { result = switch (entry.getKey()) { case "body" -> body(nativeLevel, entry.getValue()); case "barrier" -> barrier(nativeLevel, entry.getValue()); default -> blockEntity(nativeLevel, entry.getValue()); }; }
                                catch (Throwable error) { result = Map.of("status", "ERROR", "error", cause(error).toString(), "input", entry.getValue()); }
                                result = new LinkedHashMap<>(result); result.put("utc_ms", System.currentTimeMillis());
                                counts.merge(entry.getKey() + "/" + result.get("status"), 1, Integer::sum);
                                append(output.resolve(entry.getKey() + ".jsonl"), result);
                            }
                            done.complete(null);
                        }
                        catch (Throwable error) { done.completeExceptionally(error); }
                    };
                    invoke(server, new String[]{"execute", "m_18707_"}, new Class<?>[]{Runnable.class}, capture); done.get(30, TimeUnit.SECONDS); Thread.sleep(50);
                }
            }
            catch (Throwable error) { try { append(output.resolve("ERROR.jsonl"), Map.of("error", cause(error).toString())); } catch (Exception ignored) { } }
            try
            {
                var summary = new LinkedHashMap<String, Object>(); summary.put("world_written", false); summary.put("actual_traversal_verified", false); summary.put("counts", counts); summary.put("elapsed_ms", System.currentTimeMillis() - start); summary.put("required_work_items", work.size()); summary.put("completed_work_items", counts.values().stream().mapToInt(Integer::intValue).sum()); summary.put("geometry_measurement_only", true); summary.put("unloaded_or_condition_mismatch_requires_actual_reobservation", true);
                append(output.resolve("SUMMARY.jsonl"), summary);
            }
            catch (Exception ignored) { }
        }, "SEELE-named-personnel-readonly-probe");
        worker.setDaemon(true); worker.start();
    }
}
