package com.projectseele.world;

import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.saveddata.SavedData;
import java.util.ArrayList;

/** Removes the five delivered fixed threshold tiles inside the native 7x7 car sweep. */
public final class SurfaceLiftThresholdRepairR53
{
    private static final String KEY="projectseele_surface_lift_threshold_20261025";
    private static final class Receipt extends SavedData
    {
        private CompoundTag data=new CompoundTag();
        static Receipt load(CompoundTag tag){var receipt=new Receipt();receipt.data=tag.copy();return receipt;}
        @Override public CompoundTag save(CompoundTag tag){return data.copy();}
    }
    public static void beforeCall(ServerLevel level,S20PhysicalElevatorDirector.LiftSpec spec)
    {
        if(!level.dimension().location().toString().equals("projectseele:geofront")
                ||!spec.id().equals("s20-surface-transit-v2")||spec.r52()==null
                ||!spec.lower().cabinCentre().equals(new BlockPos(130,-535,273))
                ||!spec.upper().cabinCentre().equals(new BlockPos(130,-466,273)))return;
        var receipt=level.getDataStorage().computeIfAbsent(Receipt::load,Receipt::new,KEY);
        if(receipt.data.getBoolean("Applied"))return;
        // A present cabin owns its floor. Only the empty lower landing is eligible.
        if(S20PhysicalElevatorDirector.hasAuthoredCabinAt(level,spec.lower().cabinCentre())
                ||!S20PhysicalElevatorDirector.hasAuthoredCabinAt(level,spec.upper().cabinCentre()))return;
        var cells=new ArrayList<BlockPos>();
        for(int z=271;z<=275;z++)
        {
            var pos=new BlockPos(127,-536,z);
            if(!level.hasChunkAt(pos)||level.getBlockEntity(pos)!=null
                    ||!BuiltInRegistries.BLOCK.getKey(level.getBlockState(pos).getBlock()).toString().equals("projectseele:nerv_floor_panel"))return;
            cells.add(pos);
        }
        var inverse=new ListTag();
        for(var pos:cells)
        {
            var cell=new CompoundTag();cell.putLong("Position",pos.asLong());
            cell.putString("Block","projectseele:nerv_floor_panel");inverse.add(cell);
        }
        var before=level.getBlockState(cells.get(0));
        for(var pos:cells)if(!level.setBlock(pos,Blocks.AIR.defaultBlockState(),3))
        {for(var restore:cells)level.setBlock(restore,before,3);return;}
        receipt.data.put("Before",inverse);receipt.data.putBoolean("Applied",true);receipt.setDirty();
        com.projectseele.ProjectSeele.LOGGER.info("Surface lift repaired: removed 5 fixed threshold tiles from the native car sweep; exterior landing retained");
    }
    private SurfaceLiftThresholdRepairR53() { }
}
