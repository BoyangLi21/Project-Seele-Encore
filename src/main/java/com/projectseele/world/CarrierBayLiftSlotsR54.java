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
    private CarrierBayLiftSlotsR54(){}
}
