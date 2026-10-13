package com.projectseele.world;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.projectseele.network.ClientboundFacilityFrameR52;
import io.netty.buffer.Unpooled;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.HexFormat;
import net.minecraft.core.BlockPos;
import net.minecraft.network.FriendlyByteBuf;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;

/** Tests the production parser and packet using the actual complete inherited
 * door receipt after translation. No substitute world or movement pass. */
public final class NervHeadquartersFrameR52Test
{
    private static int checks;
    private static void check(boolean value,String why) { checks++; if(!value)throw new AssertionError(why); }
    private static void rejects(Runnable call,String why)
    {boolean failed=false;try{call.run();}catch(RuntimeException expected){failed=true;}check(failed,why);}
    public static void main(String[] args) throws Exception
    {
        Path root=Path.of(args[0]);
        JsonObject declaration=JsonParser.parseString(Files.readString(root.resolve("r52/headquarters.json"))).getAsJsonObject();
        long epoch=declaration.get("epoch").getAsLong();String fingerprint=declaration.get("directory_fingerprint").getAsString();
        var frame=NervHeadquartersFrameR52.parse(declaration,epoch,fingerprint);
        check(frame.translation().equals(new BlockPos(0,-93,0)),"Root headquarters translation was changed");
        byte[] bytes=Files.readAllBytes(root.resolve(frame.commandDoorManifest()));
        check(HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes)).equals(frame.commandDoorSha256()),"Actual full door artifact differs from Root SHA");
        JsonObject doors=JsonParser.parseString(new String(bytes,java.nio.charset.StandardCharsets.UTF_8)).getAsJsonObject();
        check(CommandRoomSlidingDoorDirector.validateDeclaredDoorDocument(doors,frame)==39,"Production parser did not bind all 39 original fixed inputs");
        check(frame.apply(new BlockPos(32,-407,286)).equals(new BlockPos(32,-500,286)),"Physical launch key lost its moved address");
        check(frame.inverse(new BlockPos(32,-500,286)).equals(new BlockPos(32,-407,286)),"Moved press did not resolve the original authored action");
        check(!frame.inverse(new BlockPos(32,-407,286)).equals(new BlockPos(32,-407,286)),"Old-address press was re-enabled");
        Vec3 screen=frame.apply(new Vec3(28,-415.795,322.793));
        check(Math.abs(screen.y+508.795)<1e-9&&screen.x==28&&screen.z==322.793,"Screen was transformed more than once or lost its source plane");
        AABB viewer=frame.apply(new AABB(-42,-479,246,103,-353,407));
        check(viewer.contains(28,-509,300)&&!viewer.contains(28,-360,300),"Feed demand still uses the retired viewer room");
        var packet=new ClientboundFacilityFrameR52(new ResourceLocation("projectseele:geofront"),true,epoch,true,frame.translation());
        var buffer=new FriendlyByteBuf(Unpooled.buffer());packet.encode(buffer);
        check(new ClientboundFacilityFrameR52(buffer).equals(packet)&&buffer.readableBytes()==0,"Native frame packet lost exact new coordinates");buffer.release();
        rejects(()->NervHeadquartersFrameR52.parse(declaration,epoch+1,fingerprint),"Foreign claim epoch accepted");
        rejects(()->NervHeadquartersFrameR52.parse(declaration,epoch,"f".repeat(64)),"Foreign directory accepted");
        var component=declaration.deepCopy();component.addProperty("component","terminal");
        rejects(()->NervHeadquartersFrameR52.parse(component,epoch,fingerprint),"Terminal component admitted as headquarters");
        var wrong=declaration.deepCopy();wrong.add("translation",JsonParser.parseString("[0,-280,-7]"));var terminal=wrong;
        rejects(()->NervHeadquartersFrameR52.parse(terminal,epoch,fingerprint),"Terminal translation mixed into headquarters");
        wrong=declaration.deepCopy();wrong.add("translation",JsonParser.parseString("[0,0,0]"));var zero=wrong;
        rejects(()->NervHeadquartersFrameR52.parse(zero,epoch,fingerprint),"Retired coordinates admitted");
        wrong=declaration.deepCopy();wrong.addProperty("command_door_manifest","r52/../other_world.json");var escape=wrong;
        rejects(()->NervHeadquartersFrameR52.parse(escape,epoch,fingerprint),"Door declaration escaped the Root directory");
        var partial=doors.deepCopy();partial.getAsJsonArray("doors").remove(0);
        rejects(()->CommandRoomSlidingDoorDirector.validateDeclaredDoorDocument(partial,frame),"Partial door owner set accepted");
        var unbound=doors.deepCopy();unbound.getAsJsonArray("doors").get(0).getAsJsonObject().remove("fixedInputContractsR45");
        rejects(()->CommandRoomSlidingDoorDirector.validateDeclaredDoorDocument(unbound,frame),"Door without complete physical-input contract accepted");
        var misplaced=doors.deepCopy();misplaced.getAsJsonArray("doors").get(0).getAsJsonObject().add("lower",JsonParser.parseString("[8,-429,282]"));
        rejects(()->CommandRoomSlidingDoorDirector.validateDeclaredDoorDocument(misplaced,frame),"Retired door plane admitted");
        var foreign=doors.deepCopy();foreign.addProperty("directory_fingerprint","f".repeat(64));
        rejects(()->CommandRoomSlidingDoorDirector.validateDeclaredDoorDocument(foreign,frame),"Door artifact from another claim accepted");
        System.out.println("R52 headquarters production frame/door-parser/packet PASS checks="+checks+"; metadata and native packet only, no live world acceptance");
    }
    private NervHeadquartersFrameR52Test() {}
}
