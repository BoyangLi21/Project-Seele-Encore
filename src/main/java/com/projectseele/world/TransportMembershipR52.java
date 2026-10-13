package com.projectseele.world;

import java.util.Set;
import java.util.UUID;
import net.minecraft.nbt.CompoundTag;
import com.projectseele.world.NervRouteReservationsR52.Original;

/** Provenance and physically carried membership are different contracts.
 * An ejected capsule/pilot is retained at its actual location and UUID. */
public final class TransportMembershipR52
{
    public enum Kind { OCCUPIED,HULL_ONLY_RECOVERY }
    public static Set<UUID> members(Original original,Kind kind)
    {return kind==Kind.HULL_ONLY_RECOVERY?Set.of(original.eva()):Set.of(original.eva(),original.plug(),original.pilot());}
    /** Pure check of the same actual persistent receipts written by V ejection.
     * A caller still must inspect the loaded hull and empty passenger graph. */
    public static boolean originalEjectionReceipts(Original original,CompoundTag hull)
    {return hull.hasUUID("R49EjectedPlug")&&hull.getUUID("R49EjectedPlug").equals(original.plug())&&hull.hasUUID("R49EjectedPilot")&&hull.getUUID("R49EjectedPilot").equals(original.pilot());}
    public static boolean hullRecoveryAdmission(Original original,CompoundTag actualHullReceipt,Set<UUID> actualHullPassengers,boolean plugInserted,boolean hullStopped)
    {return originalEjectionReceipts(original,actualHullReceipt)&&actualHullPassengers.isEmpty()&&!plugInserted&&hullStopped
            &&actualHullReceipt.hasUUID("R49RecoveryOwner")&&actualHullReceipt.getUUID("R49RecoveryOwner").equals(original.owner());}
    private TransportMembershipR52(){}
}
