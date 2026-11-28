package com.projectseele.world;

import com.google.gson.JsonParser;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.WeakHashMap;
import net.minecraft.commands.arguments.blocks.BlockStateParser;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.block.entity.SignBlockEntity;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.chunk.LevelChunk;

/** Switched circuits and daylight shutters for the secondary operations floor. */
final class ReserveHallPower
{
    private record Load(BlockPos pos,BlockState powered,BlockState unpowered) {}
    private record Circuit(List<Load> loads,List<BlockPos> signs)
    {
        Circuit() { this(new ArrayList<>(),new ArrayList<>()); }
    }
    private static final Map<ChunkPos,Circuit> CIRCUITS = load();
    private static final Map<LevelChunk,Boolean> APPLIED = new WeakHashMap<>();

    private static Map<ChunkPos,Circuit> load()
    {
        var circuits=new HashMap<ChunkPos,Circuit>();
        try (var stream=ReserveHallPower.class.getResourceAsStream("/assets/projectseele/command/reserve_power.json"))
        {
            if(stream==null)throw new IllegalStateException("Missing reserve floor circuits");
            var registry=BuiltInRegistries.BLOCK.asLookup();
            var data=JsonParser.parseReader(new InputStreamReader(stream,StandardCharsets.UTF_8)).getAsJsonArray();
            for(var element:data)
            {
                var group=element.getAsJsonObject();
                var on=BlockStateParser.parseForBlock(registry,group.get("on").getAsString(),false).blockState();
                var off=BlockStateParser.parseForBlock(registry,group.get("off").getAsString(),false).blockState();
                for(var item:group.getAsJsonArray("columns"))
                {
                    var row=item.getAsJsonArray();
                    int x=row.get(0).getAsInt(),z=row.get(1).getAsInt();
                    var circuit=circuits.computeIfAbsent(new ChunkPos(x>>4,z>>4),key->new Circuit());
                    for(int y=row.get(2).getAsInt();y<=row.get(3).getAsInt();y++)
                        circuit.loads.add(new Load(new BlockPos(x,y,z),on,off));
                }
            }
            for(var pos:ReserveCommandHall.litSigns())
                circuits.computeIfAbsent(new ChunkPos(pos),key->new Circuit()).signs.add(pos);
            return circuits;
        }
        catch(Exception ex) { throw new IllegalStateException("Cannot read reserve floor lighting",ex); }
    }

    static void apply(ServerLevel level,boolean on)
    {
        for(var entry:CIRCUITS.entrySet())
        {
            var key=entry.getKey();
            var chunk=level.getChunkSource().getChunkNow(key.x,key.z);
            if(chunk==null || Boolean.valueOf(on).equals(APPLIED.get(chunk)))continue;
            for(var load:entry.getValue().loads)
            {
                var current=level.getBlockState(load.pos);
                if(current==(on?load.unpowered:load.powered))
                    level.setBlock(load.pos,on?load.powered:load.unpowered,3);
            }
            for(var pos:entry.getValue().signs)
                if(level.getBlockEntity(pos) instanceof SignBlockEntity sign)
                    sign.updateText(text->text.setHasGlowingText(on),true);
            APPLIED.put(chunk,on);
        }
    }
    private ReserveHallPower() {}
}
