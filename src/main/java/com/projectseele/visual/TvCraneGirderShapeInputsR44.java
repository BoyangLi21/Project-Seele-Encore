package com.projectseele.visual;

import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.projectseele.ProjectSeele;
import com.projectseele.registry.ModBlocks;
import com.projectseele.world.FacilitySchemaV2;
import com.projectseele.world.TvCraneGirderR44;
import net.minecraft.core.BlockPos;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.shapes.CollisionContext;
import net.minecraft.world.phys.shapes.VoxelShape;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.Files;

/** Optional realregistered six-state native shape export; no block/entity mutation. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class TvCraneGirderShapeInputsR44
{
    private static int age;
    private static boolean written;
    private static JsonArray boxes(VoxelShape shape)
    {
        var rows=new JsonArray();
        for(var b:shape.toAabbs())
        {
            var row=new JsonArray();for(double value:new double[]{b.minX,b.minY,b.minZ,b.maxX,b.maxY,b.maxZ})row.add(value);
            rows.add(row);
        }
        return rows;
    }
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(!Boolean.getBoolean("projectseele.r44CraneGirderShapeExport")||written||event.phase!=TickEvent.Phase.END||++age<60)return;
        var server=event.getServer();var root=server.getWorldPath(LevelResource.ROOT).normalize();
        if(!root.getFileName().toString().equals(com.projectseele.visual.NativeReviewWorldsR45.expectedName()))throw new IllegalStateException("Girder export refuses another world");
        var level=server.getLevel(FacilitySchemaV2.DIMENSION);if(level==null)return;
        var collision=new JsonObject();var outline=new JsonObject();var block=ModBlocks.NERV_CRANE_GIRDER_R44.get();
        for(var segment:TvCraneGirderR44.Segment.values())for(boolean joint:new boolean[]{false,true})
        {
            var state=block.defaultBlockState().setValue(TvCraneGirderR44.SEGMENT,segment).setValue(TvCraneGirderR44.JOINT,joint);
            String key="projectseele:nerv_crane_girder_r44[joint="+joint+",segment="+segment.getSerializedName()+"]";
            var at=new BlockPos(34,-374,-240);
            collision.add(key,boxes(state.getCollisionShape(level,at,CollisionContext.empty())));
            outline.add(key,boxes(state.getShape(level,at,CollisionContext.empty())));
        }
        var report=new JsonObject();report.addProperty("actual_registered_block",ModBlocks.NERV_CRANE_GIRDER_R44.getId().toString());
        report.add("collision_shapes",collision);report.add("outline_shapes",outline);
        report.addProperty("source","Actual registered block native six states, reallevel/position context; no geometry fallback, no writes or switches");
        report.addProperty("states",6);report.addProperty("world_blocks_mutated",false);
        try { Files.writeString(root.resolve("r44_crane_girder_shapes.json"),new GsonBuilder().setPrettyPrinting().create().toJson(report)); }
        catch(Exception error) { throw new IllegalStateException("Girder native shape export failed",error); }
        written=true;
    }
    private TvCraneGirderShapeInputsR44() { }
}
