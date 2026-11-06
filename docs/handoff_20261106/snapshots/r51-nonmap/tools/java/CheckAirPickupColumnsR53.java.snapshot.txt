package com.projectseele.world;

import com.google.gson.*;
import java.nio.file.*;
import java.util.*;

/** Checks real authored routes without starting or moving any actor. */
public final class CheckAirPickupColumnsR53
{
    static void require(boolean value,String reason){if(!value)throw new IllegalStateException(reason);}
    static Map<String,JsonObject> index(JsonObject root,String key,String id)
    {var map=new HashMap<String,JsonObject>();for(var value:root.getAsJsonArray(key)){var row=value.getAsJsonObject();require(map.put(row.get(id).getAsString(),row)==null,"Duplicate "+key);}return map;}
    static String chain(JsonArray ids,String start,Map<String,JsonObject> edges)
    {String at=start;for(var id:ids){var c=edges.get(id.getAsString());require(c!=null&&c.get("from").getAsString().equals(at),"Disconnected source/receiver chain");at=c.get("to").getAsString();}return at;}
    public static void main(String[] args)throws Exception
    {
        var original=JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject();
        var root=NervAirPickupColumnR53.expand(original);var nodes=index(root,"nodes","id");var edges=index(root,"corridors","id");var receivers=index(root,"receivers","port");var planes=index(root,"aircraft","id");
        var oldNodes=index(original,"nodes","id");int separated=0,missions=0;
        for(var entry:oldNodes.entrySet())require(entry.getValue().equals(nodes.get(entry.getKey())),"Authored destination geometry changed");
        for(var value:root.getAsJsonArray("missions"))
        {
            var m=value.getAsJsonObject();String source=m.get("pickup_node").getAsString(),destination=receivers.get(m.get("receiver").getAsString()).get("flight_node").getAsString(),stand=planes.get(m.get("aircraft").getAsString()).get("stand_node").getAsString();
            require(!source.equals(destination),"Pickup and return destination still alias");
            require(chain(m.getAsJsonArray("outbound"),stand,edges).equals(source),"Outbound did not reach pickup");
            require(chain(m.getAsJsonArray("loaded"),source,edges).equals(destination),"Loaded chain did not reach stationary receiver");
            require(chain(m.getAsJsonArray("retreat"),destination,edges).equals(stand),"Return did not reach original aircraft stand");
            for(var id:m.getAsJsonArray("outbound"))
            {
                var c=edges.get(id.getAsString());boolean reverse=false;
                for(var r:edges.values())if(r.get("from").equals(c.get("to"))&&r.get("to").equals(c.get("from"))&&r.get("ticks").equals(c.get("ticks")))reverse=true;
                require(reverse,"Cancellation has no same-duration physical reverse");
            }
            if(source.contains("/source/"))separated++;
            missions++;
        }
        System.out.println("Actual authored missions="+missions+"; separated pickup columns="+separated+"; original receivers and cancellation routes preserved; actors moved=0");
    }
}
