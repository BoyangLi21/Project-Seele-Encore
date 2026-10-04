package com.projectseele.combat;

import java.util.HashSet;
import java.util.Set;
import java.util.UUID;

/** Per-airframe accepted hits for one actual ordinary attack, never target invulnerability state. */
public final class EvaContactHitsR45
{
    public enum Admission
    {
        FIRST,ALREADY_ACCEPTED,BLOCKED;
        public boolean allowsDamage(){return this==FIRST;}
        public boolean countsAsAcceptedContact(){return this==ALREADY_ACCEPTED;}
    }
    /** Real field energy consumed is one settled contact even when the hull hurt Boolean stays false. */
    public static boolean settledContactR46(boolean hullAccepted,float fieldBefore,float fieldAfter)
    {
        return hullAccepted||Float.isFinite(fieldBefore)&&Float.isFinite(fieldAfter)
                &&fieldBefore>0&&fieldAfter>=0&&fieldAfter<fieldBefore;
    }
    private int sequence=-1;
    private long startedAt=Long.MIN_VALUE;
    private boolean active;
    private final Set<UUID> accepted=new HashSet<>();
    private final Set<UUID> inFlight=new HashSet<>();

    public void begin(int actualSequence,long actualStartedAt)
    {
        if(sequence==actualSequence&&startedAt==actualStartedAt)return;
        sequence=actualSequence;startedAt=actualStartedAt;active=true;accepted.clear();inFlight.clear();
    }
    public void end(){active=false;}
    public boolean permits(int actualSequence,UUID target)
    {return active&&actualSequence==sequence&&target!=null&&!accepted.contains(target)&&!inFlight.contains(target);}
    /** The dispatcher uses these decisions directly; pending/closed/stale grants no hit credit. */
    public Admission admit(int actualSequence,UUID target)
    {
        if(active&&actualSequence==sequence&&target!=null&&accepted.contains(target))return Admission.ALREADY_ACCEPTED;
        return beginAttempt(actualSequence,target)?Admission.FIRST:Admission.BLOCKED;
    }
    public boolean recordAccepted(int actualSequence,UUID target)
    {return permits(actualSequence,target)&&accepted.add(target);}
    public boolean beginAttempt(int actualSequence,UUID target)
    {return permits(actualSequence,target)&&inFlight.add(target);}
    public void finishAttempt(int actualSequence,long actualStartedAt,UUID target,boolean actuallyAccepted)
    {
        if(actualSequence!=sequence||actualStartedAt!=startedAt)return;
        inFlight.remove(target);if(actuallyAccepted)accepted.add(target);
    }
    public long startedAt(){return startedAt;}
    public int acceptedCount(){return accepted.size();}
}
