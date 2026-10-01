package com.projectseele.world;

import com.google.gson.JsonParser;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.zip.GZIPInputStream;

/** Exact authored columns shared by the existing-world patch and future terrain. */
final class TvAuthoredTerrainR44
{
    private static final int MIN_X = 720, MAX_X = 1080, MIN_Z = 560, MAX_Z = 940;
    private static final int WIDTH = MAX_X - MIN_X + 1;
    private static final String RESOURCE = "/data/projectseele/worldgen/authored/geofront_east_ranges_r44.json.gz";

    private static final class Data
    {
        private static final short[] HEIGHTS = load();
    }

    static int ground(int x, int z, int original)
    {
        if (x < MIN_X || x > MAX_X || z < MIN_Z || z > MAX_Z) return original;
        int value = Data.HEIGHTS[(z - MIN_Z) * WIDTH + x - MIN_X];
        return value == Short.MIN_VALUE ? original : value;
    }

    private static short[] load()
    {
        short[] values = new short[WIDTH * (MAX_Z - MIN_Z + 1)];
        Arrays.fill(values, Short.MIN_VALUE);
        try (var raw = TvAuthoredTerrainR44.class.getResourceAsStream(RESOURCE))
        {
            if (raw == null) throw new IllegalStateException("Missing authored GeoFront height field");
            try (var reader = new InputStreamReader(new GZIPInputStream(raw), StandardCharsets.UTF_8))
            {
                var data = JsonParser.parseReader(reader).getAsJsonObject();
                if (!data.get("format").getAsString().equals("r44_absolute_eligible_ground_v1"))
                    throw new IllegalStateException("Unknown authored GeoFront format");
                var bounds = data.getAsJsonArray("bounds");
                int[] expected = {MIN_X, MIN_Z, MAX_X, MAX_Z};
                if (bounds.size() != expected.length) throw new IllegalStateException("Invalid terrain bounds");
                for (int i = 0; i < expected.length; i++)
                    if (bounds.get(i).getAsInt() != expected[i]) throw new IllegalStateException("Terrain bounds changed");
                var columns = data.getAsJsonArray("columns");
                if (columns.isEmpty() || columns.size() > values.length) throw new IllegalStateException("Invalid terrain coverage");
                for (var item : columns)
                {
                    var column = item.getAsJsonArray();
                    if (column.size() != 3) throw new IllegalStateException("Invalid terrain column");
                    int x = column.get(0).getAsInt(), z = column.get(1).getAsInt(), y = column.get(2).getAsInt();
                    if (x < MIN_X || x > MAX_X || z < MIN_Z || z > MAX_Z || y < -530 || y > -350
                            || y > TvWorldPreviewTerrain.roof(x, z) - 24
                            || Math.hypot(x - TvWorldPreviewTerrain.CENTRE_X, z - TvWorldPreviewTerrain.CENTRE_Z) < 650)
                        throw new IllegalStateException("Authored terrain exceeds protected cavern envelope");
                    int index = (z - MIN_Z) * WIDTH + x - MIN_X;
                    if (values[index] != Short.MIN_VALUE) throw new IllegalStateException("Duplicate authored terrain column");
                    values[index] = (short) y;
                }
            }
            return values;
        }
        catch (Exception failure)
        {
            throw new IllegalStateException("Could not load the exact authored GeoFront terrain", failure);
        }
    }

    private TvAuthoredTerrainR44() { }
}
