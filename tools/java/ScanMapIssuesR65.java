import java.io.BufferedWriter;
import java.io.ByteArrayInputStream;
import java.io.DataInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.RandomAccessFile;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.atomic.AtomicLong;
import java.util.zip.GZIPInputStream;
import java.util.zip.InflaterInputStream;

/**
 * Whole-map scans of a cold copy of a world's region files (R65 feedback 2: items 32 ticket machines facing the wrong
 * way, 33 stairs without headroom, 29 dark walkable places). Reads only.
 *
 * java -Xmx10g tools/java/ScanMapIssuesR65.java <mode> <region dir> <out dir> [--threads 6] [--y0 -1344] [--y1 320]
 *   mode survey : block counts (MTR blocks, stairs, light sources), light data presence
 *   mode scan   : the three issue lists (machines.tsv, stairs.tsv, dark.tsv) and a summary
 */
public final class ScanMapIssuesR65
{
    // ------------------------------------------------------------------ NBT and Anvil

    static Object readTag(DataInputStream in, int type) throws IOException
    {
        switch (type)
        {
            case 1: return in.readByte();
            case 2: return in.readShort();
            case 3: return in.readInt();
            case 4: return in.readLong();
            case 5: return in.readFloat();
            case 6: return in.readDouble();
            case 7: { byte[] b = new byte[in.readInt()]; in.readFully(b); return b; }
            case 8: return in.readUTF();
            case 9:
            {
                int t = in.readByte(), n = in.readInt();
                List<Object> list = new ArrayList<>(Math.max(n, 0));
                for (int i = 0; i < n; i++) list.add(readTag(in, t));
                return list;
            }
            case 10:
            {
                Map<String, Object> map = new HashMap<>();
                while (true)
                {
                    int t = in.readByte();
                    if (t == 0) return map;
                    String name = in.readUTF();
                    map.put(name, readTag(in, t));
                }
            }
            case 11: { int[] a = new int[in.readInt()]; for (int i = 0; i < a.length; i++) a[i] = in.readInt(); return a; }
            case 12: { long[] a = new long[in.readInt()]; for (int i = 0; i < a.length; i++) a[i] = in.readLong(); return a; }
            default: throw new IOException("bad tag " + type);
        }
    }

    @SuppressWarnings("unchecked")
    static Map<String, Object> readChunk(RandomAccessFile raf, int index) throws IOException
    {
        raf.seek(index * 4L);
        int loc = raf.readInt();
        int offset = loc >>> 8, sectors = loc & 0xFF;
        if (offset == 0 || sectors == 0 || offset * 4096L + 5 > raf.length()) return null;
        raf.seek(offset * 4096L);
        int length = raf.readInt();
        int kind = raf.readByte();
        if (length <= 1 || length > sectors * 4096 || offset * 4096L + 4 + length > raf.length()) return null;
        byte[] data = new byte[length - 1];
        raf.readFully(data);
        InputStream raw = new ByteArrayInputStream(data);
        InputStream in = kind == 2 ? new InflaterInputStream(raw) : kind == 1 ? new GZIPInputStream(raw) : raw;
        try (DataInputStream d = new DataInputStream(new java.io.BufferedInputStream(in, 1 << 16)))
        {
            int t = d.readByte();
            d.readUTF();
            return (Map<String, Object>) readTag(d, t);
        }
    }

    // ------------------------------------------------------------------ block states

    /** One block state: name (no namespace for vanilla), properties, and derived traits. */
    static final class State
    {
        final String key, name;
        final Map<String, String> props;
        boolean air, passable, stairs, liquid, opaque, natural;
        int emits;
        /** A machine with a front: the horizontal direction (0 N, 1 E, 2 S, 3 W) its front looks, else -1. */
        int front = -1;
        String machine;

        State(String key, String name, Map<String, String> props)
        {
            this.key = key;
            this.name = name;
            this.props = props;
        }

        String prop(String k) { return props.getOrDefault(k, ""); }
    }

    static final Map<String, Integer> ids = new ConcurrentHashMap<>();
    static final List<State> states = Collections.synchronizedList(new ArrayList<>());

    // matched as parts of the name, so no word here may sit inside a solid block's name ("air" is in stairs and chair)
    static final String[] PASSABLE = {"structure_void", "torch", "banner", "button", "lever",
            "carpet", "redstone_wire", "tripwire", "pressure_plate", "ladder", "vine", "grass", "fern", "flower",
            "sapling", "tulip", "dandelion", "poppy", "orchid", "allium", "cornflower", "bluet", "daisy", "lily_of",
            "seagrass", "kelp", "dead_bush", "sugar_cane", "snow", "item_frame", "cobweb", "string", "scaffolding_x",
            "moss_carpet", "glow_lichen", "sculk_vein", "candle", "skull", "flower_pot"};

    static int stateId(Map<String, Object> entry)
    {
        String name = (String) entry.get("Name");
        Object p = entry.get("Properties");
        TreeMap<String, String> props = new TreeMap<>();
        if (p instanceof Map) for (var e : ((Map<?, ?>) p).entrySet()) props.put(String.valueOf(e.getKey()), String.valueOf(e.getValue()));
        String key = props.isEmpty() ? name : name + props;
        Integer id = ids.get(key);
        if (id != null) return id;
        synchronized (states)
        {
            id = ids.get(key);
            if (id != null) return id;
            String shortName = name.startsWith("minecraft:") ? name.substring(10) : name;
            State s = new State(key, shortName, props);
            classify(s);
            states.add(s);
            id = states.size() - 1;
            ids.put(key, id);
            return id;
        }
    }

