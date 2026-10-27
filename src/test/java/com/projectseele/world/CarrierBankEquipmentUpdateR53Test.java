package com.projectseele.world;

import com.google.gson.JsonObject;

/** Only the one permitted equipment-source delta; no world or actor fixture. */
public final class CarrierBankEquipmentUpdateR53Test
{
    public static void main(String[] args)
    {
        var before=new JsonObject();var sources=new JsonObject();sources.addProperty("original", "retained");
        before.add("mechanism_sources",sources);before.addProperty("original_owner", "unchanged");
        var after=before.deepCopy();after.getAsJsonObject("mechanism_sources").addProperty(NervLegacyBankClearanceR53.SOURCE,NervLegacyBankClearanceR53.SOURCE_SHA);
        check(CarrierEquipmentUpdateR53.bankOverlayDelta(before,after),"Exact one-source addition rejected");
        check(!before.getAsJsonObject("mechanism_sources").has(NervLegacyBankClearanceR53.SOURCE),"Accepted predecessor was modified");
        var changed=after.deepCopy();changed.addProperty("original_owner","changed");reject(before,changed);
        changed=after.deepCopy();changed.getAsJsonObject("mechanism_sources").addProperty("original","changed");reject(before,changed);
        changed=after.deepCopy();changed.getAsJsonObject("mechanism_sources").addProperty("unrelated","extra");reject(before,changed);
        changed=after.deepCopy();changed.getAsJsonObject("mechanism_sources").addProperty(NervLegacyBankClearanceR53.SOURCE,"wrong");reject(before,changed);
        check(!CarrierEquipmentUpdateR53.bankOverlayDelta(after,after),"Installed source was treated as a new refit");
        check(!CarrierEquipmentUpdateR53.bankOverlayDelta(before,before),"Absent refit source was admitted");
        var firstBank=before.deepCopy();firstBank.getAsJsonObject("mechanism_sources").addProperty(NervLegacyBankClearanceR53.SOURCE,NervLegacyBankClearanceR53.PREVIOUS_SOURCE_SHA);
        check(CarrierEquipmentUpdateR53.bankOverlayDelta(firstBank,after),"Exact first-bank source extension rejected");
        changed=after.deepCopy();changed.addProperty("original_owner","changed");reject(firstBank,changed);
        var unknown=firstBank.deepCopy();unknown.getAsJsonObject("mechanism_sources").addProperty(NervLegacyBankClearanceR53.SOURCE,"unknown_predecessor");reject(unknown,after);
    }
    private static void reject(JsonObject before,JsonObject after)
    {
        try{CarrierEquipmentUpdateR53.bankOverlayDelta(before,after);throw new AssertionError("Unrelated owner/source delta admitted");}
        catch(IllegalArgumentException expected){}
    }
    private static void check(boolean value,String why){if(!value)throw new AssertionError(why);}
    private CarrierBankEquipmentUpdateR53Test(){}
}
