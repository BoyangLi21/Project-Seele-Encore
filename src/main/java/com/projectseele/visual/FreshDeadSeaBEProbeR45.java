package com.projectseele.visual;

import com.google.gson.GsonBuilder;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import com.projectseele.registry.ModBlocks;
import net.minecraft.commands.arguments.blocks.BlockStateParser;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.world.level.block.EntityBlock;
import net.minecraft.world.level.block.HorizontalDirectionalBlock;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;

/** Root-reviewed optional heap-only native constructor/save probe. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class FreshDeadSeaBEProbeR45
{
    private static final String INPUT=System.getProperty("projectseele.r45FreshDeadSeaInput","");
    private static final String OUTPUT=System.getProperty("projectseele.r45FreshDeadSeaOutput","");
    private static boolean done;
    private static int age;

    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(INPUT.isEmpty()||done||event.phase!=TickEvent.Phase.END||++age<30)return;
        done=true;
        try
        {
            Path input=Path.of(INPUT),output=Path.of(OUTPUT);
            if(!input.isAbsolute()||!output.isAbsolute()||Files.exists(output))
                throw new IllegalArgumentException("Fresh unique absolute probe input/output required");
            var request=JsonParser.parseString(Files.readString(input)).getAsJsonObject();
            String world=event.getServer().getWorldPath(LevelResource.ROOT).normalize().getFileName().toString();
            if(!world.equals("SEELE_FIELD_R45_REVIEW")||!world.equals(request.get("world").getAsString()))
                throw new IllegalStateException("Wrong original private review target; no world mutation");
            var point=request.getAsJsonArray("position");
            if(point.size()!=3)throw new IllegalArgumentException("Explicit xyz required");
            var pos=new BlockPos(point.get(0).getAsInt(),point.get(1).getAsInt(),point.get(2).getAsInt());
            if(!pos.equals(new BlockPos(30,-329,345)))throw new IllegalArgumentException("Only the declared new chamber book position");
            var state=ModBlocks.DEAD_SEA_ARCHIVE.get().defaultBlockState()
                    .setValue(HorizontalDirectionalBlock.FACING,Direction.NORTH);
            if(!BlockStateParser.serialize(state).equals(request.get("state").getAsString()))
                throw new IllegalArgumentException("Exact registered book state differs");
            BlockEntity fresh=((EntityBlock)state.getBlock()).newBlockEntity(pos,state);
            if(fresh==null||fresh.getLevel()!=null)throw new IllegalStateException("Must be fresh unattached native BE");
            var full=fresh.saveWithFullMetadata().copy();
            var loaded=BlockEntity.loadStatic(pos,state,full.copy());
            if(loaded==null||!loaded.saveWithFullMetadata().equals(full))
                throw new IllegalStateException("Full constructor/save/load roundtrip differs");
            var result=new JsonObject();
            result.addProperty("kind","fresh_unattached_native_constructor_save");
            result.addProperty("world",world);
            result.addProperty("state",BlockStateParser.serialize(state));
            result.add("position",point.deepCopy());
            result.addProperty("block_entity_type",BuiltInRegistries.BLOCK_ENTITY_TYPE.getKey(fresh.getType()).toString());
            result.addProperty("runtime_class",fresh.getClass().getName());
            result.addProperty("full_snbt",full.toString());
            var collision = state.getCollisionShape(net.minecraft.world.level.EmptyBlockGetter.INSTANCE, pos,
                    net.minecraft.world.phys.shapes.CollisionContext.empty());
            var outline = state.getShape(net.minecraft.world.level.EmptyBlockGetter.INSTANCE, pos,
                    net.minecraft.world.phys.shapes.CollisionContext.empty());
            var gson = new GsonBuilder().create();
            result.add("native_collision_aabbs", gson.toJsonTree(collision.toAabbs().stream()
                    .map(box -> java.util.List.of(box.minX, box.minY, box.minZ, box.maxX, box.maxY, box.maxZ)).toList()));
            result.add("native_outline_aabbs", gson.toJsonTree(outline.toAabbs().stream()
                    .map(box -> java.util.List.of(box.minX, box.minY, box.minZ, box.maxX, box.maxY, box.maxZ)).toList()));
            result.addProperty("native_geometry_query_context", "EmptyBlockGetter.INSTANCE / CollisionContext.empty");
            result.addProperty("native_registered_state_geometry_executed", true);
            result.addProperty("actual_world_geometry_read", false);
            result.addProperty("fresh_created",true);
            result.addProperty("world_instance_read",false);
            result.addProperty("level_attached",false);
            result.addProperty("world_written",false);
            result.addProperty("player_or_reading_progress_read",false);
            result.addProperty("complete_load_save_roundtrip",true);
            Files.writeString(output,new GsonBuilder().setPrettyPrinting().create().toJson(result),StandardOpenOption.CREATE_NEW);
            ProjectSeele.LOGGER.info("R45 FRESH DEAD SEA BE captured state={} type={} no world instance/no level write",state,fresh.getType());
        }
        catch(Exception exception){throw new IllegalStateException("Fresh Dead Sea default BE capture failed; no block/entity placed",exception);}
    }
    private FreshDeadSeaBEProbeR45(){}
}
