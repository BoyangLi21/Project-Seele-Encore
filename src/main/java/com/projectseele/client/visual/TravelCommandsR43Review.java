package com.projectseele.client.visual;

import com.google.gson.*;
import com.projectseele.ProjectSeele;
import com.projectseele.visual.SeeleTravelCommandsR43;
import com.projectseele.world.FacilitySchemaV2;
import net.minecraft.client.Minecraft;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.level.GameType;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.*;
import java.util.*;

/** Actual player command dispatch with the production command tree, in a disposable copy. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID,value=Dist.CLIENT)
public final class TravelCommandsR43Review
{
    private static final boolean ENABLED=Boolean.getBoolean("projectseele.travelReview");
    private static volatile boolean done;
    private static int age,index,settle;
    private static Vec3 arrival;
    private static final JsonArray CASES=new JsonArray();
    private static final JsonObject RESULT=new JsonObject();
    @SubscribeEvent public static void client(TickEvent.ClientTickEvent e)
    {
        if(!ENABLED||e.phase!=TickEvent.Phase.END)return;
        var mc=Minecraft.getInstance();mc.options.pauseOnLostFocus=false;
        if(done)mc.stop();
    }
    @SubscribeEvent public static void server(TickEvent.ServerTickEvent e)
    {
        if(!ENABLED||done||e.phase!=TickEvent.Phase.END)return;
        var server=e.getServer();Path world=server.getWorldPath(LevelResource.ROOT).normalize();
        if(!world.getFileName().toString().equals("SEELE_R43_TRAVEL_REVIEW"))throw new IllegalStateException("Travel review refuses owner world");
        if(server.getPlayerList().getPlayers().isEmpty())return;
        ServerPlayer player=server.getPlayerList().getPlayers().get(0);
        try
        {
            if(++age>2200)throw new IllegalStateException("Travel review deadline");
            if(age<100)return;
            if(age==100)
            {
                var root=server.getCommands().getDispatcher().getRoot().getChild("seele");
                for(String retired:List.of("geofront","facility_v2","visual","motionlab","silo","firstbattle","siege"))
                    require(root.getChild(retired)==null,"Retired command exposed: "+retired);
                for(String active:List.of("enter","tp","eva","military","tv","tokyo3","armament"))require(root.getChild(active)!=null,"Live command missing: "+active);
                RESULT.add("root_commands",new Gson().toJsonTree(root.getChildren().stream().map(n->n.getName()).sorted().toList()));
                player.stopRiding();player.setGameMode(GameType.CREATIVE);player.getAbilities().flying=false;player.onUpdateAbilities();
                player.teleportTo(server.overworld(),.5,120,.5,0,0);
            }
            if(settle>0)
            {
                if(--settle>0)return;
                require(player.level().dimension().equals(FacilitySchemaV2.DIMENSION),"Wrong dimension after command");
                require(player.position().distanceTo(arrival)<.3,"Unstable landing: "+player.position()+" vs "+arrival);
                require(player.onGround(),"Arrival did not settle on a floor");
                CASES.get(CASES.size()-1).getAsJsonObject().addProperty("settled",true);index++;
            }
            int total=SeeleTravelCommandsR43.DESTINATIONS.size()+2;
            if(index>=total)
            {
                RESULT.addProperty("passed",true);RESULT.add("cases",CASES);write(world);done=true;return;
            }
            String command;Vec3 expected=null;
            if(index==0){command="seele enter";expected=SeeleTravelCommandsR43.DESTINATIONS.get(0).point();}
            else if(index==1)command="seele tp hanger";
            else{var destination=SeeleTravelCommandsR43.DESTINATIONS.get(index-2);command="seele tp "+destination.key();expected=destination.point();}
            int result=server.getCommands().getDispatcher().execute(command,player.createCommandSourceStack().withPermission(4));
            require(result>0,"Command rejected: "+command);
            require(player.level().dimension().equals(FacilitySchemaV2.DIMENSION),"Command did not enter SEELE world: "+command);
            if(expected!=null)require(player.position().distanceTo(expected)<.001,"Wrong fixed arrival: "+command);
            arrival=player.position();JsonObject row=new JsonObject();row.addProperty("command",command);row.addProperty("position",arrival.toString());row.addProperty("success",true);CASES.add(row);settle=30;
            ProjectSeele.LOGGER.info("R43 TRAVEL command={} position={}",command,arrival);
        }
        catch(Exception failure)
        {
            RESULT.addProperty("passed",false);RESULT.addProperty("error",failure.toString());RESULT.add("cases",CASES);write(world);ProjectSeele.LOGGER.error("R43 travel review failed",failure);done=true;
        }
    }
    private static void require(boolean condition,String message){if(!condition)throw new IllegalStateException(message);}
    private static void write(Path world)
    {
        try{Files.writeString(world.resolve("r43_travel_review.json"),new GsonBuilder().setPrettyPrinting().create().toJson(RESULT));}
        catch(Exception failure){throw new IllegalStateException(failure);}
    }
    private TravelCommandsR43Review() {}
}