    static void classify(State s)
    {
        String n = s.name;
        s.air = n.equals("air") || n.equals("cave_air") || n.equals("void_air");
        s.liquid = n.equals("water") || n.equals("lava") || n.equals("bubble_column");
        s.stairs = n.endsWith("_stairs");
        boolean pass = s.air || s.liquid;
        String local = n.substring(n.indexOf(':') + 1);
        for (String w : PASSABLE) if (local.contains(w) && !local.endsWith("_block") && !local.endsWith("_leaves")) pass = true;
        // names that must match whole: the invisible light block, vanilla rails and signs, heads
        if (local.equals("light") || local.equals("rail") || local.equals("powered_rail") || local.equals("detector_rail")
                || local.equals("activator_rail") || local.endsWith("_sign") || local.endsWith("_head") && !n.contains(":")) pass = true;
        if (n.startsWith("minecraft:") || !n.contains(":")) { if (local.endsWith("_head")) pass = true; }
        if (local.endsWith("_door") && !local.contains("trapdoor") || local.equals("store_door") || local.equals("city_personnel_door")
                || local.endsWith("_fence_gate")) pass = true;
        if (local.endsWith("_slab") && s.prop("type").equals("bottom")) pass = false;
        s.passable = pass;
        s.emits = emission(local, s);
        // parts of names that let light through; none may sit inside a solid block's name (light_gray_concrete,
        // nerv_machine_panel and nerv_wall_panel are solid)
        String[] seeThrough = {"glass", "pane", "leaves", "fence", "slab", "stairs", "door", "bars", "chain",
                "lantern", "scaffolding", "ladder", "carpet", "lamp", "rail", "sign", "banner", "fixture", "seat", "chair",
                "stool", "table", "sofa", "bench", "board", "post", "guard", "apg", "barrier", "railing", "pipe", "gutter",
                "slope"};
        boolean see = pass;
        for (String w : seeThrough) if (local.contains(w)) see = true;
        if (local.endsWith("_wall") || local.endsWith("_light") || local.equals("light") || n.equals("mtr:ticket_machine")) see = true;
        s.opaque = !see && !local.equals("lcl");
        String[] nature = {"stone", "deepslate", "dirt", "grass_block", "sand", "gravel", "granite", "diorite", "andesite", "tuff",
                "calcite", "podzol", "mud", "clay", "_ore", "bedrock", "netherrack", "moss_block", "rooted_dirt", "snow_block",
                "terracotta", "bitumen_ore", "coarse_dirt", "mycelium", "farmland", "dirt_path"};
        boolean nat = false;
        for (String w : nature) if (local.equals(w) || local.endsWith(w) && !local.contains("brick") && !local.contains("polished")
                && !local.contains("smooth") && !local.contains("tile") && !local.contains("chiseled") && !local.contains("cut_")
                && !local.contains("cobble") && !local.contains("sandstone")) nat = true;
        s.natural = nat;
        int facing = switch (s.prop("facing")) { case "north" -> 0; case "east" -> 1; case "south" -> 2; case "west" -> 3; default -> -1; };
        if (facing >= 0)
        {
            if (n.equals("mtr:ticket_machine") && s.prop("half").equals("lower")) { s.front = (facing + 2) % 4; s.machine = "mtr_ticket_machine"; }
            else if (n.equals("projectseele:nerv_access_reader")) { s.front = facing; s.machine = "access_reader"; }
            else if (n.equals("projectseele:period_fixture"))
            {
                String kind = s.prop("kind");
                if (java.util.Set.of("vending_machine", "coffee_machine", "public_phone", "drinking_fountain", "letter_box",
                        "newspaper_rack", "notice_board", "utility_box").contains(kind)) { s.front = facing; s.machine = kind; }
            }
        }
    }

    /** Block light a state gives off (vanilla values for the common sources; any mod block named lamp/light: 15). */
    static int emission(String n, State s)
    {
        if (n.equals("air") || n.equals("cave_air")) return 0;
        // this mod's lamps (ModBlocks): lit strip 14, lit ceiling / alert / beacon 15, street head 15, briefing tile 6
        if (n.equals("nerv_strip_light")) return s.prop("lit").equals("true") ? 14 : 0;
        if (n.equals("nerv_ceiling_light") || n.equals("nerv_alert_light") || n.equals("nerv_warning_beacon")) return s.prop("lit").equals("true") ? 15 : 0;
        if (n.equals("street_light_head")) return 15;
        if (n.equals("nerv_briefing_tile")) return 6;
        if (n.equals("geofront_skyweave")) return 4;
        if (n.equals("light")) { try { return Integer.parseInt(s.prop("level")); } catch (NumberFormatException e) { return 15; } }
        if (n.equals("glowstone") || n.equals("sea_lantern") || n.equals("shroomlight") || n.equals("beacon") || n.equals("lava")
                || n.equals("jack_o_lantern") || n.equals("froglight") || n.endsWith("_froglight") || n.equals("end_gateway")) return 15;
        if (n.equals("redstone_lamp")) return s.prop("lit").equals("true") ? 15 : 0;
        if (n.equals("lantern") || n.equals("campfire") || n.equals("conduit")) return 15;
        if (n.equals("torch") || n.equals("wall_torch") || n.equals("end_rod")) return 14;
        if (n.equals("soul_lantern") || n.equals("soul_torch") || n.equals("soul_wall_torch") || n.equals("soul_campfire")) return 10;
        if (n.startsWith("ochre") || n.contains("verdant") || n.contains("pearlescent")) return 15;
        if (n.contains("lamp") || n.contains("light") && !n.contains("lightning") && !n.contains("light_gray") && !n.contains("light_blue")
                && !n.contains("weighted")) return 15;
        return 0;
    }

    // ------------------------------------------------------------------ world access

    static int Y0 = -1344, Y1 = 320;

    static final class Section
    {
        int[] palette;   // global state ids
        long[] data;     // null: single state
        int bits;
        byte[] blockLight, skyLight;

        int get(int x, int y, int z)
        {
            if (data == null) return palette[0];
            int i = (y << 8) | (z << 4) | x;
            int per = 64 / bits;
            int p = (int) ((data[i / per] >>> ((i % per) * bits)) & ((1L << bits) - 1));
            return p < palette.length ? palette[p] : palette[0];
        }

        static int nibble(byte[] a, int x, int y, int z)
        {
            if (a == null) return -1;
            int i = (y << 8) | (z << 4) | x;
            int b = a[i >> 1] & 0xFF;
            return (i & 1) == 0 ? b & 15 : b >> 4;
        }
    }

    static final class Chunk
    {
        final Section[] sections = new Section[(Y1 - Y0) / 16];
        boolean lightOn;
    }

    static final class Region
    {
        final int rx, rz;
        final Chunk[] chunks = new Chunk[1024];

        Region(int rx, int rz) { this.rx = rx; this.rz = rz; }
    }

    static Path regionDir;
    static final int AIR_ID = 0;
    static final Map<Long, Region> cache = Collections.synchronizedMap(new LinkedHashMap<>(32, .75f, true)
    {
        @Override
        protected boolean removeEldestEntry(Map.Entry<Long, Region> e) { return size() > CACHE; }
    });
    static int CACHE = 24;
    static final Map<Long, Object> loadLocks = new ConcurrentHashMap<>();

    static long key(int a, int b) { return ((long) a << 32) ^ (b & 0xffffffffL); }

    static Region region(int rx, int rz)
    {
        long k = key(rx, rz);
        Region r = cache.get(k);
        if (r != null) return r;
        synchronized (loadLocks.computeIfAbsent(k, x -> new Object()))
        {
            r = cache.get(k);
            if (r != null) return r;
            r = loadRegion(rx, rz);
            cache.put(k, r);
            return r;
        }
    }

