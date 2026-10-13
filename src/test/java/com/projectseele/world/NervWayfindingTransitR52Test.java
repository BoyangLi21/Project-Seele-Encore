package com.projectseele.world;
import com.google.gson.*;

/** Explicit train links must not silently become walking or elevator edges. */
public final class NervWayfindingTransitR52Test
{
    private static int checked;
    private static JsonObject document()
    {return JsonParser.parseString("{\"transport_edges\":[{\"from\":0,\"to\":1,\"kind\":\"TRAIN\",\"line\":\"U2\",\"destination\":\"原机库车站\",\"source_station_id\":\"9166787716217601435\",\"destination_station_id\":\"6417785485925618840\"}]}").getAsJsonObject();}
    private static void rejected(JsonObject doc,boolean[] active)
    {try{NervWayfindingR24.readTransit(doc,active);}catch(RuntimeException expected){checked++;return;}throw new AssertionError("Invalid train edge admitted");}
    public static void main(String[] args)
    {
        var result=NervWayfindingR24.readTransit(document(),new boolean[]{true,true});if(result.size()!=1||!result.get(1L).line().equals("U2"))throw new AssertionError("Actual directed train leg absent");checked++;
        if(!NervWayfindingR24.readTransit(new JsonObject(),new boolean[]{true}).isEmpty())throw new AssertionError("Legacy graph changed");checked++;
        for(int to:new int[]{-1,0,2}){var d=document();d.getAsJsonArray("transport_edges").get(0).getAsJsonObject().addProperty("to",to);rejected(d,new boolean[]{true,true});}
        var d=document();d.getAsJsonArray("transport_edges").get(0).getAsJsonObject().addProperty("from",.5);rejected(d,new boolean[]{true,true});
        d=document();d.getAsJsonArray("transport_edges").get(0).getAsJsonObject().addProperty("kind","WALK");rejected(d,new boolean[]{true,true});
        rejected(document(),new boolean[]{true,false});
        d=document();d.getAsJsonArray("transport_edges").add(d.getAsJsonArray("transport_edges").get(0).deepCopy());rejected(d,new boolean[]{true,true});
        d=document();d.getAsJsonArray("transport_edges").get(0).getAsJsonObject().addProperty("destination_station_id","9166787716217601435");rejected(d,new boolean[]{true,true});
        System.out.println("NervWayfindingTransitR52Test PASS "+checked+" transport identity/bounds/legacy checks");
    }
}
