import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.RandomAccessFile;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.atomic.AtomicLong;
import java.util.zip.GZIPInputStream;
import java.util.zip.GZIPOutputStream;
import java.util.zip.InflaterInputStream;

/**
 * Bake the GeoFront cavity's far view (version 2) from a cold copy of the world's GeoFront region files.
 *
 * java -Xmx12g tools/java/BakeGeoFrontFarViewR65.java <geofront region dir> <out.bin.gz> [--threads 6]
 *
 * Every block face that looks into the cavity's own air is kept at full resolution (one block), and again at two and
 * four blocks (a coarse cell is solid when any block in it is; its faces show the block most often seen on the cell's
 * surface), so the client can draw near ground block by block and coarsen with distance. Faces keep the full block
 * state, so the client can give each face the real texture that side of that block shows. The cavity is the largest
 * connected air at four-block cells (a cell with four or more solid blocks counts as solid); a block face counts when
 * the air in front of it lies in that cavity or one coarse cell from it, so thin walls and roofs are never lost.
 * Neighbouring faces of the same block state in a plane are merged; nothing crosses a 64x64 tile.
 *
 * Format (little-endian, gzip): b"SGDM", u8 version (2), u8 tile size (64), i32 x0, y0, z0 (tile grid origin),
 * u16 tiles along x, u16 tiles along z, u16 height, u8 level count, u8 level scale each (1, 2, 4), u32 palette count,
 * palette (u16 length + UTF-8 "namespace:id[key=value,...]" each), u32 tile count, then per tile u16 tx, u16 tz and per
 * level u32 quad count and quads of 11 bytes: u8 x, u16 y, u8 z (the solid cell, in level cells from the tile origin),
 * u16 du, dv (extent in level cells along the face's in-plane axes), u8 face (0 -X, 1 +X, 2 -Y, 3 +Y, 4 -Z, 5 +Z),
 * u16 palette index. In-plane axes: X faces (y, z), Y faces (x, z), Z faces (x, y).
 *
 * The output is a private build product derived from the map, installed into the pack's jar at
 * assets/projectseele/geofront/dome_far_r65.bin.gz and never committed.
 */
public final class BakeGeoFrontFarViewR65
{
    static final int X0 = -1888, X1 = 1952, Z0 = -1600, Z1 = 2240, Y0 = -528, Y1 = 64, H = Y1 - Y0;
    static final int TILE = 64, COARSE = 4, EDGE = 4;
    static final int[] LEVELS = {1, 2, 4};
    static final int GX0 = Math.floorDiv(X0, TILE) * TILE, GZ0 = Math.floorDiv(Z0, TILE) * TILE;
    static final int GX1 = -Math.floorDiv(-X1, TILE) * TILE, GZ1 = -Math.floorDiv(-Z1, TILE) * TILE;
    static final Set<String> AIR = Set.of("air", "cave_air", "void_air", "light", "barrier", "structure_void");
    static final String[] PLANTS = {"grass", "fern", "flower", "sapling", "tulip", "vine", "lily", "carpet", "dandelion",
            "poppy", "orchid", "allium", "cornflower", "mushroom", "torch", "button", "tripwire", "seagrass", "kelp", "bush",
            "sign", "banner", "rail", "lantern", "chain", "pressure_plate", "lever", "candle", "snow"};

    // global palette: index 0 = see-through; 1.. = solid block states
    static final Map<String, Integer> palette = new ConcurrentHashMap<>();
    static final List<String> names = java.util.Collections.synchronizedList(new ArrayList<>());

    static int stateId(String key)
    {
        Integer id = palette.get(key);
        if (id != null) return id;
        synchronized (names)
        {
            id = palette.get(key);
            if (id != null) return id;
            names.add(key);
            id = names.size();
            palette.put(key, id);
            return id;
        }
    }

    static boolean seeThrough(String name)
    {
        String key = name.substring(name.indexOf(':') + 1);
        if (AIR.contains(key)) return true;
        if (key.equals("grass_block")) return false;
        if (key.equals("tall_seagrass")) return true;
        if (key.endsWith("_block") || key.endsWith("_leaves") || key.endsWith("_log") || key.endsWith("_planks")) return false;
        for (String w : PLANTS) if (key.contains(w)) return true;
        return false;
    }

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

