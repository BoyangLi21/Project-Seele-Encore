package com.projectseele.world;

import it.unimi.dsi.fastutil.longs.Long2ObjectOpenHashMap;
import java.io.ByteArrayOutputStream;
import java.util.Arrays;
import java.util.zip.DataFormatException;
import java.util.zip.Deflater;
import java.util.zip.Inflater;

/**
 * A set of block cells, one bit per cell in 16-cube sections, for a lookup in a collision sweep, and the compact form
 * the server sends it to clients in: the cells sorted, the gaps between them as variable-length numbers, deflated.
 * Holds no world: see StreetPassR64.
 */
public final class StreetPassCellsR64
{
    public static final StreetPassCellsR64 EMPTY = new StreetPassCellsR64(new Long2ObjectOpenHashMap<>(), 0,
            Integer.MAX_VALUE, Integer.MAX_VALUE, Integer.MAX_VALUE, Integer.MIN_VALUE, Integer.MIN_VALUE, Integer.MIN_VALUE);
    /** A clientbound payload stays under the channel's limit of one mebibyte with room for the rest of the message. */
    public static final int MAX_ENCODED = 900_000;

    private final Long2ObjectOpenHashMap<long[]> sections;
    private final int size, minX, minY, minZ, maxX, maxY, maxZ;

    private StreetPassCellsR64(Long2ObjectOpenHashMap<long[]> sections, int size, int minX, int minY, int minZ, int maxX, int maxY, int maxZ)
    {
        this.sections = sections;
        this.size = size;
        this.minX = minX;
        this.minY = minY;
        this.minZ = minZ;
        this.maxX = maxX;
        this.maxY = maxY;
        this.maxZ = maxZ;
    }

    private static long section(int x, int y, int z)
    {
        return ((long) (x >> 4) & 0x3FFFFFL) << 42 | ((long) (z >> 4) & 0x3FFFFFL) << 20 | (long) (y >> 4) & 0xFFFFFL;
    }

    private static int bit(int x, int y, int z)
    {
        return (y & 15) << 8 | (z & 15) << 4 | x & 15;
    }

    /** Cells as x, y, z triples; repeats count once. */
    public static StreetPassCellsR64 of(int[] xyz)
    {
        if (xyz.length % 3 != 0) throw new IllegalArgumentException("Cells come as x, y, z triples");
        if (xyz.length == 0) return EMPTY;
        var sections = new Long2ObjectOpenHashMap<long[]>();
        int size = 0, minX = Integer.MAX_VALUE, minY = Integer.MAX_VALUE, minZ = Integer.MAX_VALUE;
        int maxX = Integer.MIN_VALUE, maxY = Integer.MIN_VALUE, maxZ = Integer.MIN_VALUE;
        for (int i = 0; i < xyz.length; i += 3)
        {
            int x = xyz[i], y = xyz[i + 1], z = xyz[i + 2];
            long[] bits = sections.computeIfAbsent(section(x, y, z), key -> new long[64]);
            int b = bit(x, y, z);
            if ((bits[b >> 6] & 1L << b) != 0) continue;
            bits[b >> 6] |= 1L << b;
            size++;
            minX = Math.min(minX, x);
            minY = Math.min(minY, y);
            minZ = Math.min(minZ, z);
            maxX = Math.max(maxX, x);
            maxY = Math.max(maxY, y);
            maxZ = Math.max(maxZ, z);
        }
        return new StreetPassCellsR64(sections, size, minX, minY, minZ, maxX, maxY, maxZ);
    }

    public boolean contains(int x, int y, int z)
    {
        if (x < minX || x > maxX || y < minY || y > maxY || z < minZ || z > maxZ) return false;
        long[] bits = sections.get(section(x, y, z));
        if (bits == null) return false;
        int b = bit(x, y, z);
        return (bits[b >> 6] & 1L << b) != 0;
    }

    public int size()
    {
        return size;
    }

    public boolean isEmpty()
    {
        return size == 0;
    }

    public int sections()
    {
        return sections.size();
    }

