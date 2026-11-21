package com.projectseele.client.map;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import java.awt.image.BufferedImage;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import javax.imageio.ImageIO;
import net.minecraft.client.Minecraft;
import net.minecraft.resources.ResourceKey;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.packs.resources.ResourceManager;
import net.minecraft.server.packs.resources.SimplePreparableReloadListener;
import net.minecraft.util.profiling.ProfilerFiller;
import net.minecraft.world.level.Level;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.RegisterClientReloadListenersEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, value = Dist.CLIENT, bus = Mod.EventBusSubscriber.Bus.MOD)
public final class AreaMapAtlas extends SimplePreparableReloadListener<List<AreaMapLayer>>
{
    private static final ResourceLocation INDEX = new ResourceLocation("projectseele", "area_maps/index.json");
    private static final ResourceLocation DIMENSION = new ResourceLocation("projectseele", "geofront");
    private static volatile List<AreaMapLayer> layers = List.of();

    @SubscribeEvent public static void register(RegisterClientReloadListenersEvent event)
    {
        event.registerReloadListener(new AreaMapAtlas());
    }

    @Override protected List<AreaMapLayer> prepare(ResourceManager manager, ProfilerFiller profiler)
    {
        var file = manager.getResource(INDEX);
        if (file.isEmpty()) return List.of();
        var layers = new ArrayList<AreaMapLayer>();
        Map<ResourceLocation, AreaMapLayer.Mask> masks = new HashMap<>();
        Map<ResourceLocation, AreaMapLayer.Heights> heights = new HashMap<>();
        try (var reader = file.get().openAsReader())
        {
            var index = JsonParser.parseReader(reader).getAsJsonObject();
            if (index.get("schema").getAsInt() != 1 || !DIMENSION.toString().equals(index.get("dimension").getAsString()))
                throw new IOException("Unexpected area map schema or dimension");
            for (var entry : index.getAsJsonArray("layers"))
            {
                try
                {
                    var row = entry.getAsJsonObject();
                    var texture = location(row, "texture");
                    if (texture == null || manager.getResource(texture).isEmpty()) throw new IOException("Missing " + texture);
                    var preview = location(row, "preview");
                    if (preview == null || manager.getResource(preview).isEmpty()) preview = texture;
                    var zones = new ArrayList<AreaMapLayer.Bounds>();
                    if (row.has("zones")) for (var zone : row.getAsJsonArray("zones")) zones.add(bounds(zone.getAsJsonObject()));
                    var mask = location(row, "mask");
                    if (mask != null && !masks.containsKey(mask)) masks.put(mask, AreaMapLayer.Mask.from(image(manager, mask)));
                    var bottom = location(row, "bottom");
                    var ceiling = location(row, "ceiling");
                    var ground = location(row, "ground");
                    Integer floorY = row.has("floorY") ? row.get("floorY").getAsInt() : null;
                    for (var path : new ResourceLocation[]{bottom, ceiling, ground})
                        if (path != null && !heights.containsKey(path)) heights.put(path, AreaMapLayer.Heights.from(image(manager, path)));
                    var area = bounds(row);
                    AreaMapLayer.Bounds hudFrame = null;
                    if (row.has("hudFrame"))
                    {
                        var f = row.getAsJsonObject("hudFrame");
                        hudFrame = new AreaMapLayer.Bounds(f.get("minX").getAsInt(), area.minY(), f.get("minZ").getAsInt(),
                                f.get("maxX").getAsInt(), area.maxY(), f.get("maxZ").getAsInt());
                        if (hudFrame.minX() < area.minX() || hudFrame.maxX() > area.maxX()
                                || hudFrame.minZ() < area.minZ() || hudFrame.maxZ() > area.maxZ()) hudFrame = null;
                    }
                    layers.add(new AreaMapLayer(row.get("id").getAsString(), row.get("label").getAsString(), area,
                            row.get("priority").getAsInt(), texture, preview, masks.get(mask), heights.get(bottom),
                            heights.get(ceiling), heights.get(ground), floorY, List.copyOf(zones), hudFrame));
                }
                catch (RuntimeException | IOException invalid)
                {
                    ProjectSeele.LOGGER.warn("Skipping invalid area map {}", entry, invalid);
                }
            }
        }
        catch (IOException | RuntimeException invalid)
        {
            ProjectSeele.LOGGER.warn("Could not read area map index {}", INDEX, invalid);
            return List.of();
        }
        layers.sort(Comparator.comparingInt(AreaMapLayer::priority).reversed());
        return List.copyOf(layers);
    }

    private static AreaMapLayer.Bounds bounds(JsonObject o)
    {
        return new AreaMapLayer.Bounds(o.get("minX").getAsInt(), o.get("minY").getAsInt(), o.get("minZ").getAsInt(),
                o.get("maxX").getAsInt(), o.get("maxY").getAsInt(), o.get("maxZ").getAsInt());
    }

    private static ResourceLocation location(JsonObject o, String key)
    {
        JsonElement element = o.get(key);
        return element == null || element.isJsonNull() ? null : new ResourceLocation(element.getAsString());
    }

    private static BufferedImage image(ResourceManager manager, ResourceLocation name) throws IOException
    {
        try (var stream = manager.open(name))
        {
            var image = ImageIO.read(stream);
            if (image == null) throw new IOException("Unreadable PNG " + name);
            return image;
        }
    }

    @Override protected void apply(List<AreaMapLayer> prepared, ResourceManager manager, ProfilerFiller profiler)
    {
        layers = prepared;
        if (!prepared.isEmpty()) ProjectSeele.LOGGER.info("Loaded {} GeoFront area map layers", prepared.size());
    }

    public static AreaMapLayer current(ResourceKey<Level> viewedDimension)
    {
        Minecraft mc = Minecraft.getInstance();
        if (mc.player == null || mc.level == null || !DIMENSION.equals(mc.level.dimension().location())
                || viewedDimension == null || !DIMENSION.equals(viewedDimension.location())) return null;
        var player = mc.player;
        for (AreaMapLayer layer : layers)
            if (layer.selects(player.getX(), player.getY(), player.getZ()))
                return layer.nearSurfaceEdge(player.getX(), player.getZ()) ? null : layer;
        return null;
    }
}
