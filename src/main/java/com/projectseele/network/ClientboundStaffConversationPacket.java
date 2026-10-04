package com.projectseele.network;

import java.util.*;
import java.util.function.Supplier;
import net.minecraft.network.FriendlyByteBuf;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.fml.DistExecutor;
import net.minecraftforge.network.NetworkEvent;

/** Small authoritative dialogue snapshot; no client-side command execution. */
public record ClientboundStaffConversationPacket(UUID session, UUID person, int entityId,
        String name, String role, String skin, boolean open, boolean valid,
        boolean canCommand, boolean radio, String reply, String order, List<String> units,
        long coordinationFormationRevision,long coordinationEvidenceRevision,List<String> participants)
{
    public ClientboundStaffConversationPacket(UUID session,UUID person,int entityId,String name,String role,String skin,
            boolean open,boolean valid,boolean canCommand,boolean radio,String reply,String order,List<String> units)
    {this(session,person,entityId,name,role,skin,open,valid,canCommand,radio,reply,order,units,0,0,List.of());}
    public ClientboundStaffConversationPacket(FriendlyByteBuf buffer)
    {
        this(buffer.readUUID(), buffer.readUUID(), buffer.readVarInt(),
                buffer.readUtf(80), buffer.readUtf(40), buffer.readUtf(40),
                buffer.readBoolean(), buffer.readBoolean(), buffer.readBoolean(), buffer.readBoolean(),
                buffer.readUtf(1400), buffer.readUtf(180), readUnits(buffer),buffer.readLong(),buffer.readLong(),readParticipants(buffer));
    }

    private static List<String> readUnits(FriendlyByteBuf buffer)
    {
        int count = buffer.readVarInt();
        if (count < 0 || count > 3) throw new IllegalArgumentException("Staff snapshot unit count");
        List<String> rows = new ArrayList<>();
        for (int i = 0; i < count; i++) rows.add(buffer.readUtf(120));
        return List.copyOf(rows);
    }

    private static List<String> readParticipants(FriendlyByteBuf buffer)
    {
        int count=buffer.readVarInt();if(count<0||count>5)throw new IllegalArgumentException("Participant budget");
        List<String> rows=new ArrayList<>();for(int i=0;i<count;i++)rows.add(buffer.readUtf(80));return List.copyOf(rows);
    }
    public void encode(FriendlyByteBuf buffer)
    {
        buffer.writeUUID(session); buffer.writeUUID(person); buffer.writeVarInt(entityId);
        buffer.writeUtf(name, 80); buffer.writeUtf(role, 40); buffer.writeUtf(skin, 40);
        buffer.writeBoolean(open); buffer.writeBoolean(valid); buffer.writeBoolean(canCommand); buffer.writeBoolean(radio);
        buffer.writeUtf(reply, 1400); buffer.writeUtf(order, 180); buffer.writeVarInt(units.size());
        for (String row : units) buffer.writeUtf(row, 120);
        buffer.writeLong(coordinationFormationRevision);buffer.writeLong(coordinationEvidenceRevision);buffer.writeVarInt(participants.size());
        for(String row:participants)buffer.writeUtf(row,80);
    }

    public void handle(Supplier<NetworkEvent.Context> supplier)
    {
        DistExecutor.unsafeRunWhenOn(Dist.CLIENT,
                () -> () -> com.projectseele.client.screen.StaffConversationScreen.receive(this));
        supplier.get().setPacketHandled(true);
    }
}
