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
    private record ExpectedCell(NervAssemblyOwnerR52.Cell source, BlockState retainedGuard) {}
    private record Section(BlockPos key, List<ExpectedCell> cells, BlockState uniform) {}
    private final List<Section> sections;

    NervDryBayReadbackR53(List<List<NervAssemblyOwnerR52.Cell>> layers)
    {
        Map<BlockPos,List<ExpectedCell>> grouped=new LinkedHashMap<>();
        for(var layer:layers)for(var cell:layer)
        {
            var at=cell.at();
            grouped.computeIfAbsent(new BlockPos(at.getX()>>4,at.getY()>>4,at.getZ()>>4),ignored->new ArrayList<>())
                    .add(new ExpectedCell(cell,CarrierBayTrayR53.retainedGuardStateR53(cell)));
        }
        var result=new ArrayList<Section>();
        grouped.forEach((key,cells)->
        {
            BlockState expected=cells.get(0).source().open();
            result.add(new Section(key,List.copyOf(cells),cells.stream().allMatch(c->c.source().open().equals(expected))?expected:null));
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
            for(var expected:section.cells())
            {
                var cell=expected.source();var at=cell.at();
                var state=actual.getBlockState(at.getX()&15,at.getY()&15,at.getZ()&15);
                if(state.equals(cell.open()))continue;
                if(expected.retainedGuard()!=null&&level.dimension().equals(FacilitySchemaV2.DIMENSION)
                        &&state.equals(expected.retainedGuard())&&level.getBlockEntity(at)==null)continue;
                return false;
            }
        }
        return true;
    }
}