    @SuppressWarnings("unchecked")
    static Region loadRegion(int rx, int rz)
    {
        Region r = new Region(rx, rz);
        Path file = regionDir.resolve("r." + rx + "." + rz + ".mca");
        if (!Files.exists(file)) return r;
        try (RandomAccessFile raf = new RandomAccessFile(file.toFile(), "r"))
        {
            if (raf.length() < 8192) return r;
            for (int index = 0; index < 1024; index++)
            {
                Map<String, Object> root;
                try { root = readChunk(raf, index); } catch (IOException bad) { continue; }
                if (root == null) continue;
                Object level = root.get("Level");
                if (level instanceof Map) root = (Map<String, Object>) level;
                Chunk c = new Chunk();
                Object lo = root.get("isLightOn");
                c.lightOn = lo instanceof Number && ((Number) lo).intValue() != 0;
                Object secs = root.containsKey("sections") ? root.get("sections") : root.get("Sections");
                if (secs instanceof List)
                    for (Object so : (List<Object>) secs)
                    {
                        Map<String, Object> s = (Map<String, Object>) so;
                        int sy = ((Number) s.get("Y")).intValue();
                        int si = sy - Y0 / 16;
                        if (si < 0 || si >= c.sections.length) continue;
                        Section sec = new Section();
                        Map<String, Object> bs = (Map<String, Object>) s.get("block_states");
                        if (bs != null && bs.get("palette") instanceof List)
                        {
                            List<Object> pal = (List<Object>) bs.get("palette");
                            sec.palette = new int[pal.size()];
                            for (int i = 0; i < pal.size(); i++) sec.palette[i] = stateId((Map<String, Object>) pal.get(i));
                            sec.data = (long[]) bs.get("data");
                            sec.bits = Math.max(4, 32 - Integer.numberOfLeadingZeros(Math.max(1, pal.size() - 1)));
                        }
                        else sec.palette = new int[]{AIR_ID};
                        Object bl = s.get("BlockLight"), sl = s.get("SkyLight");
                        sec.blockLight = bl instanceof byte[] ? (byte[]) bl : null;
                        sec.skyLight = sl instanceof byte[] ? (byte[]) sl : null;
                        c.sections[si] = sec;
                    }
                r.chunks[index] = c;
            }
        }
        catch (IOException bad)
        {
            System.err.println("unreadable " + file + ": " + bad);
        }
        return r;
    }

    static Section section(int x, int y, int z)
    {
        if (y < Y0 || y >= Y1) return null;
        Region r = region(Math.floorDiv(x, 512), Math.floorDiv(z, 512));
        Chunk c = r.chunks[(Math.floorMod(x >> 4, 32)) + (Math.floorMod(z >> 4, 32)) * 32];
        if (c == null) return null;
        return c.sections[(y - Y0) >> 4];
    }

    static int block(int x, int y, int z)
    {
        Section s = section(x, y, z);
        return s == null ? AIR_ID : s.get(x & 15, y & 15, z & 15);
    }

    static State state(int x, int y, int z) { return states.get(block(x, y, z)); }

    static int blockLight(int x, int y, int z)
    {
        Section s = section(x, y, z);
        return s == null ? -1 : Section.nibble(s.blockLight, x & 15, y & 15, z & 15);
    }

    static int skyLight(int x, int y, int z)
    {
        Section s = section(x, y, z);
        return s == null ? -1 : Section.nibble(s.skyLight, x & 15, y & 15, z & 15);
    }

    // ------------------------------------------------------------------ main

    public static void main(String[] args) throws Exception
    {
        String mode = args[0];
        regionDir = Path.of(args[1]);
        Path out = Path.of(args[2]);
        Files.createDirectories(out);
        int threads = 6;
        for (int i = 3; i < args.length; i++)
        {
            if (args[i].equals("--threads")) threads = Integer.parseInt(args[++i]);
            else if (args[i].equals("--y0")) Y0 = Integer.parseInt(args[++i]);
            else if (args[i].equals("--y1")) Y1 = Integer.parseInt(args[++i]);
        }
        Map<String, Object> airEntry = new HashMap<>();
        airEntry.put("Name", "minecraft:air");
        stateId(airEntry); // id 0 = air
        List<int[]> regions = new ArrayList<>();
        try (var list = Files.list(regionDir))
        {
            for (Path p : (Iterable<Path>) list::iterator)
            {
                String[] parts = p.getFileName().toString().split("\\.");
                if (parts.length == 4 && parts[3].equals("mca") && Files.size(p) >= 8192)
                    regions.add(new int[]{Integer.parseInt(parts[1]), Integer.parseInt(parts[2])});
            }
        }
        regions.sort((a, b) -> a[1] != b[1] ? Integer.compare(a[1], b[1]) : Integer.compare(a[0], b[0]));
        long began = System.nanoTime();
        ExecutorService pool = Executors.newFixedThreadPool(threads, r -> { Thread t = new Thread(r); t.setDaemon(true); return t; });
        if (mode.equals("survey")) Survey.run(regions, pool, out);
        else if (mode.equals("scan")) Scan.run(regions, pool, out);
        else if (mode.equals("states"))
        {
            // states <cells.tsv> : each line x y z -> x y z state key (for the writer's exact "from")
            List<String> lines = Files.readAllLines(Path.of(System.getProperty("cells")));
            try (BufferedWriter w = Files.newBufferedWriter(out.resolve("states.tsv"), StandardCharsets.UTF_8))
            {
                for (String line : lines)
                {
                    String[] v = line.trim().split("\\s+");
                    if (v.length < 3) continue;
                    int x = Integer.parseInt(v[0]), y = Integer.parseInt(v[1]), z = Integer.parseInt(v[2]);
                    w.write(x + "\t" + y + "\t" + z + "\t" + state(x, y, z).key + "\n");
                }
            }
        }
        else if (mode.equals("probe"))
        {
            // probe x,y,z,r: every non-air block within r (by layer, top down)
            String[] v = System.getProperty("probe").split(",");
            int px = Integer.parseInt(v[0]), py = Integer.parseInt(v[1]), pz = Integer.parseInt(v[2]), r = Integer.parseInt(v[3]);
            for (int y = py + r; y >= py - r; y--)
                for (int z = pz - r; z <= pz + r; z++)
                    for (int x = px - r; x <= px + r; x++)
                    {
                        State s = state(x, y, z);
                        if (!s.air) System.out.println(x + " " + y + " " + z + " " + s.key + (s.passable ? " (pass)" : ""));
                    }
        }
        else throw new IllegalArgumentException(mode);
        pool.shutdown();
        System.out.printf("done in %.0f s, %d block states%n", (System.nanoTime() - began) / 1e9, states.size());
    }

    // ------------------------------------------------------------------ survey

    static final class Survey
    {
        static void run(List<int[]> regions, ExecutorService pool, Path out) throws Exception
        {
            Map<Integer, AtomicLong> counts = new ConcurrentHashMap<>();
            AtomicLong chunks = new AtomicLong(), lightOn = new AtomicLong(), withBlockLight = new AtomicLong(), sections = new AtomicLong();
            List<Future<?>> jobs = new ArrayList<>();
            for (int[] rr : regions)
                jobs.add(pool.submit(() -> {
                    Region r = loadRegion(rr[0], rr[1]);
                    for (Chunk c : r.chunks)
                    {
                        if (c == null) continue;
                        chunks.incrementAndGet();
                        if (c.lightOn) lightOn.incrementAndGet();
                        for (Section s : c.sections)
                        {
                            if (s == null) continue;
                            sections.incrementAndGet();
                            if (s.blockLight != null) withBlockLight.incrementAndGet();
                            if (s.data == null) { counts.computeIfAbsent(s.palette[0], k -> new AtomicLong()).addAndGet(4096); continue; }
                            int[] local = new int[s.palette.length];
                            int per = 64 / s.bits;
                            long mask = (1L << s.bits) - 1;
                            for (int i = 0; i < 4096; i++)
                            {
                                int p = (int) ((s.data[i / per] >>> ((i % per) * s.bits)) & mask);
                                if (p < local.length) local[p]++;
                            }
                            for (int p = 0; p < local.length; p++)
                                if (local[p] > 0) counts.computeIfAbsent(s.palette[p], k -> new AtomicLong()).addAndGet(local[p]);
                        }
                    }
                    return null;
                }));
            for (Future<?> f : jobs) f.get();
            try (BufferedWriter w = Files.newBufferedWriter(out.resolve("survey.tsv"), StandardCharsets.UTF_8))
            {
                List<Map.Entry<Integer, AtomicLong>> list = new ArrayList<>(counts.entrySet());
                list.sort((a, b) -> Long.compare(b.getValue().get(), a.getValue().get()));
                for (var e : list) w.write(e.getValue().get() + "\t" + states.get(e.getKey()).key + "\n");
            }
            System.out.printf("chunks %d, light on %d; sections %d, with block light %d%n", chunks.get(), lightOn.get(), sections.get(), withBlockLight.get());
        }
    }

