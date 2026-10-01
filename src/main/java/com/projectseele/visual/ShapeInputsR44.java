package com.projectseele.visual;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import net.minecraft.commands.arguments.blocks.BlockStateParser;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.level.block.Blocks;
import net.minecraftforge.registries.ForgeRegistries;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.TreeSet;

/** Re-measures known native states; never inherits old collision-box values. */
final class ShapeInputsR44
{
    static JsonArray current(Path world, JsonArray regional) throws java.io.IOException
    {
        var states=new TreeSet<String>();
        for(var entry:regional)states.add(entry.getAsString());
        int regionalCount=states.size();
        Path previous=world.resolve("native_collision_shapes.json");
        if(Files.isRegularFile(previous))
            states.addAll(JsonParser.parseString(Files.readString(previous)).getAsJsonObject().keySet());
        int inheritedKeys=states.size()-regionalCount;
        // R44 adds door, access and facade states after the old regional
        // palette was frozen. Enumerate their real registered definitions.
        for(var block:ForgeRegistries.BLOCKS.getValues())
        {
            var name=ForgeRegistries.BLOCKS.getKey(block);
            if(name!=null&&name.getNamespace().equals("projectseele"))
                for(var state:block.getStateDefinition().getPossibleStates())
                    states.add(BlockStateParser.serialize(state));
        }
        // Inspect the pinned transit mod's actual sign geometry before any
        // candidate is placed. The registry, not its JSON render model or a
        // full-cube fallback, defines passenger clearance.
        for(String name:java.util.List.of("mtr:route_sign_wall_light",
                "mtr:route_sign_standing_light","mtr:psd_top"))
        {
            var block=ForgeRegistries.BLOCKS.getValue(new ResourceLocation(name));
            if(block==null||block==Blocks.AIR)throw new IllegalStateException("Missing pinned native station sign: "+name);
            for(var state:block.getStateDefinition().getPossibleStates())
                states.add(BlockStateParser.serialize(state));
        }
        Path gates=world.resolve("r44_public_station_gates.json");
        if(Files.isRegularFile(gates))
        {
            var root=JsonParser.parseString(Files.readString(gates));
            var rows=root.isJsonArray()?root.getAsJsonArray():root.getAsJsonObject().getAsJsonArray("gates");
            if(rows==null)throw new IllegalStateException("Finite gate manifest lacks its actual gate list");
            var names=new TreeSet<String>();
            for(var entry:rows)names.add(entry.getAsJsonObject().get("block").getAsString());
            for(String name:names)
            {
                var block=ForgeRegistries.BLOCKS.getValue(new ResourceLocation(name));
                if(block==null||block==Blocks.AIR)throw new IllegalStateException("Missing native gate block: "+name);
                for(var state:block.getStateDefinition().getPossibleStates())
                    states.add(BlockStateParser.serialize(state));
            }
        }
        var result=new JsonArray();states.forEach(result::add);
        var record=new JsonObject();record.addProperty("regional_input_count",regionalCount);
        record.addProperty("additional_previous_state_keys",inheritedKeys);
        record.addProperty("current_registered_state_count",states.size());
        record.addProperty("old_shape_values_copied",false);
        record.addProperty("scope","Current native collision shapes only; motor movement, equipment lifecycle and art are separate checks");
        Files.writeString(world.resolve("native_shape_inputs_r44.json"),record.toString());
        return result;
    }

    private ShapeInputsR44() { }
}