    @SuppressWarnings("unchecked")
    static String stateKey(Map<String, Object> entry)
    {
        String name = (String) entry.get("Name");
        if (seeThrough(name)) return null;
        Object props = entry.get("Properties");
        if (!(props instanceof Map) || ((Map<?, ?>) props).isEmpty()) return name;
        TreeMap<String, Object> sorted = new TreeMap<>((Map<String, Object>) props);
        StringBuilder b = new StringBuilder(name).append('[');
        boolean first = true;
        for (var e : sorted.entrySet())
        {
            if (!first) b.append(',');
            first = false;
            b.append(e.getKey()).append('=').append(e.getValue());
        }
        return b.append(']').toString();
    }

    /** A region's blocks in the bake band as global state ids, [x][y][z] flattened (x * H + y) * 512 + z. */
    @SuppressWarnings("unchecked")
    static short[] decodeRegion(Path file, int rx, int rz) throws IOException
    {
        short[] out = new short[512 * H * 512];
        try (RandomAccessFile raf = new RandomAccessFile(file.toFile(), "r"))
        {
            if (raf.length() < 8192) return out; // an empty region file (no header): no chunks
            for (int index = 0; index < 1024; index++)
            {
                int lx = index & 31, lz = index >> 5;
                int wx = rx * 512 + lx * 16, wz = rz * 512 + lz * 16;
                if (wx + 16 <= X0 || wx >= X1 || wz + 16 <= Z0 || wz >= Z1) continue;
                Map<String, Object> root = readChunk(raf, index);
                if (root == null) continue;
                Object level = root.get("Level");
                if (level instanceof Map) root = (Map<String, Object>) level;
                Object secs = root.containsKey("sections") ? root.get("sections") : root.get("Sections");
                if (!(secs instanceof List)) continue;
                for (Object so : (List<Object>) secs)
                {
                    Map<String, Object> s = (Map<String, Object>) so;
                    int sy = ((Number) s.get("Y")).intValue();
                    if (sy * 16 < Y0 || sy * 16 >= Y1) continue;
                    Map<String, Object> bs = (Map<String, Object>) s.get("block_states");
                    if (bs == null) continue;
                    List<Object> pal = (List<Object>) bs.get("palette");
                    if (pal == null || pal.isEmpty()) continue;
                    int[] ids = new int[pal.size()];
                    boolean any = false;
                    for (int i = 0; i < ids.length; i++)
                    {
                        String key = stateKey((Map<String, Object>) pal.get(i));
                        ids[i] = key == null ? 0 : stateId(key);
                        any |= ids[i] != 0;
                    }
                    if (!any) continue;
                    long[] data = (long[]) bs.get("data");
                    int bits = Math.max(4, 32 - Integer.numberOfLeadingZeros(pal.size() - 1));
                    int per = 64 / bits;
                    long mask = (1L << bits) - 1;
                    int ybase = sy * 16 - Y0;
                    for (int i = 0; i < 4096; i++)
                    {
                        int p = data == null ? 0 : (int) ((data[i / per] >>> ((i % per) * bits)) & mask);
                        int id = p < ids.length ? ids[p] : 0;
                        if (id == 0) continue;
                        int y = i >> 8, z = (i >> 4) & 15, x = i & 15;
                        int ax = lx * 16 + x, az = lz * 16 + z;
                        out[(ax * H + ybase + y) * 512 + az] = (short) id;
                    }
                }
            }
        }
        return out;
    }

    // ------------------------------------------------------------------ main

    record Region(int rx, int rz, Path file) {}

    static int cnx, cny, cnz;
    static boolean[] coarseSolid;
    static boolean[] cavity; // coarse, dilated by one cell

