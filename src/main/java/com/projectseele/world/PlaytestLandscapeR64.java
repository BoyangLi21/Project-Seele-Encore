package com.projectseele.world;

import java.io.BufferedInputStream;
import java.io.DataInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.lang.ref.SoftReference;
import java.util.Arrays;
import java.util.zip.GZIPInputStream;

import net.minecraft.commands.arguments.blocks.BlockStateParser;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.chunk.ChunkAccess;
import net.minecraft.world.level.chunk.ChunkStatus;

/** Measured surface corrections for newly generated TV chunks. No level tick or existing chunk scan. */
final class PlaytestLandscapeR64
{
    private static final String ROOT = "/data/projectseele/worldgen/playtest_landscape_r64/";
    private static final int NONE = Short.MIN_VALUE;
    private static final Index INDEX = index();

    private PlaytestLandscapeR64() {}

    static boolean hasSurvey() { return INDEX.entries.length != 0; }

    static HakoneSurfaceField.Surface surface(int x, int z, HakoneSurfaceField.Surface original)
    {
        if (original == null) return null;
        Region region = INDEX.region(x >> 9, z >> 9);
        if (region == null) return original;
        Patch patch = region.data().chunks[((z >> 4) & 31) * 32 + ((x >> 4) & 31)];
        if (patch == null) return original;
        int local = (z & 15) * 16 + (x & 15);
        if (patch.profiles != null && patch.profiles[local] != null) return patch.profiles[local];
        if (patch.heights == null || original.water() > original.ground()) return original;
        int y = patch.heights[local];
        return y == NONE || y == original.ground() ? original : new HakoneSurfaceField.Surface(y, original.water());
    }

    /** The old surface recipe may have just restored a worn cliff or canopy edge. */
    static void decorate(ChunkAccess chunk)
    {
        if (chunk.getStatus().isOrAfter(ChunkStatus.FULL)) return;
        int cx = chunk.getPos().x, cz = chunk.getPos().z;
        Region region = INDEX.region(cx >> 5, cz >> 5);
        if (region == null) return;
        Data data = region.data();
        Patch patch = data.chunks[(cz & 31) * 32 + (cx & 31)];
        if (patch == null) return;
        BlockState[] states = data.states();
        BlockPos.MutableBlockPos cursor = new BlockPos.MutableBlockPos();
        for (Section section : patch.sections)
        {
            byte[] runs = section.runs;
            for (int at = 0; at < runs.length; at += 4)
            {
                int xz = Byte.toUnsignedInt(runs[at]), ends = Byte.toUnsignedInt(runs[at + 1]);
                BlockState old = states[Byte.toUnsignedInt(runs[at + 2])], placed = states[Byte.toUnsignedInt(runs[at + 3])];
                if (old == null || placed == null) continue;
                int x = (cx << 4) + (xz & 15), z = (cz << 4) + (xz >> 4);
                var lake = patch.profiles == null ? null : patch.profiles[xz];
                boolean sediment = placed.is(Blocks.GRAVEL) || placed.is(Blocks.STONE) || placed.is(Blocks.CLAY);
                for (int y = section.base + (ends >> 4); y <= section.base + (ends & 15); y++)
                {
                    cursor.set(x, y, z);
                    BlockState now = chunk.getBlockState(cursor);
                    if (now == placed || now.hasBlockEntity()) continue;
                    // Generated variants can differ in snowy soil or leaf distance. Authored
                    // facilities and unrelated blocks never qualify as a measured old state.
                    // The base generator gives a freshly surveyed lake a gravel bed.
                    boolean nativeBed = lake != null && lake.water() > lake.ground() && y == lake.ground() && sediment && now.is(Blocks.GRAVEL);
                    if (nativeBed || now.is(old.getBlock()) || (old.isAir() && now.isAir()))
                        chunk.setBlockState(cursor, placed, false);
                }
            }
        }
    }

    private record Section(int base, byte[] runs) {}
    private record Patch(short[] heights, Section[] sections, HakoneSurfaceField.Surface[] profiles) {}

