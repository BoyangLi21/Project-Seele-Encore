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
    public static double launchVelocity(double gravity) {
        if(!Double.isFinite(gravity)||gravity<=0)throw new IllegalArgumentException("Actual positive native gravity required");
        double sum=(1-Math.pow(DRAG,FLIGHT_TICKS))/(1-DRAG);
        return (LANDING_DELTA+gravity*DRAG/(1-DRAG)*(FLIGHT_TICKS-sum))/((1-Math.pow(DRAG,FLIGHT_TICKS))/(1-DRAG));
    }
    public static double height(int ticks,double gravity) {
        if(ticks<0||ticks>FLIGHT_TICKS)throw new IllegalArgumentException("Native flight clock outside admitted launch");
        double v=launchVelocity(gravity),y=0;for(int t=0;t<ticks;t++){y+=v;v=(v-gravity)*DRAG;}return y;
    }
    private record Surface(NervRigidMeshSweepR52 mesh,RigidTransform local){}
    public static final class Proof {
        private final Original original;private final String source;private final RigidTransform start;private final double gravity;private final List<Surface> payload;private final AABB nativeBody,pilot;private final Vec3 seat;private final FootSupportFrameR52.Binding binding;
        private Proof(Original o,String source,RigidTransform start,double gravity,List<Surface> payload,AABB body,AABB pilot,Vec3 seat,FootSupportFrameR52.Binding binding){original=o;this.source=source;this.start=start;this.gravity=gravity;this.payload=List.copyOf(payload);nativeBody=body;this.pilot=pilot;this.seat=seat;this.binding=binding;}
        public RigidTransform root(int ticks){return new RigidTransform(start.translation().add(0,height(ticks,gravity),0),start.qx(),start.qy(),start.qz(),start.qw());}
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
                var nativeSweep=nativeBody.move(shiftA).minmax(nativeBody.move(shiftB));if(!EntryPlugEjectionR48.loaded(l,nativeSweep)||l.getBlockCollisions(e,nativeSweep.deflate(1e-5)).iterator().hasNext())return false;
                for(var s:payload){var a=from.compose(s.local());var b=to.compose(s.local());var box=s.mesh().envelope(a,b);if(!EntryPlugEjectionR48.loaded(l,box))return false;for(var shape:l.getBlockCollisions(e,box))for(var obstacle:shape.toAabbs())if(s.mesh().intersects(a,b,obstacle,.003))return false;for(var actor:l.getEntities((Entity)null,box,x->!own.contains(x.getUUID())&&x.isAlive()&&(x instanceof LivingEntity||x.canBeCollidedWith()))){var actual=NervFlightProofR52.actualObstacleMeshes(actor);if(actual==null||actual.isEmpty()){if(s.mesh().intersects(a,b,actor.getBoundingBox(),.003))return false;}else for(var m:actual)if(s.mesh().intersects(a,b,m.mesh(),m.frame(),m.endFrame(),.003,Vec3.ZERO))return false;}}
                var rider=pilot.move(from.transformPoint(seat).subtract(start.transformPoint(seat))).minmax(pilot.move(to.transformPoint(seat).subtract(start.transformPoint(seat))));if(!EntryPlugEjectionR48.loaded(l,rider)||l.getBlockCollisions(l.getEntity(original.pilot()),rider).iterator().hasNext()||!l.getEntities((Entity)null,rider,x->!own.contains(x.getUUID())&&x.isAlive()&&(x instanceof LivingEntity||x.canBeCollidedWith())).isEmpty())return false;
            }
            for(int t=1;t<=CARRIER_TICKS;t++)if(!NervMappedPlugMechanicsR52.clearCarrierRise(l,e,start,1-(t-1)/(float)CARRIER_TICKS,1-t/(float)CARRIER_TICKS,own))return false;
            // The real hatch's lift/travel are cubic smoothsteps. Split each
            // closing tick into eight chords with the global |f''|<=6
            // certificate; no endpoint-only leaf/body test is accepted.
            var geometry=((NervSiloDoorEntity)l.getEntity(hatch.visual())).declaredGeometryR52();var stowed=new ArrayList<Surface>();NervMappedPlugMechanicsR52.selectedMachinery().carrierParts(e.getUnitVariant(),0,e.recoveryRackR39(),0,EvaMechanicalFrameR52.carrierDeckTravelR52(e)).values().forEach(v->stowed.add(new Surface(new NervRigidMeshSweepR52(v),RigidTransform.identity())));
            double dp=1D/(CLOSE_TICKS*8),ex=hatch.siloHatch().pocketX()*6/.49*dp*dp/8+.001,ey=hatch.siloHatch().maximumTier()*6/.09*dp*dp/8+.001;
            for(int t=1;t<=CLOSE_TICKS;t++)for(int sub=0;sub<8;sub++) {
                double a=(t-1+sub/8D)/CLOSE_TICKS,b=(t-1+(sub+1)/8D)/CLOSE_TICKS;var first=geometry.pieces((float)(1-a));var last=geometry.pieces((float)(1-b));var bodyFrom=root(CARRIER_TICKS+t-1).interpolate(root(CARRIER_TICKS+t),sub/8D);var bodyTo=root(CARRIER_TICKS+t-1).interpolate(root(CARRIER_TICKS+t),(sub+1)/8D);
                for(int i=0;i<first.size();i++){var piece=first.get(i);var mesh=new NervRigidMeshSweepR52(piece.part().xyz());var f=hatch.frame().compose(piece.local());var n=hatch.frame().compose(last.get(i).local());var error=piece.moving()?new Vec3(ex,ey,0):Vec3.ZERO;for(var s:payload)if(s.mesh().intersects(bodyFrom.compose(s.local()),bodyTo.compose(s.local()),mesh,f,n,.003,error))return false;for(var s:stowed)if(s.mesh().intersects(start,start,mesh,f,n,.003,error))return false;}
            }
            return true;
        }
    }
    public static Proof capture(ServerLevel l,Original o,EvaUnit01Entity e,RigidTransform start) {
        if(!EvaMechanicalFrameR52.active(e)||EvaMechanicalFrameR52.kind(e)!=TransportMembershipR52.Kind.OCCUPIED||!(l.getEntity(o.plug()) instanceof EntryPlugCarrierEntity p)||!p.isHatchFullySealed()||p.getVehicle()!=e||p.getFirstPassenger()==null||!p.getFirstPassenger().getUUID().equals(o.pilot())||!p.usesPhysicalPilotSeatR52())return null;
        var g=EvaMechanicalFrameR52.capturedGeometry(e);var binding=EvaMechanicalFrameR52.measuredBinding(e,o);var surfaces=new ArrayList<Surface>();for(var part:g.parts())surfaces.add(new Surface(new NervRigidMeshSweepR52(part.triangles()),RigidTransform.identity()));for(var mesh:NervMappedPlugMechanicsR52.selectedMachinery().closedPlugParts(o.variant()).values())surfaces.add(new Surface(new NervRigidMeshSweepR52(mesh),binding.plugInEva()));
        return new Proof(o,g.sourceFingerprint(),start,e.getAttributeValue(net.minecraftforge.common.ForgeMod.ENTITY_GRAVITY.get()),surfaces,e.getBoundingBox().move(start.translation().subtract(e.position())),p.getFirstPassenger().getBoundingBox().move(start.translation().subtract(e.position())),binding.plugInEva().transformPoint(EntryPlugKinematics.PILOT_SEAT_P),binding);
    }
    private NervBallisticHandoffR52(){}
}
