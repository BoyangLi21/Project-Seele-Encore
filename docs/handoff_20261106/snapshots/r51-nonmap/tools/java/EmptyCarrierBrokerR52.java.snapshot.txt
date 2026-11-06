package com.projectseele.world;

import com.google.gson.*;
import com.projectseele.world.NervRouteReservationsR52.*;
import com.projectseele.world.NervRouteDirectoryR52.*;
import com.projectseele.world.TransportMembershipR52.Kind;
import java.nio.file.*;
import java.util.*;

/** Broker replay is synthetic; the path test reads only the actual Root graph. */
public final class EmptyCarrierBrokerR52
{
    private static int checks;
    private static void check(boolean value,String why){checks++;if(!value)throw new AssertionError(why);}
    public static void main(String[] args)throws Exception
    {
        var fixture=NervRouteCoreR52Test.rootFixtureForNativeBindingTest();var directory=NervRouteDirectoryR52.parse(fixture);var pool=new NervRouteReservationsR52(directory);
        var route=directory.routes().values().stream().filter(r->r.variant()==0&&!r.recovery()).findFirst().orElseThrow();var ids=directory.leg(route.legs().get(0)).resources();var unit=directory.unit(0);
        UUID hardware=UUID.randomUUID(),task=UUID.randomUUID(),plane=UUID.randomUUID(),flight=UUID.randomUUID();
        var original=new Original(directory.epoch(),0,unit.eva(),unit.plug(),UUID.randomUUID(),UUID.randomUUID(),"synthetic",directory.node(directory.leg(route.legs().get(0)).from()).dimension());
        HardwareAccess access=new HardwareAccess(){public boolean sameOriginalCarrier(UUID id,int v,long epoch){return id.equals(hardware)&&v==0&&epoch==directory.epoch();}public boolean checkedCarrierGeometry(UUID id,Set<Resource> set,boolean restoring){return true;}};
        var lease=new HardwareLease(task,hardware,0,directory.epoch(),directory.fingerprint(),ids,null);
        check(pool.reserveHardware(lease,access,false),"Empty hardware claims actual declared resource kinds");check(pool.leasedMembers(task).equals(Set.of(hardware)),"Hardware never acquires EVA/pilot/plug control");check(!pool.available(route),"Hardware occupies the same ground resource broker");
        check(!pool.reserveHardware(new HardwareLease(UUID.randomUUID(),unit.eva(),0,directory.epoch(),directory.fingerprint(),ids,null),access,false),"EVA identity cannot masquerade as empty hardware");
        NativeAccess ground=new NativeAccess(){public boolean sameOriginalAssembly(Original o){return true;}public boolean canTraverse(Original o,Route r,Leg l,double a,double b){return true;}public boolean canRestore(Original o,Route r,int l,double f){return true;}};
        var saved=new Snapshot(task,original,directory.fingerprint(),route.id(),0,0,Stage.HOLD,"");
        check(!pool.quarantineGround(saved),"Saved ground task cannot alias an actual hardware task");
        check(!pool.restore(saved,ground).accepted(),"Cold restore cannot overwrite physical hardware claims");
        check(!pool.restore(new Snapshot(UUID.randomUUID(),original,directory.fingerprint(),route.id(),0,0,Stage.HOLD,""),ground).accepted(),"Independent saved ground task cannot restore through occupied steel space");
        check(pool.leasedMembers(task).equals(Set.of(hardware)),"Rejected cold restore retains only original steel controller custody");
        check(pool.releaseHardware(task,hardware),"Original hardware lease releases its own resources");
        String space=ids.stream().filter(id->directory.resource(id).kind()==ResourceKind.SPACE).findFirst().orElseThrow();
        FlightAccess flying=new FlightAccess(){public boolean sameOriginalAssembly(Original o){return o.equals(original);}public boolean sameMovingAssembly(Original o,Kind k){return o.equals(original);}public boolean originalAircraft(UUID id){return id.equals(plane);}public boolean checkedFlightGeometry(Original o,Set<Resource> r,boolean restoring){return true;}};
        check(pool.reserveFlight(flight,original,plane,Kind.HULL_ONLY_RECOVERY,Set.of(space),Set.of(),flying),"Original hull/aircraft flight lease");
        var buddy=new HardwareLease(task,hardware,0,directory.epoch(),directory.fingerprint(),ids,flight);check(pool.reserveHardware(buddy,access,false),"Actual companion keeps distinct hardware/aircraft claims in shared SPACE");
        check(pool.leasedMembers(flight).equals(Set.of(unit.eva(),plane)),"Ejected capsule/pilot remain outside carried membership");check(pool.leasedMembers(task).equals(Set.of(hardware)),"Hardware task still owns only its controller");
        check(!pool.resourcesAvailable(UUID.randomUUID(),ids),"Unrelated route cannot enter shared hardware space");check(pool.resourcesAvailable(flight,Set.of(space)),"Companion stationary geometry may remain in its own shared SPACE");
        HardwareAccess blocked=new HardwareAccess(){public boolean sameOriginalCarrier(UUID id,int v,long epoch){return true;}public boolean checkedCarrierGeometry(UUID id,Set<Resource> set,boolean restoring){return false;}};
        check(!pool.reserveHardware(buddy,blocked,false)&&pool.queryHardware(task).equals(buddy),"A failed physical proof keeps previous hardware lease unchanged");
        check(!pool.quarantineFlight(new FlightLease(task,original,directory.fingerprint(),Set.of(space),UUID.randomUUID(),Kind.HULL_ONLY_RECOVERY,false,Set.of())),"Saved flight task cannot alias original steel task");
        var actual=JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject();var root=NervRouteDirectoryR52.parse(actual);int paths=0;
        for(int v=0;v<3;v++)for(var a:root.ports().values())for(var b:root.ports().values())if(a.reverseRoutes().containsKey(v)&&b.reverseRoutes().containsKey(v)&&!a.id().equals(b.id()))
        {var path=NervEmptyCarrierTransferR52.existingPath(root,v,a.node(),b.node());check(path!=null&&!path.isEmpty(),"Root existing original-port path must exist");String current=a.node();for(String id:path){var leg=root.leg(id);check(leg!=null&&leg.from().equals(current),"Only continuous Root-declared legs");current=leg.to();check(root.node(current).role()!=Role.BAY,"Port-to-port empty transfer cuts at common bank, never enters occupied bay");}check(current.equals(b.node()),"Path reaches the selected existing port");paths++;}
        var report=Map.of("broker_checks",checks,"actual_root_port_paths",paths,"world_written",false,"native_hardware_motion_acceptance",false);var out=Path.of(args[1]);Files.createDirectories(out);Files.writeString(out.resolve("EMPTY_CARRIER_BROKER_REPORT.json"),new GsonBuilder().setPrettyPrinting().create().toJson(report));System.out.println(report);
    }
}
