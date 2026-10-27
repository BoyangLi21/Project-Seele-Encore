package com.projectseele.network;

import com.projectseele.world.NervLaunchFeedbackR53.Contact;
import java.util.ArrayList;
import java.util.List;
import java.util.function.Supplier;
import net.minecraft.network.FriendlyByteBuf;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.fml.DistExecutor;
import net.minecraftforge.network.NetworkEvent;

/** Actual committed guide contacts, not a client-inferred launch phase. */
public record ClientboundLaunchFeedbackR54(ResourceLocation dimension,int entity,long tick,
        boolean burst,float speed,List<Contact> contacts)
{
    public ClientboundLaunchFeedbackR54
    {
        if(!Float.isFinite(speed)||speed<0||contacts.isEmpty()||contacts.size()>16)
            throw new IllegalArgumentException("Bounded committed launch feedback required");
        contacts=List.copyOf(contacts);
    }
    public ClientboundLaunchFeedbackR54(FriendlyByteBuf buffer)
    {this(buffer.readResourceLocation(),buffer.readVarInt(),buffer.readLong(),buffer.readBoolean(),buffer.readFloat(),readContacts(buffer));}
    private static List<Contact> readContacts(FriendlyByteBuf buffer)
    {
        int size=buffer.readVarInt();if(size<1||size>16)throw new IllegalArgumentException("Launch contact count");
        var result=new ArrayList<Contact>();
        for(int i=0;i<size;i++)result.add(new Contact(new Vec3(buffer.readDouble(),buffer.readDouble(),buffer.readDouble()),
                new Vec3(buffer.readFloat(),buffer.readFloat(),buffer.readFloat())));
        return result;
    }
    public void encode(FriendlyByteBuf buffer)
    {
        buffer.writeResourceLocation(dimension);buffer.writeVarInt(entity);buffer.writeLong(tick);buffer.writeBoolean(burst);buffer.writeFloat(speed);buffer.writeVarInt(contacts.size());
        for(var contact:contacts)
        {
            buffer.writeDouble(contact.point().x);buffer.writeDouble(contact.point().y);buffer.writeDouble(contact.point().z);
            buffer.writeFloat((float)contact.tangent().x);buffer.writeFloat((float)contact.tangent().y);buffer.writeFloat((float)contact.tangent().z);
        }
    }
    public void handle(Supplier<NetworkEvent.Context> context)
    {
        DistExecutor.unsafeRunWhenOn(Dist.CLIENT,()->()->com.projectseele.client.NervLaunchFeedbackClientR54.receive(this));
        context.get().setPacketHandled(true);
    }
}
