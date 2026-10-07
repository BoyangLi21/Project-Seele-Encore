package com.projectseele.world;

import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.EvaBayRepairR33;

import com.google.gson.*;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.EvaPrototypeEntity;
import com.projectseele.entity.NervHangarDoorEntity;
import com.projectseele.registry.ModItems;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.nbt.*;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.TicketType;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.decoration.ArmorStand;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.saveddata.SavedData;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.common.capabilities.ForgeCapabilities;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.event.entity.player.PlayerInteractEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.*;
import java.util.*;

/** World-owned R07 equipment and a resumable, bounded experimental wet-cell cycle. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class MilitaryR07Director
{
    public enum Phase { WET,DRAINING,DRY,OPENING,OPEN,CLOSING,FILLING }
    private static final Vec3 HOME=new Vec3(6442.5,77,-6205.5),DOOR=new Vec3(6442.5,77,-6135.5);
    private static final BlockPos[] BUTTONS={new BlockPos(6394,78,-6141),new BlockPos(6398,78,-6141),new BlockPos(6406,78,-6141)};
    private static final TicketType<ChunkPos> TICKET=TicketType.create("seele_experimental_cell",Comparator.comparingLong(ChunkPos::toLong),100);
    private static final String DATA="projectseele_military_r07";
    private static JsonObject plan;
    private static Path planWorld;

    public static final class State extends SavedData
    {
        public Phase phase=Phase.WET;
        public int cursor;
        public int poolWidth=33;
        public boolean commissioned,defense=true,power=true,baseGenerator=true,portGenerator=true;
        public final Map<String,UUID> entities=new LinkedHashMap<>();
        static State load(CompoundTag tag)
        {
            State d=new State();d.commissioned=tag.getBoolean("Commissioned");d.cursor=tag.getInt("Cursor");d.poolWidth=tag.contains("PoolWidth")?tag.getInt("PoolWidth"):33;
            try { d.phase=Phase.valueOf(tag.getString("Phase")); } catch(Exception ignored) { }
            d.defense=!tag.contains("Defense")||tag.getBoolean("Defense");d.power=!tag.contains("Power")||tag.getBoolean("Power");
            d.baseGenerator=!tag.contains("BaseGenerator")||tag.getBoolean("BaseGenerator");d.portGenerator=!tag.contains("PortGenerator")||tag.getBoolean("PortGenerator");
            CompoundTag ids=tag.getCompound("Entities");for(String key:ids.getAllKeys())if(ids.hasUUID(key))d.entities.put(key,ids.getUUID(key));
            return d;
        }
        @Override public CompoundTag save(CompoundTag tag)
        {
            tag.putBoolean("Commissioned",commissioned);tag.putString("Phase",phase.name());tag.putInt("Cursor",cursor);
            tag.putInt("PoolWidth",poolWidth);
            tag.putBoolean("Defense",defense);tag.putBoolean("Power",power);tag.putBoolean("BaseGenerator",baseGenerator);tag.putBoolean("PortGenerator",portGenerator);CompoundTag ids=new CompoundTag();entities.forEach(ids::putUUID);tag.put("Entities",ids);return tag;
        }
    }
    public static State state(ServerLevel level) { return level.getDataStorage().computeIfAbsent(State::load,State::new,DATA); }
    private static JsonObject plan(ServerLevel level)
    {
        Path world=level.getServer().getWorldPath(LevelResource.ROOT).normalize();
        if(!world.equals(planWorld)) { plan=null;planWorld=world; }
        if(plan==null)
        {
            Path file=world.resolve("r07_installations.json");if(!Files.isRegularFile(file))return null;
            try { plan=JsonParser.parseString(Files.readString(file)).getAsJsonObject(); }
            catch(Exception error) { throw new IllegalStateException("R07 installation plan",error); }
        }
        return plan;
    }
    private static Entity entity(ServerLevel level,State data,String key)
    {
        UUID id=data.entities.get(key);return id==null?null:level.getEntity(id);
    }
    private static boolean card(Player player)
    {
        if(player.isCreative())return true;
        for(int i=0;i<player.getInventory().getContainerSize();i++)
        {
            var stack=player.getInventory().getItem(i);
            if(stack.is(ModItems.NERV_EMPLOYEE_CARD.get())||stack.is(ModItems.TERMINAL_DOGMA_ACCESS_CARD.get()))return true;
        }
        return false;
    }
    private static void say(Player player,String text) { if(player!=null)player.displayClientMessage(Component.literal(text),true); }
    public static String request(ServerLevel level,String action,Player operator)
    {
        State data=state(level);if(!data.commissioned)return "设施尚未完成调试";
        if(operator!=null&&!card(operator))return "需要 NERV 身份卡";
        var repairId=UNRecoveryR22.identity(level,0);
        if(repairId!=null&&level.getEntity(repairId) instanceof EvaUnit01Entity repairing&&EvaBayRepairR33.active(repairing))return "机体正在检修，请等待机械臂撤回。";
        switch(action)
        {
            case "drain" -> {
                if(data.phase!=Phase.WET&&data.phase!=Phase.FILLING)return "当前无需排液";
                if(!level.getEntitiesOfClass(Player.class,UNHangarDimensionsR31.pit(level,0),p->!p.isSpectator()).isEmpty())return "请先离开 LCL 试验区";
                data.phase=Phase.DRAINING;data.cursor=0;
            }
            case "door" -> {
                if(data.phase==Phase.DRY)
                {
                    if(fluidCells(level)>0){data.phase=Phase.DRAINING;data.cursor=0;data.setDirty();return "检测到余液，继续排液";}
                    data.phase=Phase.OPENING;data.cursor=0;
                }
                else if(data.phase==Phase.OPEN){
                    if(occupiedDoor(level))return "舱门运行区域有人员或载具";
                    data.phase=Phase.CLOSING;data.cursor=0;
                }
                else if(data.phase==Phase.CLOSING)data.phase=Phase.OPENING;
                else if(data.phase==Phase.OPENING)return "舱门正在开启";
                else return "LCL 未排空，舱门锁定";
            }
            case "fill" -> {
                if(data.phase!=Phase.DRY)return "请先关闭舱门";
                Entity unit=entity(level,data,"prototype");
                if(unit==null||unit.position().distanceTo(HOME)>3||unit.isVehicle())return "试验机须归位并解除驾驶";
                if(!level.getEntitiesOfClass(Player.class,UNHangarDimensionsR31.pit(level,0),p->!p.isSpectator()).isEmpty())return "请先离开 LCL 试验区";
                data.phase=Phase.FILLING;data.cursor=0;
            }
            case "defense" -> data.defense=!data.defense;
            case "power" -> data.power=!data.power;
            default -> { return status(data); }
        }
        data.setDirty();
        if(action.equals("defense"))return data.defense?"防御系统已启用":"防御系统已待机";
        if(action.equals("power"))return data.power?"防御能源网已接通":"防御能源网已关闭";
        return status(data);
    }
    public static String status(State data)
    {
        String phase=switch(data.phase){case WET->"LCL 保管";case DRAINING->"排液中";case DRY->"干燥 / 舱门关闭";case OPENING->"舱门开启中";case OPEN->"允许出舱";case CLOSING->"舱门关闭中";case FILLING->"注液中";};
        return "试验格纳库 · "+phase+((data.phase==Phase.DRAINING||data.phase==Phase.FILLING)?" "+(100*data.cursor/(data.poolWidth*90*44))+"%":"");
    }
    private static boolean occupiedDoor(ServerLevel level)
    {
        return !level.getEntities((Entity)null,UNHangarDimensionsR31.sweep(level,0),e->!(e instanceof NervHangarDoorEntity)&&!(e instanceof ArmorStand stand&&stand.isMarker())
                &&e.isAlive()&&!e.isSpectator()&&(e instanceof net.minecraft.world.entity.LivingEntity||e.isVehicle()||e.getTags().contains("seele_r07_owned"))).isEmpty();
    }
    public static int fluidCells(ServerLevel level)
    {
        Block lcl=BuiltInRegistries.BLOCK.get(new ResourceLocation("projectseele:lcl"));int count=0;
        for(BlockPos pos:BlockPos.betweenClosed(UNHangarDimensionsR31.minimum(level,0),UNHangarDimensionsR31.maximum(level,0)))if(level.getBlockState(pos).is(lcl))count++;
        return count;
    }
    private static void tickets(ServerLevel level,boolean keep)
    {
        for(int x=6400>>4;x<=6496>>4;x++)for(int z=-6240>>4;z<=-6128>>4;z++)
        {
            ChunkPos p=new ChunkPos(x,z);
            if(keep)level.getChunkSource().addRegionTicket(TICKET,p,2,p);else level.getChunkSource().removeRegionTicket(TICKET,p,2,p);
        }
    }
    private static boolean barrier(ServerLevel level,boolean closed)
    {
        int low=UNHangarDimensionsR31.minimum(level,0).getX(),high=UNHangarDimensionsR31.maximum(level,0).getX();
        for(int x=low;x<=high;x++)for(int y=77;y<=141;y++)
        {
            BlockState old=level.getBlockState(new BlockPos(x,y,-6136));
            if(!old.isAir()&&!old.is(Blocks.BARRIER))return false;
        }
        BlockState state=(closed?Blocks.BARRIER:Blocks.AIR).defaultBlockState();
        for(int x=low;x<=high;x++)for(int y=77;y<=141;y++)level.setBlock(new BlockPos(x,y,-6136),state,2);
        return true;
    }
    @SubscribeEvent public static void interact(PlayerInteractEvent.RightClickBlock event)
    {
        if(!(event.getLevel() instanceof ServerLevel level)||!level.dimension().equals(FacilitySchemaV2.DIMENSION)||plan(level)==null)return;
        String action=null;for(int i=0;i<BUTTONS.length;i++)if(BUTTONS[i].equals(event.getPos()))action=new String[]{"drain","door","fill"}[i];
        if(event.getPos().equals(new BlockPos(6400,76,-6545)))action="defense";
        if(event.getPos().equals(new BlockPos(6404,76,-6545)))action="power";
        if(action==null)return;
        event.setCanceled(true);
        event.setCancellationResult(net.minecraft.world.InteractionResult.SUCCESS);
        if(event.getHand()!=net.minecraft.world.InteractionHand.MAIN_HAND)return;
        if(card(event.getEntity()))
        {
            BlockState button=level.getBlockState(event.getPos());
            if(button.getBlock() instanceof net.minecraft.world.level.block.ButtonBlock)
                button.use(level,event.getEntity(),event.getHand(),event.getHitVec());
        }
        say(event.getEntity(),request(level,action,event.getEntity()));
    }
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(event.phase!=TickEvent.Phase.END)return;
        ServerLevel level=event.getServer().getLevel(FacilitySchemaV2.DIMENSION);
        if(level==null||plan(level)==null)return;State data=state(level);if(!data.commissioned)return;
        int width=UNHangarDimensionsR31.width(level),layerSize=UNHangarDimensionsR31.layer(level),total=UNHangarDimensionsR31.total(level);
        if(data.poolWidth!=width)
        {
            data.poolWidth=width;
            if(data.phase==Phase.DRAINING||data.phase==Phase.FILLING)data.cursor=0;
            data.setDirty();
        }
        // The local integrated server must accept genuine SBW aircraft motion.
        // Dedicated distributions already ship allow-flight=true in server.properties.
        if(event.getServer().isSingleplayer()&&!event.getServer().isFlightAllowed())event.getServer().setFlightAllowed(true);
        if(level.getGameTime()%20==0)powerAndDefense(level,data);
        boolean operating=data.phase==Phase.DRAINING||data.phase==Phase.FILLING||data.phase==Phase.OPENING||data.phase==Phase.CLOSING;
        if(operating)
        {
            tickets(level,true);
            // Finish explicitly started machinery even if its operator logs
            // out; vanilla otherwise stops entity ticks after 300 idle ticks.
            level.resetEmptyTime();
        }
        if(!level.hasChunkAt(BUTTONS[0]))return;
        FacilityAudioR21.auxiliary(level,"UN00",data.phase,DOOR);
        boolean open=data.phase==Phase.OPEN||data.phase==Phase.OPENING;
        NervHangarDoorEntity.reconcile(level,3,DOOR,open);
        if(data.phase==Phase.DRAINING||data.phase==Phase.FILLING)
        {
            var lcl=BuiltInRegistries.BLOCK.get(new ResourceLocation("projectseele:lcl"));
            int minimumX=UNHangarDimensionsR31.minimum(level,0).getX();
            for(int n=0;n<512&&data.cursor<total;n++,data.cursor++)
            {
                int layer=data.cursor/layerSize,within=data.cursor%layerSize;
                BlockPos pos=new BlockPos(minimumX+within%width,data.phase==Phase.DRAINING?120-layer:77+layer,-6226+within/width);
                BlockState old=level.getBlockState(pos);
                if(data.phase==Phase.DRAINING&&old.is(lcl))level.setBlock(pos,Blocks.AIR.defaultBlockState(),Block.UPDATE_CLIENTS|Block.UPDATE_KNOWN_SHAPE);
                if(data.phase==Phase.FILLING&&(old.isAir()||old.is(lcl)))level.setBlock(pos,lcl.defaultBlockState(),Block.UPDATE_CLIENTS|Block.UPDATE_KNOWN_SHAPE);
            }
            if(data.cursor==total)
            {
                if(data.phase==Phase.DRAINING&&fluidCells(level)>0)data.cursor=0;
                else {data.phase=data.phase==Phase.DRAINING?Phase.DRY:Phase.WET;tickets(level,false);}
            }
            data.setDirty();
        }
        else if(data.phase==Phase.OPENING||data.phase==Phase.CLOSING)
        {
            var doors=level.getEntitiesOfClass(NervHangarDoorEntity.class,new AABB(DOOR,DOOR).inflate(3),e->e.getVariant()==3);
            if(!doors.isEmpty())
            {
                float progress=doors.get(0).getOpenProgress(1);
                if(data.phase==Phase.OPENING&&progress>=.99F&&barrier(level,false)){data.phase=Phase.OPEN;tickets(level,false);data.setDirty();}
                if(data.phase==Phase.CLOSING)
                {
                    if(occupiedDoor(level)){data.phase=Phase.OPENING;data.setDirty();}
                    else
                    {
                        if(progress<.99F)barrier(level,true);
                        if(progress<=.001F){data.phase=Phase.DRY;tickets(level,false);data.setDirty();}
                    }
                }
            }
        }
        Entity unit=entity(level,data,"prototype");
        if(unit instanceof EvaPrototypeEntity prototype&&!UNAirLiftR29.ownsMotion(level,0))
        {
            if(data.phase==Phase.OPEN&&!EvaBayRepairR33.active(prototype)){prototype.setNervLogisticsLocked(false);prototype.setNoGravity(false);}
            else if(prototype.position().distanceTo(HOME)<4&&!prototype.isVehicle())
            {
                prototype.setNervLogisticsLocked(true);prototype.setNoGravity(true);
                if(prototype.isUmbilicalSevered()||prototype.isEntryPlugInserted()||prototype.getWeapon()!=com.projectseele.entity.EvaUnit01Entity.WEAPON_FISTS)
                    prototype.enterHangarStandby();
            }
        }
    }
    private static void powerAndDefense(ServerLevel level,State data)
    {
        BlockPos basePower=new BlockPos(6360,75,-6038),portPower=new BlockPos(1330,69,474);
        if(level.hasChunkAt(basePower)) { boolean present=level.getBlockState(basePower).is(Blocks.IRON_BLOCK);if(present!=data.baseGenerator){data.baseGenerator=present;data.setDirty();} }
        if(level.hasChunkAt(portPower)) { boolean present=level.getBlockState(portPower).is(Blocks.IRON_BLOCK);if(present!=data.portGenerator){data.portGenerator=present;data.setDirty();} }
        for(var entry:data.entities.entrySet())
        {
            Entity e=level.getEntity(entry.getValue());if(e==null||!entry.getKey().startsWith("vehicle/"))continue;
            boolean supplied=data.power&&(data.baseGenerator&&e.getX()>6300&&e.getX()<6900&&e.getZ()>-7090&&e.getZ()<-5900
                    ||data.portGenerator&&e.getX()>1200&&e.getX()<1656&&e.getZ()>280&&e.getZ()<640);
            if(supplied)e.getCapability(ForgeCapabilities.ENERGY).ifPresent(storage->storage.receiveEnergy(2000,false));
            if(e.getTags().contains("seele_r07_defense")&&!TvMarineDirectorR50.marineCannonControlledR50(e))
            {
                try { e.getClass().getMethod("setActive",boolean.class).invoke(e,data.defense); }
                catch(ReflectiveOperationException error){throw new IllegalStateException("SBW defense interface changed",error);}
            }
        }
    }
    /** Explicit one-time commissioning; saved UUIDs are never replaced because a chunk is unloaded. */
    public static JsonObject commission(ServerLevel level)
    {
        JsonObject plan=plan(level);if(plan==null)throw new IllegalStateException("Missing R07 installation plan");
        return commissionSpecs(level,plan.getAsJsonArray("entities"),false);
    }
    /** Explicit expansion of the same saved fleet; unloaded UUIDs are retained. */
    public static JsonObject reinforce(ServerLevel level,JsonArray additions)
    {
        if(!state(level).commissioned)throw new IllegalStateException("Original base not commissioned");
        return commissionSpecs(level,additions,true);
    }
    private static JsonObject commissionSpecs(ServerLevel level,JsonArray specifications,boolean addition)
    {
        State state=state(level);if(state.commissioned&&!addition)throw new IllegalStateException("R07 already commissioned; inspect saved identities");
        JsonArray receipts=new JsonArray();
        for(var item:specifications)
        {
            JsonObject spec=item.getAsJsonObject();String key=spec.get("key").getAsString();var pos=spec.getAsJsonArray("position");
            if(state.entities.containsKey(key))
            {
                JsonObject retained=new JsonObject();retained.addProperty("key",key);retained.addProperty("uuid",state.entities.get(key).toString());retained.addProperty("retained",true);receipts.add(retained);continue;
            }
            Vec3 point=new Vec3(pos.get(0).getAsDouble(),pos.get(1).getAsDouble(),pos.get(2).getAsDouble());
            level.getChunk(BlockPos.containing(point));
            var id=new ResourceLocation(spec.get("id").getAsString());
            if(!BuiltInRegistries.ENTITY_TYPE.containsKey(id))throw new IllegalStateException("Missing installed vehicle "+id);
            Entity e=BuiltInRegistries.ENTITY_TYPE.get(id).create(level);if(e==null)throw new IllegalStateException("Cannot create "+id);
            CompoundTag tag=new CompoundTag();e.saveWithoutId(tag);tag.putBoolean("GearUp",false);tag.putFloat("ServerYaw",spec.get("yaw").getAsFloat());
            if(id.getNamespace().equals("superbwarfare"))
            {
                for(String health:new String[]{"Health","TurretHealth","LeftWheelHealth","RightWheelHealth","MainEngineHealth","SubEngineHealth"})tag.remove(health);
                try { tag.putInt("Energy",((Number)e.getClass().getMethod("getMaxEnergy").invoke(e)).intValue()); }
                catch(ReflectiveOperationException error){throw new IllegalStateException("SBW energy interface changed",error);}
                ResourceLocation ammo=new ResourceLocation("superbwarfare:creative_ammo_box");
                if(!BuiltInRegistries.ITEM.containsKey(ammo))throw new IllegalStateException("SBW supply item unavailable");
                tag.remove("Inventory");ListTag items=new ListTag();CompoundTag box=new ItemStack(BuiltInRegistries.ITEM.get(ammo)).save(new CompoundTag());box.putByte("Slot",(byte)0);items.add(box);tag.put("Items",items);
            }
            e.load(tag);e.moveTo(point.x,point.y,point.z,spec.get("yaw").getAsFloat(),0);e.addTag("seele_r07_owned");
            if(addition)
            {
                for(int cx=(int)Math.floor(e.getBoundingBox().minX-2)>>4;cx<=(int)Math.floor(e.getBoundingBox().maxX+2)>>4;cx++)
                    for(int cz=(int)Math.floor(e.getBoundingBox().minZ-2)>>4;cz<=(int)Math.floor(e.getBoundingBox().maxZ+2)>>4;cz++)level.getChunk(cx,cz);
                if(!level.noCollision(e))throw new IllegalStateException("New vehicle intersects a block or existing vehicle: "+key+" "+point);
                if(level.getBlockState(BlockPos.containing(point.add(0,-.05,0))).getCollisionShape(level,BlockPos.containing(point.add(0,-.05,0))).isEmpty())
                    throw new IllegalStateException("New vehicle pad has no support: "+key);
                e.addTag("seele_r23_readiness");
            }
            if(spec.has("role")&&spec.get("role").getAsString().equals("defense"))
            {
                UUID ownerId=state.entities.get("owner/"+key);
                if(ownerId==null)
                {
                    ArmorStand owner=EntityType.ARMOR_STAND.create(level);if(owner==null)throw new IllegalStateException("Defense control node");
                    CompoundTag marker=new CompoundTag();marker.putBoolean("Marker",true);marker.putBoolean("Invisible",true);marker.putBoolean("Invulnerable",true);marker.putBoolean("NoGravity",true);owner.load(marker);
                    owner.setPos(point.x,point.y-1,point.z);owner.setSilent(true);owner.addTag("seele_r07_control_node");level.addFreshEntity(owner);ownerId=owner.getUUID();state.entities.put("owner/"+key,ownerId);state.setDirty();
                }
                CompoundTag owned=e.saveWithoutId(new CompoundTag());owned.putUUID("Owner",ownerId);owned.putBoolean("Active",true);e.load(owned);e.setPos(point);e.addTag("seele_r07_defense");
            }
            if(e instanceof EvaPrototypeEntity prototype){prototype.setNervLogisticsLocked(true);prototype.setNoGravity(true);prototype.setNoAi(true);}
            if(!level.addFreshEntity(e))throw new IllegalStateException("Rejected R07 entity "+key);
            state.entities.put(key,e.getUUID());JsonObject row=new JsonObject();row.addProperty("key",key);row.addProperty("type",id.toString());row.addProperty("uuid",e.getStringUUID());receipts.add(row);state.setDirty();
        }
        state.commissioned=true;state.setDirty();JsonObject report=new JsonObject();report.add("entities",receipts);report.addProperty("phase",state.phase.name());return report;
    }
}
