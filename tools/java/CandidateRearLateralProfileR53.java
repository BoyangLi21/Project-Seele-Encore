package com.projectseele.world;

import java.util.*;
import net.minecraft.world.phys.Vec3;

/** Uninstalled new-hardware candidate. Existing rail contacts occur only at retraction zero. */
public final class CandidateRearLateralProfileR53
{
    public static final double RETRACTION=.65;
    private final CarrierRearGuideR53.Hardware hardware;
    private final CandidateAboveFloorCarrierProfileR53 aboveFloor;
    public CandidateRearLateralProfileR53(CarrierRearGuideR53.Hardware hardware)
    {this.hardware=hardware;aboveFloor=new CandidateAboveFloorCarrierProfileR53(hardware);}
    public CarrierRearGuideR53.Hardware hardware(){return hardware;}
    public CandidateAboveFloorCarrierProfileR53 aboveFloor(){return aboveFloor;}
    public List<NervLegacyCarrierRideR52.Piece> partsAt(RigidTransform root,float rise,Vec3 direction,double slide,double lift,double retract)
    {
        if(!Double.isFinite(retract)||retract<0||retract>1)throw new IllegalArgumentException("Bounded transverse actuator required");
        var out=new ArrayList<NervLegacyCarrierRideR52.Piece>();var baseline=aboveFloor.rearPartsAt(root,rise,direction,slide,lift);
        for(int i=0;i<baseline.size();i++)
        {
            var p=baseline.get(i);var template=hardware.parts().get(i);boolean moves=template.role().equals("ball")||template.role().equals("lateral_rod")||template.frame().equals("rear_l")||template.frame().equals("rear_r");
            if(!moves){out.add(p);continue;}
            int side=p.name().startsWith("rear/rear_l/")?-1:1;var f=p.frame();var origin=f.translation().add(root.transformVector(new Vec3(-side*RETRACTION*retract,0,0)));
            out.add(new NervLegacyCarrierRideR52.Piece(p.name(),p.mesh(),p.rgb(),new RigidTransform(origin,f.qx(),f.qy(),f.qz(),f.qw()),p.role()));
        }
        return List.copyOf(out);
    }
}