    public static void main(String[] args) throws Exception
    {
        Path dir = Path.of(args[0]);
        Path outFile = Path.of(args[1]);
        int threads = 6;
        for (int i = 2; i < args.length; i++) if (args[i].equals("--threads")) threads = Integer.parseInt(args[++i]);
        long began = System.nanoTime();
        List<Region> regions = new ArrayList<>();
        try (var list = Files.list(dir))
        {
            for (Path p : (Iterable<Path>) list::iterator)
            {
                String[] parts = p.getFileName().toString().split("\\.");
                if (parts.length != 4 || !parts[3].equals("mca")) continue;
                int rx = Integer.parseInt(parts[1]), rz = Integer.parseInt(parts[2]);
                if (rx * 512 >= X1 || rx * 512 + 512 <= X0 || rz * 512 >= Z1 || rz * 512 + 512 <= Z0) continue;
                regions.add(new Region(rx, rz, p));
            }
        }
        cnx = (GX1 - GX0) / COARSE;
        cnz = (GZ1 - GZ0) / COARSE;
        cny = H / COARSE;
        coarseSolid = new boolean[cnx * cny * cnz];
        // edge slabs EDGE blocks deep on each side of every region, for the faces and coarse cells at region seams
        Map<Long, short[][]> edges = new ConcurrentHashMap<>();
        ExecutorService pool = Executors.newFixedThreadPool(threads, r -> { Thread t = new Thread(r); t.setDaemon(true); return t; });
        List<Future<?>> jobs = new ArrayList<>();
        for (Region r : regions)
        {
            jobs.add(pool.submit(() -> {
                short[] v = decodeRegion(r.file, r.rx, r.rz);
                coarse(v, r.rx, r.rz);
                edges.put(key(r.rx, r.rz), slabs(v));
                return null;
            }));
        }
        for (Future<?> f : jobs) f.get();
        jobs.clear();
        System.out.printf("pass 1: %d regions, %d block states in %.0f s%n", regions.size(), names.size(), secs(began));
        cavity = largestAir();
        System.out.printf("cavity found in %.0f s%n", secs(began));

        Map<Long, byte[][]> tiles = new ConcurrentHashMap<>();
        AtomicLong[] counts = {new AtomicLong(), new AtomicLong(), new AtomicLong()};
        for (Region r : regions)
        {
            jobs.add(pool.submit(() -> {
                short[] v = decodeRegion(r.file, r.rx, r.rz);
                bakeRegion(v, r.rx, r.rz, edges, tiles, counts);
                return null;
            }));
        }
        for (Future<?> f : jobs) f.get();
        pool.shutdown();
        System.out.printf("pass 2: %d tiles; quads at 1/2/4 blocks: %d / %d / %d, in %.0f s%n", tiles.size(),
                counts[0].get(), counts[1].get(), counts[2].get(), secs(began));
        write(outFile, tiles);
        System.out.printf("wrote %s: %d bytes, %d block states, in %.0f s%n", outFile, Files.size(outFile), names.size(), secs(began));
    }

    static double secs(long began) { return (System.nanoTime() - began) / 1e9; }

    static long key(int a, int b) { return ((long) a << 32) ^ (b & 0xffffffffL); }

    static void coarse(short[] v, int rx, int rz)
    {
        int bx = rx * 512, bz = rz * 512;
        for (int cx = 0; cx < 512 / COARSE; cx++)
            for (int cz = 0; cz < 512 / COARSE; cz++)
            {
                int wx = bx + cx * COARSE, wz = bz + cz * COARSE;
                if (wx < GX0 || wx >= GX1 || wz < GZ0 || wz >= GZ1) continue;
                int gx = (wx - GX0) / COARSE, gz = (wz - GZ0) / COARSE;
                for (int cy = 0; cy < cny; cy++)
                {
                    int n = 0;
                    for (int x = 0; x < COARSE; x++)
                        for (int y = 0; y < COARSE; y++)
                        {
                            int base = ((cx * COARSE + x) * H + cy * COARSE + y) * 512 + cz * COARSE;
                            for (int z = 0; z < COARSE; z++) if (v[base + z] != 0) n++;
                        }
                    if (n >= 4) coarseSolid[(gx * cny + cy) * cnz + gz] = true;
                }
            }
    }

    /** [0] west (x = 0..EDGE-1), [1] east (x = 512-EDGE..511), [2] north (z = 0..), [3] south (z = 512-EDGE..). */
    static short[][] slabs(short[] v)
    {
        short[][] s = new short[4][EDGE * H * 512];
        for (int e = 0; e < EDGE; e++)
            for (int y = 0; y < H; y++)
                for (int t = 0; t < 512; t++)
                {
                    int i = (e * H + y) * 512 + t;
                    s[0][i] = v[(e * H + y) * 512 + t];
                    s[1][i] = v[((512 - EDGE + e) * H + y) * 512 + t];
                    s[2][i] = v[(t * H + y) * 512 + e];
                    s[3][i] = v[(t * H + y) * 512 + 512 - EDGE + e];
                }
        return s;
    }

