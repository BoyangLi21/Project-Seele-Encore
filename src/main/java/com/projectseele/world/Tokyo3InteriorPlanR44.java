package com.projectseele.world;

import com.google.gson.*;
import com.projectseele.ProjectSeele;
import java.io.BufferedWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.zip.GZIPOutputStream;
import net.minecraft.core.BlockPos;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.EntityBlock;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Complete tower rooms and ports, exported as exact reversible native plans. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class Tokyo3InteriorPlanR44
{
    private static final String OUTPUT=System.getProperty("projectseele.r44TokyoInteriorPlan","");
    private static boolean done;private static int age,index,depth;
    private static BufferedWriter forward,inverse;
    private static final JsonArray buildings=new JsonArray(),walks=new JsonArray(),held=new JsonArray();
    private static final JsonArray entrances=new JsonArray();
    private static long cells;

    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(OUTPUT.isEmpty()||done||event.phase!=TickEvent.Phase.END)return;
        try
        {
            Path world=event.getServer().getWorldPath(LevelResource.ROOT).toAbsolutePath().normalize();
            if(!world.getFileName().toString().equals("SEELE_FIELD_R44_REVIEW"))throw new IllegalStateException("Wrong city plan world");
            if(++age<40)return;
            ServerLevel level=event.getServer().getLevel(FacilitySchemaV2.DIMENSION);
            BlockPos origin=IntegratedNervMapBuilder.tokyo3Origin(level);
            if(forward==null)
            {
                Path out=Path.of(OUTPUT).toAbsolutePath();Files.createDirectories(out);
                forward=writer(out.resolve("forward.jsonl.gz"));inverse=writer(out.resolve("inverse.jsonl.gz"));
                Tokyo3RetractionSavedData.StoredDistrict district=Tokyo3RetractionSavedData.get(level).get(origin).orElseThrow();
                if(district.cursor()!=0||district.voxelCursor()!=0||district.depth()!=district.targetDepth())
                    throw new IllegalStateException("City is in motion; source must be settled before authoring");
                depth=district.depth();
            }
            var towers=ThirdTokyoSurfaceBuilder.movableBuildings(level);
            if(index<towers.size())
            {plan(level,origin,towers.get(index),index++);return;}
            forward.close();inverse.close();forward=null;inverse=null;
            JsonObject report=new JsonObject();report.addProperty("world",world.toString().replace('\\','/'));
            report.addProperty("depth",depth);report.addProperty("towers",buildings.size());report.addProperty("cells",cells);
            report.addProperty("world_changed",false);report.addProperty("native_function_passed",false);report.addProperty("visual_self_review",false);
            report.add("buildings",buildings);report.add("preserved_non_template_cells",held);
            report.add("entrance_cells",entrances);report.addProperty("entrance_cell_denominator",towers.size()*9);
            Files.writeString(Path.of(OUTPUT).resolve("audit.json"),new GsonBuilder().setPrettyPrinting().create().toJson(report),StandardCharsets.UTF_8);
            Files.writeString(Path.of(OUTPUT).resolve("native_stair_cases.json"),new GsonBuilder().setPrettyPrinting().create().toJson(walks),StandardCharsets.UTF_8);
            done=true;
        }
        catch(Throwable error)
        {
            done=true;try{if(forward!=null)forward.close();if(inverse!=null)inverse.close();
                JsonObject failure=new JsonObject();failure.addProperty("error",error.toString());failure.addProperty("tower_cursor",index);
                Files.writeString(Path.of(OUTPUT).resolve("failed.json"),failure.toString(),StandardCharsets.UTF_8);}
            catch(Exception ignored){}
            ProjectSeele.LOGGER.error("Native full city interior plan failed",error);
        }
    }

    private static void plan(ServerLevel level,BlockPos origin,ThirdTokyoSurfaceBuilder.TowerSpec tower,int id) throws Exception
    {
        BlockPos centre=origin.offset(tower.x(),0,tower.z());int roof=origin.getY()+ThirdTokyoSurfaceBuilder.ceilingRoofRelativeY(tower,origin);
        int travel=Math.max(tower.height(),origin.getY()-roof);
        boolean surface=depth==0,ceiling=depth-travel>=tower.height();
        if(!surface&&!ceiling)throw new IllegalStateException("Full cargo source required for tower "+id);
        int base=surface?origin.getY():roof-tower.height()-1;
        long beforeCells=cells;
        for(int y=0;y<=tower.height();y++)
            for(int x=-tower.halfSize()+1;x<tower.halfSize();x++)
                for(int z=-tower.halfSize()+1;z<tower.halfSize();z++)
                {
                    BlockState desired=TvTokyo3Architecture.interior(x,y,z,tower);
                    if(desired==null||desired.isAir())continue;
                    emit(level,new BlockPos(centre.getX()+x,base+y,centre.getZ()+z),desired,id,"Complete occupied floor, alternating stair core, guarded landing or functional room fitting",y==0,false);
                }
        for(int y=1;y<=3;y++)for(int x=-1;x<=1;x++)
        {
            BlockState desired=TvTokyo3Architecture.entrance(x,y,tower.halfSize(),tower);
            if(x==-1)desired=tower.tv()?TvTokyo3Architecture.wall(y,x,tower):Blocks.POLISHED_DEEPSLATE.defaultBlockState();
            if(desired==null)desired=Blocks.AIR.defaultBlockState();
            emit(level,new BlockPos(centre.getX()+x,base+y,centre.getZ()+tower.halfSize()),desired,id,"Complete double personnel entrance, its header and its full left jamb",false,true);
        }
        int lastFloor=(tower.height()-3)/TvTokyo3Architecture.FLOOR_SPACING*TvTokyo3Architecture.FLOOR_SPACING;
        JsonArray floors=new JsonArray();for(int floor=0;floor<=lastFloor;floor+=TvTokyo3Architecture.FLOOR_SPACING)floors.add(base+floor+1);
        JsonObject b=new JsonObject();b.addProperty("id","tokyo3_retractable/"+id);b.addProperty("x",centre.getX());b.addProperty("z",centre.getZ());
        b.addProperty("height",tower.height());b.addProperty("base",base);b.addProperty("cells",cells-beforeCells);b.add("floor_feet",floors);
        b.addProperty("entry_when_raised",centre.getX()+","+(origin.getY()+1)+","+(centre.getZ()+tower.halfSize()));
        b.addProperty("below_ceiling_entry","Mechanical hanging building; public road entrance only operates after restoration to street datum");
        b.addProperty("native_movement_and_rooms","PENDING");buildings.add(b);
        for(int floor=0;floor<lastFloor;floor+=6)
        {
            boolean north=(floor/6)%2==0;int lane=-tower.halfSize()+(north?3:7);
            int start=-tower.halfSize()+(north?10:5),direction=north?-1:1;
            for(int delta=-1;delta<=1;delta++)
            {
                JsonObject test=new JsonObject();test.addProperty("id","tokyo3_retractable/"+id+"/floor_"+floor+"/lane_"+delta);
                test.add("start",point(centre.getX()+lane+delta+.5,base+floor+1,centre.getZ()+start-direction+.5));
                test.add("end",point(centre.getX()+lane+delta+.5,base+floor+7,centre.getZ()+start+direction*6+.5));
                test.addProperty("both_directions",true);walks.add(test);
            }
        }
    }

    private static void emit(ServerLevel level,BlockPos pos,BlockState desired,int id,String reason,boolean base,boolean entrance) throws Exception
    {
        level.getChunkAt(pos);BlockState current=level.getBlockState(pos);BlockEntity old=level.getBlockEntity(pos);
        JsonObject entry=null;
        if(entrance)
        {
            entry=new JsonObject();entry.addProperty("tower",id);entry.add("pos",point(pos.getX(),pos.getY(),pos.getZ()));
            entry.addProperty("before",RegionalEcologyRetrofitR44.state(current));entry.addProperty("desired",RegionalEcologyRetrofitR44.state(desired));
            entry.addProperty("has_complete_nbt",old!=null);entrances.add(entry);
        }
        if(base&&current.is(Blocks.SEA_LANTERN))return;
        if(entrance&&current.is(com.projectseele.registry.ModBlocks.CITY_PERSONNEL_DOOR.get()))
        {entry.addProperty("status","EXISTING_PERSONNEL_DOOR_USE_PENDING");return;}
        if(current.equals(desired)){if(entry!=null)entry.addProperty("status","ALREADY_EXPECTED_NATIVE_USE_PENDING");return;}
        if(old!=null||!current.isAir()&&!(entrance&&ownedEntranceShell(current))&&!(base&&(current.is(Blocks.POLISHED_DEEPSLATE)||current.is(Blocks.SEA_LANTERN)
                ||current.is(Blocks.SMOOTH_STONE)||current.is(Blocks.GRAY_CONCRETE)||current.is(Blocks.LIGHT_GRAY_CONCRETE)
                ||current.is(Blocks.BLACK_CONCRETE)||current.is(Blocks.ORANGE_CONCRETE)||current.is(Blocks.IRON_BLOCK))))
        {
            JsonObject hold=new JsonObject();hold.addProperty("tower",id);hold.add("pos",point(pos.getX(),pos.getY(),pos.getZ()));
            hold.addProperty("state",RegionalEcologyRetrofitR44.state(current));hold.addProperty("reason","Preserve dynamic user block or complete existing NBT");held.add(hold);
            if(entry!=null)entry.addProperty("status","USER_OR_NBT_PRESERVED_REVIEW_REQUIRED");return;
        }
        String beforeNBT=old==null?null:old.saveWithFullMetadata().toString(),afterNBT=null;
        if(desired.hasBlockEntity())
        {
            BlockEntity entity=((EntityBlock)desired.getBlock()).newBlockEntity(pos,desired);
            if(entity==null)throw new IllegalStateException("Missing furniture block entity factory");
            afterNBT=entity.saveWithFullMetadata().toString();
        }
        JsonObject row=new JsonObject();row.add("pos",point(pos.getX(),pos.getY(),pos.getZ()));
        row.addProperty("before",RegionalEcologyRetrofitR44.state(current));row.addProperty("after",RegionalEcologyRetrofitR44.state(desired));
        row.addProperty("before_nbt",beforeNBT);row.addProperty("after_nbt",afterNBT);
        row.addProperty("owner","r44/tokyo3_retractable/"+id);row.addProperty("reason",reason);forward.write(row.toString());forward.newLine();
        JsonElement state=row.get("before"),tag=row.get("before_nbt");row.add("before",row.get("after"));row.add("before_nbt",row.get("after_nbt"));row.add("after",state);row.add("after_nbt",tag);
        inverse.write(row.toString());inverse.newLine();cells++;
        if(entry!=null)entry.addProperty("status","EXACT_OWNED_TEMPLATE_REPLACEMENT_PLANNED");
    }
    private static boolean ownedEntranceShell(BlockState state)
    {
        return state.is(Blocks.GRAY_CONCRETE)||state.is(Blocks.LIGHT_GRAY_CONCRETE)||state.is(Blocks.WHITE_CONCRETE)
                ||state.is(Blocks.BLACK_CONCRETE)||state.is(Blocks.DEEPSLATE_TILES)||state.is(Blocks.POLISHED_DEEPSLATE)
                ||state.is(Blocks.POLISHED_ANDESITE)||state.is(Blocks.SMOOTH_STONE)||state.is(Blocks.RED_TERRACOTTA)
                ||state.is(Blocks.GRAY_STAINED_GLASS)||state.is(Blocks.CYAN_STAINED_GLASS)||state.is(Blocks.BLUE_STAINED_GLASS)
                ||state.is(Blocks.LIGHT_BLUE_STAINED_GLASS)||state.is(Blocks.BLACK_STAINED_GLASS)||state.is(Blocks.IRON_DOOR);
    }
    private static BufferedWriter writer(Path path) throws Exception
    {return new BufferedWriter(new java.io.OutputStreamWriter(new GZIPOutputStream(Files.newOutputStream(path)),StandardCharsets.UTF_8));}
    private static JsonArray point(double x,double y,double z){JsonArray q=new JsonArray();q.add(x);q.add(y);q.add(z);return q;}
    private Tokyo3InteriorPlanR44(){}
}
