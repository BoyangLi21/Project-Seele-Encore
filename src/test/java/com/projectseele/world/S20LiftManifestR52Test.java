package com.projectseele.world;

import com.google.gson.*;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import java.nio.file.*;
import java.lang.reflect.Method;

/** Root-supplied shared planes and parser semantics; no level, groups, installation or writes. */
public final class S20LiftManifestR52Test
{
    private static void rejected(JsonObject json,String label)
    {boolean rejected=false;try{S20LiftManifestR52.parse(json);}catch(RuntimeException expected){rejected=true;}if(!rejected)throw new AssertionError(label);}
    public static void main(String[] args)throws Exception
    {
        JsonObject candidate=JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject();
        var document=S20LiftManifestR52.parse(candidate);if(document.ready())throw new AssertionError("Candidate unexpectedly ready");
        var lift=document.lifts().get(0);var spec=lift.spec();
        if(lift.floors().size()!=5||lift.controllerSide()!=Direction.SOUTH||lift.controllerFacing()!=Direction.NORTH)throw new AssertionError("Root shared binding lost");
        for(var floor:spec.stops())
        {
            int y=floor.walkY();
            if(!S20MovingElevatorsAdapter.controllerPosition(spec,floor).equals(new BlockPos(108,y,410)))throw new AssertionError("Shared controller guessed from NORTH clockwise");
            if(!floor.r52().callButton().equals(new BlockPos(111,y+1,403)))throw new AssertionError("Root fixed call position changed");
            if(java.util.stream.Stream.concat(floor.r52().landingDoors().keySet().stream(),floor.r52().cabinDoors().keySet().stream()).anyMatch(p->p.getX()==108&&p.getZ()==401))throw new AssertionError("Root door plane reached preserved HQ escalator");
            if(floor.r52().restricted()!=(y==-766))throw new AssertionError("Lilith/public stop permissions changed");
        }
        var invalid=candidate.deepCopy();invalid.getAsJsonArray("lifts").get(0).getAsJsonObject().addProperty("controller_side","east");rejected(invalid,"Default EAST accepted for actual SOUTH controllers");
        invalid=candidate.deepCopy();invalid.getAsJsonArray("lifts").add(invalid.getAsJsonArray("lifts").get(0).deepCopy());rejected(invalid,"Duplicate lift/shaft accepted");
        invalid=candidate.deepCopy();invalid.getAsJsonArray("lifts").get(0).getAsJsonObject().getAsJsonArray("floors").get(0).getAsJsonObject().addProperty("exit","up");rejected(invalid,"Vertical landing exit accepted");
        var two=candidate.deepCopy();var floors=two.getAsJsonArray("lifts").get(0).getAsJsonObject().getAsJsonArray("floors");while(floors.size()>2)floors.remove(1);
        if(S20LiftManifestR52.parse(two).lifts().get(0).floors().size()!=2)throw new AssertionError("Parser forced obsolete four-stop compact lift");
        var vanilla=candidate.deepCopy();
        for(var row:vanilla.getAsJsonArray("lifts").get(0).getAsJsonObject().getAsJsonArray("floors"))
        {var call=row.getAsJsonObject().getAsJsonArray("calls").get(0).getAsJsonObject();call.addProperty("kind","vanilla_button");call.addProperty("state","minecraft:polished_blackstone_button[face=wall,facing=north,powered=false]");call.remove("display");}
        var originalCalls=S20LiftManifestR52.parse(vanilla).lifts().get(0).floors();
        if(originalCalls.stream().anyMatch(f->f.calls().get(0).kind()!=S20LiftManifestR52.CallKind.VANILLA_BUTTON||f.callDisplay()!=null))throw new AssertionError("Original vanilla calls required invented native displays");
        invalid=vanilla.deepCopy();invalid.getAsJsonArray("lifts").get(0).getAsJsonObject().getAsJsonArray("floors").get(1).getAsJsonObject().getAsJsonArray("calls").get(0).getAsJsonObject().add("target_controller",candidate.getAsJsonArray("lifts").get(0).getAsJsonObject().getAsJsonArray("floors").get(0).getAsJsonObject().getAsJsonArray("controller").deepCopy());rejected(invalid,"Call allowed a different native floor controller");
        invalid=candidate.deepCopy();invalid.getAsJsonArray("lifts").get(0).getAsJsonObject().addProperty("id","regional_gateway");rejected(invalid,"Independent gateway duplicated in S20 list");
        invalid=candidate.deepCopy();invalid.addProperty("ready",true);rejected(invalid,"Partial candidate became complete ready S20 replacement");
        invalid=vanilla.deepCopy();invalid.getAsJsonArray("lifts").get(0).getAsJsonObject().getAsJsonArray("floors").get(0).getAsJsonObject().getAsJsonArray("calls").get(0).getAsJsonObject().addProperty("kind","seele_reader");rejected(invalid,"Unowned reader granted office authority");
        if(!S20LiftDirectoryR52.independentGateway(true,-368,750,Direction.EAST)
                ||S20LiftDirectoryR52.independentGateway(false,-368,750,Direction.EAST)
                ||S20LiftDirectoryR52.independentGateway(true,-367,750,Direction.EAST)
                ||S20LiftDirectoryR52.independentGateway(true,-368,750,Direction.WEST))throw new AssertionError("Independent native gateway confused with pending S20 claim");
        var legacy=new S20PhysicalElevatorDirector.LiftSpec("legacy-test",new S20PhysicalElevatorDirector.Landing("lower",new BlockPos(0,0,0),Direction.NORTH),new S20PhysicalElevatorDirector.Landing("upper",new BlockPos(0,10,0),Direction.NORTH));
        Method side=S20MovingElevatorsAdapter.class.getDeclaredMethod("controllerSide",S20PhysicalElevatorDirector.LiftSpec.class);side.setAccessible(true);
        if(legacy.r52()!=null||side.invoke(null,legacy)!=Direction.EAST)throw new AssertionError("Legacy default controller rule changed");
        System.out.println("PASS: Root shared5 stops/SOUTH controllers/NORTH calls and explicit doors; exact native ownership; original vanilla calls need no display; wrong floor/unowned reader/independent gateway/partial ready rejected; HQ escalator untouched; Lilith-only restricted; arbitrary2 stops and legacy default retained; parsing alone did not install");
    }
}