    // These terrain journals contain contiguous source water from bed + 1 to the surface.
    // Decode the same profile for base-height queries and block generation.
    private static HakoneSurfaceField.Surface[] lakeColumns(Section[] sections, boolean[] water)
    {
        if (water == null) return null;
        HakoneSurfaceField.Surface[] lakes = null;
        for (Section section : sections)
        {
            byte[] runs = section.runs;
            for (int at = 0; at < runs.length; at += 4)
            {
                if (!water[Byte.toUnsignedInt(runs[at + 3])]) continue;
                if (lakes == null) lakes = new HakoneSurfaceField.Surface[256];
                int local = Byte.toUnsignedInt(runs[at]);
                int ends = Byte.toUnsignedInt(runs[at + 1]);
                int bed = section.base + (ends >> 4) - 1;
                int top = section.base + (ends & 15);
                var previous = lakes[local];
                if (previous != null)
                {
                    bed = Math.min(bed, previous.ground());
                    top = Math.max(top, previous.water());
                }
                lakes[local] = new HakoneSurfaceField.Surface(bed, top);
            }
        }
        return lakes;
    }

    private static final class Data
    {
        final String[] names;
        final Patch[] chunks = new Patch[1024];
        private volatile BlockState[] palette;

        Data(String[] names) { this.names = names; }

        BlockState[] states()
        {
            BlockState[] found = palette;
            if (found != null) return found;
            synchronized (this)
            {
                if (palette != null) return palette;
                found = new BlockState[names.length];
                try
                {
                    for (int i = 0; i < found.length; i++)
                    {
                        String state = names[i];
                        if (!state.startsWith("minecraft:") && !state.startsWith("projectseele:"))
                        {
                            // Optional ores can occur in the surveyed land. Skip just their
                            // edits when that block is absent from the installed mod pack.
                            ResourceLocation id = ResourceLocation.read(new com.mojang.brigadier.StringReader(state));
                            if (!BuiltInRegistries.BLOCK.containsKey(id)) continue;
                        }
                        found[i] = BlockStateParser.parseForBlock(BuiltInRegistries.BLOCK.asLookup(), state, false).blockState();
                    }
                }
                catch (com.mojang.brigadier.exceptions.CommandSyntaxException failure)
                {
                    throw new IllegalStateException("Invalid measured landscape block", failure);
                }
                return palette = found;
            }
        }
    }

    // A delta cannot describe water that was already in the old lake, or the
    // final dry ground on a filled inlet. Read the surveyed beds and banks last.
    private static void readShoreProfiles(Data data, int rx, int rz) throws IOException
    {
        String file = "/data/projectseele/worldgen/playtest_shores_r64/" + rx + "_" + rz + ".bin.gz";
        InputStream raw = PlaytestLandscapeR64.class.getResourceAsStream(file);
        if (raw == null) return;
        try (var in = new DataInputStream(new BufferedInputStream(new GZIPInputStream(raw))))
        {
            if (in.readInt() != 0x53485231) throw new IOException("Invalid shore profiles");
            int chunks = in.readUnsignedShort(), lastChunk = -1;
            for (int i = 0; i < chunks; i++)
            {
                int index = in.readUnsignedShort(), count = in.readUnsignedShort();
                if (index <= lastChunk || index >= 1024 || count < 1 || count > 256)
                    throw new IOException("Invalid shore chunk");
                lastChunk = index;
                Patch patch = data.chunks[index];
                var profiles = patch != null && patch.profiles != null ? patch.profiles : new HakoneSurfaceField.Surface[256];
                int lastPosition = -1;
                for (int j = 0; j < count; j++)
                {
                    int position = in.readUnsignedByte(), bed = in.readShort(), water = in.readShort();
                    if (position <= lastPosition || (water != NONE && water <= bed)) throw new IOException("Invalid surveyed shore column");
                    profiles[position] = new HakoneSurfaceField.Surface(bed, water);
                    lastPosition = position;
                }
                data.chunks[index] = patch == null ? new Patch(null, new Section[0], profiles) : new Patch(patch.heights, patch.sections, profiles);
            }
            if (in.read() != -1) throw new IOException("Trailing shore data");
        }
    }

    private static final class Region
    {
        final int x, z;
        private volatile SoftReference<Data> resident = new SoftReference<>(null);

