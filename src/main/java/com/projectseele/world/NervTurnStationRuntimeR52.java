package com.projectseele.world;

import com.projectseele.entity.NervCarrierPlatformEntity;
import com.projectseele.world.NervFootGuideDockR52.*;
import java.io.IOException;
import java.util.*;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.phys.AABB;

/** The occupied and empty jobs share one actual station phase driver.
 * Geometry, custody and clocks remain in their existing typed owners. */
public final class NervTurnStationRuntimeR52 {
 private static final String KEY="RootTurnStationR52";
 public record Admission(UUID task,Set<String> resources,Map<String,NervRouteNativeR52.Binding> bindings,NervRouteReservationsR52 pool){public Admission{resources=Set.copyOf(resources);bindings=NervDynamicAirspaceR52.immutableBindings(bindings);}}
 static boolean covered(Admission a,List<AABB> envelopes){if(a==null||!a.pool().resourcesHeldR52(a.task(),a.resources()))return false;var spaces=new ArrayList<AABB>();for(String id:a.resources()){var binding=a.bindings().get(id);if(binding!=null)spaces.addAll(binding.spaces());}return envelopes.stream().allMatch(b->NervAirspaceCoverageR52.covered(b,spaces));}
 private static double toward(double from,double to){return from<to?Math.min(to,from+.025):Math.max(to,from-.025);}
 private static boolean same(double a,double b){return Math.abs(a-b)<1e-9;}
 private static boolean reverse(Spec s){return s.leg().id().endsWith("/reverse");}
 /** Prepare the fixed hardware while the approaching carrier is still on
  * the preceding Root leg. Reorientation is permitted only fully lowered. */
 public static boolean prepare(ServerLevel l,Spec spec,Admission admission)throws IOException {
  var station=NervFootGuideStationR52.controller(l,spec);if(station==null)return false;var p=NervFootGuideStationR52.currentPose(station);var target=NervFootGuideDockR52.stationPose(spec,new Sample(Stage.COUPLE,0));if(p.equals(target))return covered(admission,List.of(NervFootGuideStationR52.boundsR52(station)));if(p.coupling()!=0||NervFootGuideStationR52.rawState(station).getLong("At")==l.getGameTime())return false;StationPose next;
  if(!same(p.turn(),target.turn())){if(p.incoming()!=1)next=new StationPose(p.turn(),toward(p.incoming(),1),p.outgoing(),0,p.raised());else if(p.outgoing()!=1)next=new StationPose(p.turn(),1,toward(p.outgoing(),1),0,p.raised());else if(p.raised()!=0)next=new StationPose(p.turn(),1,1,0,toward(p.raised(),0));else next=new StationPose(toward(p.turn(),target.turn()),1,1,0,0);}
  else if(p.outgoing()!=target.outgoing()&&(!reverse(spec)))next=new StationPose(p.turn(),p.incoming(),toward(p.outgoing(),target.outgoing()),0,p.raised());
  else if(p.incoming()!=target.incoming()&&reverse(spec))next=new StationPose(p.turn(),toward(p.incoming(),target.incoming()),p.outgoing(),0,p.raised());
  else if(p.raised()!=1)next=new StationPose(p.turn(),p.incoming(),p.outgoing(),0,toward(p.raised(),1));
  else next=new StationPose(p.turn(),toward(p.incoming(),target.incoming()),toward(p.outgoing(),target.outgoing()),0,1);
  var proof=NervFootGuideDockR52.proposeStation(l,station,NervFootGuideStationR52.view(station),p,next,Set.of(station.getUUID()));if(proof==null||!covered(admission,proof.envelopes())||!NervFootGuideStationR52.acceptStationStepR52(l,proof))return false;return next.equals(target);
 }
 private static CompoundTag state(CompoundTag data,Spec spec){var t=data.getCompound(KEY);if(!t.getString("Leg").equals(spec.leg().id()))return new CompoundTag();return t.copy();}
 private static void save(CompoundTag data,Spec spec,Sample p,long at){var tag=new CompoundTag();tag.putString("Leg",spec.leg().id());tag.putString("Source",NervFootGuideDockR52.SOURCE_SHA);tag.putString("Stage",p.stage().name());tag.putDouble("Fraction",p.fraction());tag.putLong("At",at);data.put(KEY,tag);}
 private static Sample sample(CompoundTag state){if(!state.getString("Source").equals(NervFootGuideDockR52.SOURCE_SHA))throw new IllegalStateException("Actual station source clock changed");return new Sample(Stage.valueOf(state.getString("Stage")),state.getDouble("Fraction"));}
 private static boolean advance(ServerLevel l,NervCarrierPlatformEntity carrier,Spec spec,Admission a,Set<UUID> own,CompoundTag data,Sample from,Sample to)throws IOException {
  var proof=NervFootGuideDockR52.propose(l,carrier,spec,from,to,own);if(proof==null||!covered(a,proof.envelopes())||!NervOriginalCarrierR52.acceptDockStepR52(l,proof))return false;save(data,spec,to,l.getGameTime());return true;
 }
 public static boolean beforeTurn(ServerLevel l,NervCarrierPlatformEntity carrier,Spec spec,Admission admission,Set<UUID> own,CompoundTag data)throws IOException {
  var t=state(data,spec);if(t.isEmpty()){if(!prepare(l,spec,admission)||NervFootGuideStationR52.rawState(NervFootGuideStationR52.controller(l,spec)).getLong("At")==l.getGameTime())return false;save(data,spec,new Sample(Stage.COUPLE,0),Long.MIN_VALUE);t=state(data,spec);}var p=sample(t);if(p.stage().ordinal()>=Stage.TURN.ordinal())return true;if(t.getLong("At")==l.getGameTime())return false;
  if(p.fraction()==1){var next=new Sample(p.stage()==Stage.COUPLE?Stage.OPEN_INCOMING:Stage.TURN,0);return advance(l,carrier,spec,admission,own,data,p,next)&&next.stage()==Stage.TURN;}
  var to=new Sample(p.stage(),Math.min(1,p.fraction()+.025));return advance(l,carrier,spec,admission,own,data,p,to)&&to.stage()==Stage.OPEN_INCOMING&&to.fraction()==1;
 }
 public static AcceptedDockStep checkTurn(ServerLevel l,NervCarrierPlatformEntity carrier,Spec spec,Admission admission,Set<UUID> own,CompoundTag data,double from,double to)throws IOException {
  var t=state(data,spec);if(t.isEmpty())return null;var p=sample(t);if(p.stage()!=Stage.TURN||!same(p.fraction(),from)||t.getLong("At")==l.getGameTime())return null;var proof=NervFootGuideDockR52.propose(l,carrier,spec,p,new Sample(Stage.TURN,to),own);return proof!=null&&covered(admission,proof.envelopes())?proof:null;
 }
 public static boolean commitTurn(ServerLevel l,AcceptedDockStep proof,CompoundTag data){if(proof==null||!proof.current(l)||!NervOriginalCarrierR52.acceptDockStepR52(l,proof))return false;save(data,proof.spec(),proof.to(),l.getGameTime());return true;}
 public static boolean afterTurn(ServerLevel l,NervCarrierPlatformEntity carrier,Spec spec,Admission admission,Set<UUID> own,CompoundTag data)throws IOException {
  var t=state(data,spec);if(t.isEmpty())return false;var p=sample(t);if(p.stage()==Stage.RELEASE&&p.fraction()==1)return true;if(t.getLong("At")==l.getGameTime())return false;
  if(p.stage()==Stage.TURN){if(p.fraction()!=1)return false;advance(l,carrier,spec,admission,own,data,p,new Sample(Stage.CLOSE_OUTGOING,0));return false;}else if(p.stage()==Stage.CLOSE_OUTGOING&&p.fraction()==1){advance(l,carrier,spec,admission,own,data,p,new Sample(Stage.RELEASE,0));return false;}if(p.stage()!=Stage.CLOSE_OUTGOING&&p.stage()!=Stage.RELEASE)return false;var to=new Sample(p.stage(),Math.min(1,p.fraction()+.025));return advance(l,carrier,spec,admission,own,data,p,to)&&to.stage()==Stage.RELEASE&&to.fraction()==1;
 }
 /** The world proof includes the departed carrier; contact is never ignored
  * merely because that carrier previously used this station. */
 public static boolean idleComplete(ServerLevel l,Spec spec){var station=NervFootGuideStationR52.controller(l,spec);if(station==null)return false;var p=NervFootGuideStationR52.currentPose(station);return p.coupling()==0&&p.incoming()==1&&p.outgoing()==1&&p.raised()==0;}
 /** Keep the outgoing bridge under the pads until the actual pads have
  * completely passed its finite head. Clearance is derived from both real
  * sources, so the 3.4 m cut cannot lose support during the first half metre. */
 private static boolean guidesHaveDeparted(ServerLevel l,com.projectseele.entity.NervCarrierPlatformEntity station)throws IOException {var heads=new ArrayList<AABB>();for(var part:NervFootGuideStationR52.actualPartsR52(station,1))if(part.name().startsWith("service_bridge/dock/")&&part.name().endsWith("/0"))heads.add(part.mesh().envelope(part.frame(),part.frame()).inflate(.003));for(var head:heads)for(var actor:l.getEntities((net.minecraft.world.entity.Entity)null,head.inflate(80),e->e instanceof com.projectseele.entity.NervCarrierPlatformEntity n&&NervOriginalCarrierR52.declared(n))){var carrier=(com.projectseele.entity.NervCarrierPlatformEntity)actor;for(var part:NervOriginalCarrierR52.actualPartsR52(carrier))if(part.name().startsWith("guide/foot_guide_pad_")&&part.mesh().envelope(part.frame(),part.frame()).intersects(head))return false;}return true;}
 public static boolean idle(ServerLevel l,Spec spec,Admission admission)throws IOException {var station=NervFootGuideStationR52.controller(l,spec);if(station==null)return false;var p=NervFootGuideStationR52.currentPose(station);if(p.coupling()!=0)return false;if(idleComplete(l,spec))return true;if(NervFootGuideStationR52.rawState(station).getLong("At")==l.getGameTime()||!guidesHaveDeparted(l,station))return false;StationPose next=p.incoming()!=1?new StationPose(p.turn(),toward(p.incoming(),1),p.outgoing(),0,p.raised()):p.outgoing()!=1?new StationPose(p.turn(),1,toward(p.outgoing(),1),0,p.raised()):new StationPose(p.turn(),1,1,0,toward(p.raised(),0));var proof=NervFootGuideDockR52.proposeStation(l,station,NervFootGuideStationR52.view(station),p,next,Set.of(station.getUUID()));return proof!=null&&covered(admission,proof.envelopes())&&NervFootGuideStationR52.acceptStationStepR52(l,proof)&&idleComplete(l,spec);}
 private NervTurnStationRuntimeR52(){}
}
