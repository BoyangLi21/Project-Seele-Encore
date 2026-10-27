package com.projectseele.world;

import com.google.gson.*;
import java.util.*;

/** Separate source and receiver columns when a recovery reuses one port. */
final class NervAirPickupColumnR53
{
    static JsonObject expand(JsonObject original)
    {
        var root=original.deepCopy();var nodes=index(root,"nodes");var corridors=index(root,"corridors");
        var deliveries=new JsonArray();var added=new HashSet<String>();
        for(var value:root.getAsJsonArray("missions"))
        {
            var m=value.getAsJsonObject();String pickup=m.get("pickup_node").getAsString();
            String aircraft=m.get("aircraft").getAsString();
            if(!m.get("intent").getAsString().equals("RECOVER")||!pickup.startsWith("delivery/city/")||!m.get("pickup_region").getAsString().equals("SURFACE")||!added.add(aircraft+"/"+pickup))continue;
            var delivery=m.deepCopy();delivery.addProperty("id","r53/surface-delivery/"+pickup.substring(pickup.lastIndexOf('/')+1)
                    +(aircraft.equals("nerv_surface_0")?"":"/"+aircraft));delivery.addProperty("intent","DELIVER");delivery.addProperty("receiver",pickup);
            var loaded=new JsonArray();loaded.add(edge(corridors,pickup,pickup+"/lifted"));loaded.add(edge(corridors,pickup+"/lifted",pickup));delivery.add("loaded",loaded);
            var retreat=new JsonArray();var outbound=m.getAsJsonArray("outbound");
            for(int i=outbound.size()-1;i>=0;i--){var c=corridors.get(outbound.get(i).getAsString());retreat.add(edge(corridors,c.get("to").getAsString(),c.get("from").getAsString()));}
            delivery.add("retreat",retreat);deliveries.add(delivery);
        }
        root.getAsJsonArray("missions").addAll(deliveries);
        var receivers=new HashMap<String,JsonObject>();
        for(var value:root.getAsJsonArray("receivers")){var r=value.getAsJsonObject();receivers.put(r.get("port").getAsString(),r);}
        var coordinates=new JsonArray();
        for(var value:root.getAsJsonArray("missions"))
        {
            var m=value.getAsJsonObject();
            String intent=m.get("intent").getAsString();
            if(!intent.equals("RECOVER")&&(m.get("id").getAsString().startsWith("r53/")
                    ||!Set.of("DELIVER","FAR_MOUNTAIN").contains(intent)))continue;
            var template=receivers.get(m.get("receiver").getAsString());String port="r53/coordinate/"+template.get("port").getAsString();
            if(!receivers.containsKey(port))
            {
                var receiver=template.deepCopy();receiver.addProperty("port",port);receiver.addProperty("delivery",true);
                receiver.add("reverse_routes",new JsonObject());receiver.add("actual_support_cells",new JsonArray());receiver.add("gates",new JsonArray());
                root.getAsJsonArray("receivers").add(receiver);receivers.put(port,receiver);
            }
            // Include commissioned delivery routes as well as recovery:
            // their receiver region determines legal coordinate destinations.
            // Keep the commissioned cross-layer route. Only its final
            // column moves to the XYZ landing measured at request time.
            var delivery=m.deepCopy();delivery.addProperty("id","r53/coordinate/"+m.get("id").getAsString());
            delivery.addProperty("intent","DELIVER");delivery.addProperty("receiver",port);coordinates.add(delivery);
        }
        root.getAsJsonArray("missions").addAll(coordinates);
        for(var value:root.getAsJsonArray("missions"))
        {
            var mission=value.getAsJsonObject();String pickup=mission.get("pickup_node").getAsString();
            var receiver=receivers.get(mission.get("receiver").getAsString());
            if(!pickup.equals(receiver.get("flight_node").getAsString()))continue;
            String prefix=pickup+"/source/"+mission.get("id").getAsString();
            var names=new HashMap<String,String>();
            for(var node:nodes.entrySet())if(node.getKey().equals(pickup)||node.getKey().startsWith(pickup+"/"))
            {
                String id=prefix+node.getKey().substring(pickup.length());names.put(node.getKey(),id);
                var copy=node.getValue().deepCopy();copy.addProperty("id",id);
                // Pickup columns follow the observed EVA. The stationary
                // port's floor cells belong only to its receiver column.
                copy.add("actual_cells",new JsonArray());root.getAsJsonArray("nodes").add(copy);
            }
            var selected=new LinkedHashSet<String>();
            for(var id:mission.getAsJsonArray("outbound"))
            {
                var c=corridors.get(id.getAsString());
                if(names.containsKey(c.get("from").getAsString())||names.containsKey(c.get("to").getAsString()))selected.add(id.getAsString());
            }
            var ascent=new ArrayList<String>();var descent=new ArrayList<String>();
            var column=List.of(pickup,pickup+"/lifted",pickup+"/prone",pickup+"/main");
            for(int i=0;i<column.size()-1;i++)
            {
                ascent.add(edge(corridors,column.get(i),column.get(i+1)));
                descent.add(0,edge(corridors,column.get(i+1),column.get(i)));
            }
            selected.addAll(ascent);
            // Cancellation must reverse the same source column, rather than
            // taking the aircraft to the stationary destination column.
            var clones=new LinkedHashSet<>(selected);
            for(String id:selected)for(var c:corridors.values())
                if(c.has("reverse_of")&&(c.get("id").getAsString().equals(id)||c.get("reverse_of").getAsString().equals(id)))
                {clones.add(c.get("id").getAsString());clones.add(c.get("reverse_of").getAsString());}
            for(String id:clones)
            {
                var copy=corridors.get(id).deepCopy();copy.addProperty("id",prefix+"/corridor/"+id);
                for(String endpoint:List.of("from","to"))copy.addProperty(endpoint,names.getOrDefault(copy.get(endpoint).getAsString(),copy.get(endpoint).getAsString()));
                if(copy.has("reverse_of"))copy.addProperty("reverse_of",prefix+"/corridor/"+copy.get("reverse_of").getAsString());
                root.getAsJsonArray("corridors").add(copy);
            }
            for(String chain:List.of("outbound"))
            {
                var replacement=new JsonArray();
                for(var id:mission.getAsJsonArray(chain))
                {
                    String old=id.getAsString();boolean source=selected.contains(old);
                    replacement.add(source?prefix+"/corridor/"+old:old);
                }
                mission.add(chain,replacement);
            }
            var bridge=corridors.get(ascent.get(ascent.size()-1)).deepCopy();
            String bridgeId=prefix+"/actual_loaded_bridge_r53";
            bridge.addProperty("id",bridgeId);bridge.addProperty("from",names.get(pickup+"/main"));bridge.addProperty("to",pickup+"/main");
            bridge.addProperty("ticks",1);bridge.remove("reverse_of");root.getAsJsonArray("corridors").add(bridge);
            var loaded=new JsonArray();for(String id:ascent)loaded.add(prefix+"/corridor/"+id);loaded.add(bridgeId);for(String id:descent)loaded.add(id);
            mission.add("loaded",loaded);
            mission.addProperty("pickup_node",prefix);
        }
        return root;
    }

    private static Map<String,JsonObject> index(JsonObject root,String key)
    {
        var result=new LinkedHashMap<String,JsonObject>();
        for(var value:root.getAsJsonArray(key)){var row=value.getAsJsonObject();result.put(row.get("id").getAsString(),row);}
        return result;
    }
    private static String edge(Map<String,JsonObject> corridors,String from,String to)
    {
        for(var c:corridors.values())if(from.equals(c.get("from").getAsString())&&to.equals(c.get("to").getAsString()))return c.get("id").getAsString();
        throw new IllegalStateException("Original pickup column lacks its physical ascent/descent");
    }
    private NervAirPickupColumnR53(){}
}
