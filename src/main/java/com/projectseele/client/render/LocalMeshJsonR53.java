package com.projectseele.client.render;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.google.gson.stream.JsonReader;
import com.google.gson.stream.JsonToken;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.HashMap;
import java.util.Map;
import java.util.zip.CRC32;
import java.util.zip.CheckedInputStream;

/** Keeps authored skin metadata, without boxing millions of vertex scalars. */
final class LocalMeshJsonR53
{
    record Document(JsonObject metadata, Map<String, float[]> vertices,
                    Map<String, Map<String, float[]>> influences,
                    Map<String, float[]> pairWeights, long crc) {}

    static Document read(InputStream input) throws IOException
    {
        CRC32 crc = new CRC32();
        JsonObject root = new JsonObject();
        Map<String, float[]> vertices = new HashMap<>();
        Map<String, Map<String, float[]>> influences = new HashMap<>();
        Map<String, float[]> pairWeights = new HashMap<>();
        try (var reader = new JsonReader(new InputStreamReader(
                new CheckedInputStream(input, crc), StandardCharsets.UTF_8)))
        {
            reader.beginObject();
            while (reader.hasNext())
            {
                String name = reader.nextName();
                if (name.equals("jointSkins"))
                {
                    root.add(name, readSkins(reader, influences, pairWeights));
                    continue;
                }
                if (!name.equals("parts"))
                {
                    root.add(name, JsonParser.parseReader(reader));
                    continue;
                }
                JsonObject parts = new JsonObject();
                vertices.clear();
                reader.beginObject();
                while (reader.hasNext())
                {
                    String partName = reader.nextName();
                    JsonObject part = new JsonObject();
                    float[] values = null;
                    reader.beginObject();
                    while (reader.hasNext())
                    {
                        String field = reader.nextName();
                        if (field.equals("vertices")) values = readVertices(reader);
                        else part.add(field, JsonParser.parseReader(reader));
                    }
                    reader.endObject();
                    if (values == null) throw new IOException("Missing vertices: " + partName);
                    parts.add(partName, part);
                    vertices.put(partName, values);
                }
                reader.endObject();
                root.add(name, parts);
            }
            reader.endObject();
            if (reader.peek() != JsonToken.END_DOCUMENT)
                throw new IOException("Trailing local mesh data");
        }
        return new Document(root, Map.copyOf(vertices), Map.copyOf(influences),
                Map.copyOf(pairWeights), crc.getValue());
    }

    private static JsonObject readSkins(JsonReader reader,
            Map<String, Map<String, float[]>> influences,
            Map<String, float[]> pairWeights) throws IOException
    {
        JsonObject skins = new JsonObject();
        influences.clear();
        pairWeights.clear();
        reader.beginObject();
        while (reader.hasNext())
        {
            String name = reader.nextName();
            JsonObject skin = new JsonObject();
            reader.beginObject();
            while (reader.hasNext())
            {
                String field = reader.nextName();
                if (field.equals("influences"))
                {
                    Map<String, float[]> palette = new HashMap<>();
                    reader.beginObject();
                    while (reader.hasNext()) palette.put(reader.nextName(), readVertices(reader));
                    reader.endObject();
                    influences.put(name, Map.copyOf(palette));
                    skin.add(field, new JsonObject());
                }
                else if (field.equals("weights"))
                {
                    pairWeights.put(name, readVertices(reader));
                }
                else skin.add(field, JsonParser.parseReader(reader));
            }
            reader.endObject();
            skins.add(name, skin);
        }
        reader.endObject();
        return skins;
    }

    private static float[] readVertices(JsonReader reader) throws IOException
    {
        float[] values = new float[1024];
        int size = 0;
        reader.beginArray();
        while (reader.hasNext())
        {
            // Match JsonPrimitive.getAsFloat directly; nextDouble followed by
            // a cast can round differently at a float midpoint.
            float value = Float.parseFloat(reader.nextString());
            if (!Float.isFinite(value)) throw new IOException("Non-finite vertex");
            if (size == values.length) values = Arrays.copyOf(values, size * 2);
            values[size++] = value;
        }
        reader.endArray();
        return Arrays.copyOf(values, size);
    }

    private LocalMeshJsonR53() {}
}
