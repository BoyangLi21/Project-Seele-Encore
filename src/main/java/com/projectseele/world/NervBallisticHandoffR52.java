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
    private record Surface(UUID actor,String part,NervRigidMeshSweepR52 mesh,RigidTransform local){}
    /** One current-world body step. The owner pairs it with the original rack
     * step before either commit; the detached rack is deliberately checked by
     * that paired proof, not treated as a stationary copy of itself. */
    public static final class StepR53
    {
        private final Proof proof;
        private final long checkedAt;
        private final int fromTick;
        private final RigidTransform from,to;
        private final Map<UUID,List<NervFlightProofR52.ObstacleMesh>> actors;
        private final AABB pilotSweep;
        private final List<AABB> envelopes;
        private StepR53(Proof proof,ServerLevel level,EvaUnit01Entity eva)
        {
            this.proof=proof;checkedAt=level.getGameTime();fromTick=EvaMechanicalFrameR52.ballisticTicksR52(eva);
            from=EvaMechanicalFrameR52.frame(eva,1);
            var target=proof.root(fromTick+1);
            if(!NervTraversalPolicyR53.strict(level))
            {
                // A pre-update save may already be above the outlet. Carry
                // its current offset forward once, then consume that offset
                // over the remaining landing clock without rewinding it.
                int landingStart=CARRIER_TICKS/2+CLOSE_TICKS;
                double a=Math.max(0,(fromTick-landingStart)/(double)(FLIGHT_TICKS-landingStart));
                double b=Math.max(0,(fromTick+1-landingStart)/(double)(FLIGHT_TICKS-landingStart));
                double remaining=1-a*a*a*(10+a*(-15+6*a));
                double nextRemaining=1-b*b*b*(10+b*(-15+6*b));
                double residual=from.translation().y-proof.root(fromTick).translation().y;
                if(remaining>0&&residual!=0)target=new RigidTransform(target.translation().add(0,residual*nextRemaining/remaining,0),
                        target.qx(),target.qy(),target.qz(),target.qw());
            }
            to=target;
            var grouped=new HashMap<UUID,List<NervFlightProofR52.ObstacleMesh>>();var boxes=new ArrayList<AABB>();
            if(NervTraversalPolicyR53.strict(level))for(var s:proof.payload)
            {
                var a=from.compose(s.local());var b=to.compose(s.local());
                grouped.computeIfAbsent(s.actor(),key->new ArrayList<>()).add(new NervFlightProofR52.ObstacleMesh(s.mesh(),a,b));
                boxes.add(s.mesh().envelope(a,b));
            }
            grouped.replaceAll((key,value)->List.copyOf(value));actors=Map.copyOf(grouped);
            pilotSweep=proof.pilot.move(from.transformPoint(proof.seat).subtract(proof.start.transformPoint(proof.seat)))
                    .minmax(proof.pilot.move(to.transformPoint(proof.seat).subtract(proof.start.transformPoint(proof.seat))));
            if(!NervTraversalPolicyR53.strict(level))boxes.add(proof.nativeBody.move(from.translation().subtract(proof.start.translation()))
                    .minmax(proof.nativeBody.move(to.translation().subtract(proof.start.translation()))));
            boxes.add(pilotSweep);envelopes=List.copyOf(boxes);
        }
        public Original original(){return proof.original;}
        public RigidTransform fromRoot(){return from;}
        public RigidTransform toRoot(){return to;}
        public int fromTick(){return fromTick;}
        public int toTick(){return fromTick+1;}
        public List<NervFlightProofR52.ObstacleMesh> actorMeshes(UUID actor){return actors.get(actor);}
        public AABB pilotSweep(){return pilotSweep;}
        public List<AABB> envelopes(){return envelopes;}
        public boolean current(ServerLevel level,EvaUnit01Entity eva)
        {return level.getGameTime()==checkedAt&&proof.current(eva)&&proof.placement(level,eva)
                &&EvaMechanicalFrameR52.controlledBallisticR53(eva)
                &&EvaMechanicalFrameR52.ballisticTicksR52(eva)==fromTick
                &&NervAirTransportManifestR52.same(EvaMechanicalFrameR52.frame(eva,1),from);}
    }
    public static final class Proof {
        private final Original original;private final String source;private final RigidTransform start;private final double gravity;private final Profile profile;private final List<Surface> payload;private final AABB nativeBody,pilot;private final Vec3 seat;private final FootSupportFrameR52.Binding binding;
        private Proof(Original o,String source,RigidTransform start,double gravity,Profile profile,List<Surface> payload,AABB body,AABB pilot,Vec3 seat,FootSupportFrameR52.Binding binding){original=o;this.source=source;this.start=start;this.gravity=gravity;this.profile=profile;this.payload=List.copyOf(payload);nativeBody=body;this.pilot=pilot;this.seat=seat;this.binding=binding;}
        public Profile profile(){return profile;}
        public Original original(){return original;}
        public double launchVelocity(){return 0;}
        public RigidTransform root(int ticks){
            if(ticks<0||ticks>FLIGHT_TICKS)throw new IllegalArgumentException("Outlet clock outside admitted handoff");
            int landingStart=CARRIER_TICKS/2+CLOSE_TICKS;
            double t=Math.max(0,(ticks-landingStart)/(double)(FLIGHT_TICKS-landingStart));
            double height=profile.landingDelta()*t*t*t*(10+t*(-15+6*t));
            return new RigidTransform(start.translation().add(0,height,0),start.qx(),start.qy(),start.qz(),start.qw());
        }
        public boolean current(EvaUnit01Entity e){return original.eva().equals(e.getUUID())&&EvaMechanicalFrameR52.active(e)&&EvaMechanicalFrameR52.kind(e)==TransportMembershipR52.Kind.OCCUPIED&&EvaMechanicalFrameR52.epoch(e)==original.epoch()&&EvaMechanicalFrameR52.capturedGeometry(e).sourceFingerprint().equals(source)&&Math.abs(e.getAttributeValue(net.minecraftforge.common.ForgeMod.ENTITY_GRAVITY.get())-gravity)<1e-12;}
        public AABB envelope(){return nativeBody.minmax(nativeBody.move(0,profile.landingDelta(),0));}
        private List<AABB> sourceEnvelopesR53;
        /** The fixed source only translates vertically during this finite impulse.
         * Its extrema enclose every intermediate body, plug and pilot step. */
        public List<AABB> sourceEnvelopesR53()
        {
            if(sourceEnvelopesR53!=null)return sourceEnvelopesR53;
            var from=root(0);var to=root(FLIGHT_TICKS);var boxes=new ArrayList<AABB>();
            for(var surface:payload)boxes.add(surface.mesh().envelope(from.compose(surface.local()),to.compose(surface.local())));
            boxes.add(pilot.move(from.translation().subtract(start.translation()))
                    .minmax(pilot.move(to.translation().subtract(start.translation()))));
            sourceEnvelopesR53=List.copyOf(boxes);return sourceEnvelopesR53;
        }
        public boolean placement(ServerLevel l,EvaUnit01Entity e) {
            if(!current(e))return false;int age=EvaMechanicalFrameR52.ballisticTicksR52(e);if(age<0||age>FLIGHT_TICKS+4)return false;
            var actual=EvaMechanicalFrameR52.frame(e,1);var expected=root(Math.min(age,FLIGHT_TICKS));
            boolean priorFlight=!NervTraversalPolicyR53.strict(l)&&EvaMechanicalFrameR52.ballisticCustodyR52(e)&&age<FLIGHT_TICKS;
            if((priorFlight?actual.translation().subtract(expected.translation()).horizontalDistanceSqr():actual.translation().distanceToSqr(expected.translation()))>4e-4
                    ||!Double.isFinite(actual.translation().y)||actual.rotationErrorDegrees(expected)>.04)return false;
            if(!(l.getEntity(original.plug()) instanceof EntryPlugCarrierEntity p)||p.getVehicle()!=e||p.getFirstPassenger()==null||!p.getFirstPassenger().getUUID().equals(original.pilot())||p.getCanonicalTransform().translation().distanceToSqr(actual.compose(binding.plugInEva()).translation())>4e-6)return false;
            return true;
        }
        private String rejectionR53="";
        public String rejectionR53(){return rejectionR53;}
        private StepR53 rejectR53(String reason){rejectionR53=reason;return null;}
        public StepR53 proposeStepR53(ServerLevel level,EvaUnit01Entity eva)
        {
            rejectionR53="";
            if(!current(eva)||!placement(level,eva)||!EvaMechanicalFrameR52.controlledBallisticR53(eva)
                    ||EvaMechanicalFrameR52.ballisticTicksR52(eva)>=FLIGHT_TICKS)return rejectR53("ballistic_original_or_clock_changed");
            var step=new StepR53(this,level,eva);AABB area=step.pilotSweep();
            for(var box:step.envelopes()){if(!loadedBallistic(level,box))return rejectR53("ballistic_column_not_loaded");area=area.minmax(box);}
            if(!NervTraversalPolicyR53.strict(level))
                return NervOriginalCarrierR52.controller(level,original)==null?rejectR53("ballistic_original_rack_missing"):step;
            var blocks=new ArrayList<AABB>();for(var shape:level.getBlockCollisions(eva,area))blocks.addAll(shape.toAabbs());
            var blockIndex=new NervStaticSpatialIndexR52<AABB>(blocks,box->box);
            var own=new HashSet<>(TransportMembershipR52.members(original,TransportMembershipR52.Kind.OCCUPIED));
            var carrier=NervOriginalCarrierR52.controller(level,original);
            if(carrier==null)return rejectR53("ballistic_original_rack_missing");
            own.add(carrier.getUUID());
            var actors=new ArrayList<Map.Entry<Entity,List<NervFlightProofR52.ObstacleMesh>>>();
            for(var actor:level.getEntities((Entity)null,area.inflate(100),actor->!own.contains(actor.getUUID())&&actor.isAlive()
                    &&(actor instanceof LivingEntity||actor.canBeCollidedWith()||actor instanceof NervCarrierPlatformEntity
                        ||actor instanceof NervSiloDoorEntity||actor instanceof NervHangarDoorEntity||actor instanceof UNTransportEntity)))
            {
                var meshes=NervFlightProofR52.actualObstacleMeshes(actor);
                if(meshes==null)return rejectR53("ballistic_unknown_actor="+actor.getUUID());
                actors.add(Map.entry(actor,meshes));
            }
            var query=new NervRigidMeshSweepR52.PairQuery();
            for(var s:payload)
            {
                var a=step.fromRoot().compose(s.local());var b=step.toRoot().compose(s.local());var box=s.mesh().envelope(a,b);
                for(var obstacle:blockIndex.query(box))
                    if(!landingContactR53(s,a,b,obstacle,step.toTick())&&s.mesh().intersects(a,b,obstacle,.003))
                        return rejectR53("ballistic_block / "+s.part()+" / "+obstacle);
                for(var row:actors)
                {
                    if(row.getValue().isEmpty())
                    {
                        if(box.intersects(row.getKey().getBoundingBox())&&s.mesh().intersects(a,b,row.getKey().getBoundingBox(),.003))
                            return rejectR53("ballistic_actor / "+s.part()+" / "+row.getKey().getUUID());
                    }
                    else for(var obstacle:row.getValue())
                    {
                        var bound=obstacle.mesh().envelope(obstacle.frame(),obstacle.endFrame());
                        if(!box.intersects(bound)||landingContactR53(s,a,b,bound,step.toTick()))continue;
                        if(s.mesh().intersects(a,b,obstacle.mesh(),obstacle.frame(),obstacle.endFrame(),.003,Vec3.ZERO,query))
                            return rejectR53("ballistic_actor_mesh / "+s.part()+" / "+row.getKey().getUUID());
                    }
                }
            }
            for(var obstacle:blockIndex.query(step.pilotSweep()))if(step.pilotSweep().intersects(obstacle))return rejectR53("ballistic_pilot_block");
            for(var row:actors)
                if(row.getValue().isEmpty()?step.pilotSweep().intersects(row.getKey().getBoundingBox())
                        :row.getValue().stream().anyMatch(m->m.mesh().intersects(m.frame(),m.endFrame(),step.pilotSweep(),.003)))
                    return rejectR53("ballistic_pilot_actor="+row.getKey().getUUID());
            return step;
        }
        private static boolean landingContactR53(Surface surface,RigidTransform from,RigidTransform to,AABB support,int tick)
        {
            if(tick!=FLIGHT_TICKS||!(surface.part().equals("foot_l")||surface.part().equals("foot_r"))
                    ||to.translation().y>from.translation().y)return false;
            double first=surface.mesh().envelope(from,from).minY,last=surface.mesh().envelope(to,to).minY;
            return first>=support.maxY-.0002&&last>=support.maxY-.0002&&Math.abs(last-support.maxY)<=.0002;
        }
        public boolean clearHatchStepR53(ServerLevel level,EvaUnit01Entity eva,NervAssemblyOwnerR52.Gate hatch,StepR53 step)
        {
            if(step==null||step.proof!=this||!step.current(level,eva)||hatch.kind()!=NervAssemblyOwnerR52.GateKind.SILO
                    ||hatch.siloHatch()==null||hatch.siloHatch().closeTicks()!=CLOSE_TICKS
                    ||!(level.getEntity(hatch.visual()) instanceof NervSiloDoorEntity door)
                    ||!door.matchesDeclaredR52(hatch.siloHatch())
                    ||!NervAirTransportManifestR52.same(door.actualFrameR52(),hatch.frame()))
            {rejectionR53="ballistic_hatch_identity_changed";return false;}
            float from=door.actualOpenProgressR52(),to=door.proposedDeclaredProgressR52(false);
            if(to>from){rejectionR53="ballistic_hatch_reversed";return false;}
            var carrier=NervOriginalCarrierR52.controller(level,original);
            if(carrier==null||NervOriginalCarrierR52.progress(carrier,1)!=0)
            {rejectionR53="ballistic_hatch_rack_not_stowed";return false;}
            if(!NervTraversalPolicyR53.strict(level))return true;
            var moving=new HashSet<net.minecraft.core.BlockPos>();var supports=new HashSet<net.minecraft.core.BlockPos>();
            for(var row:hatch.collisionSteps())for(var cell:row)moving.add(cell.at());
            for(var cell:hatch.supports())supports.add(cell.at());
            var own=new HashSet<>(TransportMembershipR52.members(original,TransportMembershipR52.Kind.OCCUPIED));
            own.add(carrier.getUUID());
            if(!door.clearDeclaredSweepR52(level,from,to,own,moving,supports))
            {rejectionR53="ballistic_hatch_world_sweep";return false;}
            List<NervFlightProofR52.ObstacleMesh> rack;
            try{rack=NervOriginalCarrierR52.actualMeshesR52(carrier);}
            catch(java.io.IOException missing){rejectionR53="ballistic_hatch_rack_source_missing";return false;}
            var geometry=door.declaredGeometryR52();double rawFrom=inverseSmoothR53(from),rawTo=inverseSmoothR53(to);
            double dp=Math.abs(rawTo-rawFrom)/8;
            double ex=hatch.siloHatch().pocketX()*(21.09375/.49+9/.7)*dp*dp/8+.001;
            double ey=hatch.siloHatch().maximumTier()*(21.09375/.09+9/.3)*dp*dp/8+.001;
            var query=new NervRigidMeshSweepR52.PairQuery();
            for(int sub=0;sub<8;sub++)
            {
                query.nextInterval();double a=sub/8D,b=(sub+1)/8D;
                float pa=sub==0?from:EvaDorsalMechanism.smooth((float)(rawFrom+(rawTo-rawFrom)*a));
                float pb=sub==7?to:EvaDorsalMechanism.smooth((float)(rawFrom+(rawTo-rawFrom)*b));
                var first=geometry.pieces(pa);var last=geometry.pieces(pb);
                var bodyFrom=step.fromRoot().interpolate(step.toRoot(),a);var bodyTo=step.fromRoot().interpolate(step.toRoot(),b);
                var pilotAtA=pilot.move(bodyFrom.transformPoint(seat).subtract(start.transformPoint(seat)));
                var pilotAtB=pilot.move(bodyTo.transformPoint(seat).subtract(start.transformPoint(seat)));
                for(int i=0;i<first.size();i++)
                {
                    var piece=first.get(i);var mesh=NervObstacleMeshesR53.part(piece.part());
                    var f=hatch.frame().compose(piece.local());var n=hatch.frame().compose(last.get(i).local());
                    var error=piece.moving()?new Vec3(ex,ey,0):Vec3.ZERO;
                    for(var s:payload)
                        if(s.mesh().intersects(bodyFrom.compose(s.local()),bodyTo.compose(s.local()),mesh,f,n,.003,error,query))
                        {rejectionR53="ballistic_hatch_payload / "+s.part();return false;}
                    if(mesh.intersects(f,n,pilotAtA.minmax(pilotAtB).inflate(error.x,error.y,error.z),.003))
                    {rejectionR53="ballistic_hatch_pilot";return false;}
                    for(var member:rack)
                        if(mesh.intersects(f,n,member.mesh(),member.frame(),member.endFrame(),.003,error,query))
                        {rejectionR53="ballistic_hatch_stowed_rack";return false;}
                }
            }
            return true;
        }
        private static double inverseSmoothR53(float value)
        {
            if(value<=0)return 0;if(value>=1)return 1;double lo=0,hi=1;
            for(int i=0;i<40;i++){double mid=(lo+hi)*.5;if(EvaDorsalMechanism.smooth((float)mid)<value)lo=mid;else hi=mid;}
            return (lo+hi)*.5;
        }
        public boolean clearLaunch(ServerLevel l,EvaUnit01Entity e,NervAssemblyOwnerR52.Gate hatch) {
            if(!current(e)||!placement(l,e)||hatch.kind()!=NervAssemblyOwnerR52.GateKind.SILO||hatch.siloHatch()==null||hatch.siloHatch().closeTicks()!=CLOSE_TICKS)return false;
            if(!NervTraversalPolicyR53.strict(l))return loadedBallistic(l,envelope());
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
            if(originalCarrier!=null)try{for(var p:NervOriginalCarrierR52.partsAtR53(e.getUnitVariant(),start,0,NervOriginalCarrierR52.guideUp(originalCarrier),NervOriginalCarrierR52.actualRidePoseR52(originalCarrier),NervOriginalCarrierR52.uprightDirectionR52(originalCarrier,1),0))stowed.add(new Surface(originalCarrier.getUUID(),p.name(),p.mesh(),start.inverse().compose(p.frame())));}catch(java.io.IOException missing){return false;}
            else NervMappedPlugMechanicsR52.selectedMachinery().carrierParts(e.getUnitVariant(),0,e.recoveryRackR39(),0,EvaMechanicalFrameR52.carrierDeckTravelR52(e)).values().forEach(v->stowed.add(new Surface(original.eva(),"legacy_carrier",new NervRigidMeshSweepR52(v),RigidTransform.identity())));
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
        var g=EvaMechanicalFrameR52.capturedGeometry(e);var binding=EvaMechanicalFrameR52.measuredBinding(e,o);
        var surfaces=new ArrayList<Surface>();var body=NervObstacleMeshesR53.body(g);
        // Sole contact refers to these same immutable source meshes in the
        // paired rack step; rebuilding equal triangles loses that identity.
        for(int i=0;i<g.parts().size();i++)
            surfaces.add(new Surface(o.eva(),g.parts().get(i).bone(),body.get(i),RigidTransform.identity()));
        for(var part:NervMappedPlugMechanicsR52.selectedMachinery().closedPlugParts(o.variant()).entrySet())
            surfaces.add(new Surface(o.plug(),part.getKey(),new NervRigidMeshSweepR52(part.getValue()),binding.plugInEva()));
        return new Proof(o,g.sourceFingerprint(),start,e.getAttributeValue(net.minecraftforge.common.ForgeMod.ENTITY_GRAVITY.get()),profile,surfaces,e.getBoundingBox().move(start.translation().subtract(e.position())),p.getFirstPassenger().getBoundingBox().move(start.translation().subtract(e.position())),binding.plugInEva().transformPoint(EntryPlugKinematics.PILOT_SEAT_P),binding);
    }
    private NervBallisticHandoffR52(){}
}
