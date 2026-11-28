package com.projectseele.world;

import com.google.gson.JsonParser;
import com.projectseele.registry.ModBlocks;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.properties.BlockStateProperties;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;

/** The reserve operator banks are in the independently placed GeoFront command podium. */
public final class ReserveCommandHall
{
    private static final AABB ROOM = new AABB(222,-463,374,256,-452,417);
    private static final BlockPos LIGHT_SWITCH = new BlockPos(231,-461,383);
    private static final BlockPos SCREEN_SWITCH = new BlockPos(231,-461,389);
    private static final Map<BlockPos,Integer> KEYS = readKeys();

    private static Map<BlockPos,Integer> readKeys()
    {
        String file = "/assets/projectseele/command/reserve_console.json";
        try (var stream = ReserveCommandHall.class.getResourceAsStream(file))
        {
            if (stream == null) throw new IllegalStateException("Missing reserve console layout");
            var keys = new HashMap<BlockPos,Integer>();
            var ids = new java.util.HashSet<Integer>();
            var stations = JsonParser.parseReader(new InputStreamReader(stream,StandardCharsets.UTF_8)).getAsJsonArray();
            for (var element : stations)
            {
                var station = element.getAsJsonObject();
                int offset = -1;
                for (var item : station.getAsJsonArray("keys"))
                {
                    var id = item.getAsJsonObject().get("id");
                    var pos = new BlockPos(station.get("x").getAsInt(),-461,station.get("z").getAsInt()+offset++);
                    if (id.getAsString().equals("lights"))
                    {
                        if (!pos.equals(LIGHT_SWITCH)) throw new IllegalStateException("Invalid reserve lighting address");
                        continue;
                    }
                    int action = id.getAsInt();
                    if (action<0 || action>=30 || !ids.add(action) || keys.put(pos,action)!=null)
                        throw new IllegalStateException("Invalid reserve command key "+action);
                }
            }
            if (keys.size()!=30) throw new IllegalStateException("Incomplete reserve command console");
            return Map.copyOf(keys);
        }
        catch (IOException error) { throw new IllegalStateException("Invalid reserve console layout",error); }
    }

    private static boolean present(Level level)
    {
        return level.dimension().equals(FacilitySchemaV2.DIMENSION)
                && level.hasChunkAt(LIGHT_SWITCH) && level.hasChunkAt(SCREEN_SWITCH)
                && level.getBlockState(LIGHT_SWITCH).is(Blocks.LEVER)
                && level.getBlockState(SCREEN_SWITCH).is(Blocks.WARPED_BUTTON);
    }

    public static boolean viewer(Level level,Vec3 point)
    {
        return ROOM.contains(point) && present(level);
    }

    public static int action(Level level,BlockPos pos)
    {
        Integer action = KEYS.get(pos);
        return action!=null && present(level) ? action : -1;
    }

    public static void updateLights(ServerLevel level)
    {
        if (!present(level)) return;
        boolean on=level.getBlockState(LIGHT_SWITCH).getValue(BlockStateProperties.POWERED);
        for (int x=225;x<=246;x+=7)
            for (int z : new int[]{380,388,404,411})
            {
                var pos=new BlockPos(x,-454,z);
                if (!level.hasChunkAt(pos)) continue;
                var state=level.getBlockState(pos);
                if (state.is(ModBlocks.NERV_CEILING_LIGHT.get()) && state.getValue(BlockStateProperties.LIT)!=on)
                    level.setBlock(pos,state.setValue(BlockStateProperties.LIT,on),3);
            }
    }

    private ReserveCommandHall() {}
}
