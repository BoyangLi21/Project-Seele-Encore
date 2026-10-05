package com.projectseele.world;

import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.HashSet;
import java.util.TreeSet;
import net.minecraft.SharedConstants;
import net.minecraft.commands.arguments.blocks.BlockStateParser;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.NbtUtils;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.shapes.CollisionContext;
import net.minecraftforge.event.level.LevelEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** One bounded native input capture; no registry enumeration, actors, or world writes. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID)
public final class NativeCollisionInputsR47
{
    private static final String INPUT = System.getProperty("projectseele.nativeCollisionInputsR47", "");
    private static final String OUTPUT = System.getProperty("projectseele.nativeCollisionOutputR47", "");
    private static boolean attempted;

    private NativeCollisionInputsR47() {}

    @SubscribeEvent
    public static void load(LevelEvent.Load event)
    {
        if (attempted || INPUT.isBlank() || !(event.getLevel() instanceof ServerLevel level)
                || !level.dimension().equals(FacilitySchemaV2.DIMENSION)) return;
        attempted = true;
        try
        {
            if (OUTPUT.isBlank()) throw new IllegalArgumentException("R47 collision output property is required");
            Path input = Path.of(INPUT).toAbsolutePath();
            JsonObject request = JsonParser.parseString(Files.readString(input, StandardCharsets.UTF_8)).getAsJsonObject();
            if (!"projectseele.r47.exact-native-collision-capture-request.v1".equals(request.get("schema").getAsString()))
                throw new IllegalArgumentException("Foreign R47 collision input schema");
            JsonArray states = request.getAsJsonArray("states");
            if (states.size() < 1 || states.size() > 32) throw new IllegalArgumentException("Only 1..32 explicitly requested states are allowed");
            JsonObject shapes = new JsonObject();
            JsonArray traits = new JsonArray();
            var seen = new HashSet<String>();
            for (var raw : states)
            {
                String requested = raw.getAsString();
                BlockState state = exactState(requested);
                String key = canonical(BlockStateParser.serialize(state));
                if (!seen.add(key)) throw new IllegalArgumentException("Duplicate collision input: " + key);
                JsonArray boxes = new JsonArray();
                for (var box : state.getCollisionShape(level, BlockPos.ZERO, CollisionContext.empty()).toAabbs())
                {
                    JsonArray values = new JsonArray();
                    for (double value : new double[]{box.minX, box.minY, box.minZ, box.maxX, box.maxY, box.maxZ}) values.add(value);
                    boxes.add(values);
                }
                shapes.add(key, boxes);
                JsonObject trait = new JsonObject();
                trait.addProperty("state", key);
                trait.addProperty("registry_block", BuiltInRegistries.BLOCK.getKey(state.getBlock()).toString());
                trait.addProperty("block_class", state.getBlock().getClass().getName());
                trait.addProperty("has_block_entity", state.hasBlockEntity());
                trait.addProperty("air", state.isAir());
                traits.add(trait);
            }
            JsonObject report = new JsonObject();
            report.addProperty("schema", "projectseele.r47.exact-native-collision-capture.v1");
            report.addProperty("minecraft_version", SharedConstants.getCurrentVersion().getName());
            report.addProperty("dimension", level.dimension().location().toString());
            report.addProperty("input", input.toString());
            report.addProperty("state_count", shapes.size());
            report.addProperty("collision_context", "empty; actual ServerLevel at BlockPos.ZERO; block-local AABBs");
            report.addProperty("world_written", false);
            report.add("registry_traits", traits);
            Path output = Path.of(OUTPUT).toAbsolutePath();
            write(output, shapes);
            write(output.resolveSibling(output.getFileName() + ".traits.json"), report);
            ProjectSeele.LOGGER.info("R47 captured {} requested native collision states at {}", shapes.size(), output);
        }
        catch (Exception failure)
        {
            ProjectSeele.LOGGER.error("R47 bounded native collision input capture failed; no partial shape file produced", failure);
        }
    }

    private static BlockState exactState(String text)
    {
        int start = text.indexOf('[');
        String name = start < 0 ? text : text.substring(0, start);
        ResourceLocation id = new ResourceLocation(name);
        if (!BuiltInRegistries.BLOCK.containsKey(id)) throw new IllegalArgumentException("Unknown registered block: " + name);
        CompoundTag tag = new CompoundTag();
        tag.putString("Name", name);
        if (start >= 0)
        {
            if (!text.endsWith("]")) throw new IllegalArgumentException("Malformed state: " + text);
            CompoundTag properties = new CompoundTag();
            for (String pair : text.substring(start + 1, text.length() - 1).split(","))
            {
                String[] parts = pair.split("=", -1);
                if (parts.length != 2 || properties.contains(parts[0])) throw new IllegalArgumentException("Malformed state property: " + pair);
                properties.putString(parts[0], parts[1]);
            }
            tag.put("Properties", properties);
        }
        BlockState state = NbtUtils.readBlockState(BuiltInRegistries.BLOCK.asLookup(), tag);
        if (!canonical(BlockStateParser.serialize(state)).equals(canonical(text)))
            throw new IllegalArgumentException("Native registry rejected or defaulted a requested property: " + text);
        return state;
    }

    private static String canonical(String state)
    {
        int start = state.indexOf('[');
        if (start < 0) return state;
        var properties = new TreeSet<String>();
        java.util.Collections.addAll(properties, state.substring(start + 1, state.length() - 1).split(","));
        return state.substring(0, start) + "[" + String.join(",", properties) + "]";
    }

    private static void write(Path path, JsonObject content) throws Exception
    {
        Files.createDirectories(path.getParent());
        Path temporary = path.resolveSibling(path.getFileName() + ".tmp");
        Files.writeString(temporary, new GsonBuilder().setPrettyPrinting().create().toJson(content), StandardCharsets.UTF_8);
        Files.move(temporary, path, StandardCopyOption.REPLACE_EXISTING);
    }
}
