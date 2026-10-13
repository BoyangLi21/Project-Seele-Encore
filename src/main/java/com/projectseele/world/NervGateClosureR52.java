package com.projectseele.world;
import com.projectseele.entity.*;
import java.util.*;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.*;
import net.minecraft.world.phys.AABB;

/** Exact finite closed voxel mask admission before the first closing step.
 * This is geometry only; the one directory/broker still owns every lease. */
public final class NervGateClosureR52 {
    private record Row(int y,int x0,int x1){}
    private record Column(int x0,int x1,int z0,int z1){}
    public static List<AABB> coalesce(Set<BlockPos> cells) {
        var rows=new TreeMap<Integer,TreeMap<Integer,SortedSet<Integer>>>();for(var p:cells)rows.computeIfAbsent(p.getY(),k->new TreeMap<>()).computeIfAbsent(p.getZ(),k->new TreeSet<>()).add(p.getX());
        var alongZ=new HashMap<Row,TreeMap<Integer,Integer>>();for(var layer:rows.entrySet())for(var line:layer.getValue().entrySet()){Integer begin=null,last=null;for(int x:line.getValue()){if(begin==null){begin=last=x;}else if(x==last+1)last=x;else{alongZ.computeIfAbsent(new Row(layer.getKey(),begin,last+1),k->new TreeMap<>()).put(line.getKey(),line.getKey()+1);begin=last=x;}}if(begin!=null)alongZ.computeIfAbsent(new Row(layer.getKey(),begin,last+1),k->new TreeMap<>()).put(line.getKey(),line.getKey()+1);}
        var alongY=new HashMap<Column,SortedSet<Integer>>();for(var entry:alongZ.entrySet()){var row=entry.getKey();Integer first=null,last=null;for(int z:entry.getValue().keySet()){if(first==null){first=last=z;}else if(z==last+1)last=z;else{alongY.computeIfAbsent(new Column(row.x0(),row.x1(),first,last+1),k->new TreeSet<>()).add(row.y());first=last=z;}}if(first!=null)alongY.computeIfAbsent(new Column(row.x0(),row.x1(),first,last+1),k->new TreeSet<>()).add(row.y());}
        var out=new ArrayList<AABB>();for(var entry:alongY.entrySet()){var column=entry.getKey();Integer first=null,last=null;for(int y:entry.getValue()){if(first==null){first=last=y;}else if(y==last+1)last=y;else{out.add(new AABB(column.x0(),first,column.z0(),column.x1(),last+1,column.z1()));first=last=y;}}if(first!=null)out.add(new AABB(column.x0(),first,column.z0(),column.x1(),last+1,column.z1()));}return List.copyOf(out);
    }
    public static boolean clearActualActors(ServerLevel level,Entity door,Set<BlockPos> closedMask) {
        var boxes=coalesce(closedMask);if(boxes.isEmpty())return false;AABB broad=null;for(var b:boxes){if(!EntryPlugEjectionR48.loaded(level,b))return false;broad=broad==null?b:broad.minmax(b);}
        if(!clearIndependentMeshes(NervFlightProofR52.detachedCarrierObstacles(level),boxes))return false;
        for(var actor:level.getEntities(door,broad.inflate(200),e->e.isAlive()&&!e.isSpectator()&&(e instanceof LivingEntity||e.canBeCollidedWith()||e instanceof UNTransportEntity||e instanceof EntryPlugCarrierEntity))){var meshes=NervFlightProofR52.actualObstacleMeshes(actor);if(meshes==null||meshes.isEmpty()){var bounds=actor instanceof UNTransportEntity plane?plane.getBoundingBoxForCulling():actor.getBoundingBox();if(boxes.stream().anyMatch(b->b.intersects(bounds)))return false;}else for(var mesh:meshes)for(var b:boxes)if(mesh.mesh().intersects(mesh.frame(),mesh.endFrame(),b,.005))return false;}
        return true;
    }
    public static boolean clearIndependentMeshes(List<NervFlightProofR52.ObstacleMesh> meshes,List<AABB> boxes)
    {if(meshes==null)return false;for(var mesh:meshes)for(var box:boxes)if(mesh.mesh().intersects(mesh.frame(),mesh.endFrame(),box,.005))return false;return true;}
    private NervGateClosureR52(){}
}