    static final int[] DX = {0, 1, 0, -1}, DZ = {-1, 0, 1, 0};
    static final String[] DIRS = {"north", "east", "south", "west"};

    static boolean pass(int x, int y, int z) { return states.get(block(x, y, z)).passable; }

    /** Blocks down to the first solid one below (1 = solid right under), or 99 when none within 4. */
    static int floorDrop(int x, int y, int z)
    {
        for (int d = 1; d <= 4; d++) if (!pass(x, y - d, z)) return d;
        return 99;
    }

    static boolean open(int x, int y, int z) { return pass(x, y, z) && pass(x, y + 1, z) && floorDrop(x, y, z) <= 3; }

    static final Map<Long, int[]> chunkTops = new ConcurrentHashMap<>();

    /** The highest opaque block of a column (Y0 - 1 when none): above it is open sky. Worked out per chunk column. */
    static int top(int x, int z)
    {
        int cx = x >> 4, cz = z >> 4;
        int[] t = chunkTops.computeIfAbsent(key(cx, cz), k -> {
            int[] out = new int[256];
            java.util.Arrays.fill(out, Y0 - 1);
            Region r = region(Math.floorDiv(cx, 32), Math.floorDiv(cz, 32));
            Chunk c = r.chunks[Math.floorMod(cx, 32) + Math.floorMod(cz, 32) * 32];
            if (c == null) return out;
            int left = 256;
            boolean[] done = new boolean[256];
            for (int si = c.sections.length - 1; si >= 0 && left > 0; si--)
            {
                Section sec = c.sections[si];
                if (sec == null) continue;
                if (sec.data == null)
                {
                    if (!states.get(sec.palette[0]).opaque) continue;
                    for (int i = 0; i < 256; i++) if (!done[i]) { done[i] = true; out[i] = Y0 + si * 16 + 15; left--; }
                    continue;
                }
                boolean anyOpaque = false;
                for (int id : sec.palette) if (states.get(id).opaque) { anyOpaque = true; break; }
                if (!anyOpaque) continue;
                for (int i = 0; i < 256; i++)
                {
                    if (done[i]) continue;
                    int lx = i & 15, lz = i >> 4;
                    for (int y = 15; y >= 0; y--)
                        if (states.get(sec.get(lx, y, lz)).opaque) { done[i] = true; out[i] = Y0 + si * 16 + y; left--; break; }
                }
            }
            return out;
        });
        return t[(x & 15) | (z & 15) << 4];
    }

    static final class Scan
    {
        static final List<String> machines = Collections.synchronizedList(new ArrayList<>());
        static final List<String> stairs = Collections.synchronizedList(new ArrayList<>());
        static final List<String> stairClears = Collections.synchronizedList(new ArrayList<>());
        static final List<String> machineChanges = Collections.synchronizedList(new ArrayList<>());
        static final AtomicLong walkableStairs = new AtomicLong(), machinesSeen = new AtomicLong();
        static String dim = "projectseele:geofront";
        /** Air blocks wanted above every step of a walked flight (scan.headroom, default 3). */
        static final int HEADROOM = Integer.getInteger("scan.headroom", 3);
        static int[] exclude; // x0 y0 z0 x1 y1 z1 (inclusive): left out of the dark scan
        static final List<long[]> darkCells = Collections.synchronizedList(new ArrayList<>());
        static final List<long[]> gateCells = Collections.synchronizedList(new ArrayList<>());
        static final List<long[]> stationMarks = Collections.synchronizedList(new ArrayList<>());
        static final java.util.Set<String> STATION = java.util.Set.of("mtr:platform", "mtr:platform_slab", "mtr:apg_glass", "mtr:apg_door",
                "mtr:escalator_step", "mtr:escalator_side", "mtr:ticket_barrier_entrance_1", "mtr:ticket_barrier_exit_1", "mtr:ticket_machine",
                "mtr:pids_1", "mtr:pids_4", "projectseele:station_tactile_warning", "projectseele:station_tactile_path",
                "projectseele:period_station_floor", "projectseele:station_departure_board", "projectseele:station_seat",
                "projectseele:station_drain");

        static void run(List<int[]> regions, ExecutorService pool, Path out) throws Exception
        {
            String d = System.getProperty("scan.dim");
            if (d != null) dim = d;
            String ex = System.getProperty("scan.exclude");
            if (ex != null) { String[] v = ex.split(","); exclude = new int[6]; for (int i = 0; i < 6; i++) exclude[i] = Integer.parseInt(v[i]); }
            List<Future<?>> jobs = new ArrayList<>();
            for (int[] rr : regions) jobs.add(pool.submit(() -> { region(rr[0], rr[1]); scanRegion(rr[0], rr[1]); return null; }));
            for (Future<?> f : jobs) f.get();
            jobs.clear();
            System.out.printf("machines: %d seen, %d reversed; walkable stairs: %d, %d steps without headroom%n", machinesSeen.get(),
                    machines.stream().filter(l -> l.contains("\treversed\t")).count(), walkableStairs.get(), stairs.size());
            boolean dark = !"false".equals(System.getProperty("scan.dark"));
            AtomicLong doneRegions = new AtomicLong();
            if (dark) for (int[] rr : regions) jobs.add(pool.submit(() -> {
                Dark.darkRegion(rr[0], rr[1]);
                long d2 = doneRegions.incrementAndGet();
                if (d2 % 25 == 0) System.out.printf("dark: %d of %d regions%n", d2, regions.size());
                return null;
            }));
            for (Future<?> f : jobs) f.get();
            System.out.printf("dark walkable cells: %d%n", darkCells.size());
            write(out.resolve("machines.tsv"), "dim\tx\ty\tz\tmachine\tfacing\tfront\tverdict\tfront_cell\tback_cell", machines);
            write(out.resolve("machine_changes.tsv"), "dim\tx\ty\tz\tfrom\tto", machineChanges);
            Gates.run(out);
            write(out.resolve("stairs.tsv"), "dim\tx\ty\tz\tstair\tfacing\trun_bottom\tobstruction\tkind\tbreaks_out", stairs);
            write(out.resolve("stair_clears.tsv"), "dim\tx\ty\tz\tfrom\tto\tbreaks_out", stairClears);
            if (dark) Dark.report(out);
        }

