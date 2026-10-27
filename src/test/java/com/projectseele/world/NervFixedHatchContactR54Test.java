package com.projectseele.world;

import com.projectseele.entity.SiloHatchMechanism;
import java.util.List;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;

/** The open cannon hatch casing is fixed; none of its independently moving leaves is. */
public final class NervFixedHatchContactR54Test
{
    public static void main(String[] args)throws Exception
    {
        var source=NervSiloHatchGeometryR52.loadClasspath(new SiloHatchMechanism.Spec(39,53,80,80,1,-2.02));
        var frame=new RigidTransform(new Vec3(-1251.5,174.02,-1397.5),0,0,0,1);int checks=0;
        for(float phase:new float[]{0,.25F,.5F,.75F,1})for(var piece:source.pieces(phase))
        {
            var mesh=NervObstacleMeshesR53.part(piece.part());var at=frame.compose(piece.local());
            var obstacle=new NervFlightProofR52.ObstacleMesh(mesh,at);
            if(NervFlightProofR52.fixedHatchMemberR54(source,frame,obstacle)==piece.moving())
                throw new AssertionError("Fixed-source identity differs at "+phase+": "+piece.part().name());
            checks++;
            var shifted=new RigidTransform(at.translation().add(0,.01,0),at.qx(),at.qy(),at.qz(),at.qw());
            if(NervFlightProofR52.fixedHatchMemberR54(source,frame,new NervFlightProofR52.ObstacleMesh(mesh,at,shifted)))
                throw new AssertionError("Moving casing cannot reuse a static contact");
            checks++;
            if(!piece.moving())
            {
                var rebuilt=new NervRigidMeshSweepR52(mesh.triangles());
                if(!NervFlightProofR52.fixedHatchMemberR54(source,frame,new NervFlightProofR52.ObstacleMesh(rebuilt,at)))
                    throw new AssertionError("Immutable source cache rebuild lost the exact fixed member");
                checks++;
            }
        }
        var panel=source.pieces(1).stream().filter(p->p.moving()&&p.part().name().equals("panel/1")
                &&p.local().translation().x>0).findFirst().orElseThrow();
        var mesh=NervObstacleMeshesR53.part(panel.part());var panelFrame=frame.compose(panel.local());
        var bounds=mesh.envelope(panelFrame,panelFrame);var centre=bounds.getCenter();
        double[] body={centre.x-.1,centre.y-1,centre.z,centre.x+.1,centre.y-1,centre.z,centre.x,centre.y+1,centre.z};
        var geometry=new EvaOriginalMeshGeometryR52.Geometry(0,"endpoint-contact-fixture",List.of(
                new EvaOriginalMeshGeometryR52.Part("body","fixture","fixture",body,
                        new AABB(centre.x-.1,centre.y-1,centre.z,centre.x+.1,centre.y+1,centre.z))));
        var initial=RigidTransform.identity();var raised=new RigidTransform(new Vec3(0,3,0),0,0,0,1);
        var exit=new NervRescueActorEgressR53(geometry,initial,List.of(mesh),panelFrame);
        if(!exit.separates(initial,initial)||!exit.separates(initial,raised))throw new AssertionError("Original stopped open leaf permits finite initial vertical exit");
        if(exit.separates(raised,new RigidTransform(new Vec3(0,4,0),0,0,0,1))
                ||exit.separates(initial,new RigidTransform(new Vec3(.01,3,0),0,0,0,1)))
            throw new AssertionError("Endpoint contact cannot authorize post-exit or horizontal motion");
        checks+=4;
        NervRescueActorEgressR53Test.main(args);
        System.out.println("PASS fixed hatch source phase/motion/cache identity: "+checks);
    }
}
