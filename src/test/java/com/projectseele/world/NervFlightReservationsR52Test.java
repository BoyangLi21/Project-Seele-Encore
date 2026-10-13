package com.projectseele.world;

import com.google.gson.*;
import java.util.*;
import com.projectseele.world.NervRouteDirectoryR52.*;
import com.projectseele.world.NervRouteReservationsR52.*;
import com.projectseele.world.TransportMembershipR52.Kind;

/** Synthetic bookkeeping checks; never claims real flight geometry passed. */
public final class NervFlightReservationsR52Test
{
    private static int checks;
    private static void check(boolean value,String message){checks++;if(!value)throw new AssertionError(message);}
    private static UUID id(int n){return new UUID(0,n);}
    private static Original original(int v){return new Original(7,v,id(10+v),id(20+v),id(30+v),id(100),"synthetic_mission","test:synthetic_route_graph");}
    private static final class Access implements FlightAccess,NativeAccess
    {
        boolean clear=true,aircraft=true,receiver=true,delivery=false;int deliveryCalls;
        public boolean sameOriginalAssembly(Original o){return true;}
        public boolean sameMovingAssembly(Original o,Kind kind){return true;}
        public boolean checkedFlightGeometry(Original o,Set<Resource> spaces,boolean restoring){return clear;}
        public boolean checkedAircraftOnlyGeometry(UUID plane,Set<Resource> spaces,boolean restoring){return clear;}
        public boolean originalAircraft(UUID plane){return aircraft;}
        public boolean checkedSupportedDelivery(Original o,Kind kind){deliveryCalls++;return delivery;}
        public boolean canTraverse(Original o,Route r,Leg l,double a,double b){return clear;}
        public boolean canRestore(Original o,Route r,int leg,double fraction){return receiver;}
        public boolean sameAssembly(Original o,Kind kind){return true;}
        public boolean canRestoreAssembly(Original o,Kind kind,Route r,int leg,double f){return receiver;}
    }
    public static void main(String[] args)
    {
        var root=NervRouteCoreR52Test.rootFixtureForNativeBindingTest();
        for(String name:List.of("airA","airB","airC","sharedAir","airDoor"))
        {var r=new JsonObject();r.addProperty("id",name);r.addProperty("kind",name.equals("airDoor")?"DOOR":"SPACE");r.addProperty("component","synthetic/"+name);root.getAsJsonArray("resources").add(r);}
        var directory=NervRouteDirectoryR52.parse(root);var pool=new NervRouteReservationsR52(directory);var actual=new Access();
        check(pool.reserveFlight(id(201),original(0),id(301),Kind.HULL_ONLY_RECOVERY,Set.of("airA"),Set.of(),actual),"Original hull flight admitted");
        check(pool.leasedMembers(id(201)).equals(Set.of(id(10),id(301))),"Ejected capsule/pilot are not moving/self-excluded members");
        check(pool.reserveFlight(id(202),original(1),id(302),Kind.OCCUPIED,Set.of("airB"),Set.of(),actual),"Second original aircraft concurrent");
        check(!pool.reserveFlight(id(203),original(2),id(301),Kind.OCCUPIED,Set.of("airC"),Set.of(),actual),"One aircraft cannot have two jobs");
        check(!pool.reserveFlight(id(204),original(0),id(303),Kind.HULL_ONLY_RECOVERY,Set.of("airC"),Set.of(),actual),"One EVA cannot have two flights");
        check(!pool.reserveFlight(id(205),original(2),id(303),Kind.OCCUPIED,Set.of("airB"),Set.of(),actual),"Shared real flight space excludes another aircraft");
        check(pool.retargetFlightSpaces(id(201),Set.of("sharedAir"),Set.of("airDoor"),actual),"Atomic next segment + actual door lease");
        check(!pool.retargetFlightSpaces(id(202),Set.of("sharedAir"),Set.of(),actual),"Blocked next segment retains previous lease");
        check(pool.queryFlight(id(202)).spaces().equals(Set.of("airB")),"Failed transition does not release current space");
        actual.clear=false;check(!pool.retargetFlightSpaces(id(201),Set.of("airA"),Set.of(),actual),"Failed full geometry retains lease");actual.clear=true;
        check(pool.queryFlight(id(201)).spaces().equals(Set.of("sharedAir")),"Blocked geometry does not fake progress");
        check(!pool.cancel(id(201),id(999)).accepted(),"Unrelated owner cannot cancel original flight");
        check(pool.cancel(id(201),id(100)).accepted(),"Same original owner cancels bookkeeping");
        check(pool.reserveFlight(id(206),original(0),id(301),Kind.HULL_ONLY_RECOVERY,Set.of("airA","space1"),Set.of(),actual),"Same plane/EVA available only after explicit release");
        actual.receiver=false;
        check(!pool.handoffFlightToGround(id(206),id(207),"return_b1l1",Set.of("airA"),Set.of(),actual,actual).accepted(),"Missing actual receiver blocks handoff");
        check(pool.leasedMembers(id(206)).equals(Set.of(id(10),id(301))),"Failed handoff does not clear attached actor lease");actual.receiver=true;
        check(!pool.handoffFlightToGround(id(206),id(207),"return_b1l1",Set.of("space1"),Set.of(),actual,actual).accepted(),"Aircraft must physically clear receiver resource before handoff");
        var handed=pool.handoffFlightToGround(id(206),id(207),"return_b1l1",Set.of("airA"),Set.of(),actual,actual);
        check(handed.accepted()&&handed.state().kind()==Kind.HULL_ONLY_RECOVERY,"Original hull membership retained in ground return");
        check(pool.leasedMembers(id(207)).equals(Set.of(id(10))),"Ground hull owner still does not claim field capsule/pilot");
        check(pool.leasedMembers(id(206)).equals(Set.of(id(301))),"Aircraft owns only its retreat after payload handoff");
        check(pool.queryFlight(id(206)).payloadTransferred(),"Explicit transferred flight receipt");
        var restored=new NervRouteReservationsR52(directory);
        check(restored.restoreFlight(pool.queryFlight(id(206)),actual),"Aircraft-only retreat restores without dragging delivered cargo");
        actual.aircraft=false;
        check(!new NervRouteReservationsR52(directory).restoreFlight(pool.queryFlight(id(202)),actual),"Missing original plane cannot be replaced on reload");
        actual.aircraft=true;check(!pool.handoffFlightToDelivery(id(202),Set.of("airC"),Set.of(),actual),"Unsupported delivery retains occupied payload");check(pool.leasedMembers(id(202)).equals(Set.of(id(11),id(21),id(31),id(302))),"Failed actual support does not release sealed original crew graph");int before=actual.deliveryCalls;actual.delivery=true;actual.clear=false;check(!pool.handoffFlightToDelivery(id(202),Set.of("airC"),Set.of(),actual)&&actual.deliveryCalls==before,"Geometry/resource checks precede the real Owner release callback");actual.clear=true;check(pool.handoffFlightToDelivery(id(202),Set.of("airC"),Set.of(),actual),"Supported original occupied delivery atomically releases payload");check(pool.leasedMembers(id(202)).equals(Set.of(id(302)))&&pool.queryFlight(id(202)).payloadTransferred(),"Original return aircraft remains leased after supported delivery");check(pool.reserveFlight(id(208),original(1),id(303),Kind.OCCUPIED,Set.of("airB"),Set.of(),actual),"Delivered original EVA can take a new task without waiting for the empty aircraft to land");var hullPool=new NervRouteReservationsR52(directory);check(hullPool.reserveFlight(id(209),original(0),id(309),Kind.HULL_ONLY_RECOVERY,Set.of("airA"),Set.of(),actual),"Hull recovery reserved for negative delivery test");check(!hullPool.handoffFlightToDelivery(id(209),Set.of("airA"),Set.of(),actual),"Ejected hull cannot use occupied delivery to release field provenance");
        var cold=new NervRouteReservationsR52(directory);var unknown=new FlightLease(id(501),original(0),directory.fingerprint(),Set.of("airA"),id(801),Kind.HULL_ONLY_RECOVERY,false,Set.of("airDoor"));check(cold.quarantineFlight(unknown)&&cold.flightQuarantined(id(501)),"Unknown cold-load original flight retains resources without geometry admission");check(cold.leasedMembers(id(501)).equals(Set.of(id(10),id(801))),"Cold hull reservation retains actual moving membership only");check(!cold.reserveFlight(id(502),original(1),id(802),Kind.OCCUPIED,Set.of("airA"),Set.of(),actual),"Unloaded original plane cannot let a new flight take its saved space");check(!cold.cancel(id(501),id(100)).accepted(),"Unknown physical placement cannot release provisional flight space");check(!cold.handoffFlightToGround(id(501),id(503),"return_b1l1",Set.of("airA"),Set.of(),actual,actual).accepted(),"Provisional bookkeeping cannot authorize a ground handoff");actual.clear=false;check(!cold.retargetFlightSpaces(id(501),Set.of("airC"),Set.of(),actual)&&cold.flightQuarantined(id(501)),"Failed actual proof leaves cold-load claims intact");actual.clear=true;check(cold.retargetFlightSpaces(id(501),Set.of("airC"),Set.of(),actual)&&!cold.flightQuarantined(id(501)),"Only actual checked geometry upgrades the original cold-load flight");
        var groundCold=new NervRouteReservationsR52(directory);var groundSave=new Snapshot(id(601),original(0),directory.fingerprint(),"depart_b1l1",0,.3,Stage.MOVING,"",Kind.OCCUPIED);check(groundCold.quarantineGround(groundSave)&&groundCold.groundQuarantined(id(601))&&groundCold.query(id(601))==null,"Cold ground provisional claims never appear as restored motion");check(!groundCold.reserve(id(602),original(0),"depart_b1l1",actual).accepted(),"Unloaded original ground group retains its same actors/physical route");check(!groundCold.quarantineFlight(new FlightLease(id(601),original(1),directory.fingerprint(),Set.of("airA"),id(901),Kind.OCCUPIED,true,Set.of())),"Air/ground provisional tasks cannot alias one bookkeeping task ID");check(!groundCold.cancel(id(601),id(100)).accepted(),"Unloaded ground cancellation cannot silently discard physical claims");actual.receiver=false;check(!groundCold.restore(groundSave,actual).accepted()&&groundCold.groundQuarantined(id(601)),"Native ground restore rejection preserves provisional space");actual.receiver=true;check(groundCold.restore(groundSave,actual).accepted()&&!groundCold.groundQuarantined(id(601)),"Native same-progress ground geometry alone restores motion eligibility");
        System.out.println("PASS R52 flight identity/membership/segment/handoff bookkeeping: "+checks);
    }
}