        static void write(Path file, String head, List<String> rows) throws IOException
        {
            List<String> sorted = new ArrayList<>(rows);
            Collections.sort(sorted);
            try (BufferedWriter w = Files.newBufferedWriter(file, StandardCharsets.UTF_8))
            {
                w.write(head + "\n");
                for (String r : sorted) w.write(r + "\n");
            }
        }

        static void scanRegion(int rx, int rz)
        {
            Region r = region(rx, rz);
            for (int ci = 0; ci < 1024; ci++)
            {
                Chunk c = r.chunks[ci];
                if (c == null) continue;
                int bx = rx * 512 + (ci & 31) * 16, bz = rz * 512 + (ci >> 5) * 16;
                for (int si = 0; si < c.sections.length; si++)
                {
                    Section sec = c.sections[si];
                    if (sec == null) continue;
                    boolean any = false;
                    for (int id : sec.palette) { State st = states.get(id); if (st.front >= 0 || st.stairs || STATION.contains(st.name) || st.name.startsWith("mtr:ticket_barrier")) { any = true; break; } }
                    if (!any) continue;
                    int by = Y0 + si * 16;
                    for (int y = 0; y < 16; y++) for (int z = 0; z < 16; z++) for (int x = 0; x < 16; x++)
                    {
                        State st = states.get(sec.get(x, y, z));
                        if (STATION.contains(st.name) && ((bx + x) & 7) == 0 && ((bz + z) & 7) == 0) stationMarks.add(new long[]{bx + x, by + y, bz + z});
                        if (st.name.startsWith("mtr:ticket_barrier")) gateCells.add(new long[]{bx + x, by + y, bz + z, sec.get(x, y, z)});
                        if (st.front >= 0) machine(st, bx + x, by + y, bz + z);
                        else if (st.stairs && st.prop("half").equals("bottom")) stair(st, bx + x, by + y, bz + z);
                    }
                }
            }
        }

        static String cell(int x, int y, int z)
        {
            State s = states.get(block(x, y, z));
            return s.passable ? (floorDrop(x, y, z) <= 3 ? "walkway" : "drop") : s.name;
        }

        static void machine(State st, int x, int y, int z)
        {
            machinesSeen.incrementAndGet();
            int f = st.front, b = (f + 2) % 4;
            int fx = x + DX[f], fz = z + DZ[f], kx = x + DX[b], kz = z + DZ[b];
            boolean frontOpen = open(fx, y, fz) || pass(fx, y, fz) && floorDrop(fx, y, fz) <= 3;
            boolean backOpen = open(kx, y, kz) || pass(kx, y, kz) && floorDrop(kx, y, kz) <= 3;
            String verdict = frontOpen ? "ok" : backOpen ? "reversed" : "boxed";
            String facing = st.prop("facing");
            machines.add(dim + "\t" + x + "\t" + y + "\t" + z + "\t" + st.machine + "\t" + facing + "\t" + DIRS[f] + "\t" + verdict
                    + "\t" + cell(fx, y, fz) + "\t" + cell(kx, y, kz));
            if (!verdict.equals("reversed")) return;
            String turned = DIRS[(java.util.Arrays.asList(DIRS).indexOf(facing) + 2) % 4];
            machineChanges.add(dim + "\t" + x + "\t" + y + "\t" + z + "\t" + st.key + "\t" + st.key.replace("facing=" + facing, "facing=" + turned));
            // the parts above a tall machine turn with it
            for (int up = 1; up <= 2; up++)
            {
                State above = states.get(block(x, y + up, z));
                if (above.prop("facing").equals(facing) && (above.name.equals("mtr:ticket_machine") || above.name.equals("projectseele:period_fixture_part")))
                    machineChanges.add(dim + "\t" + x + "\t" + (y + up) + "\t" + z + "\t" + above.key + "\t" + above.key.replace("facing=" + facing, "facing=" + turned));
            }
        }

        static boolean sameStair(int x, int y, int z, String facing)
        {
            State s = states.get(block(x, y, z));
            return s.stairs && s.prop("half").equals("bottom") && s.prop("facing").equals(facing);
        }

        static void stair(State st, int x, int y, int z)
        {
            String facing = st.prop("facing");
            int f = java.util.Arrays.asList(DIRS).indexOf(facing);
            if (f < 0) return;
            boolean up = sameStair(x + DX[f], y + 1, z + DZ[f], facing), down = sameStair(x - DX[f], y - 1, z - DZ[f], facing);
            if (!up && !down) return; // a single stair (a seat, a kerb), not a flight
            int bx = x, by = y, bz = z, n = 0;
            while (sameStair(bx - DX[f], by - 1, bz - DZ[f], facing) && n++ < 64) { bx -= DX[f]; by--; bz -= DZ[f]; }
            int tx = x, ty = y, tz = z;
            n = 0;
            while (sameStair(tx + DX[f], ty + 1, tz + DZ[f], facing) && n++ < 64) { tx += DX[f]; ty++; tz += DZ[f]; }
            boolean bottomLanding = pass(bx - DX[f], by, bz - DZ[f]) && pass(bx - DX[f], by + 1, bz - DZ[f]) && floorDrop(bx - DX[f], by, bz - DZ[f]) == 1;
            boolean topLanding = !pass(tx + DX[f], ty, tz + DZ[f]) && pass(tx + DX[f], ty + 1, tz + DZ[f]) && pass(tx + DX[f], ty + 2, tz + DZ[f]);
            if (!bottomLanding && !topLanding) return; // a roof or a wall pattern: nobody walks it
            if (x == bx && y == by && z == bz) walkableStairs.incrementAndGet();
            State above = states.get(block(x, y + 1, z));
            // the lowest step under a floor is built in, not walked; a handrail standing on the edge column is meant to be there
            if (above.opaque && x == bx && y == by && z == bz) return;
            String an = above.name;
            if (an.contains("guard") || an.contains("railing") || an.contains("fence") || an.endsWith("_wall") || an.contains("bars") || an.contains("pane")) return;
            StringBuilder what = new StringBuilder();
            boolean natural = false, built = false, breaks = false;
            for (int h = 1; h <= HEADROOM; h++)
            {
                State o = states.get(block(x, y + h, z));
                if (o.passable) continue;
                if (what.length() > 0) what.append(' ');
                what.append(h).append(':').append(o.name);
                if (o.natural) natural = true; else built = true;
                boolean out = breaksOut(x, y + h, z, y);
                breaks |= out;
                stairClears.add(dim + "\t" + x + "\t" + (y + h) + "\t" + z + "\t" + o.key + "\tminecraft:air\t" + out);
            }
            if (what.length() == 0) return;
            stairs.add(dim + "\t" + x + "\t" + y + "\t" + z + "\t" + st.name + "\t" + facing + "\t" + bx + "," + by + "," + bz + "\t" + what
                    + "\t" + (natural && !built ? "sunk" : built && !natural ? "low_ceiling" : "both") + "\t" + breaks);
        }