        Region(int x, int z) { this.x = x; this.z = z; }

        Data data()
        {
            Data result = resident.get();
            if (result != null) return result;
            synchronized (this)
            {
                result = resident.get();
                if (result != null) return result;
                try (var in = new DataInputStream(new BufferedInputStream(new GZIPInputStream(open(x + "_" + z + ".bin.gz")))))
                {
                    int count = in.readUnsignedShort();
                    if (count < 1 || count > 255) throw new IOException("Invalid landscape palette");
                    String[] names = new String[count];
                    boolean[] water = null;
                    for (int i = 0; i < count; i++)
                    {
                        names[i] = in.readUTF();
                        if (names[i].equals("minecraft:water[level=0]") || names[i].equals("minecraft:water"))
                        {
                            if (water == null) water = new boolean[count];
                            water[i] = true;
                        }
                    }
                    result = new Data(names);
                    int chunks = in.readUnsignedShort();
                    for (int i = 0; i < chunks; i++)
                    {
                        int index = in.readUnsignedShort(), h = in.readUnsignedShort();
                        if (index >= 1024 || result.chunks[index] != null || h > 256) throw new IOException("Invalid landscape chunk");
                        short[] heights = null;
                        if (h > 0)
                        {
                            heights = new short[256];
                            Arrays.fill(heights, (short) NONE);
                            byte[] indices = new byte[h];
                            in.readFully(indices);
                            for (byte pos : indices) heights[Byte.toUnsignedInt(pos)] = in.readShort();
                        }
                        Section[] sections = new Section[in.readUnsignedByte()];
                        for (int s = 0; s < sections.length; s++)
                        {
                            int base = in.readByte() * 16;
                            byte[] runs = new byte[4 * in.readUnsignedShort()];
                            in.readFully(runs);
                            sections[s] = new Section(base, runs);
                        }
                        result.chunks[index] = new Patch(heights, sections, lakeColumns(sections, water));
                    }
                    if (in.read() != -1) throw new IOException("Trailing landscape data");
                    readShoreProfiles(result, x, z);
                }
                catch (IOException failure) { throw new IllegalStateException("Missing or invalid landscape region " + x + "," + z, failure); }
                resident = new SoftReference<>(result);
                return result;
            }
        }
    }

    private record Index(int west, int north, int width, int depth, Region[] entries)
    {
        Region region(int x, int z)
        {
            int i = x-west, j = z-north;
            return i < 0 || j < 0 || i >= width || j >= depth ? null : entries[j*width+i];
        }
    }

    private static InputStream open(String file) throws IOException
    {
        InputStream in = PlaytestLandscapeR64.class.getResourceAsStream(ROOT + file);
        if (in == null) throw new IOException("Missing landscape resource " + file);
        return in;
    }

    private static Index index()
    {
        InputStream index = PlaytestLandscapeR64.class.getResourceAsStream(ROOT + "index.bin");
        if (index == null) return new Index(0, 0, 0, 0, new Region[0]);
        try (var in = new DataInputStream(new BufferedInputStream(index)))
        {
            if (in.readInt() != 0x534c3634) throw new IOException("Invalid landscape format");
            Region[] regions = new Region[in.readUnsignedShort()];
            int minX = Integer.MAX_VALUE, minZ = Integer.MAX_VALUE, maxX = Integer.MIN_VALUE, maxZ = Integer.MIN_VALUE;
            for (int i = 0; i < regions.length; i++)
            {
                int x = in.readShort(), z = in.readShort();
                regions[i] = new Region(x, z);
                minX = Math.min(minX,x); maxX = Math.max(maxX,x);
                minZ = Math.min(minZ,z); maxZ = Math.max(maxZ,z);
            }
            int width = maxX-minX+1, depth = maxZ-minZ+1;
            if (regions.length == 0 || (long) width * depth > 65536 || in.read() != -1) throw new IOException("Invalid landscape index");
            Region[] map = new Region[width * depth];
            for (Region r : regions) map[(r.z-minZ)*width+r.x-minX] = r;
            return new Index(minX,minZ,width,depth,map);
        }
        catch (IOException failure) { throw new IllegalStateException("Cannot read the surveyed landscape index", failure); }
    }
}
