package com.projectseele.network;

import com.projectseele.world.NervLaunchFeedbackR53.Contact;
import io.netty.buffer.Unpooled;
import java.util.ArrayList;
import java.util.List;
import net.minecraft.network.FriendlyByteBuf;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.phys.Vec3;

public final class ClientboundLaunchFeedbackR54Test
{
    public static void main(String[] args)
    {
        var contacts=new ArrayList<Contact>();
        for(int i=0;i<6;i++)contacts.add(new Contact(new Vec3(i<3?-15:15,-503.42,i*2-14.78),new Vec3(0,1,0)));
        var packet=new ClientboundLaunchFeedbackR54(new ResourceLocation("projectseele","geofront"),737,123456,true,210,contacts);
        var buffer=new FriendlyByteBuf(Unpooled.buffer());packet.encode(buffer);
        var decoded=new ClientboundLaunchFeedbackR54(buffer);
        if(!packet.equals(decoded)||buffer.readableBytes()!=0)throw new AssertionError("Remote committed contact packet did not round trip");
        if(buffer.writerIndex()>300)throw new AssertionError("Six-contact feedback packet exceeds bounded payload");
        buffer.release();
        for(int size:new int[]{0,17})
        {
            boolean rejected=false;
            try{new ClientboundLaunchFeedbackR54(packet.dimension(),1,1,false,1,java.util.Collections.nCopies(size,contacts.get(0)));}
            catch(IllegalArgumentException expected){rejected=true;}
            if(!rejected)throw new AssertionError("Unbounded contact payload accepted");
        }
        var invalid=new FriendlyByteBuf(Unpooled.buffer());invalid.writeResourceLocation(packet.dimension());invalid.writeVarInt(737);invalid.writeLong(1);invalid.writeBoolean(false);invalid.writeFloat(1);invalid.writeVarInt(17);
        boolean rejected=false;try{new ClientboundLaunchFeedbackR54(invalid);}catch(IllegalArgumentException expected){rejected=true;}finally{invalid.release();}
        if(!rejected)throw new AssertionError("Decoder did not bound allocation before reading contacts");
        System.out.println("PASS remote launch packet: exact six guide contacts, dimension/tick/source identity, bounded encode/decode");
    }
}
