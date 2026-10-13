package com.projectseele.world;

import java.util.*;
import net.minecraft.nbt.*;
import com.projectseele.world.NervRouteReservationsR52.*;
import com.projectseele.world.TransportMembershipR52.Kind;

/** Real production receipt codec/lifecycle/broker checks. No native actor
 * creation, alternate graph model or fabricated occupied recovery. */
public final class TransportMembershipR52Test
{
    private static int checks;
    private static void check(boolean ok,String why){checks++;if(!ok)throw new AssertionError(why);}
    public static void main(String[] args)
    {
        var directory=NervRouteDirectoryR52.parse(NervRouteCoreR52Test.rootFixtureForNativeBindingTest());var u=directory.unit(0);UUID pilot=new UUID(0,30),owner=new UUID(0,100);var original=new Original(7,0,u.eva(),u.plug(),pilot,owner,"original_mission","test:synthetic_route_graph");
        // Test dimension is the actual declared synthetic directory dimension.
        original=new Original(7,0,u.eva(),u.plug(),pilot,owner,"original_mission",directory.node(directory.leg(directory.route("return_b1l1").legs().get(0)).from()).dimension());
        var saved=new NervRouteRuntimeStateR52();saved.claim(7,directory.fingerprint());UUID outbound=new UUID(0,801);var deployed=new Snapshot(outbound,original,directory.fingerprint(),"depart_b1l1",3,1,Stage.COMPLETE,"");
        saved.put(new NervRouteRuntimeStateR52.Job(deployed,NervRouteRuntimeStateR52.Phase.DEPLOYED,new CompoundTag(),""));
        var receipt=new CompoundTag();receipt.putUUID("R49EjectedPlug",u.plug());receipt.putUUID("R49EjectedPilot",pilot);receipt.putUUID("R49RecoveryOwner",owner);receipt.put("Passengers",new ListTag());
        Set<UUID> empty=Set.of();check(TransportMembershipR52.hullRecoveryAdmission(original,receipt,empty,false,true),"Actual disabled empty hull ejection receipts denied");
        check(!TransportMembershipR52.hullRecoveryAdmission(original,receipt,Set.of(u.plug()),false,true),"Attached capsule masqueraded as empty hull");check(!TransportMembershipR52.hullRecoveryAdmission(original,receipt,empty,true,true),"Inserted socket masqueraded as V ejected hull");check(!TransportMembershipR52.hullRecoveryAdmission(original,receipt,empty,false,false),"Active unconfirmed hull masqueraded as stopped recovery");
        var wrong=receipt.copy();wrong.putUUID("R49EjectedPlug",new UUID(0,999));check(!TransportMembershipR52.hullRecoveryAdmission(original,wrong,empty,false,true),"Foreign capsule receipt accepted");
        final Original o=original;NativeAccess actualReceiptAccess=new NativeAccess(){public boolean sameOriginalAssembly(Original q){return false;}public boolean canTraverse(Original q,NervRouteDirectoryR52.Route r,NervRouteDirectoryR52.Leg l,double a,double b){return false;}public boolean canRestore(Original q,NervRouteDirectoryR52.Route r,int l,double f){return false;}public boolean sameAssembly(Original q,Kind k){return k==Kind.HULL_ONLY_RECOVERY&&q.equals(o)&&TransportMembershipR52.hullRecoveryAdmission(q,receipt,empty,false,true);}public boolean canTraverseAssembly(Original q,Kind k,NervRouteDirectoryR52.Route r,NervRouteDirectoryR52.Leg l,double a,double b){return sameAssembly(q,k)&&r.recovery();}public boolean canRestoreAssembly(Original q,Kind k,NervRouteDirectoryR52.Route r,int l,double f){return sameAssembly(q,k)&&r.recovery();}};
        var broker=new NervRouteReservationsR52(directory);check(!broker.reserve(new UUID(0,802),original,"depart_b1l1",actualReceiptAccess,Kind.HULL_ONLY_RECOVERY).accepted(),"Hull-only departure bypassed original pilot interlock");
        UUID returning=new UUID(0,803);var reserved=broker.reserve(returning,original,"return_b1l1",actualReceiptAccess,Kind.HULL_ONLY_RECOVERY);check(reserved.accepted(),"Verified ejected provenance could not register hull recovery");check(broker.leasedMembers(returning).equals(Set.of(u.eva())),"Separated original capsule/pilot were leased as fictitious moving actors");
        var data=new CompoundTag();data.putString("AssemblyKindR52",Kind.HULL_ONLY_RECOVERY.name());data.putBoolean("Returning",true);saved.put(new NervRouteRuntimeStateR52.Job(reserved.state(),NervRouteRuntimeStateR52.Phase.RETURNING,data,""));var readback=NervRouteRuntimeStateR52.load(saved.save(new CompoundTag()));check(readback.job(0).snapshot().kind()==Kind.HULL_ONLY_RECOVERY&&readback.job(0).snapshot().original().equals(original),"Real NBT lost original separated actor provenance or actual membership");
        var afterRestart=new NervRouteReservationsR52(directory);check(afterRestart.restore(readback.job(0).snapshot(),actualReceiptAccess).accepted()&&afterRestart.leasedMembers(returning).equals(Set.of(u.eva())),"Restart resurrected fictitious pilot/capsule leases");
        check(afterRestart.advanceRetainingCompletion(returning,.25,actualReceiptAccess).accepted()&&afterRestart.query(returning).kind()==Kind.HULL_ONLY_RECOVERY,"Hull movement switched back to occupied graph");check(afterRestart.cancel(returning,owner).accepted()&&afterRestart.leasedMembers(returning).isEmpty(),"Hull cancellation leaked moved-actor lease");
        var oldTag=NervRouteRuntimeStateR52.encode(deployed);oldTag.remove("AssemblyKind");check(NervRouteRuntimeStateR52.decode(oldTag).kind()==Kind.OCCUPIED,"Old occupied save changed meaning");
        check(TransportMembershipR52.members(original,Kind.HULL_ONLY_RECOVERY).equals(Set.of(u.eva()))&&TransportMembershipR52.members(original,Kind.OCCUPIED).equals(Set.of(u.eva(),u.plug(),pilot)),"Original identities were replaced by membership kind");
        System.out.println("R52 deployed/ejected/hull-only real receipt+NBT lifecycle PASS checks="+checks+"; no live native movement acceptance");
    }
    private TransportMembershipR52Test(){}
}
