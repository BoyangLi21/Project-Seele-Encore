package com.projectseele.world;

import com.projectseele.world.NervAirTransportManifestR52.*;
import net.minecraft.world.phys.Vec3;

/** Saved pickup-side plans retain the actual stop and original corridor endpoint. */
public final class NervAirClearancePlanR53Test
{
    static int checks;
    static void check(boolean value,String why){checks++;if(!value)throw new AssertionError(why);}
    static void same(Frame a,Frame b,String why)
    {check(NervAirTransportManifestR52.same(a.plane(),b.plane())&&NervAirTransportManifestR52.same(a.cargo(),b.cargo())&&a.rig().equals(b.rig()),why);}
    public static void main(String[] args)
    {
        var plane=new RigidTransform(new Vec3(-1252.8747268340053,262.6589577,-1521.6224063612885),0,0,0,1);
        var cargo=new RigidTransform(plane.translation().add(0,-84,0),0,1,0,0);
        var from=new Frame(plane,cargo,new Rig(84,1,0));var to=NervAirClearancePlanR53.raised(from,300);
        check(NervAirClearancePlanR53.translationOnly(from,to),"Actual captured upright translation accepted");
        var plan=NervAirClearancePlanR53.createPickupExit("lifted",0,13,from,to);
        double[] expectedRadii={.5,1,2,3,4,8,16,32};
        for(int candidate=0;candidate<64;candidate++)
        {
            check(plan.getInt("Candidate")==candidate,"Bounded candidate cursor");
            var a=NervAirClearancePlanR53.point(plan,0);var b=NervAirClearancePlanR53.point(plan,1);
            var c=NervAirClearancePlanR53.point(plan,2);var d=NervAirClearancePlanR53.point(plan,3);
            same(a,from,"No restart or snap to original pickup floor");same(d,to,"Original lifted endpoint retained for ALIGN");
            var shift=b.plane().translation().subtract(a.plane().translation());
            check(shift.y==0&&Math.abs(Math.max(Math.abs(shift.x),Math.abs(shift.z))-expectedRadii[candidate/8])<1e-8,"Declared half-metre through 32-metre component offsets");
            check(c.plane().translation().subtract(d.plane().translation()).distanceToSqr(shift)<1e-18,"Same side offset at upper stop");
            check(c.plane().translation().x==b.plane().translation().x&&c.plane().translation().z==b.plane().translation().z,"Middle pickup segment remains vertical");
            for(int segment=0;segment<3;segment++)
            {
                var p=NervAirClearancePlanR53.point(plan,segment);var q=NervAirClearancePlanR53.point(plan,segment+1);
                check(NervAirClearancePlanR53.translationOnly(p,q),"No rotation or cargo/aircraft offset change");
                same(p.interpolate(q,0),p,"Exact segment start");same(p.interpolate(q,1),q,"Exact segment end");
                check(NervAirClearancePlanR53.ticks(plan,segment)>=20&&NervAirClearancePlanR53.slices(plan,segment)>=1,"Finite nonzero saved segment timing");
            }
            var restored=plan.copy();restored.putBoolean("Validated",true);restored.putInt("Segment",1);restored.putInt("Age",7);
            for(int point=0;point<4;point++)same(NervAirClearancePlanR53.point(plan,point),NervAirClearancePlanR53.point(restored,point),"Persisted execution state retains geometry");
            plan.putInt("CheckSegment",2);plan.putInt("CheckSlice",4);
            check(NervAirClearancePlanR53.raise(plan)==(candidate<63),"Only exhaustion rejects all 64 pickup candidates");
            if(candidate<63)check(plan.getInt("CheckSegment")==0&&plan.getInt("CheckSlice")==0,"Next candidate restarts all segment proofs");
            check(plan.getInt("OriginalAge")==13&&plan.getInt("Leg")==0,"Parent corridor clock remains original during detour");
        }
        plan.putBoolean("Rejected",true);
        var retry=NervAirClearancePlanR53.createPickupExit(plan.getString("Corridor"),plan.getInt("Leg"),plan.getInt("OriginalAge"),from,NervAirClearancePlanR53.point(plan,3));
        same(NervAirClearancePlanR53.point(retry,0),from,"Regenerated derived plan never moves the actual halted frame");
        same(NervAirClearancePlanR53.point(retry,3),to,"Regenerated plan retains original lifted endpoint");
        check(!retry.getBoolean("Rejected")&&retry.getInt("Candidate")==0&&retry.getInt("OriginalAge")==13,"Retry resets only derived search state");
        retry.putInt("Candidate",24);
        double fineShift=NervAirClearancePlanR53.point(retry,1).cargo().translation().x-from.cargo().translation().x;
        check(fineShift==3&&-1269.0321136137904+fineShift>=-1266.05&&-1237.3798175475063+fineShift<=-1233.95,"Search includes the measured narrow 3m box-fit window; full source path proof remains required");
        check(-1237.3798175475063+4>-1233.95,"Old minimum 4m step overshoots that window");
        var cruise=NervAirClearancePlanR53.create("cruise",2,7,from,to);
        check(NervAirClearancePlanR53.point(cruise,1).plane().translation().y==332,"Ordinary long-route rise retained");
        for(int i=0;i<7;i++)check(NervAirClearancePlanR53.raise(cruise),"Ordinary bounded altitude search retained");
        check(!NervAirClearancePlanR53.raise(cruise),"Ordinary altitude cap retained");
        System.out.println("PASS R54 pickup-side detour continuity, saved state, candidate bounds and ordinary route regression: "+checks);
    }
}
