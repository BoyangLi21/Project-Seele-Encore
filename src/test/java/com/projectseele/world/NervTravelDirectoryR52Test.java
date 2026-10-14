package com.projectseele.world;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;

/** Foreign installation, partial directory and retired alias regressions. */
public final class NervTravelDirectoryR52Test
{
    private static int checks;
    private static void check(boolean value,String reason)
    {checks++;if(!value)throw new AssertionError(reason);}
    private static void rejected(JsonObject document,long epoch,String fingerprint,String reason)
    {boolean rejected=false;try{NervTravelDirectoryR52.parse(document,epoch,fingerprint);}catch(RuntimeException expected){rejected=true;}check(rejected,reason);}
    public static void main(String[] args)throws Exception
    {
        String fingerprint="a".repeat(64);var document=new JsonObject();
        document.addProperty("schema",NervTravelDirectoryR52.SCHEMA);document.addProperty("dimension","projectseele:geofront");
        document.addProperty("installed",true);document.addProperty("complete_replacement",true);
        document.addProperty("epoch",53);document.addProperty("directory_fingerprint",fingerprint);
        var rows=new JsonArray();
        for(String key:new String[]{"entrance","command","hangar","station","dogma","observation"})
        {
            var row=new JsonObject();row.addProperty("key",key);row.addProperty("label",key);
            row.addProperty("component",key);row.addProperty("entry_id",key+"/authored-entry");
            var xyz=new JsonArray();xyz.add(30.5);xyz.add(-630);xyz.add(356.5);row.add("position",xyz);row.addProperty("yaw",180);rows.add(row);
        }
        document.add("destinations",rows);
        var parsed=NervTravelDirectoryR52.parse(document,53,fingerprint);
        check(parsed.arrival("hanger")==parsed.arrival("hangar"),"Legacy hangar spelling resolved a different coordinate");
        check(parsed.arrival("hanger_station")==null,"Removed old station remained an available fallback");
        rejected(document,54,fingerprint,"Foreign epoch accepted");rejected(document,53,"b".repeat(64),"Foreign directory fingerprint accepted");
        var invalid=document.deepCopy();invalid.addProperty("installed",false);rejected(invalid,53,fingerprint,"Uninstalled candidate accepted");
        invalid=document.deepCopy();invalid.addProperty("complete_replacement",false);rejected(invalid,53,fingerprint,"Partial arrivals silently merged old coordinates");
        invalid=document.deepCopy();invalid.getAsJsonArray("destinations").remove(2);rejected(invalid,53,fingerprint,"Missing actual hangar entry accepted");
        invalid=document.deepCopy();invalid.getAsJsonArray("destinations").add(rows.get(0).deepCopy());rejected(invalid,53,fingerprint,"Duplicate arrival silently replaced");
        invalid=document.deepCopy();invalid.getAsJsonArray("destinations").get(2).getAsJsonObject().addProperty("key","hanger");rejected(invalid,53,fingerprint,"Old spelling shadowed canonical hangar entry");
        invalid=document.deepCopy();invalid.getAsJsonArray("destinations").get(0).getAsJsonObject().getAsJsonArray("position").set(1,new com.google.gson.JsonPrimitive(Double.NaN));rejected(invalid,53,fingerprint,"Nonfinite point accepted");
        invalid=document.deepCopy();invalid.getAsJsonArray("destinations").get(0).getAsJsonObject().remove("entry_id");rejected(invalid,53,fingerprint,"Unidentified patch of walkable floor accepted as entrance");
        if(args.length>0)rejected(com.google.gson.JsonParser.parseString(java.nio.file.Files.readString(java.nio.file.Path.of(args[0]))).getAsJsonObject(),
                52,fingerprint,"Actual frozen unbound old travel directory accepted");
        System.out.println("PASS installed travel directory checks="+checks+"; parser only, no world acceptance");
    }
}