    static boolean[] largestAir()
    {
        int n = cnx * cny * cnz;
        int[] label = new int[n];
        int[] queue = new int[n];
        int best = 0, bestSize = 0, next = 0;
        for (int start = 0; start < n; start++)
        {
            if (coarseSolid[start] || label[start] != 0) continue;
            next++;
            int head = 0, tail = 0, size = 0;
            queue[tail++] = start;
            label[start] = next;
            while (head < tail)
            {
                int c = queue[head++];
                size++;
                int z = c % cnz, y = (c / cnz) % cny, x = c / (cnz * cny);
                int[] nb = {x > 0 ? c - cny * cnz : -1, x < cnx - 1 ? c + cny * cnz : -1, y > 0 ? c - cnz : -1,
                        y < cny - 1 ? c + cnz : -1, z > 0 ? c - 1 : -1, z < cnz - 1 ? c + 1 : -1};
                for (int m : nb)
                    if (m >= 0 && !coarseSolid[m] && label[m] == 0)
                    {
                        label[m] = next;
                        queue[tail++] = m;
                    }
            }
            if (size > bestSize)
            {
                bestSize = size;
                best = next;
            }
        }
        boolean[] out = new boolean[n];
        for (int c = 0; c < n; c++)
        {
            if (label[c] != best) continue;
            int z = c % cnz, y = (c / cnz) % cny, x = c / (cnz * cny);
            for (int dx = -1; dx <= 1; dx++)
                for (int dy = -1; dy <= 1; dy++)
                    for (int dz = -1; dz <= 1; dz++)
                    {
                        int ax = x + dx, ay = y + dy, az = z + dz;
                        if (ax >= 0 && ax < cnx && ay >= 0 && ay < cny && az >= 0 && az < cnz) out[(ax * cny + ay) * cnz + az] = true;
                    }
        }
        System.out.printf("cavity: %d coarse cells of %d (%d air pieces)%n", bestSize, n, next);
        return out;
    }

    // ------------------------------------------------------------------ pass 2

    /** Block id at world (wx, y index, wz) inside this region or its neighbours' edge slabs; 0 outside. */
    static short at(short[] v, int rx, int rz, Map<Long, short[][]> edges, int wx, int y, int wz)
    {
        if (y < 0 || y >= H) return 0;
        int lx = wx - rx * 512, lz = wz - rz * 512;
        if (lx >= 0 && lx < 512 && lz >= 0 && lz < 512) return v[(lx * H + y) * 512 + lz];
        if (lz >= 0 && lz < 512)
        {
            if (lx < 0 && lx >= -EDGE) { short[][] e = edges.get(key(rx - 1, rz)); return e == null ? 0 : e[1][((lx + EDGE) * H + y) * 512 + lz]; }
            if (lx >= 512 && lx < 512 + EDGE) { short[][] e = edges.get(key(rx + 1, rz)); return e == null ? 0 : e[0][((lx - 512) * H + y) * 512 + lz]; }
        }
        if (lx >= 0 && lx < 512)
        {
            if (lz < 0 && lz >= -EDGE) { short[][] e = edges.get(key(rx, rz - 1)); return e == null ? 0 : e[3][((lz + EDGE) * H + y) * 512 + lx]; }
            if (lz >= 512 && lz < 512 + EDGE) { short[][] e = edges.get(key(rx, rz + 1)); return e == null ? 0 : e[2][((lz - 512) * H + y) * 512 + lx]; }
        }
        return 0; // diagonal corners: treated as air
    }

    static boolean cavityAir(int wx, int y, int wz)
    {
        if (wx < X0 || wx >= X1 || wz < Z0 || wz >= Z1 || y < 0 || y >= H) return false;
        int gx = (wx - GX0) / COARSE, gz = (wz - GZ0) / COARSE, gy = y / COARSE;
        return cavity[(gx * cny + gy) * cnz + gz];
    }

    static final int[][] DIR = {{-1, 0, 0}, {1, 0, 0}, {0, -1, 0}, {0, 1, 0}, {0, 0, -1}, {0, 0, 1}};