        /** Clearing (x, y, z) opens the passage to open sky: a neighbour outside the cleared column is air under open sky. */
        static boolean breaksOut(int x, int y, int z, int stairY)
        {
            int[][] n = {{1, 0, 0}, {-1, 0, 0}, {0, 0, 1}, {0, 0, -1}, {0, 1, 0}};
            for (int[] d : n)
            {
                int ax = x + d[0], ay = y + d[1], az = z + d[2];
                if (d[1] == 1 && ay <= stairY + HEADROOM) continue; // still inside the cleared column
                if (pass(ax, ay, az) && ay > top(ax, az)) return true;
            }
            return false;
        }
    }

    // ------------------------------------------------------------------ darkness

    /**
     * Block light from every source and sky light from open sky, by breadth-first spreading (one level lost per block,
     * stopped by opaque blocks), in 64-high slabs with a 15-block margin; then the walkable covered cells on a built floor
     * where both are 3 or less.
     */
    /**
     * MTR ticket barriers. A player passes from the side opposite `facing` and walks on in the `facing` direction (the arrow
     * and the card reader sit on the side opposite `facing`; MTR opens the gate for a player on that side). So an entrance
     * gate must face into the paid area and an exit gate out of it. The paid side is the one a walk from the gate reaches
     * a platform from sooner without going through any barrier.
     */
    static final class Gates
    {
        static void run(Path out) throws IOException
        {
            List<String> rows = new ArrayList<>(), changes = new ArrayList<>();
            int ok = 0, reversed = 0, unknown = 0;
            for (long[] g : Scan.gateCells)
            {
                int x = (int) g[0], y = (int) g[1], z = (int) g[2];
                State st = states.get((int) g[3]);
                String facing = st.prop("facing");
                int f = java.util.Arrays.asList(DIRS).indexOf(facing);
                if (f < 0) continue;
                boolean entrance = st.name.contains("entrance");
                int ahead = walk(x + DX[f], y, z + DZ[f]), behind = walk(x - DX[f], y, z - DZ[f]);
                String paid = ahead < behind ? "ahead" : behind < ahead ? "behind" : "unknown";
                String verdict = paid.equals("unknown") ? "unknown" : (paid.equals("ahead") == entrance) ? "ok" : "reversed";
                if (verdict.equals("ok")) ok++; else if (verdict.equals("reversed")) reversed++; else unknown++;
                rows.add(Scan.dim + "	" + x + "	" + y + "	" + z + "	" + (entrance ? "entrance" : "exit") + "	" + facing + "	"
                        + (ahead == Integer.MAX_VALUE ? "-" : ahead) + "	" + (behind == Integer.MAX_VALUE ? "-" : behind) + "	" + verdict);
                if (verdict.equals("reversed"))
                {
                    String turned = DIRS[(f + 2) % 4];
                    changes.add(Scan.dim + "	" + x + "	" + y + "	" + z + "	" + st.key + "	" + st.key.replace("facing=" + facing, "facing=" + turned));
                }
            }
            System.out.printf("ticket barriers: %d ok, %d reversed, %d unknown%n", ok, reversed, unknown);
            Scan.write(out.resolve("gates.tsv"), "dim	x	y	z	kind	facing	platform_ahead	platform_behind	verdict", rows);
            Scan.write(out.resolve("gate_changes.tsv"), "dim	x	y	z	from	to", changes);
        }

        static boolean barrier(int x, int y, int z)
        {
            String n = states.get(block(x, y, z)).name;
            return n.startsWith("mtr:ticket_barrier");
        }

        static boolean stand(int x, int y, int z)
        {
            return pass(x, y, z) && pass(x, y + 1, z) && !pass(x, y - 1, z) && !barrier(x, y, z) && !barrier(x, y + 1, z) && !tall(x, y - 1, z);
        }

        /** Blocks a player cannot step up onto (taller than a block, or a rail along the gate line). */
        static boolean tall(int x, int y, int z)
        {
            String n = states.get(block(x, y, z)).name, local = n.substring(n.indexOf(':') + 1);
            if (local.startsWith("ticket_barrier")) return true;
            for (String w : new String[]{"fence", "_wall", "pane", "bars", "railing", "guard", "apg", "barrier", "gate", "post", "glass_door"})
                if (local.contains(w)) return true;
            return false;
        }

        static boolean platform(int x, int y, int z)
        {
            String n = states.get(block(x, y - 1, z)).name, h = states.get(block(x, y, z)).name;
            if (n.equals("mtr:platform") || n.equals("mtr:platform_slab") || h.equals("mtr:platform_slab") || n.equals("projectseele:station_tactile_warning"))
                return true;
            // the edge of a platform behind platform screen doors
            for (int d = 0; d < 4; d++) if (states.get(block(x + DX[d], y, z + DZ[d])).name.startsWith("mtr:apg")) return true;
            return false;
        }

        /** Steps from a start cell to the nearest platform floor, walking (up one, down three), never through a barrier. */
        static int walk(int sx, int sy, int sz)
        {
            int start = -99;
            for (int dy = 1; dy >= -3; dy--) if (stand(sx, sy + dy, sz)) { start = sy + dy; break; }
            if (start == -99) return Integer.MAX_VALUE;
            Map<Long, Integer> seen = new HashMap<>();
            java.util.ArrayDeque<int[]> q = new java.util.ArrayDeque<>();
            q.add(new int[]{sx, start, sz, 0});
            seen.put(pack3(sx, start, sz), 0);
            while (!q.isEmpty() && seen.size() < 200000)
            {
                int[] c = q.poll();
                if (platform(c[0], c[1], c[2])) return c[3];
                if (Math.abs(c[0] - sx) > 160 || Math.abs(c[2] - sz) > 160 || Math.abs(c[1] - sy) > 40) continue;
                for (int d = 0; d < 4; d++)
                {
                    int nx = c[0] + DX[d], nz = c[2] + DZ[d];
                    for (int dy = 1; dy >= -3; dy--)
                    {
                        int ny = c[1] + dy;
                        if (dy == 1 && !pass(c[0], c[1] + 2, c[2])) continue;
                        if (!stand(nx, ny, nz)) continue;
                        boolean clear = true;
                        for (int k = ny + 1; k <= c[1] + 1 && clear; k++) if (!pass(nx, k, nz) || barrier(nx, k, nz)) clear = false;
                        if (!clear) continue;
                        if (seen.putIfAbsent(pack3(nx, ny, nz), c[3] + 1) == null) q.add(new int[]{nx, ny, nz, c[3] + 1});
                        break;
                    }
                }
            }
            return Integer.MAX_VALUE;
        }

        static long pack3(int x, int y, int z) { return ((long) x & 0x3FFFFF) << 42 | ((long) (y + 2048) & 0xFFFFF) << 22 | ((long) z & 0x3FFFFF); }
    }

    static final class Dark
    {
        static final int M = 15, SLAB = 64;

