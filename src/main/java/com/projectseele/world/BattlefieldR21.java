package com.projectseele.world;

import com.google.gson.*;
import com.projectseele.ProjectSeele;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.nbt.*;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerChunkCache;
import net.minecraft.server.level.TicketType;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.Property;
import net.minecraft.world.level.saveddata.SavedData;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.AABB;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.*;
import java.util.*;

/** Reversible, tick-budgeted emergency cover of explicitly inventoried city fixtures. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class BattlefieldR21
{
    private record Cell(BlockPos pos,BlockState before,BlockState covered,CompoundTag blockEntity){}
    /** manifest: SHA-256 of battlefield_r21.json, so a saved conflict count can tell which manifest it was made against. */
    private record Plan(List<Cell> cells,AABB bounds,String manifest){}
    private static final Map<ServerLevel,Optional<Plan>> PLANS=new WeakHashMap<>();
    private static final int CELL_LIMIT = 2048;
    private static final long WRITE_BUDGET_NS = 3_000_000;
    private static final String RECOUNT = "recount";
    private static final TicketType<ChunkPos> FIXTURE_TICKET = TicketType.create(
            "projectseele_street_fixtures", Comparator.comparingLong(ChunkPos::toLong), 120);

    /** The saved cursor is always in original manifest order. Only chunk requests look ahead. */
    private static final class ChunkWindow
    {
        private final Set<ChunkPos> held = new HashSet<>();
        private List<ChunkPos> needed = List.of();
        private String job = "";
        private int start, end, nextRequest;
        private long renewed;

        void prepare(ServerChunkCache source, List<Cell> cells, State state, long tick)
        {
            if (!job.equals(state.job) || state.cursor < start || state.cursor >= end)
            {
                job = state.job;
                start = end = state.cursor;
                var upcoming = new LinkedHashSet<ChunkPos>();
                while (end < cells.size() && end - start < CELL_LIMIT)
                {
                    var pos = new ChunkPos(cells.get(end).pos());
                    if (upcoming.size() == 48 && !upcoming.contains(pos)) break;
                    upcoming.add(pos);
                    end++;
                }
                needed = List.copyOf(upcoming);
                nextRequest = 0;
                for (var it = held.iterator(); it.hasNext(); )
                {
                    var pos = it.next();
                    if (!upcoming.contains(pos))
                    {
                        source.removeRegionTicket(FIXTURE_TICKET, pos, 0, pos);
                        it.remove();
                    }
                }
            }
            if (tick - renewed >= 60)
            {
                for (var pos : held) source.addRegionTicket(FIXTURE_TICKET, pos, 0, pos);
                renewed = tick;
            }
            int added = 0;
            while (added < 6 && nextRequest < needed.size())
            {
                var pos = needed.get(nextRequest++);
                if (held.add(pos))
                {
                    source.addRegionTicket(FIXTURE_TICKET, pos, 0, pos);
                    added++;
                }
            }
        }

        void release(ServerChunkCache source)
        {
            for (var pos : held) source.removeRegionTicket(FIXTURE_TICKET, pos, 0, pos);
        }
    }

    public static final class State extends SavedData
    {
        private ChunkWindow window;
        public String job="",manifest="";public int cursor,conflicts;public boolean hidden,restoreRequested;
        static State load(CompoundTag t){State s=new State();s.job=t.getString("Job");s.cursor=t.getInt("Cursor");s.conflicts=t.getInt("Conflicts");s.hidden=t.getBoolean("Hidden");s.restoreRequested=t.getBoolean("RestoreRequested");s.manifest=t.getString("Manifest");return s;}
        @Override public CompoundTag save(CompoundTag t){t.putString("Job",job);t.putInt("Cursor",cursor);t.putInt("Conflicts",conflicts);t.putBoolean("Hidden",hidden);t.putBoolean("RestoreRequested",restoreRequested);t.putString("Manifest",manifest);return t;}
    }
    public static State state(ServerLevel l){return l.getDataStorage().computeIfAbsent(State::load,State::new,"projectseele_battlefield_r21");}
    @SuppressWarnings({"unchecked","rawtypes"}) private static BlockState parse(String text)
    {
        int bracket=text.indexOf('[');var block=BuiltInRegistries.BLOCK.get(new ResourceLocation(bracket<0?text:text.substring(0,bracket)));var s=block.defaultBlockState();
        if(bracket>=0)for(String part:text.substring(bracket+1,text.length()-1).split(",")){String[] pair=part.split("=");Property p=block.getStateDefinition().getProperty(pair[0]);s=s.setValue(p,(Comparable)p.getValue(pair[1]).orElseThrow());}return s;
    }
    private static Optional<Plan> plan(ServerLevel level)
    {
        return PLANS.computeIfAbsent(level,l->{
            var file=l.getServer().getWorldPath(LevelResource.ROOT).resolve("battlefield_r21.json");if(!Files.isRegularFile(file))return Optional.empty();
            try
            {
                var bytes=Files.readAllBytes(file);
                var manifest=java.util.HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(bytes));
                var d=JsonParser.parseString(new String(bytes,java.nio.charset.StandardCharsets.UTF_8)).getAsJsonObject();var cells=new ArrayList<Cell>();
                for(var e:d.getAsJsonArray("cells")){var a=e.getAsJsonArray();cells.add(new Cell(new BlockPos(a.get(0).getAsInt(),a.get(1).getAsInt(),a.get(2).getAsInt()),parse(a.get(3).getAsString()),parse(a.get(4).getAsString()),a.size()>5?TagParser.parseTag(a.get(5).getAsString()):null));}
                var b=d.getAsJsonArray("bounds");return Optional.of(new Plan(cells,new AABB(b.get(0).getAsDouble(),81,b.get(1).getAsDouble(),b.get(2).getAsDouble()+1,320,b.get(3).getAsDouble()+1),manifest));
            }
            catch(Exception x){throw new IllegalStateException("Invalid explicit R21 battlefield manifest",x);}
        });
    }
    public static boolean installed(ServerLevel level){return plan(level).isPresent();}
    /** A recount writes nothing, so it does not hide the fixtures. */
    public static boolean concealed(ServerLevel level){if(!installed(level))return false;var s=state(level);return s.hidden||!s.job.isEmpty()&&!s.job.equals(RECOUNT);}
    public static boolean deferRestore(ServerLevel level)
    {
        if(!installed(level))return false;var s=state(level);
        if(!s.hidden&&(s.job.isEmpty()||s.job.equals(RECOUNT)))return false;
        s.restoreRequested=true;if(!s.job.equals("restore")){s.job="restore";s.cursor=0;s.conflicts=0;}s.setDirty();return true;
    }
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent e)
    {
        if(e.phase!=TickEvent.Phase.END)return;var level=e.getServer().getLevel(FacilitySchemaV2.DIMENSION);if(level==null)return;
        var optional=plan(level);if(optional.isEmpty())return;var p=optional.get();var s=state(level);var origin=IntegratedNervMapBuilder.tokyo3Origin(level);
        if(s.job.isEmpty())
        {
            if (s.window != null)
            {
                s.window.release(level.getChunkSource());
                s.window = null;
            }
            // R65: the count is made only while covering or restoring, so a save covered under an older manifest
            // (the 61 kerb cells taken out of it on 11-18) kept that count, and with it the NPC interlock in
            // CityBattlefieldR29, until the city next moved. Count again, writing nothing, under the manifest as it is.
            if(!s.manifest.equals(p.manifest())){s.job=RECOUNT;s.cursor=0;s.conflicts=0;s.setDirty();}
        }
        if(s.job.isEmpty())
        {
            var city=Tokyo3RetractionSavedData.get(level).get(origin).orElse(null);
            if(s.hidden||city==null||city.depth()!=ThirdTokyoSurfaceBuilder.maximumRetractionDepth(origin)||city.targetDepth()!=city.depth()||city.cursor()!=0||city.voxelCursor()!=0)return;
            // The rigid city keeps its own state: a raise asked for right after a restore waits there (queued) for a
            // few ticks or more, while the record above still says the city rests lowered. Covering then hid the
            // fixtures again before the city rose without them (R64).
            if(CityCreateDistrictR45.owns(level,origin))
            {
                var status=CityCreateDistrictR45.status(level,origin);
                if(status==null||ArmamentTowerLogicR64.cityMode(status.phase(),status.depth(),status.maximumDepth())!=ArmamentTowerLogicR64.LOWERED)return;
            }
            // A player standing on a pavilion roof must first reach street level.
            if(!level.getEntitiesOfClass(Player.class,p.bounds,q->!q.isSpectator()&&q.getY()>82).isEmpty())return;
            s.job="cover";s.cursor=0;s.conflicts=0;s.setDirty();
        }
        boolean restore=s.job.equals("restore"),recount=s.job.equals(RECOUNT);
        long began = System.nanoTime();
        int first = s.cursor;
        var source = level.getChunkSource();
        if (s.window == null) s.window = new ChunkWindow();
        s.window.prepare(source, p.cells, s, level.getGameTime());
        while (s.cursor < s.window.end && (s.cursor == first || System.nanoTime() - began < WRITE_BUDGET_NS))
        {
            var c=p.cells.get(s.cursor);
            // The old rectangular field sliced the three east pylons at X207.
            // Keep the original plan/cursor archive, but fixed power objects
            // never belong to the temporary battlefield cover or its restore.
            if (ThirdTokyoSurfaceBuilder.fixedPowerPylonCell(origin,c.pos))
            {
                s.cursor++;
                continue;
            }
            // A ticket requests a FULL chunk without waiting for disk or world generation on this tick.
            var chunk = source.getChunkNow(c.pos.getX() >> 4, c.pos.getZ() >> 4);
            if (chunk == null) break;
            BlockState from=restore?c.covered:c.before,to=restore?c.before:c.covered,actual=chunk.getBlockState(c.pos);
            if(!actual.equals(from)&&!actual.equals(to)){s.conflicts++;s.cursor++;continue;}
            if(recount){s.cursor++;continue;}
            if(!actual.equals(to))
            {
                if(restore&&!to.getCollisionShape(level,c.pos).isEmpty()&&!level.getEntitiesOfClass(Player.class,new AABB(c.pos),q->!q.isSpectator()).isEmpty())break;
                level.setBlock(c.pos,to,18);
                if(restore&&c.blockEntity!=null){var be=level.getBlockEntity(c.pos);if(be!=null){be.load(c.blockEntity);be.setChanged();}}
            }
            s.cursor++;
        }
        if (s.cursor != first) s.setDirty();
        if(s.cursor==p.cells.size())
        {
            s.window.release(source);
            s.window = null;
            s.manifest=p.manifest();
            if(recount)
            {
                s.job="";s.cursor=0;s.setDirty();
                ProjectSeele.LOGGER.info("R21 BATTLEFIELD RECOUNTED hidden={} cells={} conflicts={}",s.hidden,p.cells.size(),s.conflicts);
                return;
            }
            s.hidden=!restore;s.job="";s.cursor=0;s.setDirty();ProjectSeele.LOGGER.info("R21 BATTLEFIELD {} cells={} conflicts={}",restore?"RESTORED":"COVERED",p.cells.size(),s.conflicts);
            if(restore&&s.restoreRequested){s.restoreRequested=false;s.setDirty();Tokyo3RetractionDirector.request(level,origin,false);}
        }
    }
    private BattlefieldR21(){}
}
