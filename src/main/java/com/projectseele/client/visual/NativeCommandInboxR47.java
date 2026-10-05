package com.projectseele.client.visual;

import com.google.gson.Gson;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.List;
import net.minecraft.client.Minecraft;
import net.minecraft.client.Screenshot;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Explicit local CLI inbox: ordinary network commands and genuine Minecraft frames only. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID,value=Dist.CLIENT)
public final class NativeCommandInboxR47
{
    private static final String DECLARED=System.getProperty("projectseele.r47NativeCommandInbox","");
    private static final List<Frame> FRAMES=new ArrayList<>();
    private static long ticks,lastSeq=Long.MIN_VALUE,waitingSeq=Long.MIN_VALUE,quitSeq;
    private static boolean quit;
    private static String lastReadError="";
    private record Frame(long seq,Path file,long due) {}
    private NativeCommandInboxR47() {}

    @SubscribeEvent public static void tick(TickEvent.ClientTickEvent event)
    {
        if(DECLARED.isBlank()||event.phase!=TickEvent.Phase.END)return;
        Minecraft mc=Minecraft.getInstance();ticks++;
        Path inbox;
        try{inbox=Path.of(DECLARED).toAbsolutePath().normalize();}
        catch(Exception failure){return;}
        for(var it=FRAMES.iterator();it.hasNext();)
        {
            Frame frame=it.next();if(ticks<frame.due)continue;it.remove();
            JsonObject ack=ack(frame.seq,"screenshot_saved");ack.addProperty("file",frame.file.toString());
            try(var image=Screenshot.takeScreenshot(mc.getMainRenderTarget()))
            {
                Files.createDirectories(frame.file.getParent());image.writeToFile(frame.file);
                ack.addProperty("width",image.getWidth());ack.addProperty("height",image.getHeight());
            }
            catch(Exception failure){ack.addProperty("event","screenshot_failed");ack.addProperty("error",failure.toString());}
            append(inbox,ack);
        }
        if(quit&&FRAMES.isEmpty())
        {append(inbox,ack(quitSeq,"quit_submitted"));mc.stop();return;}
        if(ticks%5!=0||!Files.isRegularFile(inbox))return;
        try
        {
            JsonObject input=JsonParser.parseString(Files.readString(inbox)).getAsJsonObject();
            require(input.has("seq")&&input.get("seq").isJsonPrimitive()&&input.getAsJsonPrimitive("seq").isNumber(),"Integer seq required");
            long seq=input.get("seq").getAsBigDecimal().longValueExact();if(seq<=lastSeq)return;
            List<String> commands=new ArrayList<>();Path screenshot=null;boolean requestedQuit=false;
            try
            {
                if(input.has("commands"))
                {
                    require(input.get("commands").isJsonArray(),"commands must be an array");
                    JsonArray values=input.getAsJsonArray("commands");require(values.size()<=8,"At most8 ordinary commands per seq");
                    for(var value:values)
                    {
                        require(value.isJsonPrimitive()&&value.getAsJsonPrimitive().isString(),"Command must be a string");
                        String command=value.getAsString();require(command.length()<256&&!command.isBlank()&&command.indexOf('\n')<0&&command.indexOf('\r')<0&&command.indexOf('\0')<0,"Command must be nonempty, single-line and shorter than256 characters");
                        if(command.startsWith("/"))command=command.substring(1);require(!command.isBlank(),"Empty network command");commands.add(command);
                    }
                }
                if(input.has("screenshot"))
                {
                    require(input.get("screenshot").isJsonPrimitive()&&input.getAsJsonPrimitive("screenshot").isString(),"screenshot must be an absolute PNG file string");
                    screenshot=Path.of(input.get("screenshot").getAsString());
                    require(screenshot.isAbsolute()&&screenshot.getFileName().toString().toLowerCase(java.util.Locale.ROOT).endsWith(".png"),"Absolute PNG screenshot file required");screenshot=screenshot.normalize();
                }
                if(input.has("quit"))
                {require(input.get("quit").isJsonPrimitive()&&input.getAsJsonPrimitive("quit").isBoolean(),"quit must be an explicit Boolean");requestedQuit=input.get("quit").getAsBoolean();}
            }
            catch(Exception invalid)
            {lastSeq=seq;JsonObject ack=ack(seq,"rejected");ack.addProperty("error",invalid.toString());append(inbox,ack);return;}
            if(!commands.isEmpty()&&(mc.player==null||mc.player.connection==null))
            {if(waitingSeq!=seq){waitingSeq=seq;append(inbox,ack(seq,"waiting_for_player_connection"));}return;}
            lastSeq=seq;lastReadError="";JsonArray sent=new JsonArray();
            for(String command:commands){mc.player.connection.sendCommand(command);sent.add(command);}
            JsonObject ack=ack(seq,"submitted");ack.add("commands",sent);
            if(screenshot!=null){FRAMES.add(new Frame(seq,screenshot,ticks+20));ack.addProperty("screenshot_due_client_tick",ticks+20);ack.addProperty("screenshot",screenshot.toString());}
            ack.addProperty("quit_requested",requestedQuit);append(inbox,ack);
            if(requestedQuit){quit=true;quitSeq=seq;}
        }
        catch(Exception failure)
        {
            String error=failure.toString();if(!lastReadError.equals(error))
            {lastReadError=error;JsonObject ack=ack(-1,"read_failed");ack.addProperty("error",error);append(inbox,ack);}
        }
    }
    private static JsonObject ack(long seq,String event)
    {
        JsonObject ack=new JsonObject();ack.addProperty("seq",seq);ack.addProperty("event",event);ack.addProperty("client_tick",ticks);
        ack.addProperty("function_pass_claimed",false);ack.addProperty("command_authority","ordinary_server_network_permissions");return ack;
    }
    private static void append(Path inbox,JsonObject ack)
    {
        try
        {
            Path file=inbox.resolveSibling(inbox.getFileName()+".ack.jsonl");Files.createDirectories(file.getParent());
            Files.writeString(file,new Gson().toJson(ack)+"\n",StandardOpenOption.CREATE,StandardOpenOption.APPEND);
        }
        catch(Exception failure){ProjectSeele.LOGGER.error("R47 opt-in native inbox acknowledgment write failed",failure);}
    }
    private static void require(boolean value,String message){if(!value)throw new IllegalArgumentException(message);}
}
