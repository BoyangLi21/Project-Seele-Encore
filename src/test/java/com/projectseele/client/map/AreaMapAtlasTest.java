package com.projectseele.client.map;

import com.google.gson.JsonParser;
import java.awt.image.BufferedImage;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import net.minecraft.server.packs.PackType;
import net.minecraft.server.packs.PathPackResources;
import net.minecraft.server.packs.resources.MultiPackResourceManager;
import net.minecraft.util.profiling.InactiveProfiler;

public final class AreaMapAtlasTest
{
    public static void main(String[] args) throws IOException
    {
        var bounds = new AreaMapLayer.Bounds(-400, -1000, -150, 600, 150, 250);
        var mask = new BufferedImage(2, 2, BufferedImage.TYPE_INT_ARGB);
        mask.setRGB(1, 0, 0x01010203);
        var bottom = new BufferedImage(2, 2, BufferedImage.TYPE_INT_RGB);
        var ceiling = new BufferedImage(2, 2, BufferedImage.TYPE_INT_RGB);
        bottom.setRGB(1, 0, (-471 + 32768) << 8);
        ceiling.setRGB(1, 0, (-431 + 32768) << 8);
        var layer = new AreaMapLayer("pyramid", "", bounds, 1, null, null, AreaMapLayer.Mask.from(mask),
                AreaMapLayer.Heights.from(bottom), AreaMapLayer.Heights.from(ceiling), null, -469, List.of());
        check(layer.selects(100.1, -471, -149.5), "inclusive floor and negative coordinates");
        check(!layer.selects(100.1, -471.1, -149.5), "below floor");
        check(!layer.selects(100.1, -431, -149.5), "exclusive ceiling");
        check(!layer.selects(99.99, -465, -149.5), "outside alpha footprint");
        check(!layer.selects(599.8, -465, 50.1), "south is positive z");
        check(!layer.selects(600, -465, -125), "exclusive max X");
        check(layer.fit(100, 100) == 0.1 && layer.fit(300, 100) == 0.25, "aspect ratio");
        check(layer.cursorHeight(100.1, -149.5) == -469 && layer.cursorHeight(99.99, -149.5) == Short.MAX_VALUE, "cursor respects floor and its mask");
        check(layer.overlapsView(610, 0, 20, 20) && !layer.overlapsView(620, 0, 20, 20), "underground backdrop releases after panning away");
        var surface = new AreaMapLayer("surface", "", bounds, 0, null, null, null, null, null, null, null, List.of());
        check(surface.nearSurfaceEdge(-399, 0) && !surface.nearSurfaceEdge(100, 0), "surface rim returns to navigation");
        check(!layer.nearSurfaceEdge(-399, 0), "rooms retain their plan at the door");

        // Private release PNGs can be tested through the same resource loader used on client reload.
        if (args.length > 0) checkRelease(Path.of(args[0]));
    }

    private static void checkRelease(Path root) throws IOException
    {
        var pack = new PathPackResources("area-map-check", root, false);
        try (var manager = new MultiPackResourceManager(PackType.CLIENT_RESOURCES, List.of(pack)))
        {
            var layers = new AreaMapAtlas().prepare(manager, InactiveProfiler.INSTANCE);
            try (var index = Files.newBufferedReader(root.resolve("assets/projectseele/area_maps/index.json")))
            {
                int declared = JsonParser.parseReader(index).getAsJsonObject().getAsJsonArray("layers").size();
                check(layers.size() == declared, "every declared layer loaded");
            }
            at(layers, 32.5, 81, 217.5, "surface");
            at(layers, 4160.5, -69, 1567.5, "surface");
            at(layers, 3994.5, -67, 1343.5, "un_hangars");
            at(layers, 500, -473, 256, "geofront");
            at(layers, 66, -554, 307, "pyramid_b1");
            at(layers, 66, -541, 307, "pyramid_lobby");
            at(layers, 66, -513, 307, "pyramid_research");
            at(layers, 66, -471, 307, "pyramid_upper_office");
            at(layers, 30.5, -1014, 355.5, "hangar_boarding");
            at(layers, -29.5, -987, 310.5, "hangar_observation");
            at(layers, 30.5, -1230, 246.5, "terminal_gate");
            at(layers, 30, -1264, 366, "terminal_lake");
            at(layers, -4000, -467, 300, "native");
            at(layers, 1800, -460, 1900, "native");
            var grass = layers.stream().filter(l -> l.id().equals("geofront")).findFirst().orElseThrow();
            var research = layers.stream().filter(l -> l.id().equals("pyramid_research")).findFirst().orElseThrow();
            check(grass.cursorHeight(500.5, 256.5) == -473, "surveyed grass waypoint height");
            check(research.cursorHeight(66.5, 307.5) == -513, "facility waypoint floor height");
            System.out.println("Validated " + layers.size() + " area map layers through the client resource loader.");
        }
    }

    private static void at(List<AreaMapLayer> layers, double x, double y, double z, String expected)
    {
        String current = layers.stream().filter(l -> l.selects(x, y, z)).findFirst().map(AreaMapLayer::id).orElse("native");
        check(current.equals(expected), x + ", " + y + ", " + z + " expected " + expected + ", got " + current);
    }

    private static void check(boolean value, String message) { if (!value) throw new AssertionError(message); }
}
