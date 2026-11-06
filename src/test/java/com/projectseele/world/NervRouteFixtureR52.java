package com.projectseele.world;

import com.google.gson.*;
import java.util.*;
import net.minecraft.world.phys.Vec3;
import com.projectseele.world.NervRouteDirectoryR52.*;

/** A synthetic route graph for the route checks. No Root map coordinates, real devices, actors or world. */
public final class NervRouteFixtureR52
{
    private static UUID uuid(int id){return new UUID(0,id);}
    private static JsonArray names(String... values){var a=new JsonArray();for(String v:values)a.add(v);return a;}
    private static JsonArray numbers(double... values){var a=new JsonArray();for(double v:values)a.add(v);return a;}
    private static JsonObject find(JsonArray array,String id)
    {for(var element:array){var row=element.getAsJsonObject();if(row.get("id").getAsString().equals(id))return row;}throw new AssertionError(id);}
    private static void node(JsonObject root,String id,Role role,int bank,int lane,int variant,double x,double y,double z)
    {
        var n=new JsonObject();n.addProperty("id",id);n.addProperty("dimension","test:synthetic_route_graph");n.addProperty("role",role.name());
        if(role==Role.BANK){n.addProperty("bank",bank);n.addProperty("lane",lane);}if(role==Role.BAY)n.addProperty("variant",variant);
        var f=new JsonObject();f.add("translation",numbers(x,y,z));f.add("quaternion_xyzw",numbers(0,0,0,1));n.add("foot_frame",f);root.getAsJsonArray("nodes").add(n);
    }
    private static void resource(JsonObject root,String id,ResourceKind kind)
    {var r=new JsonObject();r.addProperty("id",id);r.addProperty("kind",kind.name());r.addProperty("component","synthetic_component/"+id);root.getAsJsonArray("resources").add(r);}
    private static String leg(JsonObject root,String id,String from,String to,Motion motion,String occupied)
    {
        var l=new JsonObject();l.addProperty("id",id);l.addProperty("from",from);l.addProperty("to",to);l.addProperty("motion",motion.name());l.addProperty("ticks",10);
        l.add("eva_from_xyzw",numbers(0,0,0,1));l.add("eva_to_xyzw",numbers(0,0,0,1));l.add("rails",names("rail_"+id));resource(root,"rail_"+id,ResourceKind.RAIL);
        if(motion==Motion.TRACKED_BANK_TRANSFER){l.add("doors",names("gate_"+id));resource(root,"gate_"+id,ResourceKind.DOOR);}else l.add("doors",names());
        l.addProperty("support","support_"+id);resource(root,"support_"+id,ResourceKind.SUPPORT);l.add("occupancy",names(occupied));root.getAsJsonArray("legs").add(l);return id;
    }
    private static JsonObject route(String id,int variant,int bank,int lane,String port,String reverse,List<String> path)
    {
        var r=new JsonObject();r.addProperty("id",id);r.addProperty("variant",variant);r.addProperty("bank",bank);r.addProperty("lane",lane);r.addProperty("region",bank==2?"GEOFRONT":"SURFACE");r.addProperty("port",port);
        if(!reverse.isEmpty())r.addProperty("reverse_of",reverse);r.add("legs",names(path.toArray(String[]::new)));return r;
    }
    private static JsonObject fixture(boolean installed,boolean sharedSpace)
    {return fixture(installed,sharedSpace,new int[]{0,1,2});}
    private static JsonObject fixture(boolean installed,boolean sharedSpace,int[] unitToLane)
    {
        var r=new JsonObject();r.addProperty("schema",NervRouteDirectoryR52.SCHEMA);r.addProperty("map_author","root");r.addProperty("status",installed?"installed":"design");r.addProperty("epoch",7);
        if(installed)r.addProperty("installation_receipt_sha256","f".repeat(64));for(String key:List.of("units","nodes","resources","legs","routes","ports"))r.add(key,new JsonArray());
        if(sharedSpace)resource(r,"shared",ResourceKind.SPACE);
        for(int variant=0;variant<3;variant++)
        {
            int physicalLane=unitToLane[variant],lane=physicalLane+1;double x=lane*10;
            var u=new JsonObject();u.addProperty("variant",variant);u.addProperty("lane",physicalLane);u.addProperty("eva",uuid(10+variant).toString());u.addProperty("plug",uuid(20+variant).toString());r.getAsJsonArray("units").add(u);
            node(r,"bay"+lane,Role.BAY,0,0,variant,x,0,0);
            for(int bank=1;bank<=3;bank++)node(r,"dock"+bank+"_"+lane,Role.BANK,bank,physicalLane,-1,x,1,bank*10);
            String space=sharedSpace&&variant<2?"shared":"space"+lane;if(!space.equals("shared"))resource(r,space,ResourceKind.SPACE);
            String initial=leg(r,"original"+lane,"bay"+lane,"dock1_"+lane,Motion.ORIGINAL_UPRIGHT_TRANSFER,space);
            String bridge12=leg(r,"bridge12_"+lane,"dock1_"+lane,"dock2_"+lane,Motion.TRACKED_BANK_TRANSFER,space);
            String bridge23=leg(r,"bridge23_"+lane,"dock2_"+lane,"dock3_"+lane,Motion.TRACKED_BANK_TRANSFER,space);
            for(int bank=1;bank<=3;bank++)
            {
                String base="b"+bank+"l"+lane,exit="exit_"+base,port="port_"+base;
                var path=new ArrayList<String>();path.add(initial);if(bank>=2)path.add(bridge12);if(bank==3)path.add(bridge23);
                if(bank==2){node(r,exit,Role.EXIT,0,0,-1,x,4,20);path.add(leg(r,"vertical_"+base,"dock2_"+lane,exit,Motion.VERTICAL,space));}
                else
                {
                    String shortTop="short_"+base,inclineTop="incline_"+base;node(r,shortTop,Role.PATH,0,0,-1,x,2,bank*10);node(r,inclineTop,Role.PATH,0,0,-1,x,3,bank*10+1);node(r,exit,Role.EXIT,0,0,-1,x,4,bank*10+1);
                    path.add(leg(r,"short_vertical_"+base,"dock"+bank+"_"+lane,shortTop,Motion.VERTICAL,space));path.add(leg(r,"incline_"+base,shortTop,inclineTop,Motion.LAUNCH_INCLINE,space));path.add(leg(r,"surface_vertical_"+base,inclineTop,exit,Motion.VERTICAL,space));
                }
                String depart="depart_"+base,back="return_"+base;r.getAsJsonArray("routes").add(route(depart,variant,bank,physicalLane,port,"",path));
                var reverse=new ArrayList<String>();for(int i=path.size()-1;i>=0;i--)
                {
                    var forward=find(r.getAsJsonArray("legs"),path.get(i));String id="reverse_"+path.get(i);
                    boolean exists=false;for(var old:r.getAsJsonArray("legs"))if(old.getAsJsonObject().get("id").getAsString().equals(id))exists=true;
                    if(!exists){var v=forward.deepCopy();v.addProperty("id",id);v.addProperty("from",forward.get("to").getAsString());v.addProperty("to",forward.get("from").getAsString());r.getAsJsonArray("legs").add(v);}reverse.add(id);
                }
                r.getAsJsonArray("routes").add(route(back,variant,bank,physicalLane,port,depart,reverse));var p=new JsonObject();p.addProperty("id",port);p.addProperty("region",bank==2?"GEOFRONT":"SURFACE");p.addProperty("node",exit);var bind=new JsonObject();bind.addProperty(Integer.toString(variant),back);p.add("reverse_routes",bind);r.getAsJsonArray("ports").add(p);
            }
        }
        return r;
    }
    static JsonObject rootFixture(){return fixture(true,false);}
    private NervRouteFixtureR52(){}
}
