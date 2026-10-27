package com.projectseele.world;

import com.projectseele.entity.NervSiloDoorEntity;
import com.projectseele.entity.YashimaCannonEntityR52;
import java.util.HashSet;
import java.util.Set;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.phys.AABB;

/** The installed cannon aperture owns its existing barrier proxies and declared actuator. */
public final class YashimaCannonHatchR54
{
    private static boolean held(YashimaCannonEntityR52 gun,String reason)
    {gun.getPersistentData().putString("FixedCannonHatchHoldR54",reason);return false;}

    static Set<BlockPos> proxyCells(NervSiloDoorEntity hatch)
    {
        var spec=hatch.declaredSpecR52();var box=hatch.getPersistentData().getIntArray("CannonProxyBoxR53");
        if(spec==null||box.length!=6||box[1]!=box[4]||box[3]<box[0]||box[5]<box[2])return Set.of();
        long size=((long)box[3]-box[0]+1)*((long)box[5]-box[2]+1);
        if(size<=0||size>8192)return Set.of();
        var aperture=NervRigidMeshSweepR52.transformed(new AABB(-spec.openingX()/2D,0,-spec.openingZ()/2D,
                spec.openingX()/2D,.001,spec.openingZ()/2D),hatch.actualFrameR52());
        if((int)Math.floor(aperture.minX+.001)!=box[0]||(int)Math.floor(aperture.minY)!=box[1]
                ||(int)Math.floor(aperture.minZ+.001)!=box[2]||(int)Math.floor(aperture.maxX-.001)!=box[3]
                ||(int)Math.floor(aperture.maxZ-.001)!=box[5])return Set.of();
        var cells=new HashSet<BlockPos>();
        for(var at:BlockPos.betweenClosed(box[0],box[1],box[2],box[3],box[4],box[5]))cells.add(at.immutable());
        return Set.copyOf(cells);
    }

    public static boolean advance(ServerLevel level,TvYashimaStationR52.Plan plan,
            YashimaCannonEntityR52 gun,NervSiloDoorEntity hatch,boolean open)
    {
        if(!plan.cannon().equals(gun.getUUID())||!plan.hatch().equals(hatch.getUUID())
                ||!plan.fingerprint().equals(gun.getPersistentData().getString("StationLayoutR52")))
            return held(gun,"original_station_identity_changed");
        var cells=proxyCells(hatch);if(cells.isEmpty())return held(gun,"declared_cannon_aperture_missing");
        for(var at:cells)
        {
            if(!level.hasChunkAt(at)||level.getBlockEntity(at)!=null)return held(gun,"proxy_unloaded_or_block_entity="+at);
            var state=level.getBlockState(at);
            if(!state.isAir()&&!state.is(Blocks.BARRIER))return held(gun,"original_proxy_state_changed="+at);
        }
        float from=hatch.actualOpenProgressR52(),to=hatch.proposedDeclaredProgressR52(open);
        // Holding an endpoint moves no panel. A wreck beside an already open
        // hatch must not turn that idle state into a new obstructed movement.
        if(from!=to)
        {
            var supports=new HashSet<BlockPos>();
            for(var point:hatch.declaredGeometryR52().bearingPoints())
                supports.add(BlockPos.containing(hatch.actualFrameR52().transformPoint(point).add(0,-.001,0)));
            if(!hatch.clearDeclaredSweepR52(level,from,to,Set.of(hatch.getUUID()),cells,supports,Set.of()))
                return held(gun,"actual_hatch_support_or_sweep_blocked");
            if(!YashimaCannonMeshR52.clearHatchR54(gun,hatch,from,to))return held(gun,"actual_hatch_hits_original_gun_or_cradle");
            if(!open&&!NervGateClosureR52.clearActualActors(level,hatch,cells))return held(gun,"actual_aperture_occupied");
        }
        // Endpoint proxies never advance the physical panels or appear ahead of closure.
        if(to==0||to==1)
        {
            var target=(to==1?Blocks.AIR:Blocks.BARRIER).defaultBlockState();
            for(var at:cells)if(!level.getBlockState(at).equals(target))level.setBlock(at,target,2);
        }
        hatch.advanceDeclaredR52(open);
        gun.getPersistentData().remove("FixedCannonHatchHoldR54");
        return hatch.actualOpenProgressR52()==(open?1:0);
    }

    private YashimaCannonHatchR54(){}
}
