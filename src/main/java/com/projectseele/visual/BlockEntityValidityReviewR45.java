package com.projectseele.visual;

import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.level.block.EntityBlock;
import net.minecraft.world.level.block.entity.BlockEntityType;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.Property;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraftforge.event.RegisterCommandsEvent;
import net.minecraftforge.event.server.ServerStartedEvent;
import net.minecraftforge.fml.ModList;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;

/** Explicit registry-only review: no world reads, chunk loads, ticks, or world mutation. */
public final class BlockEntityValidityReviewR45
{
    private BlockEntityValidityReviewR45() {}

    /** Explicit opt-in for Root's existing native window; uses the registered command's ordinary console permission checks. */
    public static void exportOnStart(ServerStartedEvent event)
    {
        if(!Boolean.getBoolean("projectseele.r45BeValidityExportOnStart"))return;
        String output=System.getProperty("projectseele.r45BeValidityOutput", "");
        if(!Boolean.getBoolean("projectseele.r45BeValidityReview")||output.isBlank())
        {
            com.projectseele.ProjectSeele.LOGGER.error("R45 BE on-start export refused: explicit review=true and fresh output required");return;
        }
        var console=event.getServer().createCommandSourceStack();
        if(!console.hasPermission(4))
        {
            com.projectseele.ProjectSeele.LOGGER.error("R45 BE on-start export refused: server console lacks permission4");return;
        }
        int status=event.getServer().getCommands().performPrefixedCommand(console, "seele review_be_validity export");
        com.projectseele.ProjectSeele.LOGGER.info("R45_BE_VALIDITY_EXPORT_ON_START status={} output={}",status,output);
    }

    public static void register(RegisterCommandsEvent event)
    {
        if(!Boolean.getBoolean("projectseele.r45BeValidityReview"))return;
        event.getDispatcher().register(Commands.literal("seele")
                .then(Commands.literal("review_be_validity").requires(source -> source.hasPermission(4))
                        .then(Commands.literal("export").executes(context -> export(context.getSource())))));
    }

    private static int export(CommandSourceStack source)
    {
        try
        {
            String configured=System.getProperty("projectseele.r45BeValidityOutput", "");
            if(configured.isBlank()||!Path.of(configured).isAbsolute())
                throw new IllegalArgumentException("Explicit absolute artifact output file required");
            Path output=Path.of(configured).normalize();
            if(!output.getFileName().toString().endsWith(".json"))
                throw new IllegalArgumentException("JSON artifact output required");
            Path world=source.getServer().getWorldPath(LevelResource.ROOT).toRealPath();
            Path ancestor=output.getParent();
            while(ancestor!=null&&!Files.exists(ancestor))ancestor=ancestor.getParent();
            if(ancestor==null)throw new IllegalArgumentException("Existing artifact ancestor required");
            Path resolvedOutput=ancestor.toRealPath().resolve(ancestor.relativize(output)).normalize();
            if(resolvedOutput.startsWith(world))throw new IllegalArgumentException("Artifact output inside world forbidden");
            if(Files.exists(output))throw new IllegalArgumentException("Fresh output required; existing evidence is immutable");

            long began=System.nanoTime();
            JsonObject result=new JsonObject();
            result.addProperty("schema", "projectseele.runtime-be-valid-blocks.r45.v15");
            result.addProperty("captured_at_utc", Instant.now().toString());
            result.addProperty("world_written", false);
            result.addProperty("world_chunks_read_or_loaded", false);
            result.addProperty("native_tick_validation", false);
            result.addProperty("operation", "Loaded registries; actual BlockEntityType.isValid(defaultBlockState) for every registered block/type pair");
            JsonArray mods=new JsonArray();
            ModList.get().getMods().stream().sorted(Comparator.comparing(info -> info.getModId())).forEach(info ->
            {
                JsonObject mod=new JsonObject();mod.addProperty("id",info.getModId());
                mod.addProperty("version",info.getVersion().toString());mods.add(mod);
            });
            result.add("loaded_mod_versions",mods);
            var blocks=new ArrayList<>(BuiltInRegistries.BLOCK.keySet());blocks.sort(Comparator.comparing(Object::toString));
            var types=new ArrayList<>(BuiltInRegistries.BLOCK_ENTITY_TYPE.keySet());types.sort(Comparator.comparing(Object::toString));
            JsonArray rows=new JsonArray(),errors=new JsonArray();long calls=0;
            for(var id:types)
            {
                var type=BuiltInRegistries.BLOCK_ENTITY_TYPE.get(id);JsonObject row=new JsonObject();
                row.addProperty("be_id",id.toString());row.addProperty("java_class",type.getClass().getName());
                boolean standard=type.getClass()==BlockEntityType.class;
                row.addProperty("relation_scope",standard?"STANDARD_BLOCK_ENTITY_TYPE_BLOCK_ID_MEMBERSHIP":"CUSTOM_TYPE_DEFAULT_STATES_ONLY");
                JsonArray accepted=new JsonArray();
                for(var blockId:blocks)
                {
                    calls++;
                    try
                    {
                        if(type.isValid(BuiltInRegistries.BLOCK.get(blockId).defaultBlockState()))accepted.add(blockId.toString());
                    }
                    catch(Exception failure)
                    {
                        JsonObject error=new JsonObject();error.addProperty("be_id",id.toString());
                        error.addProperty("block_id",blockId.toString());error.addProperty("error",failure.toString());errors.add(error);
                    }
                }
                row.add("valid_default_block_ids",accepted);rows.add(row);
            }
            result.add("types",rows);result.add("errors",errors);
            result.addProperty("complete_registry_enumeration",errors.isEmpty());
            result.addProperty("registered_type_count",types.size());result.addProperty("registered_block_count",blocks.size());
            result.addProperty("actual_isValid_calls",calls);
            JsonArray probes=new JsonArray();
            probes.add(probe("projectseele:station_departure_board", "mtr:route_sign_wall_light[facing=north,half=upper,propagate_property=1]"));
            probes.add(probe("mtr:route_sign_wall_light", "mtr:route_sign_wall_light[facing=north,half=upper,propagate_property=1]"));
            probes.add(probe("mtr:route_sign_wall_light", "mtr:route_sign_wall_light[facing=north,half=lower,propagate_property=1]"));
            probes.add(probe("mtr:route_sign_wall_light", "mtr:route_sign_wall_light[facing=north,half=upper,propagate_property=2]"));
            probes.add(probe("mtr:route_sign_wall_light", "mtr:route_sign_wall_light[facing=south,half=upper,propagate_property=1]"));
            probes.add(probe("movingelevators:button_tile", "movingelevators:button_block"));
            probes.add(probe("movingelevators:display_tile", "movingelevators:display_block"));
            probes.add(probe("movingelevators:elevator_tile", "movingelevators:elevator_block[facing=east]"));
            probes.add(probe("movingelevators:elevator_tile", "movingelevators:elevator_block[facing=south]"));
            probes.add(probe("movingelevators:elevator_tile", "movingelevators:elevator_block[facing=west]"));
            result.add("exact_state_probes",probes);
            result.addProperty("elapsed_ms",(System.nanoTime()-began)/1_000_000);
            result.addProperty("limitation", "Custom BlockEntityType subclasses are not generalized beyond default states or exact probes. Factory probes are detached objects, never added to a level. Registry validity is not native tick/function/art approval; root must bind this export to installed mod jars.");
            Files.createDirectories(output.getParent());
            Files.writeString(output,new GsonBuilder().setPrettyPrinting().create().toJson(result),StandardCharsets.UTF_8,
                    StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE);
            source.sendSuccess(() -> Component.literal("BE registry review exported: "+output+"; no world/tick changes."),false);
            return errors.isEmpty()?1:0;
        }
        catch(Exception failure)
        {
            source.sendFailure(Component.literal("BE registry review failed: "+failure));return 0;
        }
    }

