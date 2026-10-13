package com.projectseele.world;

import com.google.gson.*;
import java.util.*;
import net.minecraft.world.phys.AABB;
import com.projectseele.world.NervRouteDirectoryR52.ResourceKind;

/** Production binding parser checks; synthetic values never commission a world. */
public final class NervRouteNativeBindingR52Test
{
    private static int checks;
    private static void check(boolean condition,String why){checks++;if(!condition)throw new AssertionError(why);}
    private static void rejects(Runnable call,String why){boolean rejected=false;try{call.run();}catch(RuntimeException expected){rejected=true;}check(rejected,why);}
    private static JsonArray array(Number... values){var result=new JsonArray();for(var v:values)result.add(v);return result;}
    private static JsonArray fixture(NervRouteDirectoryR52 directory)
    {
        var rows=new JsonArray();int index=0;
        for(var r:directory.declaredResources().values())
        {
            index++;var row=new JsonObject();row.addProperty("resource",r.id());row.addProperty("component",r.component());
            if(r.kind()==ResourceKind.SPACE){var spaces=new JsonArray();spaces.add(array(index*10,0,0,index*10+2,2,2));row.add("spaces",spaces);}
            else if(r.kind()==ResourceKind.DOOR){row.addProperty("entity_uuid",new UUID(0,index).toString());row.addProperty("expected_type","projectseele:nerv_hangar_door");row.addProperty("required_open",1);}
            else{var cells=new JsonArray();var cell=new JsonObject();cell.add("position",array(index*10,0,0));cell.addProperty("state","minecraft:iron_block");cells.add(cell);row.add("cells",cells);}
            rows.add(row);
        }
        return rows;
    }
    private static JsonObject first(JsonArray rows,NervRouteDirectoryR52 directory,ResourceKind kind)
    {for(var row:rows)if(directory.resource(row.getAsJsonObject().get("resource").getAsString()).kind()==kind)return row.getAsJsonObject();throw new AssertionError("Fixture resource missing");}
    public static void main(String[] args)
    {
        var directory=NervRouteDirectoryR52.parse(NervRouteCoreR52Test.rootFixtureForNativeBindingTest());var rows=fixture(directory);
        check(NervRouteNativeR52.parseBindings(rows,directory).size()==directory.declaredResources().size(),"Complete explicit native bindings rejected");
        var changed=rows.deepCopy();changed.remove(0);var missing=changed;rejects(()->NervRouteNativeR52.parseBindings(missing,directory),"Partial provider set accepted");
        changed=rows.deepCopy();first(changed,directory,ResourceKind.SPACE).getAsJsonArray("spaces").set(0,array(1,0,0,0,2,2));var reversed=changed;rejects(()->NervRouteNativeR52.parseBindings(reversed,directory),"Reversed Root bounds silently normalized");
        changed=rows.deepCopy();first(changed,directory,ResourceKind.SPACE).getAsJsonArray("spaces").set(0,array(0,0,0,2,0,2));var flat=changed;rejects(()->NervRouteNativeR52.parseBindings(flat,directory),"Zero thickness occupied volume accepted");
        changed=rows.deepCopy();var rail=first(changed,directory,ResourceKind.RAIL).getAsJsonArray("cells");var far=rail.get(0).deepCopy().getAsJsonObject();far.add("position",array(999,0,0));rail.add(far);var disconnected=changed;rejects(()->NervRouteNativeR52.parseBindings(disconnected,directory),"Disconnected physical rail cell chain accepted");
        changed=rows.deepCopy();first(changed,directory,ResourceKind.DOOR).addProperty("required_open",0);var noOpen=changed;rejects(()->NervRouteNativeR52.parseBindings(noOpen,directory),"Closed gate admitted as open");
        changed=rows.deepCopy();String actor=first(changed,directory,ResourceKind.DOOR).get("entity_uuid").getAsString();boolean other=false;for(var row:changed)if(directory.resource(row.getAsJsonObject().get("resource").getAsString()).kind()==ResourceKind.DOOR){if(other){row.getAsJsonObject().addProperty("entity_uuid",actor);break;}other=true;}var aliasedActor=changed;rejects(()->NervRouteNativeR52.parseBindings(aliasedActor,directory),"Same physical gate bypassed resource leases via two IDs");
        changed=rows.deepCopy();JsonArray firstSpace=first(changed,directory,ResourceKind.SPACE).getAsJsonArray("spaces").deepCopy();other=false;for(var row:changed)if(directory.resource(row.getAsJsonObject().get("resource").getAsString()).kind()==ResourceKind.SPACE){if(other){row.getAsJsonObject().add("spaces",firstSpace);break;}other=true;}var aliasedSpace=changed;rejects(()->NervRouteNativeR52.parseBindings(aliasedSpace,directory),"Overlapping actual space bypassed leases via separate IDs");
        var grid=new ArrayList<AABB>();for(int x=0;x<2;x++)for(int y=-1;y<3;y++)for(int z=0;z<2;z++)grid.add(new AABB(x*32,y*32,z*32,(x+1)*32,(y+1)*32,(z+1)*32));
        var fullCarrier=new AABB(8,-20,8,50,70,50);
        check(NervRouteNativeR52.coveredByDeclaredSpacesR52(fullCarrier,grid),"Real carrier spanning adjacent32m reservations was rejected");
        var hole=new ArrayList<>(grid);hole.remove(5);check(!NervRouteNativeR52.coveredByDeclaredSpacesR52(fullCarrier,hole),"Missing reserved interior cell was silently bridged");
        check(!NervRouteNativeR52.coveredByDeclaredSpacesR52(new AABB(0,0,0,32,32,32),List.of(new AABB(0,0,0,16,32,32),new AABB(16.0000001,0,0,32,32,32))),"Sub-millimetre unreserved gap was rounded away");
        check(!NervRouteNativeR52.coveredByDeclaredSpacesR52(new AABB(0,0,0,0,1,1),grid),"Zero-volume proof accepted");
        System.out.println("R52 production native binding parser PASS checks="+checks+"; configuration only, no loaded-world acceptance");
    }
    private NervRouteNativeBindingR52Test(){}
}
