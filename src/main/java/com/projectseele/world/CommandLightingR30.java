package com.projectseele.world;

import com.google.gson.JsonParser;
import com.projectseele.registry.ModBlocks;
import net.minecraft.core.BlockPos;
import net.minecraft.server.MinecraftServer;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.properties.BlockStateProperties;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.Files;
import java.util.*;

/** One labelled commander lever controls every separately surveyed command-room fixture. */
@Mod.EventBusSubscriber(modid="projectseele")
public final class CommandLightingR30
{
    private record Circuit(BlockPos lever,List<BlockPos> lamps) {}
    private static final Map<MinecraftServer,Circuit> CACHE=new WeakHashMap<>();
    private static Circuit read(MinecraftServer server)
    {
        return CACHE.computeIfAbsent(server,s->{
            var path=s.getWorldPath(LevelResource.ROOT).resolve("facility_lighting_r30.json");
            if(!Files.exists(path))return new Circuit(BlockPos.ZERO,List.of());
            try
            {
                var root=JsonParser.parseString(Files.readString(path)).getAsJsonObject();var lever=root.getAsJsonArray("command_lever");var lamps=new ArrayList<BlockPos>();
                for(var p:root.getAsJsonArray("command_lamps")){var a=p.getAsJsonArray();lamps.add(new BlockPos(a.get(0).getAsInt(),a.get(1).getAsInt(),a.get(2).getAsInt()));}
                return new Circuit(new BlockPos(lever.get(0).getAsInt(),lever.get(1).getAsInt(),lever.get(2).getAsInt()),List.copyOf(lamps));
            }
            catch(Exception error){throw new IllegalStateException("Invalid R30 command lighting circuit",error);}
        });
    }
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(event.phase!=TickEvent.Phase.END||event.getServer().getTickCount()%5!=0)return;
        var level=event.getServer().getLevel(FacilitySchemaV2.DIMENSION);if(level==null)return;var circuit=read(event.getServer());
        if(circuit.lamps.isEmpty()||!level.hasChunkAt(circuit.lever))return;
        var lever=level.getBlockState(circuit.lever);
        if(!lever.is(Blocks.LEVER))return;
        boolean on=lever.getValue(BlockStateProperties.POWERED);
        for(var pos:circuit.lamps)
        {
            if(!level.hasChunkAt(pos))continue;var state=level.getBlockState(pos);
            if((state.is(ModBlocks.NERV_CEILING_LIGHT.get())||state.is(ModBlocks.NERV_STRIP_LIGHT.get())||state.is(ModBlocks.NERV_ALERT_LIGHT.get()))
                    &&state.getValue(BlockStateProperties.LIT)!=on)level.setBlock(pos,state.setValue(BlockStateProperties.LIT,on),3);
        }
    }
    private CommandLightingR30() {}
}
