package com.projectseele.client.render;

import com.google.gson.JsonParser;
import java.io.ByteArrayInputStream;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.zip.CRC32;
import java.util.zip.ZipFile;

public final class LocalMeshJsonR53Test
{
    private static void compare(String name, byte[] bytes) throws Exception
    {
        var bean = (com.sun.management.ThreadMXBean)
                java.lang.management.ManagementFactory.getThreadMXBean();
        long thread = Thread.currentThread().getId();
        long before = bean.getThreadAllocatedBytes(thread);
        var root = JsonParser.parseString(new String(bytes, StandardCharsets.UTF_8))
                .getAsJsonObject();
        var expected = new HashMap<String, float[]>();
        for (var entry : root.getAsJsonObject("parts").entrySet())
        {
            var array = entry.getValue().getAsJsonObject().remove("vertices").getAsJsonArray();
            float[] values = new float[array.size()];
            for (int i = 0; i < values.length; i++) values[i] = array.get(i).getAsFloat();
            expected.put(entry.getKey(), values);
        }
        long oldBytes = bean.getThreadAllocatedBytes(thread) - before;
        before = bean.getThreadAllocatedBytes(thread);
        var actual = LocalMeshJsonR53.read(new ByteArrayInputStream(bytes));
        long newBytes = bean.getThreadAllocatedBytes(thread) - before;
        CRC32 crc = new CRC32();
        crc.update(bytes);
        if (crc.getValue() != actual.crc() || !root.equals(actual.metadata())
                || !expected.keySet().equals(actual.vertices().keySet()))
            throw new AssertionError("Mesh metadata/checksum changed: " + name);
        long count = 0;
        for (var entry : expected.entrySet())
        {
            float[] a = entry.getValue(), b = actual.vertices().get(entry.getKey());
            if (a.length != b.length) throw new AssertionError("Vertex count: " + name);
            for (int i = 0; i < a.length; i++)
                if (Float.floatToRawIntBits(a[i]) != Float.floatToRawIntBits(b[i]))
                    throw new AssertionError("Vertex changed: " + name + "/" + entry.getKey() + "/" + i);
            count += a.length;
        }
        System.out.printf("%s: %,d scalars identical; allocated reference=%,d streaming=%,d bytes%n",
                name, count, oldBytes, newBytes);
    }

    public static void main(String[] args) throws Exception
    {
        compare("field order, float rounding, unknown skin metadata", ("""
                {"parts":{"root":{"vertices":[-0.0,1e-45,1.0000000596046448,3.4028235e38],
                "pivot":[0,0,0],"tint":[0.5,1,0.7]}},"stride":8,
                "jointSkins":{"root":{"future":{"flag":true,"weights":[0,0.5,1]}}}}
                """).getBytes(StandardCharsets.UTF_8));
        for (String invalid : new String[]{"NaN", "Infinity", "1e1000"})
        {
            byte[] bytes = ("{\"parts\":{\"root\":{\"vertices\":[\"" + invalid
                    + "\"]}}}").getBytes(StandardCharsets.UTF_8);
            try
            {
                LocalMeshJsonR53.read(new ByteArrayInputStream(bytes));
                throw new AssertionError("Accepted non-finite vertex: " + invalid);
            }
            catch (java.io.IOException expected) {}
        }
        if (args.length > 0)
        {
            try (var zip = new ZipFile(args[0]))
            {
                for (int i = 1; i < args.length; i++)
                    try (var input = zip.getInputStream(zip.getEntry(args[i])))
                    {
                        compare(args[i], input.readAllBytes());
                    }
            }
        }
    }
}
