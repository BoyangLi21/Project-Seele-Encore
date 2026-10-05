package com.projectseele.world;

import com.projectseele.entity.NervStaffEntity;
import java.util.Set;

/** The operator's job and the caller's card are independent permissions. */
public final class StaffAuthorityR25
{
    public static boolean allows(NervStaffEntity npc, String operation)
    {
        if(operation.equals("synch_lab"))return npc.staffRole().equals("scientist")
                &&(npc.memberId().equals("r47/experiment/researcher_0")||npc.memberId().equals("r47/experiment/researcher_1"));
        return allows(npc.staffRole(), npc.skin(), operation);
    }

    public static boolean allows(String role, String skin, String operation)
    {
        if (Set.of("guard", "un_guard", "medic", "technician", "un_crew").contains(role)) return false;
        if (operation.equals("city_rise") || operation.equals("city_lower")) return skin.equals("fuyutsuki");
        if (skin.equals("misato") || skin.equals("fuyutsuki"))
            return Set.of("prepare", "launch", "recover", "deploy", "board", "weapons", "campaign").contains(operation);
        if (skin.equals("ritsuko")) return Set.of("prepare", "recover", "board").contains(operation);
        return false;
    }

    public static boolean commandContact(NervStaffEntity npc)
    { return allows(npc, "prepare") || allows(npc, "launch"); }
    private StaffAuthorityR25() {}
}
