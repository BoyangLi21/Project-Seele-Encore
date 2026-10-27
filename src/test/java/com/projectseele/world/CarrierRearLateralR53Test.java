package com.projectseele.world;

import java.nio.file.*;
import java.util.*;
import net.minecraft.world.phys.*;

/** Small actuator/contact regressions; no world-clearance claim. */
public final class CarrierRearLateralR53Test
{
    private static void require(boolean value,String message)
    {if(!value)throw new AssertionError(message);}

    public static void main(String[] args)throws Exception
    {
        double state=0;
        for(int i=0;i<20;i++)state=CarrierRearLateralR53.advance(state,1);
        require(state==1,"Retraction did not reach exact bounded stop");
        for(int i=0;i<20;i++)state=CarrierRearLateralR53.advance(state,0);
        require(state==0,"Expansion did not reach exact bounded stop");
        var root=new RigidTransform(new Vec3(30.5,-1062,321.3),0,0,0,1);
        var compact=new CarrierMountProfileR53.State(false,0,1);
        require(compact.payloadFrame(root).equals(CarrierMountProfileR53.LEGACY.payloadFrame(root)),"Lateral stroke moved original payload");
        require(compact.bodyFrame(root,.5F).equals(CarrierMountProfileR53.LEGACY.bodyFrame(root,.5F)),"Lateral stroke changed original body rise");
        require(compact.headLiftFrame(root,1,7).equals(CarrierMountProfileR53.LEGACY.headLiftFrame(root,1,7)),"Lateral stroke changed head lift");
        require(CarrierRearLateralR53.faceArea(new AABB(0,0,0,1,1,1),new AABB(0,1,0,1,2,1),1)==1,"Finite mating face lost");
        require(CarrierRearLateralR53.faceArea(new AABB(0,0,0,1,1,1),new AABB(0,1.02,0,1,2,1),1)==0,"Separated sleeve accepted");
        require(CarrierRearLateralR53.faceArea(new AABB(0,0,0,1,1,1),new AABB(1,1,0,2,2,1),1)==0,"Line contact accepted as finite support");
        if(args.length==1)
        {
            var hardware=CarrierRearGuideR53.readHardware(Files.readAllBytes(Path.of(args[0])),"uninstalled-lateral-contact-fixture");
            require(CarrierRearLateralR53.bearings(hardware,0,1),"Selected full stroke lost finite rod/sleeve contact");
            var rod=hardware.parts().stream().filter(p->p.role().equals("lateral_rod")).findFirst().orElseThrow();
            double[] damaged=rod.mesh().triangles();
            // Duplicate one triangle over its sibling. Bounds and summed face
            // area stay unchanged, but half the support surface is missing.
            boolean found=false;
            for(int i=0;i<damaged.length&&!found;i+=9)for(int j=i+9;j<damaged.length;j+=9)
            {
                boolean plane=false;for(int axis=0;axis<3;axis++)
                    if(damaged[i+axis]==damaged[i+3+axis]&&damaged[i+axis]==damaged[i+6+axis]
                        &&damaged[j+axis]==damaged[j+3+axis]&&damaged[j+axis]==damaged[j+6+axis]
                        &&damaged[i+axis]==damaged[j+axis])plane=true;
                if(plane){System.arraycopy(damaged,i,damaged,j,9);found=true;break;}
            }
            require(found&&!CarrierRearLateralR53.rectangular(new NervRigidMeshSweepR52(damaged)),"Incomplete real bearing face accepted via box/area");
        }
        System.out.println("PASS lateral actuator bounds, unchanged load datum and finite contact regressions");
    }
    private CarrierRearLateralR53Test(){}
}
