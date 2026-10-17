package com.projectseele.world;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.block.state.BlockState;

/** Compiles the declared cells, never caches a world's previous dry result. */
final class NervDryBayReadbackR53
{
    private record Section(BlockPos key, List<NervAssemblyOwnerR52.Cell> cells, BlockState uniform) {}
    private final List<Section> sections;

    NervDryBayReadbackR53(List<List<NervAssemblyOwnerR52.Cell>> layers)
    {
        Map<BlockPos,List<NervAssemblyOwnerR52.Cell>> grouped=new LinkedHashMap<>();
        for(var layer:layers)for(var cell:layer)
        {
            var at=cell.at();
            grouped.computeIfAbsent(new BlockPos(at.getX()>>4,at.getY()>>4,at.getZ()>>4),ignored->new ArrayList<>()).add(cell);
        }
        var result=new ArrayList<Section>();
        grouped.forEach((key,cells)->
        {
            BlockState expected=cells.get(0).open();
            result.add(new Section(key,List.copyOf(cells),cells.stream().allMatch(c->c.open().equals(expected))?expected:null));
        });
        sections=List.copyOf(result);
    }

    boolean matches(ServerLevel level)
    {
        for(var section:sections)
        {
            var key=section.key();
            var chunk=level.getChunkSource().getChunkNow(key.getX(),key.getZ());
            if(chunk==null)return false;
            int index=chunk.getSectionIndex(key.getY()<<4);
            if(index<0||index>=chunk.getSectionsCount())return false;
            var actual=chunk.getSection(index);
            // A palette can contain unused states; that only triggers the
            // exact per-cell fallback. Changes are visible on this same call.
            if(section.uniform()!=null&&!actual.getStates().maybeHas(state->!state.equals(section.uniform())))continue;
            for(var cell:section.cells())
            {
                var at=cell.at();
                if(!actual.getBlockState(at.getX()&15,at.getY()&15,at.getZ()&15).equals(cell.open()))return false;
            }
        }
        return true;
    }
}
