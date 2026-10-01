"""Private concrete finite source recipe and unapplied builder hooks."""
from pathlib import Path
import argparse,hashlib,json,difflib

ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'artifacts/rebuild_r44/hangar_machinery';OUT=BASE/'personnel_source_recipe_v1'

JAVA='''package com.projectseele.world;

import com.google.gson.JsonParser;
import com.projectseele.registry.ModBlocks;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.DoorBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.DoubleBlockHalf;
import net.minecraft.world.level.block.state.properties.DoorHingeSide;
import java.util.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

/** Finite declared three-bed recipe. Private candidate, not yet compiled. */
public final class TvPersonnelPlatformRecipeR44
{
    private record Cell(BlockPos position, String before, BlockState after) { }
    private static final String RECIPE_SHA256 = "HASH";
    private static final String METADATA_SHA256 = "META_DIGEST";
    private static final String MODEL_SHA256 = "MODEL_DIGEST";
    private static final Set<BlockPos> OWNERS = new HashSet<>();
    static
    {
        for (String token : "OWNED".split(";"))
        {
            String[] q=token.split(":");
            OWNERS.add(new BlockPos(Integer.parseInt(q[0]),Integer.parseInt(q[1]),Integer.parseInt(q[2])));
        }
        if (OWNERS.size()!=427) throw new IllegalStateException("Incomplete finite personnel recipe");
    }
    public static boolean owns(ServerLevel level, BlockPos position)
    {
        return TvPersonnelPlatformInterlockR44.enabled(level) && OWNERS.contains(position);
    }
    private static int variant(BlockPos bed)
    {
        for(int v=0;v<3;v++) if(bed.equals(new BlockPos(-12+42*v,-443,-240)))return v;
        return -1;
    }
    private static String stateKey(BlockState state)
    {
        String name=net.minecraft.core.registries.BuiltInRegistries.BLOCK.getKey(state.getBlock()).toString();
        if(state.getValues().isEmpty())return name;
        var props=new TreeMap<String,String>();
        state.getValues().forEach((p,v)->props.put(p.getName(),propertyName(p,v)));
        return name+"["+String.join(",",props.entrySet().stream().map(e->e.getKey()+"="+e.getValue()).toList())+"]";
    }
    @SuppressWarnings({"rawtypes","unchecked"})
    private static String propertyName(net.minecraft.world.level.block.state.properties.Property p,Comparable v)
    {return p.getName(v);}
    private static BlockState parse(String key)
    {
        String name=key.substring(0,key.indexOf('['));
        var p=new HashMap<String,String>();
        for(String part:key.substring(key.indexOf('[')+1,key.length()-1).split(","))
        {String[] pair=part.split("=");p.put(pair[0],pair[1]);}
        if(name.equals("projectseele:tv_personnel_deck_r44"))
            return ModBlocks.NERV_TV_PERSONNEL_DECK_R44.get().defaultBlockState()
                .setValue(TvPersonnelDeckR44.FACING,Direction.valueOf(p.get("facing").toUpperCase(Locale.ROOT)))
                .setValue(TvPersonnelDeckR44.LEVEL,Integer.parseInt(p.get("level")))
                .setValue(TvPersonnelDeckR44.PROFILE,TvPersonnelDeckR44.Profile.valueOf(p.get("profile").toUpperCase(Locale.ROOT)));
        if(name.equals("projectseele:tv_personnel_guard_r44"))
            return ModBlocks.NERV_TV_PERSONNEL_GUARD_R44.get().defaultBlockState()
                .setValue(TvPersonnelGuardR44.DROP,Integer.parseInt(p.get("drop")))
                .setValue(TvPersonnelGuardR44.NORTH,Boolean.parseBoolean(p.get("north")))
                .setValue(TvPersonnelGuardR44.EAST,Boolean.parseBoolean(p.get("east")))
                .setValue(TvPersonnelGuardR44.SOUTH,Boolean.parseBoolean(p.get("south")))
                .setValue(TvPersonnelGuardR44.WEST,Boolean.parseBoolean(p.get("west")));
        if(name.equals("projectseele:city_personnel_door"))
            return ModBlocks.CITY_PERSONNEL_DOOR.get().defaultBlockState()
                .setValue(DoorBlock.FACING,Direction.valueOf(p.get("facing").toUpperCase(Locale.ROOT)))
                .setValue(DoorBlock.HALF,p.get("half").equals("lower")?DoubleBlockHalf.LOWER:DoubleBlockHalf.UPPER)
                .setValue(DoorBlock.HINGE,p.get("hinge").equals("left")?DoorHingeSide.LEFT:DoorHingeSide.RIGHT)
                .setValue(DoorBlock.OPEN,Boolean.parseBoolean(p.get("open")))
                .setValue(DoorBlock.POWERED,Boolean.parseBoolean(p.get("powered")));
        throw new IllegalArgumentException("Unknown recipe block "+name);
    }
    private static boolean alreadyOwned(BlockState actual,BlockState expected)
    {
        if(actual.equals(expected))return true;
        return expected.getBlock() instanceof CityPersonnelDoorR44 && actual.is(expected.getBlock())
            && actual.setValue(DoorBlock.OPEN,false).setValue(DoorBlock.POWERED,false)
                .equals(expected.setValue(DoorBlock.OPEN,false).setValue(DoorBlock.POWERED,false));
    }
    public static Optional<String> ensure(ServerLevel level,BlockPos bed)
    {
        if(!TvPersonnelPlatformInterlockR44.enabled(level))return Optional.empty();
        int v=variant(bed);
        if(v<0)return Optional.of("Unknown personnel recipe bed");
        var entry=EvaFleetSavedData.get(level.getServer()).entry(v);
        if(entry.isPresent()&&entry.get().phase()!=EvaFleetSavedData.Phase.PARKED)
            return Optional.of("Personnel recipe cannot generate during equipment motion");
        var fault=TvPersonnelPlatformInterlockR44.prepareFault(level,v);
        if(fault.isPresent())return fault;
        try(var stream=TvPersonnelPlatformRecipeR44.class.getResourceAsStream("/data/projectseele/worldgen/authored/tv_personnel_recipe_r44.json"))
        {
            if(stream==null)return Optional.of("Personnel recipe unavailable");
            byte[] bytes=stream.readAllBytes();
            if(!HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes)).equals(RECIPE_SHA256))
                return Optional.of("Personnel recipe hash changed");
            var metadata=level.getServer().getWorldPath(net.minecraft.world.level.storage.LevelResource.ROOT)
                .resolve("r44_tv_personnel_platforms.json");
            if(!java.nio.file.Files.isRegularFile(metadata)
                ||!HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(java.nio.file.Files.readAllBytes(metadata))).equals(METADATA_SHA256))
                return Optional.of("Personnel metadata epoch changed");
            try(var model=TvPersonnelPlatformRecipeR44.class.getResourceAsStream("/assets/projectseele/mesh/tv_shoulder_shells_r44.json"))
            {
                if(model==null||!HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(model.readAllBytes())).equals(MODEL_SHA256))
                    return Optional.of("Personnel model epoch changed");
            }
            var document=JsonParser.parseString(new String(bytes,StandardCharsets.UTF_8)).getAsJsonObject();
            var rows=document.getAsJsonArray("operations");
            if(rows.size()!=427)return Optional.of("Personnel recipe incomplete");
            var cells=new ArrayList<Cell>();var seen=new HashSet<BlockPos>();
            var gateOpen=new HashMap<BlockPos,Boolean>();
            for(var gateValue:document.getAsJsonArray("entry_gate_pairs"))
            {
                var gate=gateValue.getAsJsonObject();if(gate.get("variant").getAsInt()!=v)continue;
                Boolean open=null;var leaves=new ArrayList<BlockPos>();
                for(var value:gate.getAsJsonArray("lower_positions"))
                {
                    var q=value.getAsJsonArray();var lower=new BlockPos(q.get(0).getAsInt(),q.get(1).getAsInt(),q.get(2).getAsInt());
                    leaves.add(lower);leaves.add(lower.above());
                }
                for(var pos:leaves)
                {
                    var actual=level.getBlockState(pos);
                    if(actual.getBlock() instanceof CityPersonnelDoorR44)
                    {
                        boolean flag=actual.getValue(DoorBlock.OPEN);
                        if(open!=null&&open!=flag)return Optional.of("Personnel pair has inconsistent existing open state");
                        open=flag;
                    }
                }
                for(var pos:leaves)gateOpen.put(pos,open!=null&&open);
            }
            for(var value:rows)
            {
                var row=value.getAsJsonObject();var xyz=row.getAsJsonArray("position");
                var pos=new BlockPos(xyz.get(0).getAsInt(),xyz.get(1).getAsInt(),xyz.get(2).getAsInt());
                if(!OWNERS.contains(pos)||!seen.add(pos))return Optional.of("Unknown/duplicate recipe owner");
                if(pos.getX()<bed.getX()-21||pos.getX()>bed.getX()+21)continue;
                if(!level.hasChunkAt(pos)||level.getBlockEntity(pos)!=null)return Optional.of("Unknown section or protected block entity "+pos);
                var after=parse(row.get("after").getAsString());String before=row.get("before").getAsString();
                if(after.getBlock() instanceof CityPersonnelDoorR44)
                    after=after.setValue(DoorBlock.OPEN,gateOpen.getOrDefault(pos,false));
                var actual=level.getBlockState(pos);
                if(!alreadyOwned(actual,after)&&!actual.isAir()&&!stateKey(actual).equals(before))
                    return Optional.of("Human/source state changed at "+pos);
                if(after.getBlock() instanceof CityPersonnelDoorR44&&!alreadyOwned(actual,after)
                    &&!level.getEntitiesOfClass(net.minecraft.world.entity.LivingEntity.class,
                        new net.minecraft.world.phys.AABB(pos).expandTowards(0,1,0),e->e.isAlive()&&!e.isSpectator()).isEmpty())
                    return Optional.of("Personnel gate installation leaf is occupied "+pos);
                cells.add(new Cell(pos,before,after));
            }
            // Completepreflight occurs before the first mutation. Every block
            // has finite ownership, a matching prior or air, and no BE.
            for(var cell:cells)
                if(!alreadyOwned(level.getBlockState(cell.position),cell.after))
                    level.setBlock(cell.position,cell.after,Block.UPDATE_CLIENTS);
            return Optional.empty();
        }
        catch(Exception error){return Optional.of("Personnel recipe rejected: "+error.getMessage());}
    }
    private TvPersonnelPlatformRecipeR44() { }
}
'''

