package com.projectseele.world;

import com.google.gson.*;
import com.projectseele.ProjectSeele;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.nbt.*;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.level.ServerLevel;
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
    private record Plan(List<Cell> cells,AABB bounds){}
    private static final Map<ServerLevel,Optional<Plan>> PLANS=new WeakHashMap<>();
    public static final class State extends SavedData
    {
        public String job="";public int cursor,conflicts;public boolean hidden,restoreRequested;
        static State load(CompoundTag t){State s=new State();s.job=t.getString("Job");s.cursor=t.getInt("Cursor");s.conflicts=t.getInt("Conflicts");s.hidden=t.getBoolean("Hidden");s.restoreRequested=t.getBoolean("RestoreRequested");return s;}
        @Override public CompoundTag save(CompoundTag t){t.putString("Job",job);t.putInt("Cursor",cursor);t.putInt("Conflicts",conflicts);t.putBoolean("Hidden",hidden);t.putBoolean("RestoreRequested",restoreRequested);return t;}
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
                var d=JsonParser.parseString(Files.readString(file)).getAsJsonObject();var cells=new ArrayList<Cell>();
                for(var e:d.getAsJsonArray("cells")){var a=e.getAsJsonArray();cells.add(new Cell(new BlockPos(a.get(0).getAsInt(),a.get(1).getAsInt(),a.get(2).getAsInt()),parse(a.get(3).getAsString()),parse(a.get(4).getAsString()),a.size()>5?TagParser.parseTag(a.get(5).getAsString()):null));}
                var b=d.getAsJsonArray("bounds");return Optional.of(new Plan(cells,new AABB(b.get(0).getAsDouble(),81,b.get(1).getAsDouble(),b.get(2).getAsDouble()+1,320,b.get(3).getAsDouble()+1)));
            }
            catch(Exception x){throw new IllegalStateException("Invalid explicit R21 battlefield manifest",x);}
        });
    }
    public static boolean installed(ServerLevel level){return plan(level).isPresent();}
    public static boolean concealed(ServerLevel level){if(!installed(level))return false;var s=state(level);return s.hidden||!s.job.isEmpty();}
    public static boolean deferRestore(ServerLevel level)
    {
        if(!installed(level))return false;var s=state(level);
        if(!s.hidden&&s.job.isEmpty())return false;
        s.restoreRequested=true;if(!s.job.equals("restore")){s.job="restore";s.cursor=0;s.conflicts=0;}s.setDirty();return true;
    }
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent e)
    {
        if(e.phase!=TickEvent.Phase.END)return;var level=e.getServer().getLevel(FacilitySchemaV2.DIMENSION);if(level==null)return;
        var optional=plan(level);if(optional.isEmpty())return;var p=optional.get();var s=state(level);var origin=IntegratedNervMapBuilder.tokyo3Origin(level);
        if(s.job.isEmpty())
        {
            var city=Tokyo3RetractionSavedData.get(level).get(origin).orElse(null);
            if(s.hidden||city==null||city.depth()!=ThirdTokyoSurfaceBuilder.maximumRetractionDepth(origin)||city.targetDepth()!=city.depth()||city.cursor()!=0||city.voxelCursor()!=0)return;
            // A player standing on a pavilion roof must first reach street level.
            if(!level.getEntitiesOfClass(Player.class,p.bounds,q->!q.isSpectator()&&q.getY()>82).isEmpty())return;
            s.job="cover";s.cursor=0;s.conflicts=0;s.setDirty();
        }
        boolean restore=s.job.equals("restore");int processed=0;
        while(processed++<2048&&s.cursor<p.cells.size())
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
            level.getChunk(c.pos);BlockState from=restore?c.covered:c.before,to=restore?c.before:c.covered,actual=level.getBlockState(c.pos);
            if(!actual.equals(from)&&!actual.equals(to)){s.conflicts++;s.cursor++;continue;}
            if(!actual.equals(to))
            {
                if(restore&&!to.getCollisionShape(level,c.pos).isEmpty()&&!level.getEntitiesOfClass(Player.class,new AABB(c.pos),q->!q.isSpectator()).isEmpty())break;
                level.setBlock(c.pos,to,18);
                if(restore&&c.blockEntity!=null){var be=level.getBlockEntity(c.pos);if(be!=null){be.load(c.blockEntity);be.setChanged();}}
            }
            s.cursor++;
        }
        s.setDirty();
        if(s.cursor==p.cells.size())
        {
            s.hidden=!restore;s.job="";s.cursor=0;s.setDirty();ProjectSeele.LOGGER.info("R21 BATTLEFIELD {} cells={} conflicts={}",restore?"RESTORED":"COVERED",p.cells.size(),s.conflicts);
            if(restore&&s.restoreRequested){s.restoreRequested=false;s.setDirty();Tokyo3RetractionDirector.request(level,origin,false);}
        }
    }
    private BattlefieldR21(){}
}
