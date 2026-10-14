package com.projectseele.world;

import java.util.*;
import net.minecraft.world.phys.*;
import org.joml.Quaternionf;

/** Finite sole/shape contract; synthetic fixtures never become map supports. */
public final class NervDeliverySoleSupportR53Test
{
    private static int checks;
    private static void check(boolean value,String why)
    {
        checks++;
        if(!value)throw new AssertionError(why);
    }
    private static EvaOriginalMeshGeometryR52.Part sole(String bone,double x,double y,boolean triangle)
    {
        double[] vertices=triangle
                ?new double[]{x,y,-.5,x+1,y,-.5,x,y,.5}
                :new double[]{x,y,-.5,x+1,y,-.5,x,y,.5,x+1,y,-.5,x+1,y,.5,x,y,.5};
        return new EvaOriginalMeshGeometryR52.Part(bone,"synthetic/test","0".repeat(64),vertices,new AABB(x,y,-.5,x+1,y,.5));
    }
    private static EvaOriginalMeshGeometryR52.Geometry feet(double rightY,boolean triangle)
    {
        return new EvaOriginalMeshGeometryR52.Geometry(0,"synthetic-test-source",
                List.of(sole("foot_l",-2.5,0,triangle),sole("foot_r",1.5,rightY,triangle)));
    }
    private static AABB support(double x,double z,double X,double Z)
    {
        return new AABB(x,-1,z,X,0,Z);
    }
    private static boolean bears(List<AABB> supports)
    {
        return NervFlightProofR52.finiteDeliverySolesR53(feet(0,false),RigidTransform.identity(),supports);
    }
    private static List<AABB> hole(double x,double z,double X,double Z)
    {
        return List.of(support(-3,-1,x,1),support(X,-1,3,1),support(x,-1,X,z),support(x,Z,X,1));
    }
    public static void main(String[] args)
    {
        check(bears(List.of(support(-3,-1,3,1))),"Both complete actual sole facets on one native top");
        check(!bears(List.of(support(-2.05,-.05,-1.95,.05),support(1.95,-.05,2.05,.05))),
                "Two old contact-point pedestals cannot carry the complete soles");
        var corners=new ArrayList<AABB>();
        for(double x:new double[]{-2.5,-1.5,1.5,2.5})for(double z:new double[]{-.5,.5})
            corners.add(support(x-.01,z-.01,x+.01,z+.01));
        check(!bears(corners),"Supporting every triangle vertex does not cover its interior");
        check(!bears(hole(-2.35,.20,-2.15,.40)),"Interior hole away from the old midpoint is rejected");
        check(!bears(hole(-2.10001,-1,-2.10,1)),"A real narrow seam remains a missing sole strip");
        var duplicate=new ArrayList<>(hole(-2.35,.20,-2.15,.40));
        duplicate.addAll(duplicate);
        check(!bears(duplicate),"Overlapping supports cannot double-count away a hole");
        check(bears(List.of(support(-3,-1,-2,1),support(-2,-1,0,1),support(0,-1,3,1))),
                "Adjacent native shapes cover one sole without a false boundary gap");
        check(!bears(List.of(support(-3,-1,0,1))),"Both original feet are independently required");
        check(!bears(List.of(new AABB(-3,-1,-1,3,-.003,1))),"Wrong ground height is rejected");
        check(bears(List.of(new AABB(-3,-1,-1,3,-.001,1))),"Existing measured two-millimetre fit tolerance is retained");
        check(!NervFlightProofR52.finiteDeliverySolesR53(feet(.01,false),RigidTransform.identity(),List.of(support(-3,-1,3,1))),
                "A floating second actual foot cannot borrow the first foot's support");
        var root=new RigidTransform(new Vec3(-1250,175,-1496.5),0,1,0,0);
        var transformed=NervRigidMeshSweepR52.transformed(support(-3,-1,3,1),root);
        check(NervFlightProofR52.finiteDeliverySolesR53(feet(0,false),root,List.of(transformed)),
                "World translation and original yaw180 preserve the finite faces");
        var tilted=RigidTransform.of(Vec3.ZERO,new Quaternionf().rotationX(.1F));
        check(!NervFlightProofR52.finiteDeliverySolesR53(feet(0,false),tilted,List.of(support(-3,-1,3,1))),
                "A tilted cargo frame cannot claim upright delivery support");
        var oneFoot=new EvaOriginalMeshGeometryR52.Geometry(0,"synthetic-test-source",List.of(sole("foot_l",-2.5,0,false)));
        check(!NervFlightProofR52.finiteDeliverySolesR53(oneFoot,RigidTransform.identity(),List.of(support(-3,-1,3,1))),
                "Missing original right-foot geometry is held");
        check(NervFlightProofR52.finiteDeliverySolesR53(feet(0,true),RigidTransform.identity(),hole(-1.65,.35,-1.5,.5)),
                "An empty corner outside the actual triangular sole is not falsely required");
        check(!NervFlightProofR52.finiteDeliverySolesR53(feet(0,false),RigidTransform.identity(),List.of()),
                "No declared native support is not accepted");
        System.out.println("R53 finite delivery soles PASS checks="+checks+"; synthetic geometry contract only, native frozen deliveries remain required");
    }
    private NervDeliverySoleSupportR53Test(){}
}