    /** The cells as x, y, z triples in the order the compact form keeps them. */
    public int[] cells()
    {
        long[] packed = new long[size];
        int n = 0;
        for (var entry : sections.long2ObjectEntrySet())
        {
            long key = entry.getLongKey();
            int sx = (int) (key >> 42) << 10 >> 10, sz = (int) (key >> 20 & 0x3FFFFF) << 10 >> 10, sy = (int) (key & 0xFFFFF) << 12 >> 12;
            long[] bits = entry.getValue();
            for (int b = 0; b < 4096; b++)
                if ((bits[b >> 6] & 1L << b) != 0)
                    packed[n++] = pack(sx << 4 | b & 15, sy << 4 | b >> 8, sz << 4 | b >> 4 & 15);
        }
        Arrays.sort(packed);
        int[] xyz = new int[size * 3];
        for (int i = 0; i < size; i++)
        {
            xyz[i * 3] = (int) (packed[i] >> 38);
            xyz[i * 3 + 1] = (int) (packed[i] << 52 >> 52);
            xyz[i * 3 + 2] = (int) (packed[i] << 26 >> 38);
        }
        return xyz;
    }

    /** As BlockPos packs a position: x 26 bits, z 26 bits, y 12 bits, so that sorting keeps neighbours close. */
    private static long pack(int x, int y, int z)
    {
        return ((long) x & 0x3FFFFFFL) << 38 | ((long) z & 0x3FFFFFFL) << 12 | (long) y & 0xFFFL;
    }

    public byte[] encode()
    {
        int[] xyz = cells();
        var raw = new ByteArrayOutputStream(size * 3 + 8);
        varint(raw, size);
        long previous = 0;
        for (int i = 0; i < size; i++)
        {
            long packed = pack(xyz[i * 3], xyz[i * 3 + 1], xyz[i * 3 + 2]);
            varlong(raw, packed - previous);
            previous = packed;
        }
        var deflater = new Deflater(Deflater.BEST_COMPRESSION);
        deflater.setInput(raw.toByteArray());
        deflater.finish();
        var out = new ByteArrayOutputStream();
        byte[] buffer = new byte[8192];
        while (!deflater.finished()) out.write(buffer, 0, deflater.deflate(buffer));
        deflater.end();
        return out.toByteArray();
    }

    public static StreetPassCellsR64 decode(byte[] data)
    {
        if (data.length == 0) return EMPTY;
        var inflater = new Inflater();
        inflater.setInput(data);
        var raw = new ByteArrayOutputStream(data.length * 4);
        byte[] buffer = new byte[8192];
        try
        {
            while (!inflater.finished())
            {
                int n = inflater.inflate(buffer);
                if (n == 0 && (inflater.needsInput() || inflater.needsDictionary())) throw new IllegalArgumentException("Street pass cells cut short");
                raw.write(buffer, 0, n);
                if (raw.size() > 64 << 20) throw new IllegalArgumentException("Street pass cells too large");
            }
        }
        catch (DataFormatException failure)
        {
            throw new IllegalArgumentException("Street pass cells unreadable", failure);
        }
        finally
        {
            inflater.end();
        }
        byte[] bytes = raw.toByteArray();
        int[] at = {0};
        int count = (int) readVar(bytes, at);
        if (count < 0 || count > bytes.length) throw new IllegalArgumentException("Street pass cell count out of range");
        int[] xyz = new int[count * 3];
        long packed = 0;
        for (int i = 0; i < count; i++)
        {
            packed += readVar(bytes, at);
            xyz[i * 3] = (int) (packed >> 38);
            xyz[i * 3 + 1] = (int) (packed << 52 >> 52);
            xyz[i * 3 + 2] = (int) (packed << 26 >> 38);
        }
        if (at[0] != bytes.length) throw new IllegalArgumentException("Street pass cells have trailing bytes");
        return of(xyz);
    }

    private static void varint(ByteArrayOutputStream out, int value)
    {
        varlong(out, value & 0xFFFFFFFFL);
    }

    private static void varlong(ByteArrayOutputStream out, long value)
    {
        while ((value & ~0x7FL) != 0)
        {
            out.write((int) (value & 0x7F) | 0x80);
            value >>>= 7;
        }
        out.write((int) value);
    }

    private static long readVar(byte[] bytes, int[] at)
    {
        long value = 0;
        for (int shift = 0; shift < 70; shift += 7)
        {
            if (at[0] >= bytes.length) throw new IllegalArgumentException("Street pass cells cut short");
            int b = bytes[at[0]++] & 0xFF;
            value |= (long) (b & 0x7F) << shift;
            if ((b & 0x80) == 0) return value;
        }
        throw new IllegalArgumentException("Street pass cell number too long");
    }
}
