package com.projectseele.world;

import net.minecraft.network.chat.Component;
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
        for (String[] contact : authorizedContacts(skin, operation)) able.add(contact[1]);
        if (able.isEmpty()) return "该联络人没有此权限";
        String last = able.remove(able.size() - 1);
        return "需要联络" + (able.isEmpty() ? last : String.join("、", able) + "或" + last);
    }
    public static Component denialText(boolean authorized, String skin, String operation)
    {
        if (!authorized) return Component.translatable("staff.projectseele.need_card");
        List<Component> contacts = new ArrayList<>();
        for (String[] contact : authorizedContacts(skin, operation))
            contacts.add(Component.translatable("hud.projectseele.chat.name." + contact[0]));
        if (contacts.isEmpty()) return Component.translatable("staff.projectseele.cannot_authorize");
        Component names = contacts.get(0);
        for (int i = 1; i < contacts.size(); i++)
            names = Component.translatable(i == contacts.size()-1 ? "staff.projectseele.or" : "staff.projectseele.list", names, contacts.get(i));
        return Component.translatable("staff.projectseele.contact", names);
    }
    private static List<String[]> authorizedContacts(String skin, String operation)
    {
        List<String[]> contacts = new ArrayList<>();
        for (String[] contact : CONTACTS)
        {
            boolean permits = operation.equals(COMMAND)
                    ? allows("",contact[0],"prepare") || allows("",contact[0],"launch")
                    : allows("",contact[0],operation);
            if (permits && !contact[0].equals(skin)) contacts.add(contact);
        }
        return contacts;
    }

    private StaffAuthorityR25() {}
}
