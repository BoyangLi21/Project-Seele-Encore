import java.io.File;
import java.io.PrintWriter;
import java.io.RandomAccessFile;
import java.util.Arrays;
import java.util.List;
import java.util.Map;

/** Writes surveyed black support runs at the headquarters office level as X Z bottom top floor floorType capType.
 * Compile beside BakeGeoFrontFarViewR65.java, then pass the GeoFront region directory and the output file.
 */
public final class ScanGeoFrontColumnFeetR65 {
    private static final String BLACK = "minecraft:black_concrete";
    private static final String AIR = "minecraft:air";
    private static final int FIRST_SECTION = -32;

    private static String block(String[][] grid, int column, int y) {
        String[] section = grid[(y >> 4) - FIRST_SECTION];
        return section == null ? AIR : section[(y & 15) * 256 + column];
    }

    private static boolean air(String name) {
        return name.equals(AIR) || name.endsWith("_air");
    }

    @SuppressWarnings("unchecked")
    private static void scan(Map<String, Object> chunk, int cx, int cz, PrintWriter out) {
        String[][] grid = new String[4][];
        boolean containsPost = false;
        for (var section : (List<Map<String, Object>>) chunk.get("sections")) {
            int index = ((Number) section.get("Y")).intValue() - FIRST_SECTION;
            if (index < 0 || index >= grid.length) continue;
            var states = (Map<String, Object>) section.get("block_states");
            if (states == null) continue;
            var palette = (List<Map<String, Object>>) states.get("palette");
            String[] names = palette.stream().map(p -> (String) p.get("Name")).toArray(String[]::new);
            containsPost |= Arrays.asList(names).contains(BLACK);
            String[] cells = grid[index] = new String[4096];
            long[] words = (long[]) states.get("data");
            if (words == null) {
                Arrays.fill(cells, names[0]);
            } else {
                int width = Math.max(4, 32 - Integer.numberOfLeadingZeros(names.length - 1));
                int perWord = 64 / width, mask = (1 << width) - 1;
                for (int i = 0; i < cells.length; i++) {
                    int shift = i % perWord * width;
                    cells[i] = names[(int) (words[i / perWord] >>> shift) & mask];
                }
            }
        }
        if (!containsPost) return;
        for (int column = 0; column < 256; column++) {
            for (int y = -488; y <= -474; y++) {
                if (!air(block(grid, column, y - 1)) || !BLACK.equals(block(grid, column, y))
                        || !BLACK.equals(block(grid, column, y + 1)) || !BLACK.equals(block(grid, column, y + 2))) continue;
                int floor = y - 1, top = y + 2;
                while (floor > y - 18 && air(block(grid, column, floor))) floor--;
                while (top < -451 && BLACK.equals(block(grid, column, top + 1))) top++;
                out.printf("%d %d %d %d %d %s %s%n", cx * 16 + column % 16, cz * 16 + column / 16,
                        y, top, floor, block(grid, column, floor), block(grid, column, top + 1));
            }
        }
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 2) throw new IllegalArgumentException("Expected region directory and output file");
        File[] regions = new File(args[0]).listFiles((dir, name) -> name.matches("r\\.-?\\d+\\.-?\\d+\\.mca"));
        if (regions == null) throw new IllegalArgumentException("Missing region directory");
        Arrays.sort(regions);
        int chunks = 0;
        try (PrintWriter out = new PrintWriter(args[1])) {
            for (File region : regions) {
                String[] parts = region.getName().split("\\.");
                int rx = Integer.parseInt(parts[1]), rz = Integer.parseInt(parts[2]);
                int dx = Math.max(0, Math.abs(rx * 512 + 256 - 30) - 256);
                int dz = Math.max(0, Math.abs(rz * 512 + 256 - 296) - 256);
                if (Math.hypot(dx, dz) > 1900) continue;
                try (RandomAccessFile file = new RandomAccessFile(region, "r")) {
                    for (int index = 0; index < 1024; index++) {
                        var chunk = BakeGeoFrontFarViewR65.readChunk(file, index);
                        if (chunk == null) continue;
                        scan(chunk, rx * 32 + index % 32, rz * 32 + index / 32, out);
                        chunks++;
                    }
                }
            }
            if (out.checkError()) throw new java.io.IOException("Failed to write survey");
        }
        System.out.println("Scanned chunks: " + chunks);
    }
}