    static void bakeRegion(short[] v, int rx, int rz, Map<Long, short[][]> edges, Map<Long, byte[][]> tiles, AtomicLong[] counts)
    {
        for (int tx = 0; tx < 512 / TILE; tx++)
            for (int tz = 0; tz < 512 / TILE; tz++)
            {
                int wx0 = rx * 512 + tx * TILE, wz0 = rz * 512 + tz * TILE;
                if (wx0 + TILE <= X0 || wx0 >= X1 || wz0 + TILE <= Z0 || wz0 >= Z1) continue;
                // the tile with an EDGE border: ids and cavity air
                int S = TILE + 2 * EDGE;
                short[] id = new short[S * H * S];
                boolean[] air = new boolean[S * H * S];
                boolean anyFace = false;
                for (int x = 0; x < S; x++)
                    for (int z = 0; z < S; z++)
                        for (int y = 0; y < H; y++)
                        {
                            int wx = wx0 + x - EDGE, wz = wz0 + z - EDGE;
                            short b = at(v, rx, rz, edges, wx, y, wz);
                            int i = (x * H + y) * S + z;
                            id[i] = b;
                            air[i] = b == 0 && cavityAir(wx, y, wz);
                        }
                byte[][] levels = new byte[LEVELS.length][];
                long total = 0;
                for (int li = 0; li < LEVELS.length; li++)
                {
                    int L = LEVELS[li];
                    ByteArrayOutputStream bytes = new ByteArrayOutputStream();
                    int quads = faces(id, air, S, L, bytes, wx0, wz0);
                    counts[li].addAndGet(quads);
                    total += quads;
                    ByteArrayOutputStream wrapped = new ByteArrayOutputStream();
                    try
                    {
                        DataOutputStream d = new DataOutputStream(wrapped);
                        writeIntLE(d, quads);
                        bytes.writeTo(d);
                    }
                    catch (IOException impossible) { throw new RuntimeException(impossible); }
                    levels[li] = wrapped.toByteArray();
                }
                if (total > 0) tiles.put(key((wx0 - GX0) / TILE, (wz0 - GZ0) / TILE), levels);
            }
    }

    /** Faces of one tile at scale L, greedy-merged, appended as 11-byte quads; returns the count. */
    static int faces(short[] id, boolean[] air, int S, int L, ByteArrayOutputStream out, int wx0, int wz0)
    {
        // coarse grid over the tile plus one coarse cell of border on each side (EDGE >= L)
        int border = 1, n = TILE / L + 2 * border, ny = H / L;
        short[] cid = new short[n * ny * n];
        boolean[] csolid = new boolean[n * ny * n], cair = new boolean[n * ny * n];
        int off = EDGE - border * L; // tile-local voxel index of coarse cell 0
        Map<Integer, Integer> tally = new HashMap<>();
        for (int cx = 0; cx < n; cx++)
            for (int cz = 0; cz < n; cz++)
                for (int cy = 0; cy < ny; cy++)
                {
                    int solid = 0;
                    boolean anyAir = false;
                    tally.clear();
                    int bestExposed = 0, bestCount = 0, anySolid = 0;
                    for (int x = 0; x < L; x++)
                        for (int y = 0; y < L; y++)
                            for (int z = 0; z < L; z++)
                            {
                                int vx = off + cx * L + x, vy = cy * L + y, vz = off + cz * L + z;
                                int i = (vx * H + vy) * S + vz;
                                short b = id[i];
                                if (b == 0)
                                {
                                    anyAir |= air[i];
                                    continue;
                                }
                                solid++;
                                anySolid = b;
                                if (L == 1) continue;
                                // exposed: an in-tile neighbour is cavity air
                                boolean exposed = false;
                                for (int[] d : DIR)
                                {
                                    int ax = vx + d[0], ay = vy + d[1], az = vz + d[2];
                                    if (ax < 0 || ax >= S || az < 0 || az >= S || ay < 0 || ay >= H) continue;
                                    if (air[(ax * H + ay) * S + az]) { exposed = true; break; }
                                }
                                if (exposed)
                                {
                                    int c = tally.merge((int) b, 1, Integer::sum);
                                    if (c > bestCount) { bestCount = c; bestExposed = b; }
                                }
                            }
                    int ci = (cx * ny + cy) * n + cz;
                    if (solid > 0)
                    {
                        csolid[ci] = true;
                        cid[ci] = (short) (L == 1 ? anySolid : bestExposed != 0 ? bestExposed : anySolid);
                    }
                    else cair[ci] = anyAir;
                }
        int count = 0;
        // per face direction: label grids over each slice of the tile proper (coarse cells border..border+TILE/L-1)
        int m = TILE / L;
        for (int face = 0; face < 6; face++)
        {
            int axis = face / 2;
            int[] d = DIR[face];
            int slices = axis == 1 ? ny : m;
            int nu = axis == 0 ? ny : m;          // u: X faces y, Y faces x, Z faces x
            int nv = axis == 1 ? m : axis == 0 ? m : ny; // v: X faces z, Y faces z, Z faces y
            int[] grid = new int[nu * nv];
            for (int s = 0; s < slices; s++)
            {
                boolean any = false;
                for (int u = 0; u < nu; u++)
                    for (int w = 0; w < nv; w++)
                    {
                        int x, y, z;
                        if (axis == 0) { x = s; y = u; z = w; }
                        else if (axis == 1) { x = u; y = s; z = w; }
                        else { x = u; y = w; z = s; }
                        int cx = x + border, cz = z + border;
                        int ci = (cx * ny + y) * n + cz;
                        int label = 0;
                        if (csolid[ci])
                        {
                            int ax = cx + d[0], ay = y + d[1], az = cz + d[2];
                            if (ay >= 0 && ay < ny && cair[(ax * ny + ay) * n + az]) label = cid[ci];
                        }
                        grid[u * nv + w] = label;
                        any |= label != 0;
                    }
                if (!any) continue;
                // greedy rectangles
                for (int u = 0; u < nu; u++)
                    for (int w = 0; w < nv; w++)
                    {
                        int label = grid[u * nv + w];
                        if (label == 0) continue;
                        int du = 1;
                        while (u + du < nu && grid[(u + du) * nv + w] == label) du++;
                        int dv = 1;
                        outer:
                        while (w + dv < nv)
                        {
                            for (int k = 0; k < du; k++) if (grid[(u + k) * nv + w + dv] != label) break outer;
                            dv++;
                        }
                        for (int a = 0; a < du; a++) for (int b = 0; b < dv; b++) grid[(u + a) * nv + w + b] = 0;
                        int x, y, z;
                        if (axis == 0) { x = s; y = u; z = w; }
                        else if (axis == 1) { x = u; y = s; z = w; }
                        else { x = u; y = w; z = s; }
                        // stored extents: X faces (y, z) = (u, v); Y faces (x, z) = (u, v); Z faces (x, y) = (u, v)
                        out.write(x);
                        out.write(y & 0xFF);
                        out.write(y >>> 8);
                        out.write(z);
                        out.write(du & 0xFF);
                        out.write(du >>> 8);
                        out.write(dv & 0xFF);
                        out.write(dv >>> 8);
                        out.write(face);
                        int pal = label - 1;
                        out.write(pal & 0xFF);
                        out.write(pal >>> 8);
                        count++;
                    }
            }
        }
        return count;
    }

