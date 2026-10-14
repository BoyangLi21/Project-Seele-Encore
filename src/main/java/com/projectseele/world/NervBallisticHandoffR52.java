package com.projectseele.world;

import com.projectseele.entity.*;
import com.projectseele.world.NervRouteReservationsR52.Original;
import java.util.*;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.*;
import net.minecraft.world.phys.*;

/** The giant catapult's finite vertical impulse. Ordinary locomotion and
 * Forge gravity remain unchanged. All geometry is the retained original
 * body, 34 hands, closed capsule, native seated pilot and selected dolly. */
public final class NervBallisticHandoffR52 {
    public static final int FLIGHT_TICKS=42,CARRIER_TICKS=20,CLOSE_TICKS=20;
    public static final double DRAG=.98,LANDING_DELTA=-3;
    public record Profile(double landingDelta)
    {
        public Profile{if(Math.abs(landingDelta)<1e-6)landingDelta=0;else if(Math.abs(landingDelta+3)<1e-6)landingDelta=-3;else throw new IllegalArgumentException("Actual current exit landing delta must be0 or-3 source metres");}
    }
    public static double launchVelocity(double gravity){return launchVelocity(gravity,new Profile(LANDING_DELTA));}
    public static double launchVelocity(double gravity,Profile profile) {
        if(!Double.isFinite(gravity)||gravity<=0)throw new IllegalArgumentException("Actual positive native gravity required");
        double sum=(1-Math.pow(DRAG,FLIGHT_TICKS))/(1-DRAG);
        return (profile.landingDelta()+gravity*DRAG/(1-DRAG)*(FLIGHT_TICKS-sum))/sum;
    }
    public static double height(int ticks,double gravity){return height(ticks,gravity,new Profile(LANDING_DELTA));}
    public static double height(int ticks,double gravity,Profile profile) {
        if(ticks<0||ticks>FLIGHT_TICKS)throw new IllegalArgumentException("Native flight clock outside admitted launch");
        double v=launchVelocity(gravity,profile),y=0;for(int t=0;t<ticks;t++){y+=v;v=(v-gravity)*DRAG;}return y;
    }
    public static double closingProgressR53(double fraction){if(!Double.isFinite(fraction)||fraction<0||fraction>1)throw new IllegalArgumentException("Actual normalized closing clock required");return EvaDorsalMechanism.smooth((float)(1-fraction));}
    public static boolean loadedColumnsR53(AABB bounds,int minimumY,java.util.function.BiPredicate<Integer,Integer> hasChunk)
    {if(!Double.isFinite(bounds.minX+bounds.minY+bounds.minZ+bounds.maxX+bounds.maxY+bounds.maxZ)||bounds.minY<minimumY)return false;for(int x=((int)Math.floor(bounds.minX))>>4;x<=((int)Math.floor(bounds.maxX))>>4;x++)for(int z=((int)Math.floor(bounds.minZ))>>4;z<=((int)Math.floor(bounds.maxZ))>>4;z++)if(!hasChunk.test(x,z))return false;return true;}
    private static boolean loadedBallistic(ServerLevel level,AABB bounds)
    {return loadedColumnsR53(bounds,level.getMinBuildHeight(),(x,z)->level.getChunkSource().getChunkNow(x,z)!=null);}
    private record Surface(NervRigidMeshSweepR52 mesh,RigidTransform local){}
    public static final class Proof {
        private final Original original;private final String source;private final RigidTransform start;private final double gravity;private final Profile profile;private final List<Surface> payload;private final AABB nativeBody,pilot;private final Vec3 seat;private final FootSupportFrameR52.Binding binding;
        private Proof(Original o,String source,RigidTransform start,double gravity,Profile profile,List<Surface> payload,AABB body,AABB pilot,Vec3 seat,FootSupportFrameR52.Binding binding){original=o;this.source=source;this.start=start;this.gravity=gravity;this.profile=profile;this.payload=List.copyOf(payload);nativeBody=body;this.pilot=pilot;this.seat=seat;this.binding=binding;}
        public Profile profile(){return profile;}
        public double launchVelocity(){return NervBallisticHandoffR52.launchVelocity(gravity,profile);}
        public RigidTransform root(int ticks){return new RigidTransform(start.translation().add(0,height(ticks,gravity,profile),0),start.qx(),start.qy(),start.qz(),start.qw());}
        public boolean current(EvaUnit01Entity e){return original.eva().equals(e.getUUID())&&EvaMechanicalFrameR52.active(e)&&EvaMechanicalFrameR52.kind(e)==TransportMembershipR52.Kind.OCCUPIED&&EvaMechanicalFrameR52.epoch(e)==original.epoch()&&EvaMechanicalFrameR52.capturedGeometry(e).sourceFingerprint().equals(source)&&Math.abs(e.getAttributeValue(net.minecraftforge.common.ForgeMod.ENTITY_GRAVITY.get())-gravity)<1e-12;}
        public AABB envelope(){AABB b=null;for(int t=0;t<=FLIGHT_TICKS;t++){var shift=root(t).translation().subtract(start.translation());var a=nativeBody.move(shift);b=b==null?a:b.minmax(a);}return b;}
        public boolean placement(ServerLevel l,EvaUnit01Entity e) {
            if(!current(e))return false;int age=EvaMechanicalFrameR52.ballisticTicksR52(e);if(age<0||age>FLIGHT_TICKS+4)return false;
            var actual=EvaMechanicalFrameR52.frame(e,1);var expected=root(Math.min(age,FLIGHT_TICKS));if(actual.translation().distanceToSqr(expected.translation())>4e-4||actual.rotationErrorDegrees(expected)>.04)return false;
            if(!(l.getEntity(original.plug()) instanceof EntryPlugCarrierEntity p)||p.getVehicle()!=e||p.getFirstPassenger()==null||!p.getFirstPassenger().getUUID().equals(original.pilot())||p.getCanonicalTransform().translation().distanceToSqr(actual.compose(binding.plugInEva()).translation())>4e-6)return false;
            return true;
        }
        public boolean clearLaunch(ServerLevel l,EvaUnit01Entity e,NervAssemblyOwnerR52.Gate hatch) {
            if(!current(e)||!placement(l,e)||hatch.kind()!=NervAssemblyOwnerR52.GateKind.SILO||hatch.siloHatch()==null||hatch.siloHatch().closeTicks()!=CLOSE_TICKS)return false;
            var own=TransportMembershipR52.members(original,TransportMembershipR52.Kind.OCCUPIED);
            for(int t=1;t<=FLIGHT_TICKS;t++) {
                var from=root(t-1);var to=root(t);var shiftA=from.translation().subtract(start.translation());var shiftB=to.translation().subtract(start.translation());
                var nativeSweep=nativeBody.move(shiftA).minmax(nativeBody.move(shiftB));if(!loadedBallistic(l,nativeSweep)||l.getBlockCollisions(e,nativeSweep.deflate(1e-5)).iterator().hasNext())return false;
                for(var s:payload){var a=from.compose(s.local());var b=to.compose(s.local());var box=s.mesh().envelope(a,b);if(!loadedBallistic(l,box))return false;for(var shape:l.getBlockCollisions(e,box))for(var obstacle:shape.toAabbs())if(s.mesh().intersects(a,b,obstacle,.003))return false;for(var actor:l.getEntities((Entity)null,box,x->!own.contains(x.getUUID())&&x.isAlive()&&(x instanceof LivingEntity||x.canBeCollidedWith()))){var actual=NervFlightProofR52.actualObstacleMeshes(actor);if(actual==null||actual.isEmpty()){if(s.mesh().intersects(a,b,actor.getBoundingBox(),.003))return false;}else for(var m:actual)if(s.mesh().intersects(a,b,m.mesh(),m.frame(),m.endFrame(),.003,Vec3.ZERO))return false;}}
                var rider=pilot.move(from.transformPoint(seat).subtract(start.transformPoint(seat))).minmax(pilot.move(to.transformPoint(seat).subtract(start.transformPoint(seat))));if(!loadedBallistic(l,rider)||l.getBlockCollisions(l.getEntity(original.pilot()),rider).iterator().hasNext()||!l.getEntities((Entity)null,rider,x->!own.contains(x.getUUID())&&x.isAlive()&&(x instanceof LivingEntity||x.canBeCollidedWith())).isEmpty())return false;
            }
            var originalCarrier=NervOriginalCarrierR52.controller(l,original);
            if(originalCarrier!=null){var members=new HashSet<>(own);members.add(originalCarrier.getUUID());try{if(NervOriginalCarrierR52.proposeActuator(l,originalCarrier,1,0,Set.copyOf(members))==null)return false;}catch(java.io.IOException missing){return false;}}
            else for(int t=1;t<=CARRIER_TICKS;t++)if(!NervMappedPlugMechanicsR52.clearCarrierRise(l,e,start,1-(t-1)/(float)CARRIER_TICKS,1-t/(float)CARRIER_TICKS,own))return false;
            // Native raw closure first passes the quintic controller easing
            // (|p'|<=1.875, |p''|<6), then the factory cubic lift/travel.
            // Include both derivatives in every sub-tick chord certificate.
            var geometry=((NervSiloDoorEntity)l.getEntity(hatch.visual())).declaredGeometryR52();var stowed=new ArrayList<Surface>();
            if(originalCarrier!=null)try{for(var p:NervOriginalCarrierR52.partsAtR53(e.getUnitVariant(),start,0,NervOriginalCarrierR52.guideUp(originalCarrier),NervOriginalCarrierR52.actualRidePoseR52(originalCarrier),NervOriginalCarrierR52.uprightDirectionR52(originalCarrier,1),0))stowed.add(new Surface(p.mesh(),start.inverse().compose(p.frame())));}catch(java.io.IOException missing){return false;}
            else NervMappedPlugMechanicsR52.selectedMachinery().carrierParts(e.getUnitVariant(),0,e.recoveryRackR39(),0,EvaMechanicalFrameR52.carrierDeckTravelR52(e)).values().forEach(v->stowed.add(new Surface(new NervRigidMeshSweepR52(v),RigidTransform.identity())));
            double dp=1D/(CLOSE_TICKS*8),ex=hatch.siloHatch().pocketX()*(21.09375/.49+9/.7)*dp*dp/8+.001,ey=hatch.siloHatch().maximumTier()*(21.09375/.09+9/.3)*dp*dp/8+.001;
            for(int t=1;t<=CLOSE_TICKS;t++)for(int sub=0;sub<8;sub++) {
                double a=(t-1+sub/8D)/CLOSE_TICKS,b=(t-1+(sub+1)/8D)/CLOSE_TICKS;var first=geometry.pieces((float)closingProgressR53(a));var last=geometry.pieces((float)closingProgressR53(b));var bodyFrom=root(CARRIER_TICKS+t-1).interpolate(root(CARRIER_TICKS+t),sub/8D);var bodyTo=root(CARRIER_TICKS+t-1).interpolate(root(CARRIER_TICKS+t),(sub+1)/8D);
                for(int i=0;i<first.size();i++){var piece=first.get(i);var mesh=new NervRigidMeshSweepR52(piece.part().xyz());var f=hatch.frame().compose(piece.local());var n=hatch.frame().compose(last.get(i).local());var error=piece.moving()?new Vec3(ex,ey,0):Vec3.ZERO;for(var s:payload)if(s.mesh().intersects(bodyFrom.compose(s.local()),bodyTo.compose(s.local()),mesh,f,n,.003,error))return false;for(var s:stowed){var at=start.compose(s.local());if(s.mesh().intersects(at,at,mesh,f,n,.003,error))return false;}}
            }
            return true;
        }
    }
    public static Proof capture(ServerLevel l,Original o,EvaUnit01Entity e,RigidTransform start){return capture(l,o,e,start,new Profile(LANDING_DELTA));}
    public static Proof capture(ServerLevel l,Original o,EvaUnit01Entity e,RigidTransform start,Profile profile) {
        if(!EvaMechanicalFrameR52.active(e)||EvaMechanicalFrameR52.kind(e)!=TransportMembershipR52.Kind.OCCUPIED||!(l.getEntity(o.plug()) instanceof EntryPlugCarrierEntity p)||!p.isHatchFullySealed()||p.getVehicle()!=e||p.getFirstPassenger()==null||!p.getFirstPassenger().getUUID().equals(o.pilot())||!p.usesPhysicalPilotSeatR52())return null;
        var g=EvaMechanicalFrameR52.capturedGeometry(e);var binding=EvaMechanicalFrameR52.measuredBinding(e,o);var surfaces=new ArrayList<Surface>();for(var part:g.parts())surfaces.add(new Surface(new NervRigidMeshSweepR52(part.triangles()),RigidTransform.identity()));for(var mesh:NervMappedPlugMechanicsR52.selectedMachinery().closedPlugParts(o.variant()).values())surfaces.add(new Surface(new NervRigidMeshSweepR52(mesh),binding.plugInEva()));
        return new Proof(o,g.sourceFingerprint(),start,e.getAttributeValue(net.minecraftforge.common.ForgeMod.ENTITY_GRAVITY.get()),profile,surfaces,e.getBoundingBox().move(start.translation().subtract(e.position())),p.getFirstPassenger().getBoundingBox().move(start.translation().subtract(e.position())),binding.plugInEva().transformPoint(EntryPlugKinematics.PILOT_SEAT_P),binding);
    }
    private NervBallisticHandoffR52(){}
}
