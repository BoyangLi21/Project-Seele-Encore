package com.projectseele.world;

import com.google.gson.*;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.level.block.state.properties.DoorHingeSide;
import java.util.*;

/** Explicit Root geometry only. Parsing a candidate never installs or activates it. */
public final class S20LiftManifestR52
{
    public static final String SCHEMA="projectseele.r52.s20-lifts.v1";
    public enum CallKind { NATIVE_LINKED, VANILLA_BUTTON, SEELE_READER }
    public record Display(BlockPos position,String state) {}
    public record Call(CallKind kind,BlockPos position,String state,Direction facing,BlockPos targetController,Display display) {}
    public record Floor(String label,BlockPos cabin,Direction exit,int approachY,BlockPos controller,
                        List<Call> calls,boolean restricted,Map<BlockPos,String> landingDoors,Map<BlockPos,String> cabinDoors,UUID visualDoor)
    {
        public BlockPos callButton(){return calls.get(0).position();}
        public BlockPos callDisplay(){return calls.get(0).display()==null?null:calls.get(0).display().position();}
        public Direction callFacing(){return calls.get(0).facing();}
        public List<BlockPos> callAliases(){return calls.stream().skip(1).map(Call::position).toList();}
    }
    public record Binding(String id,Direction controllerSide,Direction controllerFacing,BlockPos insideButtonOffset,
                          BlockPos insideDisplayOffset,List<Floor> floors)
    {
        public Floor floor(int y){return floors.stream().filter(f->f.cabin().getY()==y).findFirst().orElseThrow();}
        public S20PhysicalElevatorDirector.LiftSpec spec()
        {return new S20PhysicalElevatorDirector.LiftSpec(id,floors.stream().map(f->new S20PhysicalElevatorDirector.Landing(f.label(),f.cabin(),f.exit(),f.approachY(),f)).toList(),this);}
    }
    public record Door(BlockPos lower,Direction facing,DoorHingeSide hinge,List<net.minecraft.world.phys.Vec3> approachFeet) {}
    public record Reader(BlockPos position,Direction facing,BlockPos backing,Direction.Axis sideAxis,double boundary,boolean less) {}
    public record RoomControls(List<Door> gate,List<Reader> gateReaders,List<Door> pilot) {}
    public record Office(String liftId,int middleY,Set<BlockPos> readers,BlockPos middleReader,
                         List<AABB> meeting,List<AABB> liftRoom,AABB landingLease,RoomControls controls) {}
    public record MainLift(String liftId,List<Integer> headquartersFloors,int hangarFloor,Integer terminalFloor,
                           Integer observationFloor,Integer launchFloor) {}
    public record MainLifts(MainLift commandRear,MainLift eastGallery) {}
    public record Document(long epoch,String directoryFingerprint,boolean ready,List<Binding> lifts,Office office,MainLifts mainLifts) {}
    private S20LiftManifestR52() {}
    public static Document parse(JsonObject root)
    {
        require(SCHEMA.equals(root.get("schema").getAsString())&&root.get("complete_replacement").getAsBoolean(),"Complete Root lift replacement required");
        long epoch=root.get("epoch").getAsBigDecimal().longValueExact();String fingerprint=root.get("directory_fingerprint").getAsString();
        require(epoch>0&&fingerprint.matches("[0-9a-f]{64}"),"Root claim epoch/fingerprint required");
        require("s20_personnel_only".equals(root.get("scope").getAsString()),"S20-only scope required; independent gateway excluded");
        List<Binding> lifts=new ArrayList<>();Set<String> ids=new HashSet<>();Set<BlockPos> allControllers=new HashSet<>();
        Set<BlockPos> allCalls=new HashSet<>();
        for(var value:root.getAsJsonArray("lifts"))
        {
            var lift=value.getAsJsonObject();String id=lift.get("id").getAsString();require(!id.isBlank()&&ids.add(id),"Duplicate lift identity");
            require(!id.equals(NervLiftPassengerSync.GATEWAY),"Independent regional gateway must not be duplicated in S20 manifest");
            require(Set.of(S20PhysicalElevatorDirector.COMMAND_REAR_LIFT_ID,S20PhysicalElevatorDirector.COMPACT_CAGE_LIFT_ID,
                    S20PhysicalElevatorDirector.SURFACE_TRANSIT_LIFT_ID,S20PhysicalElevatorDirector.COMMANDER_OFFICE_LIFT_ID,
                    FacilityLiftsR25.EAST,FacilityLiftsR25.OBSERVATION).contains(id),
                    "Only original lift identities may be migrated; no third headquarters-to-hangar lift");
            Direction side=direction(lift,"controller_side"),facing=direction(lift,"controller_facing");require(side.getOpposite()==facing,"Controller must face its declared cabin");
            var insideButton=point(lift.getAsJsonArray("inside_button_offset"));var insideDisplay=point(lift.getAsJsonArray("inside_display_offset"));
            List<Floor> floors=new ArrayList<>();
            for(var row:lift.getAsJsonArray("floors"))
            {
                var f=row.getAsJsonObject();BlockPos cabin=point(f.getAsJsonArray("cabin")),controller=point(f.getAsJsonArray("controller"));
                int dx=controller.getX()-cabin.getX(),dz=controller.getZ()-cabin.getZ(),distance=dx*side.getStepX()+dz*side.getStepZ();
                require(controller.getY()==cabin.getY()&&distance>0&&dx==side.getStepX()*distance&&dz==side.getStepZ()*distance,"Explicit controller is not on declared side");
                require(allControllers.add(controller),"Controller assigned to multiple floors");
                var doors=cells(f.getAsJsonArray("landing_doors"));var cabinDoors=cells(f.getAsJsonArray("cabin_doors"));
                require(!doors.isEmpty()&&!cabinDoors.isEmpty(),"Explicit native door cells required");
                require(!doors.containsKey(controller)&&!cabinDoors.containsKey(controller),"Door plane overlaps controller");
                require(!f.has("call_aliases")&&!f.has("call_button")&&!f.has("call_display"),"Declare each actual call through calls[] with state and ownership");
                List<Call> calls=new ArrayList<>();for(var rowCall:f.getAsJsonArray("calls"))
                {
                    var c=rowCall.getAsJsonObject();var kind=CallKind.valueOf(c.get("kind").getAsString().toUpperCase(Locale.ROOT));var pos=point(c.getAsJsonArray("position"));
                    var target=point(c.getAsJsonArray("target_controller"));require(target.equals(controller),"Call must target this actual native floor controller");
                    String state=c.get("state").getAsString();require(!state.isBlank()&&allCalls.add(pos),"Duplicate/empty actual call state");
                    Display display=null;if(c.has("display")&&!c.get("display").isJsonNull())
                    {var d=c.getAsJsonObject("display");display=new Display(point(d.getAsJsonArray("position")),d.get("state").getAsString());require(kind==CallKind.NATIVE_LINKED&&!display.state().isBlank()&&allCalls.add(display.position()),"Only native linked inputs own displays");}
                    calls.add(new Call(kind,pos,state,direction(c,"facing"),target,display));
                }
                require(!calls.isEmpty(),"At least one measured call required per floor");
                UUID visual=f.has("visual_door_uuid")?UUID.fromString(f.get("visual_door_uuid").getAsString()):null;
                floors.add(new Floor(f.get("label").getAsString(),cabin,direction(f,"exit"),f.get("approach_y").getAsBigDecimal().intValueExact(),controller,
                        List.copyOf(calls),
                        f.get("restricted").getAsBoolean(),doors,cabinDoors,visual));
            }
            Binding binding=new Binding(id,side,facing,insideButton,insideDisplay,List.copyOf(floors));
            binding.spec();
            for(int i=1;i<floors.size();i++)require(floors.get(i-1).cabin().getY()<floors.get(i).cabin().getY(),"Native floors must be listed in ascending order");
            var transfer=NervPersonnelTransferR53.parse(id,lift);
            if(transfer==null)require(floors.stream().allMatch(f->f.controller().getX()==floors.get(0).controller().getX()&&f.controller().getZ()==floors.get(0).controller().getZ()),"Native controller group must share one axis");
            else
            {
                require(floors.stream().allMatch(f->f.controller().equals(transfer.controller(f.controller().getY()))),"Each transferred floor must use its declared original or deep shaft");
                require(floors.stream().noneMatch(f->f.controller().getY()==transfer.transferY()),"Horizontal transfer is an internal section, not a passenger stop");
                require(floors.stream().anyMatch(f->f.controller().getY()>transfer.transferY())&&floors.stream().anyMatch(f->f.controller().getY()<transfer.transferY()),"Horizontal transfer must join both actual shafts");
            }
            lifts.add(binding);
        }
        require(!lifts.isEmpty(),"Root complete list cannot be empty");Office office=null;
        if(root.has("office_access"))
        {
            var raw=root.getAsJsonObject("office_access");Set<BlockPos> readers=new HashSet<>();for(var p:raw.getAsJsonArray("readers"))require(readers.add(point(p.getAsJsonArray())),"Duplicate office reader");
            office=new Office(raw.get("lift_id").getAsString(),raw.get("middle_y").getAsInt(),Set.copyOf(readers),point(raw.getAsJsonArray("middle_reader")),
                    boxes(raw.getAsJsonArray("meeting_boxes")),boxes(raw.getAsJsonArray("lift_room_boxes")),box(raw.getAsJsonArray("landing_lease_box")),room(raw.getAsJsonObject("room_controls")));
            require(office.liftId().equals(S20PhysicalElevatorDirector.COMMANDER_OFFICE_LIFT_ID)
                    &&ids.contains(office.liftId())&&office.readers().contains(office.middleReader()),"Original office reader/lift identity binding missing");
            Office check=office;Binding owner=lifts.stream().filter(b->b.id().equals(check.liftId())).findFirst().orElseThrow();
            require(owner.floors().stream().anyMatch(f->f.cabin().getY()==check.middleY()&&f.restricted()),"SEELE middle must retain highest-card admission");
            require(owner.floors().get(owner.floors().size()-1).restricted(),"Original commander-office top must remain restricted");
        }
        boolean ready=root.get("ready").getAsBoolean();
        MainLifts mainLifts=null;
        if(root.has("main_lifts"))
        {
            var roles=root.getAsJsonObject("main_lifts");
            require(roles.keySet().equals(Set.of("command_rear","east_gallery")),"Declare only the two original headquarters main-lift roles");
            MainLift rear=mainLift(roles.getAsJsonObject("command_rear"),S20PhysicalElevatorDirector.COMMAND_REAR_LIFT_ID,lifts,12,253,9,253,true);
            MainLift east=mainLift(roles.getAsJsonObject("east_gallery"),FacilityLiftsR25.EAST,lifts,66,302,63,302,false);
            var rearHangar=lift(lifts,rear.liftId()).floor(rear.hangarFloor());
            var eastHangar=lift(lifts,east.liftId()).floor(east.hangarFloor());
            require(rearHangar.approachY()==eastHangar.approachY(),"Both original main lifts must meet the same actual hangar personnel floor");
            require(Objects.equals(rear.launchFloor(),east.launchFloor()),"Both original main lifts must serve the same launch personnel floor");
            if(rear.launchFloor()!=null)
            {
                var rearLaunch=lift(lifts,rear.liftId()).floor(rear.launchFloor());
                var eastLaunch=lift(lifts,east.liftId()).floor(east.launchFloor());
                require(rearLaunch.approachY()==eastLaunch.approachY(),"Both launch landings must meet the same actual personnel floor");
            }
            mainLifts=new MainLifts(rear,east);
        }
        if(ready)
        {
            require(mainLifts!=null,"Ready requires explicit original main/east lift roles, both hangar landings and main-lift Terminal access");
            require(ids.contains(S20PhysicalElevatorDirector.COMMANDER_OFFICE_LIFT_ID)&&office!=null,
                    "Ready must retain the original office lift and its highest-card controls");
        }
        for(var binding:lifts)for(var floor:binding.floors())for(var call:floor.calls())if(call.kind()==CallKind.SEELE_READER)
            require(office!=null&&office.liftId().equals(binding.id())&&office.readers().contains(call.position()),"Highest-card reader must belong to this actual office lift");
        return new Document(epoch,fingerprint,ready,List.copyOf(lifts),office,mainLifts);
    }
    private static Binding lift(List<Binding> lifts,String id)
    {return lifts.stream().filter(lift->lift.id().equals(id)).findFirst().orElseThrow(()->new IllegalArgumentException("Declared main lift identity is missing: "+id));}
    private static MainLift mainLift(JsonObject role,String id,List<Binding> lifts,int cabinX,int cabinZ,int controllerX,int controllerZ,boolean terminalRequired)
    {
        require(role!=null&&id.equals(role.get("lift_id").getAsString()),"Main-lift role must retain its original identity");
        Binding binding=lift(lifts,id);
        var source=role.getAsJsonObject("source_axis");
        require(source!=null&&horizontal(source.getAsJsonArray("cabin")).equals(new BlockPos(cabinX,0,cabinZ))
                &&horizontal(source.getAsJsonArray("controller")).equals(new BlockPos(controllerX,0,controllerZ)),
                "Main-lift source axis must match its measured original identity");
        var translation=horizontal(role.getAsJsonArray("shaft_translation"));
        require(Math.abs((long)translation.getX())<=4096&&Math.abs((long)translation.getZ())<=4096,"Bounded explicit whole-shaft translation required");
        if(role.has("transfer_y"))
        {
            int cut=role.get("transfer_y").getAsInt();
            var upper=role.getAsJsonObject("upper_axis");var lower=role.getAsJsonObject("lower_axis");
            for(var floor:binding.floors())
            {
                var axis=floor.cabin().getY()>cut?upper:lower;
                var cabin=horizontal(axis.getAsJsonArray("cabin"));var controller=horizontal(axis.getAsJsonArray("controller"));
                require(floor.cabin().getX()==cabin.getX()&&floor.cabin().getZ()==cabin.getZ()
                        &&floor.controller().getX()==controller.getX()&&floor.controller().getZ()==controller.getZ(),
                        "Each actual stop must match its declared retained or deep shaft axis");
            }
        }
        else for(var floor:binding.floors())require(floor.cabin().getX()==cabinX+translation.getX()&&floor.cabin().getZ()==cabinZ+translation.getZ()
                &&floor.controller().getX()==controllerX+translation.getX()&&floor.controller().getZ()==controllerZ+translation.getZ(),
                "Every original main-lift floor must use the same declared rigid shaft translation");
        int hangar=role.get("hangar_floor").getAsBigDecimal().intValueExact();
        Integer terminal=role.has("terminal_floor")?role.get("terminal_floor").getAsBigDecimal().intValueExact():null;
        Integer observation=role.has("observation_floor")?role.get("observation_floor").getAsBigDecimal().intValueExact():null;
        Integer launch=role.has("launch_floor")?role.get("launch_floor").getAsBigDecimal().intValueExact():null;
        Set<Integer> assigned=new HashSet<>();assigned.add(hangar);
        if(observation!=null)
        {
            require(observation>hangar&&assigned.add(observation),"Observation must be a separate floor above the boarding landing");
            require(!binding.floor(observation).restricted(),"Observation cannot inherit Terminal-only admission");
        }
        if(launch!=null)
        {
            require(launch<hangar&&assigned.add(launch),"Launch personnel access must be a separate floor below boarding");
            require(!binding.floor(launch).restricted(),"Launch personnel access cannot inherit Terminal-only admission");
        }
        List<Integer> headquarters=new ArrayList<>();
        for(var floor:role.getAsJsonArray("headquarters_floors"))
        {
            int y=floor.getAsBigDecimal().intValueExact();
            require(y>hangar&&assigned.add(y),"Headquarters floors must be distinct and above the hangar");
            headquarters.add(y);
        }
        require(!headquarters.isEmpty(),"Each original main lift must retain its headquarters landings");
        require(!terminalRequired||terminal!=null,"Original command lift must continue to Terminal Dogma");
        if(terminal!=null)
        {
            require(terminal<hangar&&(launch==null||terminal<launch)&&assigned.add(terminal),"Terminal Dogma must be a separate lower floor");
            require(binding.floor(terminal).restricted(),"Terminal Dogma landing must retain access control");
        }
        require(!binding.floor(hangar).restricted(),"Shared hangar landing cannot inherit Terminal-only admission");
        require(assigned.equals(binding.floors().stream().map(f->f.cabin().getY()).collect(java.util.stream.Collectors.toSet())),
                "Every actual main-lift floor must have an explicit headquarters, boarding, observation, launch or Terminal role");
        return new MainLift(id,List.copyOf(headquarters),hangar,terminal,observation,launch);
    }
    private static BlockPos horizontal(JsonArray values)
    {
        require(values!=null&&values.size()==2,"Explicit X/Z pair required");
        return new BlockPos(values.get(0).getAsBigDecimal().intValueExact(),0,values.get(1).getAsBigDecimal().intValueExact());
    }
    private static Map<BlockPos,String> cells(JsonArray rows)
    {
        Map<BlockPos,String> result=new LinkedHashMap<>();for(var value:rows){var row=value.getAsJsonObject();BlockPos p=point(row.getAsJsonArray("pos"));String state=row.get("closed_state").getAsString();require(!state.isBlank()&&result.putIfAbsent(p,state)==null,"Duplicate/empty door cell");}return Map.copyOf(result);
    }
    private static RoomControls room(JsonObject raw)
    {
        List<Door> gate=doors(raw.getAsJsonArray("gate")),pilot=doors(raw.getAsJsonArray("pilot_guard_doors"));
        require(gate.size()==2&&pilot.size()==3,"Original two SEELE leaves and three pilot guards required");
        require(pilot.stream().allMatch(d->d.approachFeet().size()==2),"Two explicit pilot doorway feet required");
        List<Reader> readers=new ArrayList<>();for(var value:raw.getAsJsonArray("gate_readers"))
        {var r=value.getAsJsonObject();Direction.Axis axis=Direction.Axis.valueOf(r.get("side_axis").getAsString().toUpperCase(Locale.ROOT));double boundary=r.get("side_boundary").getAsDouble();require(axis!=Direction.Axis.Y&&Double.isFinite(boundary),"Explicit card-reader side required");readers.add(new Reader(point(r.getAsJsonArray("position")),direction(r,"facing"),point(r.getAsJsonArray("backing")),axis,boundary,r.get("less_than").getAsBoolean()));}
        require(readers.size()==2,"Original two-sided highest-card readers required");return new RoomControls(gate,List.copyOf(readers),pilot);
    }
    private static List<Door> doors(JsonArray rows)
    {List<Door> result=new ArrayList<>();for(var value:rows){var d=value.getAsJsonObject();List<net.minecraft.world.phys.Vec3> feet=new ArrayList<>();if(d.has("approach_feet"))for(var row:d.getAsJsonArray("approach_feet")){var a=row.getAsJsonArray();require(a.size()==3,"Explicit feet vector required");var p=new net.minecraft.world.phys.Vec3(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble());require(Double.isFinite(p.lengthSqr()),"Finite feet required");feet.add(p);}result.add(new Door(point(d.getAsJsonArray("lower")),direction(d,"facing"),DoorHingeSide.valueOf(d.get("hinge").getAsString().toUpperCase(Locale.ROOT)),List.copyOf(feet)));}return List.copyOf(result);}
    private static List<AABB> boxes(JsonArray rows){List<AABB> boxes=new ArrayList<>();for(var row:rows)boxes.add(box(row.getAsJsonArray()));require(!boxes.isEmpty(),"Explicit office bounds required");return List.copyOf(boxes);}
    private static AABB box(JsonArray a){require(a.size()==6,"Six explicit box bounds required");double[] v=new double[6];for(int i=0;i<6;i++){v[i]=a.get(i).getAsDouble();require(Double.isFinite(v[i]),"Finite bounds required");}require(v[0]<=v[3]&&v[1]<=v[4]&&v[2]<=v[5],"Ordered bounds required");return new AABB(v[0],v[1],v[2],v[3],v[4],v[5]);}
    private static BlockPos point(JsonArray a){require(a.size()==3,"Three explicit block coordinates required");int[] v=new int[3];for(int i=0;i<3;i++){double d=a.get(i).getAsDouble();require(Double.isFinite(d)&&d==Math.rint(d)&&d>=Integer.MIN_VALUE&&d<=Integer.MAX_VALUE,"Integer block coordinates required");v[i]=(int)d;}return new BlockPos(v[0],v[1],v[2]);}
    private static Direction direction(JsonObject o,String key){Direction d=Direction.byName(o.get(key).getAsString());require(d!=null&&d.getAxis()!=Direction.Axis.Y,"Explicit horizontal direction required: "+key);return d;}
    private static void require(boolean value,String reason){if(!value)throw new IllegalArgumentException(reason);}
}
