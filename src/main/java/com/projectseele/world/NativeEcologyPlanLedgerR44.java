package com.projectseele.world;

import com.google.gson.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.nbt.*;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.block.state.BlockState;

/** Disk-backed batch ownership; only 96 sparse sections stay resident. */
final class NativeEcologyPlanLedgerR44
{
    private final Path root,blocks,biomes;
    private final LinkedHashMap<String,Section> cache=new LinkedHashMap<>(128,.75F,true);
    private record Cell(BlockState state,String nbt){}
    private static final class Section
    {
        final Map<Integer,Cell> cells=new HashMap<>();boolean dirty;
    }
    NativeEcologyPlanLedgerR44(Path path) throws Exception
    {root=path;blocks=root.resolve("blocks");biomes=root.resolve("biomes");Files.createDirectories(blocks);Files.createDirectories(biomes);}
    Path root(){return root;}
    private String key(BlockPos p){return (p.getX()>>4)+"_"+(p.getY()>>4)+"_"+(p.getZ()>>4);}
    private int index(BlockPos p){return ((p.getY()&15)<<8)|((p.getZ()&15)<<4)|(p.getX()&15);}
    private Section section(BlockPos p)
    {
        String key=key(p);Section result=cache.get(key);if(result!=null)return result;
        try
        {
            result=new Section();Path file=blocks.resolve(key+".nbt");
            if(Files.exists(file))for(Tag raw:NbtIo.readCompressed(file.toFile()).getList("Cells",Tag.TAG_COMPOUND))
            {
                CompoundTag tag=(CompoundTag)raw;
                result.cells.put(tag.getInt("Index"),new Cell(NbtUtils.readBlockState(BuiltInRegistries.BLOCK.asLookup(),tag.getCompound("State")),tag.contains("NBT")?tag.getString("NBT"):null));
            }
            if(cache.size()>=96)
            {
                var first=cache.entrySet().iterator().next();save(first.getKey(),first.getValue());cache.remove(first.getKey());
            }
            cache.put(key,result);return result;
        }
        catch(Exception error){throw new IllegalStateException("Ecology ledger read failed "+key,error);}
    }
    boolean owns(BlockPos p){return section(p).cells.containsKey(index(p));}
    BlockState read(BlockPos p,BlockState fallback){Cell cell=section(p).cells.get(index(p));return cell==null?fallback:cell.state;}
    String nbt(BlockPos p){Cell cell=section(p).cells.get(index(p));return cell==null?null:cell.nbt;}
    void put(BlockPos p,BlockState state,String nbt)
    {
        Section s=section(p);Cell old=s.cells.putIfAbsent(index(p),new Cell(state,nbt));
        if(old!=null&&(!old.state.equals(state)||!Objects.equals(old.nbt,nbt)))throw new IllegalStateException("Previous complete feature overwritten at "+p);
        s.dirty=true;
    }
    private void save(String key,Section section) throws Exception
    {
        if(!section.dirty)return;ListTag cells=new ListTag();
        section.cells.forEach((index,cell)->{CompoundTag tag=new CompoundTag();tag.putInt("Index",index);tag.put("State",NbtUtils.writeBlockState(cell.state));if(cell.nbt!=null)tag.putString("NBT",cell.nbt);cells.add(tag);});
        CompoundTag tag=new CompoundTag();tag.put("Cells",cells);NbtIo.writeCompressed(tag,blocks.resolve(key+".nbt").toFile());section.dirty=false;
    }
    void flush() throws Exception{for(var e:cache.entrySet())save(e.getKey(),e.getValue());cache.clear();}
    void mergeBiomes(ServerLevel level,JsonArray rows) throws Exception
    {
        for(JsonElement value:rows)
        {
            JsonObject next=value.getAsJsonObject();JsonArray chunk=next.getAsJsonArray("chunk");
            Path file=biomes.resolve(chunk.get(0).getAsInt()+"_"+next.get("section_y").getAsInt()+"_"+chunk.get(1).getAsInt()+".json");
            if(!Files.exists(file)){Files.writeString(file,next.toString(),StandardCharsets.UTF_8);continue;}
            JsonObject old=JsonParser.parseString(Files.readString(file)).getAsJsonObject();
            if(!old.get("before_snbt").equals(next.get("before_snbt"))||!old.get("before_names").equals(next.get("before_names")))
                throw new IllegalStateException("Biome section baseline differs across readonly batches "+file);
            JsonArray before=old.getAsJsonArray("before_names"),merged=old.getAsJsonArray("after_names"),incoming=next.getAsJsonArray("after_names");
            for(int i=0;i<64;i++)
            {
                if(incoming.get(i).equals(before.get(i)))continue;
                if(!merged.get(i).equals(before.get(i))&&!merged.get(i).equals(incoming.get(i)))throw new IllegalStateException("Conflicting ecological quart target "+file+" index "+i);
                merged.set(i,incoming.get(i));
            }
            JsonArray changed=new JsonArray();for(int i=0;i<64;i++)if(!merged.get(i).equals(before.get(i)))changed.add(i);
            old.add("quart_indices",changed);old.addProperty("after_snbt",NativeEcologyBiomesR44.encodeNames(level,merged));
            Files.writeString(file,old.toString(),StandardCharsets.UTF_8);
        }
    }
    JsonArray exportMergedBiomes(Path output) throws Exception
    {
        Files.createDirectories(output);
        JsonArray plans=new JsonArray(),forward=new JsonArray();int shard=0;
        try(DirectoryStream<Path> files=Files.newDirectoryStream(biomes,"*.json"))
        {
            for(Path file:files)
            {
                forward.add(JsonParser.parseString(Files.readString(file)));
                if(forward.size()==512){plans.add(exportShard(output,shard++,forward));forward=new JsonArray();}
            }
        }
        if(!forward.isEmpty())plans.add(exportShard(output,shard,forward));return plans;
    }
    private JsonObject exportShard(Path output,int shard,JsonArray forward) throws Exception
    {
        JsonArray inverse=new JsonArray();for(JsonElement item:forward)
        {
            JsonObject row=item.getAsJsonObject().deepCopy();JsonElement before=row.get("before_snbt"),names=row.get("before_names");
            row.add("before_snbt",row.get("after_snbt"));row.add("after_snbt",before);row.add("before_names",row.get("after_names"));row.add("after_names",names);inverse.add(row);
        }
        Path first=output.resolve(String.format(Locale.ROOT,"merged_biomes_%04d.forward.json",shard)),second=output.resolve(String.format(Locale.ROOT,"merged_biomes_%04d.inverse.json",shard));
        Files.writeString(first,forward.toString(),StandardCharsets.UTF_8);Files.writeString(second,inverse.toString(),StandardCharsets.UTF_8);
        JsonObject plan=new JsonObject();plan.addProperty("forward",first.toString());plan.addProperty("inverse",second.toString());plan.addProperty("unique_sections",forward.size());return plan;
    }
}
