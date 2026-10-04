package com.projectseele.world;

import com.google.gson.JsonParser;
import net.minecraft.core.BlockPos;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.nbt.Tag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.level.saveddata.SavedData;
import net.minecraftforge.event.entity.player.PlayerInteractEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;
import java.util.WeakHashMap;

/** Challenged physical reading; lore pages never impersonate the original P-05 evidence. */
@Mod.EventBusSubscriber(modid="projectseele")
public final class DeadSeaReadingR45
{
    public record Challenge(UUID nonce,UUID dossier,BlockPos book,String revision,int pages){}
    public interface Bridge {void open(ServerPlayer player,Challenge challenge);}
    private static Bridge bridge=(player,challenge)->{};
    public static void installBridge(Bridge actualBridge){bridge=java.util.Objects.requireNonNull(actualBridge);}
    private static final class Session
    {Challenge challenge;long expires,next;String dimension;}
    private static final Map<ServerLevel,Map<UUID,Session>> SESSIONS=new WeakHashMap<>();
    private static final class Edition
    {
        String revision;int pages;
        Edition()
        {
            try(var input=DeadSeaReadingR45.class.getResourceAsStream("/assets/projectseele/lore/dead_sea_archive_r45.json"))
            {
                if(input==null)throw new IllegalStateException("No shipped archive edition");
                byte[] bytes=input.readAllBytes();revision=hash(bytes);
                var json=JsonParser.parseString(new String(bytes,StandardCharsets.UTF_8)).getAsJsonObject();
                if(json.get("schema").getAsInt()!=45)throw new IllegalStateException("Unknown archive edition");
                pages=json.getAsJsonArray("pages").size();if(pages<1||pages>64)throw new IllegalStateException("Archive page budget");
            }
            catch(Exception error){throw new IllegalStateException("Cannot authorize missing/foreign archive edition",error);}
        }
    }
    private static Edition edition;
    private static Edition edition(){if(edition==null)edition=new Edition();return edition;}
    public static String currentRevision(){return edition().revision;}
    public static boolean knownDocument(String id)
    {
        if(id==null||!id.matches("r45/archive/[0-9]{1,2}"))return false;
        int page=Integer.parseInt(id.substring(id.lastIndexOf('/')+1));return page<edition().pages;
    }
    public static String hash(byte[] bytes)
    {try{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));}catch(Exception error){throw new IllegalStateException(error);}}
    public static String hashText(String text){return hash(text.getBytes(StandardCharsets.UTF_8));}
    public static final class State extends SavedData
    {
        private final Map<String,CompoundTag> receipts=new LinkedHashMap<>();
        private final ListTag quarantined=new ListTag();
        private static State load(CompoundTag tag)
        {
            var state=new State();
            for(var raw:tag.getList("Receipts",Tag.TAG_COMPOUND))
            {
                var row=(CompoundTag)raw;
                if(!row.hasUUID("Reader")||!row.hasUUID("Nonce")||!row.getString("Revision").matches("[0-9a-f]{64}")
                        ||!row.getString("Document").matches("r45/archive/[0-9]{1,2}")||row.getString("World").isBlank()
                        ||row.getString("Dimension").isBlank()||!row.contains("Book",Tag.TAG_LONG))
                {state.quarantined.add(row.copy());continue;}
                String key=row.getUUID("Reader")+"|"+row.getString("World")+"|"+row.getString("Document")+"|"+row.getString("Revision");
                if(state.receipts.putIfAbsent(key,row.copy())!=null)state.quarantined.add(row.copy());
            }
            state.quarantined.addAll(tag.getList("Quarantined",Tag.TAG_COMPOUND).copy());return state;
        }
        @Override public CompoundTag save(CompoundTag tag)
        {var rows=new ListTag();for(var receipt:receipts.values())rows.add(receipt.copy());tag.put("Receipts",rows);tag.put("Quarantined",quarantined.copy());return tag;}
    }
    private static State state(ServerLevel level)
    {return level.getDataStorage().computeIfAbsent(State::load,State::new,"projectseele_dead_sea_read_receipts_r45");}
    private static boolean physical(ServerPlayer player,BlockPos book)
    {
        var level=player.serverLevel();return player.isAlive()&&NervStaffDialogue.authorized(player)
                &&level.hasChunkAt(book)&&player.distanceToSqr(book.getX()+.5,book.getY()+.5,book.getZ()+.5)<=36
                &&level.getBlockState(book).getBlock() instanceof DeadSeaArchiveBlockR45;
    }
    @SubscribeEvent public static void opened(PlayerInteractEvent.RightClickBlock event)
    {
        if(event.getHand()!=InteractionHand.MAIN_HAND||event.isCanceled()||!(event.getEntity() instanceof ServerPlayer player)
                ||!(event.getLevel() instanceof ServerLevel level)||!physical(player,event.getPos()))return;
        var data=CityCoordinationSavedDataR44.get(level);var current=edition();var session=new Session();
        session.challenge=new Challenge(UUID.randomUUID(),data.active?data.instance:null,event.getPos().immutable(),current.revision,current.pages);
        session.expires=level.getGameTime()+2400;session.next=level.getGameTime()+20;session.dimension=level.dimension().location().toString();
        SESSIONS.computeIfAbsent(level,l->new LinkedHashMap<>()).put(player.getUUID(),session);bridge.open(player,session.challenge);
    }
    /** Root's authenticated PLAY_TO_SERVER decoder passes its actual sender, never a supplied player UUID. */
    public static boolean confirmPage(ServerPlayer player,UUID nonce,int page,String displayedRevision)
    {
        if(player==null||nonce==null)return false;var level=player.serverLevel();
        var session=SESSIONS.getOrDefault(level,Map.of()).get(player.getUUID());long now=level.getGameTime();
        if(session==null||!nonce.equals(session.challenge.nonce)||now<session.next||now>session.expires
                ||!session.dimension.equals(level.dimension().location().toString())||!physical(player,session.challenge.book)
                ||page<0||page>=session.challenge.pages||!session.challenge.revision.equals(displayedRevision)
                ||!displayedRevision.equals(currentRevision()))return false;
        var data=CityCoordinationSavedDataR44.get(level);
        if(session.challenge.dossier!=null&&(!data.active||!session.challenge.dossier.equals(data.instance)))return false;
        session.next=now+20;String document="r45/archive/"+page;var row=new CompoundTag();
        row.putUUID("Reader",player.getUUID());row.putUUID("Nonce",nonce);row.putString("Document",document);row.putString("Revision",displayedRevision);
        row.putString("World",Tokyo3BuildingWorldIdentityR44.get(level));row.putString("Dimension",session.dimension);row.putLong("Book",session.challenge.book.asLong());row.putLong("At",now);
        if(session.challenge.dossier!=null)row.putUUID("Dossier",session.challenge.dossier);
        var state=state(level);String key=player.getUUID()+"|"+row.getString("World")+"|"+document+"|"+displayedRevision;
        if(state.receipts.putIfAbsent(key,row)==null)state.setDirty();
        if(session.challenge.dossier!=null)data.recordReading(session.challenge.dossier,player.getUUID(),document,displayedRevision,"physical_archive",now);
        return true;
    }
    private DeadSeaReadingR45(){}
}