        static void darkRegion(int rx, int rz)
        {
            Region r = region(rx, rz);
            // the heights where anything stands (a slab with no section in any chunk is skipped)
            boolean[] slabUsed = new boolean[(Y1 - Y0 + SLAB - 1) / SLAB];
            for (Chunk c : r.chunks)
            {
                if (c == null) continue;
                for (int si = 0; si < c.sections.length; si++)
                {
                    Section sec = c.sections[si];
                    if (sec == null || sec.data == null && states.get(sec.palette[0]).air) continue;
                    if (sec.data == null && states.get(sec.palette[0]).opaque) continue; // solid rock section
                    slabUsed[(si * 16) / SLAB] = true;
                }
            }
            int x0 = rx * 512 - M, z0 = rz * 512 - M, nx = 512 + 2 * M, nz = 512 + 2 * M;
            int[] tops = new int[nx * nz];
            for (int i = 0; i < nx; i++) for (int k = 0; k < nz; k++) tops[i * nz + k] = top(x0 + i, z0 + k);
            for (int sl = 0; sl < slabUsed.length; sl++)
            {
                if (!slabUsed[sl]) continue;
                int ys = Y0 + sl * SLAB, y0 = ys - M, ny = SLAB + 2 * M;
                slab(rx, rz, x0, y0, z0, nx, ny, nz, ys, tops);
            }
        }

        static final byte OPAQUE = 1, PASS = 2, LIQUID = 4, NATURAL = 8, LCL = 16;

        static void slab(int rx, int rz, int x0, int y0, int z0, int nx, int ny, int nz, int ys, int[] tops)
        {
            int n = nx * ny * nz;
            byte[] kind = new byte[n], bl = new byte[n], sky = new byte[n];
            IntList blockSeeds = new IntList(), skySeeds = new IntList();
            // fill, a chunk column and a section at a time
            for (int cx = Math.floorDiv(x0, 16); cx <= Math.floorDiv(x0 + nx - 1, 16); cx++)
                for (int cz = Math.floorDiv(z0, 16); cz <= Math.floorDiv(z0 + nz - 1, 16); cz++)
                {
                    Region r = region(Math.floorDiv(cx, 32), Math.floorDiv(cz, 32));
                    Chunk c = r.chunks[Math.floorMod(cx, 32) + Math.floorMod(cz, 32) * 32];
                    int ax0 = Math.max(x0, cx * 16), ax1 = Math.min(x0 + nx, cx * 16 + 16);
                    int az0 = Math.max(z0, cz * 16), az1 = Math.min(z0 + nz, cz * 16 + 16);
                    for (int wy = y0; wy < y0 + ny; wy++)
                    {
                        Section sec = c == null || wy < Y0 || wy >= Y1 ? null : c.sections[(wy - Y0) >> 4];
                        int j = wy - y0;
                        for (int wx = ax0; wx < ax1; wx++)
                            for (int wz = az0; wz < az1; wz++)
                            {
                                State s = states.get(sec == null ? AIR_ID : sec.get(wx & 15, wy & 15, wz & 15));
                                int idx = ((wx - x0) * ny + j) * nz + (wz - z0);
                                byte k = 0;
                                if (s.opaque) k |= OPAQUE;
                                if (s.passable) k |= PASS;
                                if (s.liquid) k |= LIQUID;
                                if (s.natural) k |= NATURAL;
                                if (s.name.equals("projectseele:lcl")) k |= LCL;
                                kind[idx] = k;
                                if (s.emits > 0) { bl[idx] = (byte) s.emits; blockSeeds.add(idx); }
                                if (!s.opaque && wy > tops[(wx - x0) * nz + (wz - z0)]) sky[idx] = 15;
                            }
                    }
                }
            int sx = ny * nz, sy = nz;
            // sky: only the open-sky cells beside covered space spread
            for (int i = 0; i < nx; i++)
                for (int j = 0; j < ny; j++)
                    for (int k = 0; k < nz; k++)
                    {
                        int idx = (i * ny + j) * nz + k;
                        if (sky[idx] != 15) continue;
                        if (i > 0 && sky[idx - sx] == 0 && (kind[idx - sx] & OPAQUE) == 0 || i < nx - 1 && sky[idx + sx] == 0 && (kind[idx + sx] & OPAQUE) == 0
                                || j > 0 && sky[idx - sy] == 0 && (kind[idx - sy] & OPAQUE) == 0 || j < ny - 1 && sky[idx + sy] == 0 && (kind[idx + sy] & OPAQUE) == 0
                                || k > 0 && sky[idx - 1] == 0 && (kind[idx - 1] & OPAQUE) == 0 || k < nz - 1 && sky[idx + 1] == 0 && (kind[idx + 1] & OPAQUE) == 0)
                            skySeeds.add(idx);
                    }
            spread(bl, kind, blockSeeds, nx, ny, nz);
            spread(sky, kind, skySeeds, nx, ny, nz);
            for (int i = M; i < nx - M; i++)
                for (int k = M; k < nz - M; k++)
                    for (int j = M; j < M + SLAB && y0 + j < Y1; j++)
                    {
                        int idx = (i * ny + j) * nz + k;
                        if (bl[idx] > 3 || sky[idx] > 3) continue;
                        byte here = kind[idx];
                        if ((here & PASS) == 0 || (here & LIQUID) != 0) continue;
                        if ((kind[idx + sy] & PASS) == 0) continue;
                        byte floor = kind[idx - sy];
                        if ((floor & (PASS | NATURAL | LIQUID | LCL)) != 0) continue;
                        int wx = x0 + i, wy = y0 + j, wz = z0 + k;
                        if (wy > tops[i * nz + k]) continue;
                        int[] e = Scan.exclude;
                        if (e != null && wx >= e[0] && wx <= e[3] && wy >= e[1] && wy <= e[4] && wz >= e[2] && wz <= e[5]) continue;
                        // beside a walkway that is lit or under open sky: people get here
                        long edge = 0;
                        int[] nb = {idx - sx, idx + sx, idx - 1, idx + 1};
                        for (int m : nb)
                        {
                            if ((kind[m] & PASS) == 0 || (kind[m + sy] & PASS) == 0 || (kind[m - sy] & PASS) != 0) continue;
                            if (bl[m] > 3 || sky[m] > 3) { edge = 1; break; }
                        }
                        Scan.darkCells.add(new long[]{wx, wy, wz, edge});
                    }
        }

        /** Breadth-first light spreading, level by level: every step loses one level; opaque blocks stop it. */
        static void spread(byte[] level, byte[] kind, IntList seeds, int nx, int ny, int nz)
        {
            int sx = ny * nz, sy = nz;
            IntList now = seeds, next = new IntList();
            while (now.size > 0)
            {
                next.size = 0;
                for (int q = 0; q < now.size; q++)
                {
                    int idx = now.data[q];
                    int lv = level[idx];
                    if (lv <= 1) continue;
                    int i = idx / sx, j = (idx / sy) % ny, k = idx % nz;
                    if (i > 0) push(level, kind, idx - sx, lv, next);
                    if (i < nx - 1) push(level, kind, idx + sx, lv, next);
                    if (j > 0) push(level, kind, idx - sy, lv, next);
                    if (j < ny - 1) push(level, kind, idx + sy, lv, next);
                    if (k > 0) push(level, kind, idx - 1, lv, next);
                    if (k < nz - 1) push(level, kind, idx + 1, lv, next);
                }
                IntList t = now; now = next; next = t;
            }
        }

