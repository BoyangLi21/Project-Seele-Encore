package com.projectseele.world;
import com.projectseele.entity.*;
import java.util.*;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.*;

/** Read-only reachability under the actual declared gates' fully open
 * geometry. This plan never authorizes a flight/door movement or custody. */
public final class NervFlightGatePlanR52
{
    public record Mesh(NervRigidMeshSweepR52 geometry,RigidTransform frame){}
    private record Sample(UUID actor,RigidTransform frame,float progress){}
    private final long at;private final String directory;private final Map<BlockPos,BlockState> cells;private final Map<UUID,List<Mesh>> open;private final List<Sample> samples;
    private NervFlightGatePlanR52(ServerLevel l,Map<BlockPos,BlockState> cells,Map<UUID,List<Mesh>> open,List<Sample> samples)
    {at=l.getGameTime();directory=NervRouteRuntimeR52.flightContext(l).directory().fingerprint();this.cells=Map.copyOf(cells);this.open=Map.copyOf(open);this.samples=List.copyOf(samples);}
    public static NervFlightGatePlanR52 inspect(ServerLevel l,Map<String,NervAssemblyOwnerR52.Gate> declared,Set<String> ids,Set<UUID> members)
    {
        var context=NervRouteRuntimeR52.flightContext(l);if(context==null)return null;var cells=new HashMap<BlockPos,BlockState>();var open=new HashMap<UUID,List<Mesh>>();var samples=new ArrayList<Sample>();
        for(String id:ids)
        {
            var g=declared.get(id);if(g==null||!sampleCurrent(l,context.directory(),g))return null;
            var actor=l.getEntity(g.visual());RigidTransform frame;float progress;List<Mesh> mesh=new ArrayList<>();var moving=new HashSet<BlockPos>();var supports=new HashSet<BlockPos>();for(var p:g.supports())supports.add(p.at());for(var step:g.collisionSteps())for(var cell:step)moving.add(cell.at());
            if(actor instanceof NervSiloDoorEntity door){if(!door.matchesDeclaredR52(g.siloHatch()))return null;frame=door.actualFrameR52();progress=door.actualOpenProgressR52();if(!door.clearDeclaredSweepR52(l,progress,1,members,moving,supports))return null;for(var p:door.declaredGeometryR52().pieces(1))mesh.add(new Mesh(new NervRigidMeshSweepR52(p.part().xyz()),frame.compose(p.local())));}
            else if(actor instanceof NervHangarDoorEntity door){if(door.declaredStackR52()==null)return null;frame=door.actualFrameR52();progress=door.actualOpenProgressR52();if(!door.clearDeclaredSweepR52(l,progress,1,members,moving,supports))return null;for(var p:door.declaredGeometryR52().pieces(1))mesh.add(new Mesh(new NervRigidMeshSweepR52(p.part().xyz()),frame.compose(p.local())));}
            else return null;if(!NervAirTransportManifestR52.same(frame,g.frame()))return null;
            for(var step:g.collisionSteps())for(var cell:step){var expected=progress==1?cell.open():cell.closed();if(!l.hasChunkAt(cell.at())||!l.getBlockState(cell.at()).equals(expected)||cells.putIfAbsent(cell.at(),expected)!=null)return null;}
            open.put(g.visual(),List.copyOf(mesh));samples.add(new Sample(g.visual(),frame,progress));
        }
        return new NervFlightGatePlanR52(l,cells,open,samples);
    }
    /** Exact stopped sample only. A partly open gate remains blocked; this
     * check permits restoring an already owned gate lease, never passage. */
    public static boolean sampleCurrent(ServerLevel l,NervRouteDirectoryR52 directory,NervAssemblyOwnerR52.Gate g)
    {
        if(g==null||directory.resource(g.resource())==null||directory.resource(g.resource()).kind()!=NervRouteDirectoryR52.ResourceKind.DOOR)return false;
        for(var p:g.supports())if(!l.hasChunkAt(p.at())||!l.getBlockState(p.at()).equals(p.expected()))return false;
        var actor=l.getEntity(g.visual());RigidTransform frame;float progress;
        if(actor instanceof NervSiloDoorEntity door){if(g.kind()!=NervAssemblyOwnerR52.GateKind.SILO||door.getVariant()!=g.variant()||door.getBulkheadStage()!=g.stage()||!door.matchesDeclaredR52(g.siloHatch()))return false;frame=door.actualFrameR52();progress=door.actualOpenProgressR52();}
        else if(actor instanceof NervHangarDoorEntity door){if(g.kind()!=NervAssemblyOwnerR52.GateKind.HANGAR||door.getVariant()!=g.variant()||!door.matchesDeclaredR52(g.hangarStack()))return false;frame=door.actualFrameR52();progress=door.actualOpenProgressR52();}
        else return false;if(!Float.isFinite(progress)||progress<0||progress>1||!NervAirTransportManifestR52.same(frame,g.frame()))return false;
        for(var step:g.collisionSteps())for(var cell:step)if(!l.hasChunkAt(cell.at())||!l.getBlockState(cell.at()).equals(progress==1?cell.open():cell.closed()))return false;
        return true;
    }
    public boolean current(ServerLevel l)
    {var ctx=NervRouteRuntimeR52.flightContext(l);if(l.getGameTime()!=at||ctx==null||!ctx.directory().fingerprint().equals(directory))return false;for(var cell:cells.entrySet())if(!l.hasChunkAt(cell.getKey())||!l.getBlockState(cell.getKey()).equals(cell.getValue()))return false;for(var s:samples){var e=l.getEntity(s.actor());if(e instanceof NervSiloDoorEntity door){if(door.actualOpenProgressR52()!=s.progress()||!NervAirTransportManifestR52.same(door.actualFrameR52(),s.frame()))return false;}else if(e instanceof NervHangarDoorEntity door){if(door.actualOpenProgressR52()!=s.progress()||!NervAirTransportManifestR52.same(door.actualFrameR52(),s.frame()))return false;}else return false;}return true;}
    public List<Mesh> openMeshes(UUID actor){return open.get(actor);}
    public boolean isDeclaredSeal(ServerLevel l,AABB obstacle)
    {var at=BlockPos.containing(obstacle.minX,obstacle.minY,obstacle.minZ);return cells.containsKey(at)&&l.getBlockState(at).equals(cells.get(at))&&obstacle.minX>=at.getX()&&obstacle.maxX<=at.getX()+1&&obstacle.minY>=at.getY()&&obstacle.maxY<=at.getY()+1&&obstacle.minZ>=at.getZ()&&obstacle.maxZ<=at.getZ()+1;}
}
