package com.projectseele.world;

import com.google.gson.JsonParser;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.HashSet;
import java.util.Set;
import net.minecraft.core.BlockPos;
import net.minecraft.world.phys.AABB;

/** Explicit installed rear-mast openings; never applied to feet or route floors. */
final class CarrierBayLiftSlotsR54
{
    private static List<AABB> slots;
    private static Set<BlockPos> retained=Set.of();
    private static final java.util.Map<Integer,List<BlockPos>> covers=new java.util.HashMap<>();
    private static final Set<BlockPos> coverCells=new HashSet<>();
    static synchronized boolean contains(BlockPos pos)
    {
        if(slots==null)
        {
            try(var in=CarrierBayLiftSlotsR54.class.getResourceAsStream("/assets/projectseele/eva/carrier_bay_lift_slots_r54.json"))
            {
                if(in==null)return false;
                var root=JsonParser.parseString(new String(in.readAllBytes(),StandardCharsets.UTF_8)).getAsJsonObject();
                if(!root.get("schema").getAsString().equals("projectseele.carrier-bay-lift-slots.r54"))throw new IllegalStateException("Unknown bay slot declaration");
                var result=new ArrayList<AABB>();
                for(var raw:root.getAsJsonArray("slots"))
                {
                    var row=raw.getAsJsonObject();var a=row.getAsJsonArray("lo");var b=row.getAsJsonArray("hi");
                    result.add(new AABB(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble(),b.get(0).getAsDouble()+1,b.get(1).getAsDouble()+1,b.get(2).getAsDouble()+1));
                    var openings=new HashSet<BlockPos>();
                    if(row.has("cover_openings"))for(var rawOpening:row.getAsJsonArray("cover_openings"))
                    {
                        var p=rawOpening.getAsJsonArray();
                        openings.add(new BlockPos(p.get(0).getAsInt(),p.get(1).getAsInt(),p.get(2).getAsInt()));
                    }
                    var lid=new ArrayList<BlockPos>();
                    for(int x=a.get(0).getAsInt();x<=b.get(0).getAsInt();x++)
                        for(int z=a.get(2).getAsInt();z<=b.get(2).getAsInt();z++)
                        {
                            var p=new BlockPos(x,b.get(1).getAsInt(),z);
                            if(!openings.contains(p))lid.add(p);
                        }
                    covers.put(row.get("variant").getAsInt(),List.copyOf(lid));
                    coverCells.addAll(lid);
                }
                slots=List.copyOf(result);
            }
            catch(java.io.IOException failure){throw new IllegalStateException("Bay slot declaration unavailable",failure);}
            try(var in=CarrierBayLiftSlotsR54.class.getResourceAsStream("/assets/projectseele/eva/carrier_bay_retained_supports_r54.json"))
            {
                if(in!=null)
                {
                    var source=JsonParser.parseString(new String(in.readAllBytes(),StandardCharsets.UTF_8)).getAsJsonObject();
                    if(!source.get("schema").getAsString().equals("projectseele.carrier-bay-retained-supports.r54"))throw new IllegalStateException("Unknown original bearing shelf declaration");
                    var keep=new HashSet<BlockPos>();
                    for(var raw:source.getAsJsonArray("cells"))
                    {var at=raw.getAsJsonObject().getAsJsonArray("at");keep.add(new BlockPos(at.get(0).getAsInt(),at.get(1).getAsInt(),at.get(2).getAsInt()));}
                    retained=Set.copyOf(keep);
                }
            }
            catch(java.io.IOException failure){throw new IllegalStateException("Original bearing shelf declaration unavailable",failure);}
        }
        return !retained.contains(pos)&&slots.stream().anyMatch(b->b.contains(pos.getX()+.5,pos.getY()+.5,pos.getZ()+.5));
    }
    static boolean closedCover(net.minecraft.world.level.Level level,BlockPos pos)
    {
        return contains(pos)&&coverCells.contains(pos)
                &&level.getBlockState(pos).is(com.projectseele.registry.ModBlocks.NERV_FLOOR_PANEL.get());
    }
    static void setClosed(net.minecraft.server.level.ServerLevel level,
                          com.projectseele.entity.NervCarrierPlatformEntity carrier,boolean closed)
    {
        var bay=CarrierBayTrayR53.bay(carrier);
        if(bay==null||!CarrierMountProfileR53.read(carrier,1).shallowBay()
                ||!NervAirTransportManifestR52.same(NervOriginalCarrierR52.actualRoot(carrier,1),bay.root()))return;
        contains(bay.logicalBed());
        var target=closed?com.projectseele.registry.ModBlocks.NERV_FLOOR_PANEL.get().defaultBlockState()
                :net.minecraft.world.level.block.Blocks.AIR.defaultBlockState();
        for(var at:covers.getOrDefault(bay.variant(),List.of()))
        {
            if(retained.contains(at))continue;
            var actual=level.getBlockState(at);
            if(actual.isAir()||actual.is(com.projectseele.registry.ModBlocks.NERV_FLOOR_PANEL.get())
                    ||actual.is(com.projectseele.registry.ModBlocks.LCL_BLOCK.get()))
                if(!actual.equals(target))level.setBlock(at,target,2);
        }
    }
    private CarrierBayLiftSlotsR54(){}
}
