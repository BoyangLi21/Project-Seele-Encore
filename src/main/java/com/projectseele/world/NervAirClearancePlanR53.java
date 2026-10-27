package com.projectseele.world;

import com.projectseele.world.NervAirTransportManifestR52.*;
import net.minecraft.nbt.CompoundTag;

/** A continuous, saved clearance route inside one original flight corridor. */
final class NervAirClearancePlanR53
{
    static final String KEY="AirClearancePlanR53";
    static boolean translationOnly(Frame a,Frame b)
    {
        return a.cargo()!=null&&b.cargo()!=null&&Math.abs(a.plane().qx())<1e-7&&Math.abs(a.plane().qz())<1e-7
                &&Math.abs(b.plane().qx())<1e-7&&Math.abs(b.plane().qz())<1e-7&&NervRigidMeshSweepR52.angular(a.plane(),b.plane())<1e-7
                &&NervRigidMeshSweepR52.angular(a.cargo(),b.cargo())<1e-7
                &&a.cargo().translation().subtract(a.plane().translation()).distanceToSqr(b.cargo().translation().subtract(b.plane().translation()))<1e-10;
    }
    static Frame raised(Frame frame,double altitude)
    {
        double dy=altitude-frame.plane().translation().y;
        return new Frame(RigidTransform.of(frame.plane().translation().add(0,dy,0),frame.plane().rotation()),
                RigidTransform.of(frame.cargo().translation().add(0,dy,0),frame.cargo().rotation()),frame.rig());
    }
    static CompoundTag create(String corridor,int leg,int age,Frame from,Frame to)
    {
        var plan=new CompoundTag();plan.putString("Corridor",corridor);plan.putInt("Leg",leg);plan.putInt("OriginalAge",age);
        plan.put("From",NervAircraftFrameCodecR52.encode(from));plan.put("To",NervAircraftFrameCodecR52.encode(to));
        plan.putDouble("Altitude",Math.max(from.plane().translation().y,to.plane().translation().y)+32);
        return plan;
    }
    static CompoundTag createPickupExit(String corridor,int leg,int age,Frame from,Frame to)
    {
        var plan=create(corridor,leg,age,from,to);plan.putBoolean("PickupExit",true);return plan;
    }
    private static Frame side(Frame frame,int candidate)
    {
        double[][] directions={{1,0},{-1,0},{0,1},{0,-1},{1,1},{1,-1},{-1,1},{-1,-1}};
        double[] radii={.5,1,2,3,4,8,16,32};double radius=radii[candidate/8];var d=directions[candidate%8];
        var offset=new net.minecraft.world.phys.Vec3(d[0]*radius,0,d[1]*radius);
        return new Frame(RigidTransform.of(frame.plane().translation().add(offset),frame.plane().rotation()),
                RigidTransform.of(frame.cargo().translation().add(offset),frame.cargo().rotation()),frame.rig());
    }
    static Frame point(CompoundTag plan,int index)
    {
        var from=NervAircraftFrameCodecR52.decode(plan.getCompound("From"));var to=NervAircraftFrameCodecR52.decode(plan.getCompound("To"));
        if(plan.getBoolean("PickupExit"))return switch(index)
        {case 0->from;case 1->side(from,plan.getInt("Candidate"));case 2->side(to,plan.getInt("Candidate"));case 3->to;default->throw new IllegalArgumentException("Pickup exit point");};
        return switch(index){case 0->from;case 1->raised(from,plan.getDouble("Altitude"));case 2->raised(to,plan.getDouble("Altitude"));case 3->to;default->throw new IllegalArgumentException("Clearance point");};
    }
    static int slices(CompoundTag plan,int segment)
    {return Math.max(1,(int)Math.ceil(point(plan,segment).plane().translation().distanceTo(point(plan,segment+1).plane().translation())/32));}
    static int ticks(CompoundTag plan,int segment)
    {
        double distance=point(plan,segment).plane().translation().distanceTo(point(plan,segment+1).plane().translation());
        return Math.max(20,(int)Math.ceil(distance*1.875/(segment==1?12:2.8)));
    }
    static boolean raise(CompoundTag plan)
    {
        if(plan.getBoolean("PickupExit"))
        {
            int next=plan.getInt("Candidate")+1;if(next>=64)return false;
            plan.putInt("Candidate",next);plan.putInt("CheckSegment",0);plan.putInt("CheckSlice",0);return true;
        }
        double base=Math.max(point(plan,0).plane().translation().y,point(plan,3).plane().translation().y);
        if(plan.getDouble("Altitude")>=base+256)return false;
        plan.putDouble("Altitude",plan.getDouble("Altitude")+32);plan.putInt("CheckSegment",0);plan.putInt("CheckSlice",0);return true;
    }
    private NervAirClearancePlanR53(){}
}
