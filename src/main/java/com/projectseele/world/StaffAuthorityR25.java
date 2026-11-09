package com.projectseele.world;

import com.projectseele.entity.NervStaffEntity;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;

/** The operator's job and the caller's card are independent permissions. */
public final class StaffAuthorityR25
{
    /** Pseudo-operation for the phone's command tabs: the contact may prepare or launch. */
    public static final String COMMAND = "command";
    private static final String[][] CONTACTS = {{"misato", "美里"}, {"ritsuko", "律子"}, {"fuyutsuki", "冬月"}, {"maya", "摩耶"}};

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

    /** Why the phone refuses an operation; call it only once the operation is known to be refused. */
    public static String denial(boolean authorized, String skin, String operation)
    {
        if (!authorized) return "需要 NERV 通行证";
        List<String> able = new ArrayList<>();
        for (String[] contact : CONTACTS)
        {
            boolean permits = operation.equals(COMMAND)
                    ? allows("", contact[0], "prepare") || allows("", contact[0], "launch")
                    : allows("", contact[0], operation);
            if (permits && !contact[0].equals(skin)) able.add(contact[1]);
        }
        if (able.isEmpty()) return "该联络人没有此权限";
        String last = able.remove(able.size() - 1);
        return "需要联络" + (able.isEmpty() ? last : String.join("、", able) + "或" + last);
    }
    private StaffAuthorityR25() {}
}
