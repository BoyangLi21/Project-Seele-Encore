package com.projectseele.visual;

import com.google.gson.*;
import com.projectseele.ProjectSeele;
import com.projectseele.registry.ModItems;
import com.projectseele.world.*;
import net.minecraft.core.*;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.*;
import net.minecraft.world.*;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.GameType;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.*;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.*;

/** Real player's block use and real client walking through the commissioned aperture. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class AccessR44Review
{
    public static final boolean ENABLED=Boolean.getBoolean("projectseele.r44AccessReview");
    public static volatile boolean walk,done;
    private static int age,stage,wait;
    private static final BlockPos READER=new BlockPos(228,82,303);
    private static final JsonArray CASES=new JsonArray();
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(!ENABLED||done||event.phase!=TickEvent.Phase.END)return;var server=event.getServer();var world=server.getWorldPath(LevelResource.ROOT).normalize();
        if(!world.getFileName().toString().equals(com.projectseele.visual.NativeReviewWorldsR45.expectedName()))throw new IllegalStateException("Access review refuses an owner world");
        if(server.getPlayerList().getPlayers().isEmpty())return;var player=server.getPlayerList().getPlayers().get(0);
        try
        {
            if(++age>800)throw new IllegalStateException("Access review deadline");
            if(age<100)return;ServerLevel level=server.getLevel(FacilitySchemaV2.DIMENSION);level.getChunkAt(READER);
            if(!(level.getBlockEntity(READER) instanceof NervAccessReaderEntityR44 reader))throw new IllegalStateException("Reader missing");
            if(wait>0){wait--;return;}
            switch(stage)
            {
                case 0->{player.stopRiding();player.setGameMode(GameType.SURVIVAL);player.teleportTo(level,226.5,81,305.5,180,0);player.setItemInHand(InteractionHand.MAIN_HAND,ItemStack.EMPTY);wait=20;stage++;}
                case 1->{require(!clear(level,player),"Door must start closed");use(player,level);wait=20;stage++;}
                case 2->{require(!reader.isOpen()&&!clear(level,player),"No-card presentation opened security door");record("no_card_denied");player.setItemInHand(InteractionHand.MAIN_HAND,new ItemStack(ModItems.NERV_EMPLOYEE_CARD.get()));use(player,level);wait=24;stage++;}
                case 3->{require(reader.isOpen()&&clear(level,player),"Valid card did not clear the actual aperture: lease="+reader.isOpen()+", reader="+reader.saveWithoutMetadata()+", gate="+level.getBlockState(new BlockPos(226,81,302))+", player="+player.position());record("card_opens_real_aperture");walk=true;stage++;}
                case 4->{if(player.getZ()>300.9)return;walk=false;require(player.getY()>80.8,"Threshold lost its floor");record("actual_client_threshold_crossing");wait=140;stage++;}
                case 5->{require(!reader.isOpen()&&!clear(level,player),"Door did not close after lease");record("automatic_close");var exit=new BlockPos(224,82,301);player.gameMode.useItemOn(player,level,player.getMainHandItem(),InteractionHand.MAIN_HAND,new BlockHitResult(Vec3.atCenterOf(exit),Direction.NORTH,exit,false));wait=24;stage++;}
                case 6->{require(reader.isOpen()&&clear(level,player),"Inside release failed");record("inside_release");player.teleportTo(level,226.5,81,302.5,180,0);wait=140;stage++;}
                case 7->{require(reader.isOpen()&&clear(level,player),"Door closed on an occupant");record("occupied_threshold_stays_open");player.teleportTo(level,226.5,81,305.5,180,0);wait=40;stage++;}
                case 8->{require(!clear(level,player),"Door failed to close after occupant left");record("clear_threshold_recloses");write(world,true,"");done=true;}
            }
        }
        catch(Exception error){walk=false;write(world,false,error.toString());done=true;ProjectSeele.LOGGER.error("R44 access review failed",error);}
    }
    private static void use(ServerPlayer player,ServerLevel level)
    {player.gameMode.useItemOn(player,level,player.getMainHandItem(),InteractionHand.MAIN_HAND,new BlockHitResult(Vec3.atCenterOf(READER),Direction.SOUTH,READER,false));}
    private static boolean clear(ServerLevel level,ServerPlayer player)
    {return level.noCollision(player,new AABB(226.2,81.01,302.2,226.8,82.8,302.8));}
    private static void require(boolean pass,String error){if(!pass)throw new IllegalStateException(error);}
    private static void record(String name){JsonObject row=new JsonObject();row.addProperty("case",name);row.addProperty("passed",true);CASES.add(row);}
    private static void write(Path world,boolean pass,String error)
    {try{JsonObject result=new JsonObject();result.addProperty("passed",pass);result.addProperty("error",error);result.add("cases",CASES);Files.writeString(world.resolve("r44_access_review.json"),new GsonBuilder().setPrettyPrinting().create().toJson(result));}catch(Exception e){throw new IllegalStateException(e);}}
    private AccessR44Review() {}
}