def main(out=OUT,metadata_revision='personnel_platforms_v5_boundaries_v3',model_revision='tv_personnel_supports_v5_draft10'):
    global OUT
    OUT=Path(out)
    if OUT.exists():raise ValueError('Fresh immutable source proposal required')
    OUT.mkdir(parents=True);op=BASE/metadata_revision/'operations.json';ops=json.loads(op.read_text())
    recipe={'schema':44,'bed_owners':[[-12,-443,-240],[30,-443,-240],[72,-443,-240]],'operations':ops,
            'entry_gate_pairs':json.loads(op.with_name('r44_tv_personnel_platforms.json').read_text())['entry_gate_pairs'],
            'operations_sha256':hashlib.sha256(op.read_bytes()).hexdigest(),'inverse_sha256':hashlib.sha256(op.with_name('inverse.json').read_bytes()).hexdigest(),
            'required_metadata_sha256':hashlib.sha256(op.with_name('r44_tv_personnel_platforms.json').read_bytes()).hexdigest(),
            'root_application_before_source_activation_required':True}
    path=OUT/'data/projectseele/worldgen/authored/tv_personnel_recipe_r44.json';path.parent.mkdir(parents=True);path.write_text(json.dumps(recipe,separators=(',',':')),'utf8')
    digest=hashlib.sha256(path.read_bytes()).hexdigest();owned=';'.join(':'.join(map(str,r['position'])) for r in ops)
    java=OUT/'source/com/projectseele/world/TvPersonnelPlatformRecipeR44.java';java.parent.mkdir(parents=True);java.write_text(JAVA.replace('HASH',digest).replace('META_DIGEST',recipe['required_metadata_sha256']).replace('MODEL_DIGEST',hashlib.sha256((BASE/model_revision/'tv_shoulder_shells_r44.json').read_bytes()).hexdigest()).replace('OWNED',owned),'utf8')
    source=ROOT/'src/main/java/com/projectseele/world/EvaHangarBuilder.java';before=source.read_text('utf8');after=before
    hook='    private static void set(ServerLevel level, BlockPos position, BlockState state)\n    {\n'
    if after.count(hook)!=1:raise ValueError('Builderhook notunique')
    after=after.replace(hook,hook+'        if (TvPersonnelPlatformRecipeR44.owns(level, position)) return;\n')
    hook='    private static void buildChamber(ServerLevel level, BlockPos origin,\n                                     int variant)\n    {\n        BlockPos bed = hangarBed(origin, variant);\n'
    if after.count(hook)!=1:raise ValueError('Chamberhook notunique')
    after=after.replace(hook,hook+'        TvPersonnelPlatformRecipeR44.ensure(level, bed).ifPresent(fault ->\n                { throw new IllegalStateException("R44 personnel producer rejected before chamber writes: " + fault); });\n')
    (OUT/'unapplied_builder.diff').write_text(''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='a/src/main/java/com/projectseele/world/EvaHangarBuilder.java',tofile='b/src/main/java/com/projectseele/world/EvaHangarBuilder.java')),'utf8')
    (OUT/'manifest.json').write_text(json.dumps({'status':'PRIVATE_CONCRETE_SOURCE_CANDIDATE_UNCOMPILED_UNAPPLIED','builder_source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'recipe_sha256':digest,'source_sha256':hashlib.sha256(java.read_bytes()).hexdigest(),
        'operations':427,'exact_finite_owner_positions':True,'protects_all_BEs':True,'unknown_or_human_states_preserved':True,'already_installed_gate_open_state_preserved':True,
        'remaining':['rootcompileandnativefreshgeneration/repair/lifecycle','strictmetadatainstalledfloorandmodelhashloader','errorreceiptmustsurfaceintherealbuilderaudit','preserveoccupancy/resumption/cold/multiplayer','installationdiffandrollbackownedbyroot'],'main_source_modified':False,'world_write':False,'native_passed':False,'preapply_ready':False},indent=2),'utf8')
    print(json.dumps({'proposal':str(OUT),'recipe_sha256':digest,'operations':427,'main_source_modified':False}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=OUT);p.add_argument('--metadata-revision',default='personnel_platforms_v5_boundaries_v3');p.add_argument('--model-revision',default='tv_personnel_supports_v5_draft10')
    a=p.parse_args();main(a.out,a.metadata_revision,a.model_revision)
