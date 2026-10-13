package com.projectseele.world;

import java.util.Map;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicInteger;

/** No world/actor installation: original identity resolution and mount lifecycle admission. */
public final class NervOriginalActorsR52Test
{
    private record Actor(UUID id,int variant,boolean alive){}
    public static void main(String[] args)
    {
        UUID original=UUID.randomUUID(),nearby=UUID.randomUUID();var exact=new Actor(original,1,true);var duplicate=new Actor(nearby,1,true);
        var repo=new java.util.HashMap<UUID,Actor>();repo.put(original,exact);repo.put(nearby,duplicate);var before=Map.copyOf(repo);
        var reads=new AtomicInteger();java.util.function.Function<UUID,Actor> lookup=id->{reads.incrementAndGet();return repo.get(id);};
        var valid=(java.util.function.Predicate<Actor>)a->a.alive()&&a.variant()==1&&a.id().equals(original);
        if(NervOriginalActorsR52.originalOnly(original,lookup,valid)!=exact||reads.get()!=1)throw new AssertionError("Did not resolve only exact original UUID");
        reads.set(0);repo.remove(original);
        if(NervOriginalActorsR52.originalOnly(original,lookup,valid)!=null||reads.get()!=1||repo.get(nearby)!=duplicate)throw new AssertionError("Missing original adopted a nearby capsule");
        reads.set(0);if(NervOriginalActorsR52.originalOnly(null,lookup,valid)!=null||reads.get()!=0)throw new AssertionError("Absent receipt scanned world");
        repo.put(original,new Actor(original,2,true));if(NervOriginalActorsR52.originalOnly(original,lookup,valid)!=null)throw new AssertionError("Wrong unit identity admitted");
        repo.put(original,new Actor(original,1,false));if(NervOriginalActorsR52.originalOnly(original,lookup,valid)!=null)throw new AssertionError("Dead original substituted");
        repo.put(original,exact);if(!before.equals(repo))throw new AssertionError("Lookup mutated original/duplicate registry");
        int cases=0;for(boolean managed:new boolean[]{false,true})for(boolean alive:new boolean[]{false,true})for(boolean mounting:new boolean[]{false,true})for(boolean safe:new boolean[]{false,true})
        {boolean hold=NervOriginalActorsR52.holdDismount(managed,alive,mounting,safe);if(hold!=(managed&&alive&&!mounting&&!safe))throw new AssertionError("Mount lifecycle gate");cases++;}
        if(NervOriginalActorsR52.holdDismount(true,true,true,false))throw new AssertionError("Saved passenger graph restoration blocked before owner installation");
        if(!NervOriginalActorsR52.holdDismount(true,true,false,false)||NervOriginalActorsR52.holdDismount(true,true,false,true))throw new AssertionError("Pending rider detached or verified egress blocked");
        var absent=new NervOriginalActorsR52.Access(){};
        if(absent.originalEntryPlugBindingsReady(null)||absent.originalBoardingAnchor(null,null)!=null||absent.originalDockPose(null,1)!=null
                ||absent.originalDismountAnchor(null,null,null)!=null||absent.originalBoardingAllowed(null,null,null)
                ||absent.originalLaunchLock(null,1,null,null)||absent.originalCageDock(null,1,null,null)||absent.requestOriginalEjection(null,1,null,null)
                ||absent.originalPilot(null,1)!=null||!absent.originalStaffRoster(null).isEmpty())throw new AssertionError("Default owner fabricated readiness, coordinates, or actors");
        System.out.println("PASS: exact original/missing/wrong/dead UUID resolution without scans, substitution or registry mutation; "+cases+" mount lifecycle cases including saved graph restoration/dead cleanup/pending HOLD/mapped egress; default owner gives no coordinates or identities");
    }
}