    static void writeIntLE(DataOutputStream d, int v) throws IOException
    {
        d.write(v);
        d.write(v >>> 8);
        d.write(v >>> 16);
        d.write(v >>> 24);
    }

    static void writeShortLE(DataOutputStream d, int v) throws IOException
    {
        d.write(v);
        d.write(v >>> 8);
    }

    static void write(Path file, Map<Long, byte[][]> tiles) throws IOException
    {
        if (names.size() > 65535) throw new IOException("too many block states " + names.size());
        try (DataOutputStream d = new DataOutputStream(new java.io.BufferedOutputStream(new GZIPOutputStream(Files.newOutputStream(file), 1 << 16))))
        {
            d.write("SGDM".getBytes(StandardCharsets.US_ASCII));
            d.write(2);
            d.write(TILE);
            writeIntLE(d, GX0);
            writeIntLE(d, Y0);
            writeIntLE(d, GZ0);
            writeShortLE(d, (GX1 - GX0) / TILE);
            writeShortLE(d, (GZ1 - GZ0) / TILE);
            writeShortLE(d, H);
            d.write(LEVELS.length);
            for (int l : LEVELS) d.write(l);
            writeIntLE(d, names.size());
            for (String name : names)
            {
                byte[] raw = name.getBytes(StandardCharsets.UTF_8);
                writeShortLE(d, raw.length);
                d.write(raw);
            }
            writeIntLE(d, tiles.size());
            List<Long> keys = new ArrayList<>(tiles.keySet());
            keys.sort(null);
            for (long k : keys)
            {
                writeShortLE(d, (int) (k >> 32));
                writeShortLE(d, (int) k);
                for (byte[] level : tiles.get(k)) d.write(level);
            }
        }
    }
}
