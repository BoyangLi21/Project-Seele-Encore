package com.projectseele.visual;

import com.google.gson.GsonBuilder;
import com.google.gson.JsonObject;
import com.projectseele.ProjectSeele;
import com.projectseele.world.FacilitySchemaV2;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.Property;
import net.minecraft.world.phys.AABB;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

import java.nio.file.Files;
import java.util.List;
import java.util.TreeMap;

/** Opt-in export of actual pinned MTR collision/outline states; no block mutations. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID)
public final class PublicStationGateShapesR44
{
    private static boolean written;
    private static int age;

    @SubscribeEvent
    public static void tick(TickEvent.ServerTickEvent event)
    {
        if (!Boolean.getBoolean("projectseele.r44PublicGateShapes") || written
                || event.phase != TickEvent.Phase.END || ++age < 40)
        {
            return;
        }
        var server = event.getServer();
        var root = server.getWorldPath(LevelResource.ROOT).normalize();
        if (!root.getFileName().toString().equals("SEELE_FIELD_R44_REVIEW"))
        {
            throw new IllegalStateException("Native public-gate shape export refuses non-review world");
        }
        var level = server.getLevel(FacilitySchemaV2.DIMENSION);
        if (level == null)
        {
            return;
        }
        try
        {
            var collisions = new TreeMap<String, List<double[]>>();
            var outlines = new TreeMap<String, List<double[]>>();
            for (String id : List.of("mtr:ticket_barrier_entrance_1", "mtr:ticket_barrier_exit_1"))
            {
                var key = new ResourceLocation(id);
                if (!BuiltInRegistries.BLOCK.containsKey(key))
                {
                    throw new IllegalStateException("Pinned native MTR gate absent: " + id);
                }
                var block = BuiltInRegistries.BLOCK.get(key);
                for (var state : block.getStateDefinition().getPossibleStates())
                {
                    var properties = new TreeMap<String, String>();
                    for (var property : state.getProperties())
                    {
                        properties.put(property.getName(), serialized(state, property));
                    }
                    String name = id + "[" + String.join(",", properties.entrySet().stream()
                            .map(entry -> entry.getKey() + "=" + entry.getValue()).toList()) + "]";
                    collisions.put(name, state.getCollisionShape(level, BlockPos.ZERO).toAabbs().stream()
                            .map(PublicStationGateShapesR44::box).toList());
                    outlines.put(name, state.getShape(level, BlockPos.ZERO).toAabbs().stream()
                            .map(PublicStationGateShapesR44::box).toList());
                }
            }
            var gson = new GsonBuilder().setPrettyPrinting().create();
            var result = new JsonObject();
            result.addProperty("source", "Actual pinned MTR 4.0.5 BlockState collision and outline; no cube fallback");
            result.add("collision_shapes", gson.toJsonTree(collisions));
            result.add("outline_shapes", gson.toJsonTree(outlines));
            result.addProperty("native_passage", "UNVERIFIED real opening/occupied refusal/exit/closing/cold reload");
            Files.writeString(root.resolve("r44_public_station_gate_shapes.json"), gson.toJson(result));
            written = true;
            ProjectSeele.LOGGER.info("R44 actual native public barrier states exported: {}; no world blocks changed", collisions.size());
        }
        catch (Exception failure)
        {
            written = true;
            ProjectSeele.LOGGER.error("Actual R44 MTR gate shapes unavailable", failure);
        }
    }

    private static double[] box(AABB box)
    {
        return new double[] {box.minX, box.minY, box.minZ, box.maxX, box.maxY, box.maxZ};
    }

    private static <T extends Comparable<T>> String serialized(BlockState state, Property<T> property)
    {
        return property.getName(state.getValue(property));
    }

    private PublicStationGateShapesR44() {}
}
