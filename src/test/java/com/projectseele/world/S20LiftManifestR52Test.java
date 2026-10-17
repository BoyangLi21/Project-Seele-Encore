package com.projectseele.world;

import com.google.gson.*;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;

/** Synthetic parser regressions; no world, native installation or geometry acceptance. */
public final class S20LiftManifestR52Test
{
    private static int checks;
    private static void check(boolean value,String label)
    {checks++;if(!value)throw new AssertionError(label);}
    private static void rejected(JsonObject json,String label)
    {boolean rejected=false;try{S20LiftManifestR52.parse(json);}catch(RuntimeException expected){rejected=true;}check(rejected,label);}
    private static JsonArray array(int... values)
    {var result=new JsonArray();for(int value:values)result.add(value);return result;}
    private static JsonObject floor(int x,int z,int controllerX,int y,boolean restricted)
    {
        var floor=new JsonObject();floor.addProperty("label","test floor "+y);
        floor.add("cabin",array(x,y,z));floor.add("controller",array(controllerX,y,z));
        floor.addProperty("exit","south");floor.addProperty("approach_y",y);floor.addProperty("restricted",restricted);
        var call=new JsonObject();call.addProperty("kind","vanilla_button");call.add("position",array(x+3,y+1,z+5));
        call.addProperty("state","minecraft:polished_blackstone_button[face=wall,facing=south,powered=false]");
        call.addProperty("facing","south");call.add("target_controller",array(controllerX,y,z));
        var calls=new JsonArray();calls.add(call);floor.add("calls",calls);
        for(String key:new String[]{"landing_doors","cabin_doors"})
        {var cells=new JsonArray();var cell=new JsonObject();cell.add("pos",array(x,y,z+(key.equals("landing_doors")?4:2)));
         cell.addProperty("closed_state","minecraft:gray_stained_glass");cells.add(cell);floor.add(key,cells);}
        return floor;
    }
    private static JsonObject lift(String id,int x,int z,int controllerX,int... ys)
    {
        var lift=new JsonObject();lift.addProperty("id",id);lift.addProperty("controller_side","west");lift.addProperty("controller_facing","east");
        lift.add("inside_button_offset",array(-2,1,0));lift.add("inside_display_offset",array(-2,2,0));
        var floors=new JsonArray();for(int y:ys)floors.add(floor(x,z,controllerX,y,y==-846));lift.add("floors",floors);return lift;
    }
    private static JsonObject main(String id,int hangar,Integer terminal,int... headquarters)
    {
        var role=new JsonObject();role.addProperty("lift_id",id);role.addProperty("hangar_floor",hangar);
        var axis=new JsonObject();boolean rear=id.equals(S20PhysicalElevatorDirector.COMMAND_REAR_LIFT_ID);
        axis.add("cabin",array(rear?12:66,rear?253:302));axis.add("controller",array(rear?9:63,rear?253:302));
        role.add("source_axis",axis);role.add("shaft_translation",array(0,0));
        if(terminal!=null)role.addProperty("terminal_floor",terminal);role.add("headquarters_floors",array(headquarters));return role;
    }
    private static JsonObject candidate()
    {
        var root=new JsonObject();root.addProperty("schema",S20LiftManifestR52.SCHEMA);root.addProperty("scope","s20_personnel_only");
        root.addProperty("complete_replacement",true);root.addProperty("ready",true);root.addProperty("epoch",53);root.addProperty("directory_fingerprint","a".repeat(64));
        var lifts=new JsonArray();lifts.add(lift(S20PhysicalElevatorDirector.COMMAND_REAR_LIFT_ID,12,253,9,-846,-630,-541,-502));
        lifts.add(lift(FacilityLiftsR25.EAST,66,302,63,-630,-554,-499,-457));root.add("lifts",lifts);
        var roles=new JsonObject();roles.add("command_rear",main(S20PhysicalElevatorDirector.COMMAND_REAR_LIFT_ID,-630,-846,-541,-502));
        roles.add("east_gallery",main(FacilityLiftsR25.EAST,-630,null,-554,-499,-457));root.add("main_lifts",roles);
        var office=lift(S20PhysicalElevatorDirector.COMMANDER_OFFICE_LIFT_ID,28,321,31,-481,-457,-433);
        office.addProperty("controller_side","east");office.addProperty("controller_facing","west");
        office.add("inside_button_offset",array(2,1,0));office.add("inside_display_offset",array(2,2,0));
        office.getAsJsonArray("floors").get(1).getAsJsonObject().addProperty("restricted",true);
        office.getAsJsonArray("floors").get(2).getAsJsonObject().addProperty("restricted",true);lifts.add(office);
        root.add("office_access",JsonParser.parseString("""
                {"lift_id":"s23-commander-office-x28-z321-v1","middle_y":-457,
                 "readers":[[25,-480,316],[31,-456,316],[25,-432,316]],"middle_reader":[31,-456,316],
                 "meeting_boxes":[[16,-459,300,52,-455,316]],"lift_room_boxes":[[22,-483,312,34,-425,329]],
                 "landing_lease_box":[25,-460,315,32,-454,325],"room_controls":{
                   "gate":[{"lower":[28,-457,315],"facing":"south","hinge":"right"},{"lower":[29,-457,315],"facing":"south","hinge":"left"}],
                   "gate_readers":[{"position":[27,-456,314],"facing":"north","backing":[27,-456,315],"side_axis":"z","side_boundary":315,"less_than":true},
                                   {"position":[27,-456,316],"facing":"south","backing":[27,-456,315],"side_axis":"z","side_boundary":316,"less_than":false}],
                   "pilot_guard_doors":[{"lower":[53,-630,311],"facing":"north","hinge":"right","approach_feet":[[53.5,-630,310.5],[53.5,-630,312.5]]},
                                         {"lower":[11,-630,311],"facing":"north","hinge":"right","approach_feet":[[11.5,-630,310.5],[11.5,-630,312.5]]},
                                         {"lower":[-31,-630,311],"facing":"north","hinge":"right","approach_feet":[[-30.5,-630,310.5],[-30.5,-630,312.5]]}]}}
                """));return root;
    }
    public static void main(String[] args)throws Exception
    {
        var source=candidate();var document=S20LiftManifestR52.parse(source);
        check(document.ready()&&document.mainLifts().commandRear().terminalFloor()==-846,"Two original main-lift roles lost");
        check(document.lifts().size()==3,"Parser invented additional groups beyond two main lifts and the retained office");
        var rear=document.lifts().get(0);var spec=rear.spec();
        for(var landing:spec.stops())
        {check(S20MovingElevatorsAdapter.controllerPosition(spec,landing).equals(new BlockPos(9,landing.walkY(),253)),"Original controller axis changed");
         check(landing.r52().callDisplay()==null,"Original vanilla calls required invented native displays");}
        var invalid=source.deepCopy();invalid.remove("main_lifts");rejected(invalid,"Ready allowed missing main-lift roles");
        invalid=source.deepCopy();invalid.remove("office_access");invalid.getAsJsonArray("lifts").remove(2);rejected(invalid,"Ready discarded the user-retained original office lift");
        invalid=source.deepCopy();invalid.getAsJsonArray("lifts").get(2).getAsJsonObject().getAsJsonArray("floors").get(2).getAsJsonObject().addProperty("restricted",false);rejected(invalid,"Original office highest-card admission was weakened");
        invalid=source.deepCopy();invalid.getAsJsonObject("main_lifts").getAsJsonObject("east_gallery").addProperty("hangar_floor",-554);rejected(invalid,"East lift stopped at headquarters instead of hangar");
        invalid=source.deepCopy();invalid.getAsJsonObject("main_lifts").getAsJsonObject("command_rear").remove("terminal_floor");rejected(invalid,"Main lift lost Terminal access");
        invalid=source.deepCopy();invalid.getAsJsonArray("lifts").get(0).getAsJsonObject().getAsJsonArray("floors").get(0).getAsJsonObject().addProperty("restricted",false);rejected(invalid,"Terminal admitted without access control");
        invalid=source.deepCopy();invalid.getAsJsonArray("lifts").add(lift("r52-hq-hangar-terminal-shared",108,407,105,-846,-630,-554));rejected(invalid,"Failed third headquarters lift restored");
        invalid=source.deepCopy();invalid.getAsJsonArray("lifts").add(lift("renamed-third-main-lift",108,407,105,-846,-630,-554));rejected(invalid,"Third main lift bypassed retirement by renaming");
        invalid=source.deepCopy();invalid.getAsJsonObject("main_lifts").getAsJsonObject("east_gallery").addProperty("lift_id",S20PhysicalElevatorDirector.COMMAND_REAR_LIFT_ID);rejected(invalid,"Both main roles pointed at same lift");
        invalid=source.deepCopy();invalid.getAsJsonArray("lifts").get(0).getAsJsonObject().addProperty("controller_side","east");rejected(invalid,"Opposite native controller side accepted");
        invalid=source.deepCopy();invalid.getAsJsonArray("lifts").add(invalid.getAsJsonArray("lifts").get(0).deepCopy());rejected(invalid,"Duplicate shaft accepted");
        invalid=source.deepCopy();invalid.getAsJsonArray("lifts").get(0).getAsJsonObject().getAsJsonArray("floors").get(0).getAsJsonObject().addProperty("exit","up");rejected(invalid,"Vertical landing exit accepted");
        invalid=source.deepCopy();invalid.getAsJsonArray("lifts").get(0).getAsJsonObject().getAsJsonArray("floors").get(1).getAsJsonObject().getAsJsonArray("calls").get(0).getAsJsonObject().add("target_controller",array(9,-846,253));rejected(invalid,"Call accepted another floor controller");
        invalid=source.deepCopy();invalid.getAsJsonArray("lifts").get(0).getAsJsonObject().getAsJsonArray("floors").get(0).getAsJsonObject().getAsJsonArray("calls").get(0).getAsJsonObject().addProperty("kind","seele_reader");rejected(invalid,"Unowned reader acquired office authority");
        var optional=source.deepCopy();optional.getAsJsonArray("lifts").add(lift(S20PhysicalElevatorDirector.COMPACT_CAGE_LIFT_ID,93,-52,90,-468,-442));
        check(S20LiftManifestR52.parse(optional).lifts().size()==4,"Optional surviving original group forced a global group count");
        var draft=source.deepCopy();draft.addProperty("ready",false);draft.remove("main_lifts");check(!S20LiftManifestR52.parse(draft).ready(),"Draft parsing silently installed it");
        invalid=source.deepCopy();invalid.getAsJsonObject("main_lifts").getAsJsonObject("command_rear").add("shaft_translation",array(12,0));rejected(invalid,"Undeclared actual axis shift admitted");
        var shifted=source.deepCopy();shifted.getAsJsonObject("main_lifts").getAsJsonObject("command_rear").add("shaft_translation",array(12,0));
        var shiftedFloors=shifted.getAsJsonArray("lifts").get(0).getAsJsonObject().getAsJsonArray("floors");
        for(var raw:shiftedFloors)
        {
            var f=raw.getAsJsonObject();for(String key:new String[]{"cabin","controller"})shiftX(f.getAsJsonArray(key),12);
            for(var call:f.getAsJsonArray("calls")){shiftX(call.getAsJsonObject().getAsJsonArray("position"),12);shiftX(call.getAsJsonObject().getAsJsonArray("target_controller"),12);}
            for(String key:new String[]{"landing_doors","cabin_doors"})for(var door:f.getAsJsonArray(key))shiftX(door.getAsJsonObject().getAsJsonArray("pos"),12);
        }
        check(S20LiftManifestR52.parse(shifted).mainLifts().commandRear().liftId().equals(S20PhysicalElevatorDirector.COMMAND_REAR_LIFT_ID),"Rigidly moved original main lift lost its identity");
        var personnel=source.deepCopy();
        for(int i=0;i<2;i++)
        {
            var role=personnel.getAsJsonObject("main_lifts").getAsJsonObject(i==0?"command_rear":"east_gallery");
            role.addProperty("observation_floor",-630);role.addProperty("hangar_floor",-657);role.addProperty("launch_floor",-673);
            var binding=personnel.getAsJsonArray("lifts").get(i).getAsJsonObject();var oldFloors=binding.getAsJsonArray("floors");
            var expanded=new JsonArray();
            for(var raw:oldFloors)
            {
                if(raw.getAsJsonObject().getAsJsonArray("cabin").get(1).getAsInt()==-630)
                {expanded.add(floor(i==0?12:66,i==0?253:302,i==0?9:63,-673,false));expanded.add(floor(i==0?12:66,i==0?253:302,i==0?9:63,-657,false));}
                expanded.add(raw.deepCopy());
            }
            binding.add("floors",expanded);
        }
        var access=S20LiftManifestR52.parse(personnel).mainLifts();
        check(access.commandRear().hangarFloor()==-657&&access.commandRear().observationFloor()==-630
                &&access.commandRear().launchFloor()==-673&&access.eastGallery().launchFloor()==-673,
                "Boarding and launch stops collapsed back into observation");
        invalid=personnel.deepCopy();invalid.getAsJsonObject("main_lifts").getAsJsonObject("east_gallery").remove("launch_floor");
        rejected(invalid,"One main lift silently lost launch access");
        invalid=personnel.deepCopy();invalid.getAsJsonObject("main_lifts").getAsJsonObject("command_rear").addProperty("observation_floor",-657);
        rejected(invalid,"Observation label accepted as the boarding stop");
        invalid=personnel.deepCopy();invalid.getAsJsonObject("main_lifts").getAsJsonObject("command_rear").add("headquarters_floors",array(-630,-541,-502));
        rejected(invalid,"Observation floor received two incompatible roles");
        invalid=personnel.deepCopy();invalid.getAsJsonArray("lifts").get(1).getAsJsonObject().getAsJsonArray("floors").get(0).getAsJsonObject().addProperty("restricted",true);
        rejected(invalid,"Launch floor inherited restricted Terminal admission");
        check(S20LiftDirectoryR52.retiredControllerAxis(108,410)&&!S20LiftDirectoryR52.retiredControllerAxis(1000,1000),"Retired group confused with independent player group");
        check(S20LiftDirectoryR52.independentGateway(true,-368,750,Direction.EAST),"Independent gateway denied");
        if(args.length==2&&args[0].equals("--candidate"))
        {
            var actual=JsonParser.parseString(java.nio.file.Files.readString(java.nio.file.Path.of(args[1]))).getAsJsonObject();
            actual.addProperty("ready",true);var installed=S20LiftManifestR52.parse(actual);
            check(installed.mainLifts().commandRear().hangarFloor()==-1014&&installed.mainLifts().eastGallery().hangarFloor()==-1014,
                    "Actual proposal does not reach both boarding landings");
            check(installed.mainLifts().commandRear().launchFloor()==-1030&&installed.mainLifts().eastGallery().launchFloor()==-1030,
                    "Actual proposal does not reach both launch landings");
            check(installed.lifts().size()==6,"Actual proposal changed the six original personnel-lift identities");
        }
        else if(args.length>0)rejected(JsonParser.parseString(java.nio.file.Files.readString(java.nio.file.Path.of(args[0]))).getAsJsonObject(),
                "Actual frozen failed shared-lift manifest was accepted");
        System.out.println("PASS original two-main-lift contract checks="+checks+"; parser only, no world acceptance");
    }
    private static void shiftX(JsonArray point,int delta)
    {point.set(0,new JsonPrimitive(point.get(0).getAsInt()+delta));}
}