        static void push(byte[] level, byte[] kind, int m, int lv, IntList next)
        {
            if ((kind[m] & OPAQUE) != 0 || level[m] >= lv - 1) return;
            level[m] = (byte) (lv - 1);
            next.add(m);
        }

        static final class IntList
        {
            int[] data = new int[1024];
            int size;

            void add(int v)
            {
                if (size == data.length) data = java.util.Arrays.copyOf(data, size * 2);
                data[size++] = v;
            }
        }

        /** Dark cells grouped into connected places, with a lamp plan (one flush ceiling light per 6 blocks or so). */
        static void report(Path out) throws IOException
        {
            Map<Long, Integer> index = new HashMap<>();
            List<long[]> cells = new ArrayList<>(Scan.darkCells);
            for (int i = 0; i < cells.size(); i++) index.put(pack(cells.get(i)), i);
            int[] group = new int[cells.size()];
            java.util.Arrays.fill(group, -1);
            List<List<Integer>> groups = new ArrayList<>();
            for (int i = 0; i < cells.size(); i++)
            {
                if (group[i] >= 0) continue;
                List<Integer> members = new ArrayList<>();
                java.util.ArrayDeque<Integer> todo = new java.util.ArrayDeque<>();
                todo.add(i);
                group[i] = groups.size();
                while (!todo.isEmpty())
                {
                    int c = todo.poll();
                    members.add(c);
                    long[] p = cells.get(c);
                    for (int dx = -1; dx <= 1; dx++) for (int dy = -1; dy <= 1; dy++) for (int dz = -1; dz <= 1; dz++)
                    {
                        if (Math.abs(dx) + Math.abs(dz) != 1 && !(dx == 0 && dz == 0 && dy != 0)) continue;
                        Integer m = index.get(pack(new long[]{p[0] + dx, p[1] + dy, p[2] + dz, 0}));
                        if (m != null && group[m] < 0) { group[m] = groups.size(); todo.add(m); }
                    }
                }
                groups.add(members);
            }
            List<String> rows = new ArrayList<>(), lamps = new ArrayList<>();
            int big = 0;
            for (int g = 0; g < groups.size(); g++)
            {
                List<Integer> members = groups.get(g);
                if (members.size() < 8) continue; // a nook, not a place
                big++;
                long minx = Long.MAX_VALUE, miny = minx, minz = minx, maxx = Long.MIN_VALUE, maxy = maxx, maxz = maxx, sx = 0, sy = 0, sz = 0;
                for (int m : members)
                {
                    long[] p = cells.get(m);
                    minx = Math.min(minx, p[0]); maxx = Math.max(maxx, p[0]); miny = Math.min(miny, p[1]); maxy = Math.max(maxy, p[1]);
                    minz = Math.min(minz, p[2]); maxz = Math.max(maxz, p[2]); sx += p[0]; sy += p[1]; sz += p[2];
                }
                boolean reachable = false;
                for (int m : members) if (cells.get(m).length > 3 && cells.get(m)[3] == 1) { reachable = true; break; }
                long cxm = sx / members.size(), cym = sy / members.size(), czm = sz / members.size();
                boolean station = nearStation(minx - 24, miny - 12, minz - 24, maxx + 24, maxy + 12, maxz + 24);
                int placed = 0, tall = 0;
                List<long[]> lit = new ArrayList<>();
                for (int m : members)
                {
                    long[] p = cells.get(m);
                    boolean covered = false;
                    for (long[] l : lit) if (Math.abs(l[0] - p[0]) + Math.abs(l[2] - p[2]) <= 6 && Math.abs(l[1] - p[1]) <= 4) { covered = true; break; }
                    if (covered) continue;
                    int cx = (int) p[0], cy = (int) p[1], cz = (int) p[2];
                    int ceiling = -1;
                    for (int h = 2; h <= 12; h++) if (!pass(cx, cy + h, cz)) { ceiling = cy + h; break; }
                    if (ceiling < 0) { tall++; lit.add(p); continue; }
                    State c = states.get(block(cx, ceiling, cz));
                    if (!c.opaque) { lit.add(p); tall++; continue; }
                    if (ceiling - cy <= 6) // a low ceiling: the light set into it
                        lamps.add(Scan.dim + "\t" + cx + "\t" + ceiling + "\t" + cz + "\t" + c.key + "\tprojectseele:nerv_ceiling_light{hanging=false, lit=true}\t" + g);
                    else // a high one: a hanging light just under it, nearer the floor
                        lamps.add(Scan.dim + "\t" + cx + "\t" + (ceiling - 1) + "\t" + cz + "\t" + states.get(block(cx, ceiling - 1, cz)).key
                                + "\tprojectseele:nerv_ceiling_light{hanging=true, lit=true}\t" + g);
                    lit.add(p);
                    placed++;
                }
                int n = members.size();
                rows.add(Scan.dim + "\t" + g + "\t" + n + "\t" + (sx / n) + "," + (sy / n) + "," + (sz / n) + "\t" + minx + "," + miny + "," + minz
                        + "\t" + maxx + "," + maxy + "," + maxz + "\t" + placed + "\t" + tall + "\t" + reachable + "\t" + station
                        + "\t" + cells.get(members.get(0))[0] + "," + cells.get(members.get(0))[1] + "," + cells.get(members.get(0))[2]);
            }
            rows.sort((a, b) -> Integer.compare(Integer.parseInt(b.split("\t")[2]), Integer.parseInt(a.split("\t")[2])));
            try (BufferedWriter w = Files.newBufferedWriter(out.resolve("dark.tsv"), StandardCharsets.UTF_8))
            {
                w.write("dim\tplace\tcells\tcentre\tmin\tmax\tlamps\ttoo_tall_or_open\treachable\tnear_station\tsample_cell\n");
                for (String r : rows) w.write(r + "\n");
            }
            Scan.write(out.resolve("dark_lamps.tsv"), "dim\tx\ty\tz\tfrom\tto\tplace", lamps);
            System.out.printf("dark places (8+ cells): %d of %d groups; lamps planned: %d%n", big, groups.size(), lamps.size());
        }

        static Map<Long, List<long[]>> marks;

        static boolean nearStation(long x0, long y0, long z0, long x1, long y1, long z1)
        {
            if (marks == null)
            {
                marks = new HashMap<>();
                for (long[] m : Scan.stationMarks) marks.computeIfAbsent(key((int) (m[0] >> 6), (int) (m[2] >> 6)), k -> new ArrayList<>()).add(m);
            }
            for (long gx = x0 >> 6; gx <= x1 >> 6; gx++)
                for (long gz = z0 >> 6; gz <= z1 >> 6; gz++)
                {
                    List<long[]> l = marks.get(key((int) gx, (int) gz));
                    if (l == null) continue;
                    for (long[] m : l) if (m[0] >= x0 && m[0] <= x1 && m[1] >= y0 && m[1] <= y1 && m[2] >= z0 && m[2] <= z1) return true;
                }
            return false;
        }

        static long pack(long[] p) { return (p[0] & 0x3FFFFF) << 42 | (p[1] + 2048 & 0xFFFFF) << 22 | (p[2] & 0x3FFFFF); }
    }
}
