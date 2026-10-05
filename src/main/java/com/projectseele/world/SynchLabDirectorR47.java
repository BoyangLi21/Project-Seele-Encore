package com.projectseele.world;

import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import com.projectseele.capability.EvaPilotCapability;
import com.projectseele.capability.EvaPilotData;
import com.projectseele.capability.EvaPilotProvider;
import com.projectseele.entity.EntryPlugCarrierEntity;
import com.projectseele.entity.NervStaffEntity;
import com.projectseele.entity.TrainingPilotEntity;
import com.projectseele.registry.ModEntities;
import net.minecraft.core.BlockPos;
import net.minecraft.commands.Commands;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.nbt.Tag;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.server.level.TicketType;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.properties.BlockStateProperties;
import net.minecraft.world.level.saveddata.SavedData;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.minecraft.world.level.ClipContext;
import net.minecraft.world.phys.HitResult;
import net.minecraftforge.event.AttachCapabilitiesEvent;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.event.RegisterCommandsEvent;
import net.minecraftforge.event.entity.EntityMountEvent;
import net.minecraftforge.event.entity.player.PlayerInteractEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.Files;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;
import java.util.WeakHashMap;

/** Two independently owned laboratory capsules. Measurements never modify pilot progress. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class SynchLabDirectorR47
{
    private static final int TEST_TICKS=240, TRAVEL_TICKS=40;
    private static final float TEST_DEPTH=1.8F;
    private record Plan(int slot,int variant,Vec3 anchor,BlockPos console,BlockPos lever,Vec3 exit) {}
    private static final Map<ServerLevel,List<Plan>> PLANS=new WeakHashMap<>();
    private static final Map<ServerLevel,Map<Integer,Integer>> ATTACH_AGE=new WeakHashMap<>();
    private record ResearchRequest(UUID caller,UUID technician,boolean abort,long expires) {}
    private static final Map<ServerLevel,Map<Integer,ResearchRequest>> RESEARCH_REQUESTS=new WeakHashMap<>();
    private static final TicketType<ChunkPos> TICKET=TicketType.create("synch_lab_r47",Comparator.comparingLong(ChunkPos::toLong),100);

    private static final class Slot
    {
        UUID capsule,operator,subject,technician,pendingExit;
        UUID lastSubject;
        String subjectName="";
        String phase="IDLE",failure="";
        boolean materialized,completed,exitRequested;
        int age,samples;
        float depth,returnFrom,last,min,max;
        double sum;
        CompoundTag extra=new CompoundTag();
    }
    private static final class State extends SavedData
    {
        final Map<Integer,Slot> slots=new HashMap<>();
        private CompoundTag extra=new CompoundTag();
        static State load(CompoundTag tag)
        {
            if(tag.getInt("Version")!=1)throw new IllegalStateException("Unknown independent synchronization laboratory state");
            var state=new State();state.extra=tag.copy();var identities=new java.util.HashSet<UUID>();
            for(var raw:tag.getList("Slots",Tag.TAG_COMPOUND))
            {
                var row=(CompoundTag)raw;int index=row.getInt("Slot");
                if(index<0||index>1||state.slots.containsKey(index))throw new IllegalStateException("Duplicate/foreign laboratory slot");
                var s=new Slot();s.extra=row.copy();
                if(row.hasUUID("Capsule"))s.capsule=row.getUUID("Capsule");if(row.hasUUID("Operator"))s.operator=row.getUUID("Operator");if(row.hasUUID("Subject"))s.subject=row.getUUID("Subject");
                if(row.hasUUID("Technician"))s.technician=row.getUUID("Technician");
                if(row.hasUUID("PendingExit"))s.pendingExit=row.getUUID("PendingExit");
                if(s.capsule!=null&&!identities.add(s.capsule))throw new IllegalStateException("Laboratory slots must retain distinct capsule UUIDs");
                if(row.hasUUID("LastSubject"))s.lastSubject=row.getUUID("LastSubject");s.subjectName=row.getString("SubjectName");
                s.phase=row.getString("Phase");s.failure=row.getString("Failure");s.materialized=row.getBoolean("Materialized");s.completed=row.getBoolean("Completed");
                s.exitRequested=row.getBoolean("ExitRequested");s.age=Math.max(0,row.getInt("Age"));s.samples=Math.max(0,row.getInt("Samples"));
                s.depth=row.getFloat("Depth");s.returnFrom=row.getFloat("ReturnFrom");s.last=row.getFloat("Last");s.min=row.getFloat("Min");s.max=row.getFloat("Max");s.sum=row.getDouble("Sum");
                if(!List.of("IDLE","SEALING","LOWERING","TESTING","RAISING","OPENING","HOLD").contains(s.phase)
                        ||!Float.isFinite(s.depth)||s.depth<0||s.depth>TEST_DEPTH||!Float.isFinite(s.returnFrom)||s.returnFrom<0||s.returnFrom>TEST_DEPTH
                        ||s.samples>TEST_TICKS/10||!Float.isFinite(s.last)||!Float.isFinite(s.min)||!Float.isFinite(s.max)||!Double.isFinite(s.sum))
                    throw new IllegalStateException("Invalid laboratory progress; retain original state and capsule identity");
                state.slots.put(index,s);
            }
            return state;
        }
        @Override public CompoundTag save(CompoundTag tag)
        {
            for(var key:extra.getAllKeys())tag.put(key,extra.get(key).copy());tag.putInt("Version",1);var rows=new ListTag();
            slots.forEach((index,s)->{
                var row=s.extra.copy();row.putInt("Slot",index);if(s.capsule!=null)row.putUUID("Capsule",s.capsule);
                if(s.operator!=null)row.putUUID("Operator",s.operator);else row.remove("Operator");
                if(s.subject!=null)row.putUUID("Subject",s.subject);else row.remove("Subject");
                if(s.technician!=null)row.putUUID("Technician",s.technician);else row.remove("Technician");
                if(s.pendingExit!=null)row.putUUID("PendingExit",s.pendingExit);else row.remove("PendingExit");
                if(s.lastSubject!=null)row.putUUID("LastSubject",s.lastSubject);row.putString("SubjectName",s.subjectName);
                row.putString("Phase",s.phase);row.putString("Failure",s.failure);row.putBoolean("Materialized",s.materialized);row.putBoolean("Completed",s.completed);
                row.putBoolean("ExitRequested",s.exitRequested);row.putInt("Age",s.age);row.putInt("Samples",s.samples);row.putFloat("Depth",s.depth);row.putFloat("ReturnFrom",s.returnFrom);
                row.putFloat("Last",s.last);row.putFloat("Min",s.min);row.putFloat("Max",s.max);row.putDouble("Sum",s.sum);rows.add(row);
            });tag.put("Slots",rows);return tag;
        }
    }
    private static State state(ServerLevel level)
    {return level.getDataStorage().computeIfAbsent(State::load,State::new,"projectseele_synch_lab_r47");}
    public static String staffReportR47(ServerPlayer player,int slot)
    {
        if(!NervStaffDialogue.authorized(player))return "实验记录请由值班操作员确认。";
        var known=player.serverLevel().getDataStorage().get(State::load,"projectseele_synch_lab_r47");
        var s=known==null?null:known.slots.get(slot);
        if(s!=null&&s.phase.equals("HOLD"))return "实验设备已暂停，请由实验班确认实际状态。";
        if(s!=null&&!s.phase.equals("IDLE"))return "本槽实验仍在进行。请保持连接，等设备返回并开盖后再离舱。";
        if(s==null||s.samples==0)return "本槽还没有完整读取记录。请实际进舱，再用 /nerv synch start 联络本槽实验技师。";
        if(!s.completed)return "上次测试已经中止，没有记为完整测量。";
        return String.format(Locale.ROOT,"本槽最近记录：%s，同步率 %.1f%%，读取均值 %.1f%%。",s.subjectName,s.last,s.sum/s.samples);
    }

    private static Vec3 vec(com.google.gson.JsonArray a)
    {return new Vec3(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble());}
    private static List<Plan> plans(ServerLevel level)
    {
        return PLANS.computeIfAbsent(level,l->{
            var file=l.getServer().getWorldPath(LevelResource.ROOT).resolve("r47_synch_lab.json");if(!Files.isRegularFile(file))return List.of();
            try
            {
                var root=JsonParser.parseString(Files.readString(file)).getAsJsonObject();
                if(!"projectseele.r47.synch-lab.v1".equals(root.get("schema").getAsString())||!l.dimension().location().toString().equals(root.get("dimension").getAsString()))throw new IllegalStateException("Foreign synchronization laboratory plan");
                var result=new java.util.ArrayList<Plan>();var seen=new java.util.HashSet<Integer>();
                for(var raw:root.getAsJsonArray("slots"))
                {
                    var row=raw.getAsJsonObject();int slot=row.get("slot").getAsInt();var anchor=vec(row.getAsJsonArray("anchor"));var exit=vec(row.getAsJsonArray("exit"));
                    if(slot<0||slot>1||row.get("variant").getAsInt()!=0||!seen.add(slot)||!Double.isFinite(anchor.x+anchor.y+anchor.z+exit.x+exit.y+exit.z))throw new IllegalStateException("Incomplete laboratory slot geometry");
                    result.add(new Plan(slot,row.get("variant").getAsInt(),anchor,BlockPos.containing(vec(row.getAsJsonArray("console"))),BlockPos.containing(vec(row.getAsJsonArray("lever"))),exit));
                }
                if(result.size()!=2)throw new IllegalStateException("Laboratory requires exactly two independent slots");return List.copyOf(result);
            }
            catch(Exception failure){throw new IllegalStateException("Laboratory plan unavailable; never substitute a canonical EVA capsule",failure);}
        });
    }
    private static RigidTransform dock(Plan p)
    {
        double angle=Math.toRadians(25);
        return RigidTransform.fromAxes(p.anchor,new Vec3(1,0,0),new Vec3(0,Math.cos(angle),-Math.sin(angle)),new Vec3(0,Math.sin(angle),Math.cos(angle)));
    }
    private static void retain(ServerLevel level,Plan p)
    {var chunk=new ChunkPos(BlockPos.containing(p.anchor));level.getChunkSource().addRegionTicket(TICKET,chunk,2,chunk);level.getChunkSource().getChunkFuture(chunk.x,chunk.z,net.minecraft.world.level.chunk.ChunkStatus.FULL,true);}
    private static EntryPlugCarrierEntity capsule(ServerLevel level,Slot s)
    {return s.capsule!=null&&level.getEntity(s.capsule) instanceof EntryPlugCarrierEntity cap?cap:null;}
    private static boolean clearExit(ServerLevel level,Plan p,LivingEntity subject)
    {
        var feet=BlockPos.containing(p.exit);if(!level.hasChunkAt(feet))return false;
        var support=level.getBlockState(feet.below()).getCollisionShape(level,feet.below());
        if(support.isEmpty()||Math.abs(feet.below().getY()+support.max(net.minecraft.core.Direction.Axis.Y)-p.exit.y)>.001)return false;
        if(!level.getFluidState(feet).isEmpty()||!level.getFluidState(feet.above()).isEmpty())return false;
        return subject==null?level.getBlockState(feet).getCollisionShape(level,feet).isEmpty()&&level.getBlockState(feet.above()).getCollisionShape(level,feet.above()).isEmpty()
                :level.noCollision(subject,subject.getDimensions(net.minecraft.world.entity.Pose.STANDING).makeBoundingBox(p.exit));
    }
    private static boolean returnedDock(ServerLevel level,Plan p,Slot s,EntryPlugCarrierEntity cap)
    {
        return cap.isAlive()&&cap.laboratorySlotR47()==p.slot&&cap.getLinkedEva()==null&&cap.getUUID().equals(s.capsule)
                &&s.depth<=.0001F&&cap.position().distanceTo(p.anchor)<.05&&cap.isHatchOpen()
                &&(s.phase.equals("IDLE")||s.phase.equals("OPENING"));
    }
    /** Root carrier calls after real passenger removal; placement waits until vanilla stopRiding returns. */
    public static boolean passengerRemovedR47(EntryPlugCarrierEntity cap,Entity actor)
    {
        if(!(cap.level() instanceof ServerLevel level)||!(actor instanceof LivingEntity living)
                ||actor.level()!=level||!living.isAlive()||cap.laboratorySlotR47()<0)return false;
        var p=plans(level).stream().filter(row->row.slot==cap.laboratorySlotR47()).findFirst().orElse(null);
        var state=state(level);var s=p==null?null:state.slots.get(p.slot);
        if(s==null||!cap.getUUID().equals(s.capsule))return false;
        if(s.pendingExit!=null&&!s.pendingExit.equals(actor.getUUID()))return false;
        s.pendingExit=actor.getUUID();state.setDirty();return true;
    }
    private static void landPendingExit(ServerLevel level,Plan p,State state,Slot s,EntryPlugCarrierEntity cap)
    {
        if(s.pendingExit==null)return;
        Entity actor=level.getEntity(s.pendingExit);
        if(actor==null)actor=level.getServer().getPlayerList().getPlayer(s.pendingExit);
        if(actor==null)return; // Retain the exact original UUID while its sections/player are absent.
        if(!(actor instanceof LivingEntity living)||actor.level()!=level||!living.isAlive()
                ||actor.getVehicle()!=null||actor.position().distanceToSqr(cap.position())>16*16)
        {s.pendingExit=null;state.setDirty();return;} // Never pull a moved/remounted actor back to a lab.
        if(!returnedDock(level,p,s,cap)||!clearExit(level,p,living))return;
        // Native ServerPlayer overrides dismountTo with its connection sync.
        // This is the same returned fixture's validated dry exit, not an actor
        // transport, canonical EVA relocation or fake standby transition.
        living.dismountTo(p.exit.x,p.exit.y,p.exit.z);
        living.setDeltaMovement(Vec3.ZERO);living.resetFallDistance();living.setInvisible(false);
        if(living.position().distanceToSqr(p.exit)>.000001)return;
        s.pendingExit=null;state.setDirty();
    }
    private static void note(ServerLevel level,Slot s,Component line)
    {
        for(var player:level.players())if(player.getUUID().equals(s.operator)||player.getUUID().equals(s.subject))player.sendSystemMessage(line);
    }
    private static void raising(State state,Slot s,String reason,boolean exit)
    {
        if(s.phase.equals("RAISING")||s.phase.equals("OPENING"))
        {s.exitRequested|=exit;state.setDirty();return;}
        s.completed=false;s.failure=reason;s.exitRequested|=exit;s.returnFrom=s.depth;s.phase="RAISING";s.age=0;state.setDirty();
    }
    private static EntryPlugCarrierEntity ensure(ServerLevel level,Plan p,State state,Slot s)
    {
        var cap=capsule(level,s);
        if(cap!=null)
        {
            if(cap.laboratorySlotR47()!=p.slot||cap.getLinkedEva()!=null){s.phase="HOLD";s.failure="实验栓识别不一致";state.setDirty();return null;}
            return cap;
        }
        if(s.materialized)return null; // Unloaded or removed original is never a replacement permit.
        if(!level.hasChunkAt(BlockPos.containing(p.anchor))||!clearExit(level,p,null))return null;
        var age=ATTACH_AGE.computeIfAbsent(level,l->new HashMap<>());int ticks=age.merge(p.slot,1,Integer::sum);if(ticks<100)return null;
        var originals=level.getEntitiesOfClass(EntryPlugCarrierEntity.class,new AABB(p.anchor,p.anchor).inflate(48),e->e.laboratorySlotR47()==p.slot);
        if(originals.size()>1){s.phase="HOLD";s.failure="实验槽存在重复登记";state.setDirty();return null;}
        if(!originals.isEmpty())
        {
            cap=originals.get(0);if(cap.getLinkedEva()!=null)return null;s.capsule=cap.getUUID();s.materialized=true;state.setDirty();return cap;
        }
        if(s.capsule==null)
        {
            UUID id;boolean taken;
            do{ id=UUID.randomUUID();taken=level.getEntity(id)!=null;for(var other:state.slots.values())if(id.equals(other.capsule))taken=true;}while(taken);
            s.capsule=id;state.setDirty();
        }
        cap=ModEntities.ENTRY_PLUG_CARRIER.get().create(level);if(cap==null)return null;
        cap.setUUID(s.capsule);cap.configureLaboratoryR47(p.slot,p.variant,dock(p));cap.setCustomName(Component.literal("同步实验栓 "+(p.slot+1)));
        if(!level.addFreshEntity(cap))return null;s.materialized=true;state.setDirty();return cap;
    }

    @SubscribeEvent public static void attach(AttachCapabilitiesEvent<Entity> event)
    {
        if(event.getObject() instanceof TrainingPilotEntity&&!event.getCapabilities().containsKey(EvaPilotProvider.ID))
            event.addCapability(EvaPilotProvider.ID,new EvaPilotProvider());
    }
    private static NervStaffEntity technician(ServerLevel level,Plan p,UUID expected)
    {
        String id="r47/experiment/researcher_"+p.slot;
        UUID registered=NervStaffSavedData.get(level).identity(id);
        if(registered==null||expected!=null&&!expected.equals(registered)
                ||!level.hasChunkAt(p.lever)||!level.hasChunkAt(p.console))return null;
        if(!(level.getEntity(registered) instanceof NervStaffEntity npc)||!npc.isAlive()
                ||npc.getVehicle()!=null||!npc.memberId().equals(id)||npc.busy()
                ||!StaffAuthorityR25.allows(npc,"synch_lab"))return null;
        var post=NervStaffDirector.roster(level).stream().filter(row->row.id().equals(id)).findFirst().orElse(null);
        if(post==null||!post.role().equals("scientist")||!npc.staffRole().equals(post.role()))return null;
        if(!level.getBlockState(p.lever).is(Blocks.LEVER)
                ||npc.getEyePosition().distanceToSqr(Vec3.atCenterOf(p.lever))>9)return null;
        var sight=level.clip(new ClipContext(npc.getEyePosition(),Vec3.atCenterOf(p.lever),
                ClipContext.Block.OUTLINE,ClipContext.Fluid.NONE,npc));
        if(sight.getType()!=HitResult.Type.MISS&&!sight.getBlockPos().equals(p.lever))return null;
        return npc;
    }
    private static String operate(ServerLevel level,Plan p,State state,Slot s,EntryPlugCarrierEntity cap,
                                  ServerPlayer player,boolean abort,UUID technician)
    {
        if(cap.laboratorySlotR47()!=p.slot||cap.getLinkedEva()!=null||s.phase.equals("HOLD"))
            return "本槽实验设备暂不可用，请由实验班核对。";
        if(abort)
        {
            if(s.phase.equals("IDLE"))return "本槽没有正在进行的测试。";
            raising(state,s,"操作员中止测试",true);return "测试已中止，设备返回后开盖。";
        }
        if(!s.phase.equals("IDLE"))return "本槽测试仍在进行，请等待结束，或用 /nerv synch abort 中止。";
        if(!(cap.getFirstPassenger() instanceof LivingEntity subject)||!subject.isAlive()
                ||!subject.getCapability(EvaPilotCapability.DATA).isPresent())
            return "请先由受试者实际坐入本槽实验栓，并确认同步数据连接。";
        s.operator=player.getUUID();s.subject=subject.getUUID();s.lastSubject=subject.getUUID();s.technician=technician;
        s.subjectName=subject.getName().getString();s.phase="SEALING";s.age=0;s.samples=0;s.sum=0;
        s.depth=0;s.completed=false;s.exitRequested=false;s.failure="";
        cap.setLabHatchR47(false);state.setDirty();
        var lever=level.getBlockState(p.lever);if(lever.is(Blocks.LEVER))level.setBlock(p.lever,lever.setValue(BlockStateProperties.POWERED,true),3);
        note(level,s,Component.translatable("msg.projectseele.synch_test_run"));return "开始关盖，随后进行十二秒同步测量。";
    }
    private static String requestResearch(ServerPlayer player,boolean abort)
    {
        if(!player.serverLevel().dimension().equals(FacilitySchemaV2.DIMENSION))return "请在原实验区的登记实验栓中请求测试。";
        if(!NervStaffDialogue.authorized(player))return "同步实验需要NERV通行权限。";
        if(!(player.getVehicle() instanceof EntryPlugCarrierEntity cap)||cap.getFirstPassenger()!=player
                ||cap.laboratorySlotR47()<0||cap.getLinkedEva()!=null)
            return "请本人实际坐入原登记实验栓后，再联络本槽实验技师。";
        var level=player.serverLevel();var p=plans(level).stream().filter(row->row.slot==cap.laboratorySlotR47()).findFirst().orElse(null);
        var state=state(level);var s=p==null?null:state.slots.get(p.slot);
        if(s==null||s.capsule==null||!s.capsule.equals(cap.getUUID())||s.phase.equals("HOLD"))
            return "原实验栓身份尚未接通，未请求替代设备。";
        if(s.pendingExit!=null)return "前一位受试者仍在安全离舱流程，请先完成离舱。";
        if(!player.getCapability(EvaPilotCapability.DATA).isPresent())return "本人同步数据未接通，请由实验班核对后再测试。";
        if(abort&&s.phase.equals("IDLE"))return "本槽没有正在进行的测试。";
        if(abort&&(s.phase.equals("RAISING")||s.phase.equals("OPENING")))return "设备已在返回开盖流程，请等待安全离舱。";
        if(!abort&&!s.phase.equals("IDLE"))return "本槽测试仍在进行，请等待结束，或用 /nerv synch abort 中止。";
        var npc=technician(level,p,null);
        if(npc==null)return "本槽原登记实验技师未接通、已离开控制台或无操作职责，测试请求未执行。";
        var requests=RESEARCH_REQUESTS.computeIfAbsent(level,key->new HashMap<>());
        if(requests.containsKey(p.slot)||npc.activity()==2)return "实验技师正在操作，请等本次按键完成。";
        requests.put(p.slot,new ResearchRequest(player.getUUID(),npc.getUUID(),abort,level.getGameTime()+100));
        return "["+npc.getName().getString()+"] 收到。我在本槽控制台"+(abort?"中止测试，请等待设备返回。":"启动测试，请留在舱内。");
    }
    private static void researchTick(ServerLevel level,Plan p,State state,Slot s,EntryPlugCarrierEntity cap)
    {
        var requests=RESEARCH_REQUESTS.get(level);var request=requests==null?null:requests.get(p.slot);if(request==null)return;
        var caller=level.getServer().getPlayerList().getPlayer(request.caller);
        var npc=technician(level,p,request.technician);
        if(cap==null||s.phase.equals("HOLD")||level.getGameTime()>request.expires
                ||caller==null||caller.serverLevel()!=level||caller.getVehicle()!=cap||cap.getFirstPassenger()!=caller
                ||!NervStaffDialogue.authorized(caller)||npc==null||!cap.getUUID().equals(s.capsule)
                ||request.abort&&s.phase.equals("IDLE")||!request.abort&&!s.phase.equals("IDLE"))
        {
            requests.remove(p.slot);
            if(level.getEntity(request.technician) instanceof NervStaffEntity previous
                    &&!previous.busy()&&previous.pressTarget().equals(p.lever))previous.finishTask();
            if(caller!=null)caller.sendSystemMessage(Component.literal("实验请求已取消：原技师、实际乘坐关系或权限已变化。"));
            return;
        }
        npc.getNavigation().stop();
        npc.getLookControl().setLookAt(p.lever.getX()+.5,p.lever.getY()+.5,p.lever.getZ()+.5);
        float facing=(float)Math.toDegrees(Math.atan2(-(p.lever.getX()+.5-npc.getX()),p.lever.getZ()+.5-npc.getZ()));
        npc.setYRot(net.minecraft.util.Mth.approachDegrees(npc.getYRot(),facing,18));npc.yBodyRot=npc.getYRot();npc.setYHeadRot(npc.getYRot());
        if(Math.abs(net.minecraft.util.Mth.wrapDegrees(facing-npc.getYRot()))>12)return;
        if(!npc.beginPressGesture(p.lever))return;
        requests.remove(p.slot);
        // The original researcher reaches the real lever, completes its existing
        // press gesture, and uses the same vanilla hardware/server dispatcher.
        npc.pressing();
        var hardware=level.getBlockState(p.lever);
        hardware.use(level,caller,InteractionHand.MAIN_HAND,new net.minecraft.world.phys.BlockHitResult(
                Vec3.atCenterOf(p.lever),net.minecraft.core.Direction.UP,p.lever,false));
        caller.sendSystemMessage(Component.literal("["+npc.getName().getString()+"] "+operate(level,p,state,s,cap,caller,request.abort,npc.getUUID())));
        npc.finishTask();
    }
    @SubscribeEvent public static void commands(RegisterCommandsEvent event)
    {
        event.getDispatcher().register(Commands.literal("nerv").then(Commands.literal("synch")
                .then(Commands.literal("start").executes(context->{var player=context.getSource().getPlayerOrException();
                    player.sendSystemMessage(Component.literal(requestResearch(player,false)));return 1;}))
                .then(Commands.literal("abort").executes(context->{var player=context.getSource().getPlayerOrException();
                    player.sendSystemMessage(Component.literal(requestResearch(player,true)));return 1;}))));
    }
    @SubscribeEvent public static void use(PlayerInteractEvent.RightClickBlock event)
    {
        if(event.getHand()!=InteractionHand.MAIN_HAND||!(event.getEntity() instanceof ServerPlayer player)||!(event.getLevel() instanceof ServerLevel level))return;
        if(!level.dimension().equals(FacilitySchemaV2.DIMENSION))return;
        for(var p:plans(level))if(event.getPos().equals(p.console)||event.getPos().equals(p.lever))
        {
            event.setCanceled(true);event.setCancellationResult(InteractionResult.SUCCESS);
            if(!NervStaffDialogue.authorized(player)||player.distanceToSqr(Vec3.atCenterOf(event.getPos()))>36)
            {player.sendSystemMessage(Component.literal("同步实验操作需要NERV通行权限，请在本槽控制台前操作。"));return;}
            var state=state(level);var s=state.slots.computeIfAbsent(p.slot,k->new Slot());var cap=capsule(level,s);
            if(cap==null){player.sendSystemMessage(Component.literal(s.materialized?"原实验栓信号尚未接通，请由实验班核对设备状态。":"实验栓正在接入。请等待设备就位，再由受试者实际进舱。"));return;}
            player.sendSystemMessage(Component.literal(operate(level,p,state,s,cap,player,!s.phase.equals("IDLE"),null)));return;
        }
    }
    public static void requestExit(ServerPlayer player)
    {
        if(!(player.getVehicle() instanceof EntryPlugCarrierEntity cap)||cap.laboratorySlotR47()<0||cap.getLinkedEva()!=null)return;
        var level=player.serverLevel();var state=state(level);var s=state.slots.get(cap.laboratorySlotR47());
        if(s==null||!cap.getUUID().equals(s.capsule))return;
        if(s.phase.equals("IDLE")){s.subject=player.getUUID();s.operator=player.getUUID();s.phase="OPENING";s.exitRequested=true;s.completed=false;s.depth=0;state.setDirty();}
        else raising(state,s,"受试者请求离舱",true);
        player.sendSystemMessage(Component.literal("设备复位开盖后，将从干燥侧台离舱。"));
    }
    @SubscribeEvent public static void dismount(EntityMountEvent event)
    {
        if(!(event.getEntityBeingMounted() instanceof EntryPlugCarrierEntity cap)||cap.laboratorySlotR47()<0||cap.getLinkedEva()!=null||!(cap.level() instanceof ServerLevel level))return;
        var state=state(level);var s=state.slots.get(cap.laboratorySlotR47());
        var p=plans(level).stream().filter(plan->plan.slot==cap.laboratorySlotR47()).findFirst().orElse(null);
        if(s==null||p==null||!cap.getUUID().equals(s.capsule))
        {event.setCanceled(true);return;}
        if(event.isMounting())
        {
            if(s.pendingExit!=null)event.setCanceled(true);
            return;
        }
        var actor=event.getEntityMounting();
        boolean safe=returnedDock(level,p,s,cap)&&actor instanceof LivingEntity living&&clearExit(level,p,living);
        if(!safe)
        {
            event.setCanceled(true);
            if(actor instanceof ServerPlayer player)requestExit(player);
            else raising(state,s,"受试者离舱请求",true);
        }
    }
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(event.phase!=TickEvent.Phase.END)return;var level=event.getServer().getLevel(FacilitySchemaV2.DIMENSION);if(level==null)return;
        var plans=plans(level);if(plans.isEmpty())return;var state=state(level);
        for(var p:plans)
        {
            var s=state.slots.computeIfAbsent(p.slot,k->new Slot());
            boolean nearby=level.players().stream().anyMatch(player->player.position().distanceTo(p.anchor)<96);
            if(!nearby&&s.phase.equals("IDLE")&&s.pendingExit==null)continue;retain(level,p);
            var cap=ensure(level,p,state,s);
            researchTick(level,p,state,s,cap);
            if(cap==null||s.phase.equals("HOLD"))continue;
            landPendingExit(level,p,state,s,cap);
            var subject=cap.getFirstPassenger() instanceof LivingEntity living?living:null;
            if(s.phase.equals("IDLE"))
            {
                cap.laboratoryMotionR47(0);cap.setLabHatchR47(true);
                if(subject==null&&cap.getInsertionStage()!=EntryPlugCarrierEntity.STAGE_SUSPENDED)cap.configureLaboratoryR47(p.slot,p.variant,dock(p));
                continue;
            }
            if(!s.phase.equals("RAISING")&&!s.phase.equals("OPENING")
                    &&(subject==null||!subject.isAlive()||s.subject==null||!s.subject.equals(subject.getUUID())||!subject.getCapability(EvaPilotCapability.DATA).isPresent()))
            {raising(state,s,"同步连接中断",true);note(level,s,Component.literal("同步连接中断，测试停止。设备正在返回。"));}
            if(s.technician!=null&&!s.phase.equals("RAISING")&&!s.phase.equals("OPENING")
                    &&technician(level,p,s.technician)==null)
            {raising(state,s,"实验技师离开控制台或操作权限变化",true);note(level,s,Component.literal("本槽实验技师已离开控制台或失去操作职责，测量停止，设备正在安全返回。"));}
            s.age++;
            switch(s.phase)
            {
                case "SEALING"->{cap.setLabHatchR47(false);if(cap.isHatchFullySealed()){s.phase="LOWERING";s.age=0;}}
                case "LOWERING"->{s.depth=TEST_DEPTH*Math.min(1,s.age/(float)TRAVEL_TICKS);cap.laboratoryMotionR47(s.depth);if(s.age>=TRAVEL_TICKS){s.phase="TESTING";s.age=0;}}
                case "TESTING"->{
                    cap.laboratoryMotionR47(TEST_DEPTH);
                    if(s.age%10==0)
                    {
                        float value=subject instanceof Player player?EvaPilotCapability.synchronization(player):subject.getCapability(EvaPilotCapability.DATA).map(EvaPilotData::synchronization).orElse(Float.NaN);
                        if(!Float.isFinite(value)){raising(state,s,"同步数据不可读取",true);break;}
                        if(s.samples==0){s.min=value;s.max=value;}else{s.min=Math.min(s.min,value);s.max=Math.max(s.max,value);}
                        s.last=value;s.sum+=value;s.samples++;
                    }
                    if(s.age>=TEST_TICKS){s.completed=s.samples==TEST_TICKS/10;s.returnFrom=s.depth;s.phase="RAISING";s.age=0;}
                }
                case "RAISING"->{s.depth=s.returnFrom*(1-Math.min(1,s.age/(float)TRAVEL_TICKS));cap.laboratoryMotionR47(s.depth);if(s.age>=TRAVEL_TICKS){s.depth=0;s.phase="OPENING";s.age=0;}}
                case "OPENING"->{
                    cap.laboratoryMotionR47(0);cap.setLabHatchR47(true);
                    if(!cap.isHatchOpen()||subject!=null&&!clearExit(level,p,subject))break;
                    if(subject!=null)
                    {
                        subject.stopRiding();
                        if(subject.getVehicle()==null)passengerRemovedR47(cap,subject);
                    }
                    if(cap.getFirstPassenger()!=null)break;
                    landPendingExit(level,p,state,s,cap);
                    if(s.pendingExit!=null)break;
                    if(s.completed)note(level,s,Component.translatable("msg.projectseele.synch_test_result",String.format(Locale.ROOT,"实验槽%d · %s：%.1f%%（读取均值 %.1f%%）",p.slot+1,s.subjectName,s.last,s.sum/s.samples)));
                    else note(level,s,Component.literal("测试已停止，设备复位。请从干燥侧台离开。"));
                    var lever=level.getBlockState(p.lever);if(lever.is(Blocks.LEVER))level.setBlock(p.lever,lever.setValue(BlockStateProperties.POWERED,false),3);
                    cap.configureLaboratoryR47(p.slot,p.variant,dock(p));s.phase="IDLE";s.age=0;s.subject=null;s.operator=null;
                }
                default->{}
            }
            state.setDirty();
        }
    }
    private SynchLabDirectorR47(){}
}