    private static JsonObject probe(String beId,String text)
    {
        JsonObject row=new JsonObject();row.addProperty("be_id",beId);row.addProperty("state",text);
        try
        {
            ResourceLocation typeId=new ResourceLocation(beId);
            if(!BuiltInRegistries.BLOCK_ENTITY_TYPE.containsKey(typeId))throw new IllegalArgumentException("Type not registered");
            BlockState state=state(text);var type=BuiltInRegistries.BLOCK_ENTITY_TYPE.get(typeId);
            row.addProperty("is_valid",type.isValid(state));
            if(state.getBlock() instanceof EntityBlock factory)
            {
                var detached=factory.newBlockEntity(BlockPos.ZERO,state);
                row.addProperty("detached_factory_returned_null",detached==null);
                if(detached!=null)
                {
                    row.addProperty("detached_factory_type",BuiltInRegistries.BLOCK_ENTITY_TYPE.getKey(detached.getType()).toString());
                    row.addProperty("detached_factory_type_is_valid",detached.getType().isValid(state));
                }
            }
            row.addProperty("complete",true);
        }
        catch(Exception failure){row.addProperty("complete",false);row.addProperty("error",failure.toString());}
        return row;
    }

    private static BlockState state(String text)
    {
        int bracket=text.indexOf('[');String name=bracket<0?text:text.substring(0,bracket);
        ResourceLocation id=new ResourceLocation(name);
        if(!BuiltInRegistries.BLOCK.containsKey(id))throw new IllegalArgumentException("Block not registered: "+name);
        var block=BuiltInRegistries.BLOCK.get(id);BlockState state=block.defaultBlockState();
        if(bracket>=0)
        {
            if(!text.endsWith("]"))throw new IllegalArgumentException("Bad state syntax");
            for(String part:text.substring(bracket+1,text.length()-1).split(","))
            {
                String[] pair=part.split("=",2);
                if(pair.length!=2)throw new IllegalArgumentException("Bad property");
                Property<?> property=block.getStateDefinition().getProperty(pair[0]);
                if(property==null)throw new IllegalArgumentException("Unknown property: "+part);
                state=property(state,property,pair[1]);
            }
        }
        return state;
    }

    private static <T extends Comparable<T>> BlockState property(BlockState state,Property<T> property,String text)
    {
        return state.setValue(property,property.getValue(text).orElseThrow(() -> new IllegalArgumentException("Bad property value: "+text)));
    }
}
