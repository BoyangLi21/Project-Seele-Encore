package com.projectseele.world;

import com.projectseele.entity.*;
import java.util.*;
import java.util.concurrent.*;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.phys.Vec3;
import com.projectseele.world.NervFlightProofR52.ObstacleMesh;

/** One immutable complete-source exit receipt for an already trapped assembly. */
final class NervStationaryActorContactR54
{
    record Snapshot(Object state,List<ObstacleMesh> meshes)
    {
        Snapshot { meshes=List.copyOf(meshes); }
        boolean contains(ObstacleMesh observed)
        {return meshes.stream().anyMatch(mesh->same(mesh,observed));}
        boolean current(Snapshot next)
        {
            if(next==null||!state.equals(next.state)||meshes.size()!=next.meshes.size())return false;
            for(int i=0;i<meshes.size();i++)if(!same(meshes.get(i),next.meshes.get(i)))return false;
            return true;
        }
        private static boolean same(ObstacleMesh a,ObstacleMesh b)
        {
            return a.frame().equals(a.endFrame())&&b.frame().equals(b.endFrame())&&a.frame().equals(b.frame())
                    &&(a.mesh()==b.mesh()||Arrays.equals(a.mesh().triangles(),b.mesh().triangles()));
        }
    }
    private final UUID actor;
    private final Snapshot captured;
    private final Map<Vec3,CompletableFuture<NervRescueActorEgressR53>> exits=new HashMap<>();
    private final EvaOriginalMeshGeometryR52.Geometry assembly;
    private final RigidTransform root;
    private final List<NervRigidMeshSweepR52> fixed;

    NervStationaryActorContactR54(UUID actor,Snapshot captured,EvaOriginalMeshGeometryR52.Geometry assembly,RigidTransform root)
    {
        this.actor=actor;this.captured=captured;this.assembly=assembly;this.root=root;
        // Workers receive immutable source values only, never a live entity.
        var world=new ArrayList<NervRigidMeshSweepR52>();
        for(var part:captured.meshes())
        {
            var xyz=part.mesh().triangles();
            for(int i=0;i<xyz.length;i+=3)
            {
                var p=part.frame().transformPoint(new Vec3(xyz[i],xyz[i+1],xyz[i+2]));
                xyz[i]=p.x;xyz[i+1]=p.y;xyz[i+2]=p.z;
            }
            world.add(new NervRigidMeshSweepR52(xyz));
        }
        fixed=List.copyOf(world);
    }
    boolean separates(ServerLevel level,Entity observed,RigidTransform from,RigidTransform to,ObstacleMesh obstacle)
    {
        if(!actor.equals(observed.getUUID())||level.getEntity(actor)!=observed||!captured.contains(obstacle)
                ||!captured.current(snapshot(observed)))return false;
        var offset=to.translation().subtract(root.translation());
        double length=offset.length();
        var direction=length==0?new Vec3(0,1,0):offset.scale(1/length);
        // Coordinate subtraction and easing can produce different doubles on
        // the same ray. Reuse its immutable work within the collision precision,
        // including sub-millimetre first steps (Vec3.normalize rounds those off).
        double reach=Math.max(96,Math.max(length,from.translation().distanceTo(root.translation())));
        double angularError=.005/reach;
        for(var axis:exits.keySet())if(direction.dot(axis)>0&&direction.cross(axis).lengthSqr()<=angularError*angularError)
        {direction=axis;break;}
        var exit=exits.get(direction);
        if(exit==null)
        {
            var axis=direction;
            try{exit=NervGeometryWorkR53.submit(()->true,()->new NervRescueActorEgressR53(assembly,root,fixed,RigidTransform.identity(),axis,true));}
            catch(RejectedExecutionException busy){return false;}
            exits.put(direction,exit);
        }
        if(!exit.isDone())return false;
        try{return exit.join().separates(from,to);}
        catch(CompletionException|CancellationException unavailable){return false;}
    }
    static Snapshot snapshot(Entity actor)
    {
        if(actor instanceof NervSiloDoorEntity hatch)
        {
            if(hatch.declaredSpecR52()==null)return null;
            float open=hatch.actualOpenProgressR52();boolean endpoint=open==0||open==1;
            var meshes=new ArrayList<ObstacleMesh>();
            for(var part:hatch.declaredGeometryR52().pieces(open))if(endpoint||!part.moving())
                meshes.add(new ObstacleMesh(NervObstacleMeshesR53.part(part.part()),hatch.actualFrameR52().compose(part.local())));
            return new Snapshot(List.of(hatch.declaredSpecR52(),hatch.actualFrameR52(),endpoint?open:-1F),meshes);
        }
        if(actor instanceof YashimaCannonEntityR52 cannon)
        {
            var geometry=cannon.geometryR52();var cradle=cannon.cradleR52();
            if(geometry==null||cradle==null)return null;
            var meshes=NervFlightProofR52.actualObstacleMeshes(actor);if(meshes==null||meshes.isEmpty())return null;
            var state=new CompoundTag();state.put("Geometry",YashimaCannonGeometryR52.encode(geometry));state.put("Cradle",cradle.encode());
            state.putBoolean("Loaded",cannon.loadedR52());
            return new Snapshot(List.of(state,cannon.position(),new org.joml.Quaternionf(cannon.aimR52(1))),meshes);
        }
        // Only actual declared source equipment can seed a receipt. Unknown
        // actors keep the ordinary collision path; their AABB is not a source.
        var meshes=NervFlightProofR52.actualObstacleMeshes(actor);
        return meshes==null||meshes.isEmpty()||meshes.stream().anyMatch(p->!p.frame().equals(p.endFrame()))
                ?null:new Snapshot(actor.getType(),meshes);
    }
}
