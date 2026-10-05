package com.projectseele.world;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.EntryPlugCarrierEntity;
import com.projectseele.entity.NervStaffEntity;
import com.projectseele.network.ClientboundStaffConversationPacket;
import com.projectseele.network.SeeleNetwork;
import net.minecraft.core.BlockPos;
import net.minecraft.network.chat.Component;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.*;
import net.minecraft.world.level.ChunkPos;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.network.PacketDistributor;
import java.util.*;

/** The conversation owns no machinery: it forwards validated requests to posted personnel. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID)
public final class StaffConversationR24
{
    private static final class Session
    {
        final UUID nonce = UUID.randomUUID(), actor;
        final ServerLevel level;
        final boolean radio;
        long lastAction = -100, lastRefresh = -100;
        long requestWindow = -100;
        int requestCount;
        String reply;
        int pilotContact=-1;
        UUID coordinationInstance;
        Session(NervStaffEntity npc, boolean radio, String reply)
        { actor = npc.getUUID(); level = (ServerLevel) npc.level(); this.radio = radio; this.reply = reply; }
    }
    private record Pending(String skin, long until) {}
    private static final Map<MinecraftServer, Map<UUID, Session>> SESSIONS = new WeakHashMap<>();
    private static final Map<MinecraftServer, Map<UUID, Pending>> PENDING = new WeakHashMap<>();
    private static final TicketType<ChunkPos> TICKET = TicketType.create("nerv_staff_radio_r24", Comparator.comparingLong(ChunkPos::toLong), 100);

    private static Map<UUID, Session> sessions(ServerPlayer player)
    { return SESSIONS.computeIfAbsent(player.server, key -> new HashMap<>()); }

    public static boolean radioAllowed(ServerPlayer player)
    {
        if (!NervStaffDialogue.authorized(player)) return false;
        if (PilotRestroomServicesR47.fixedPhoneAllowedR47(player)) return true;
        if (player.getInventory().items.stream().anyMatch(s -> s.is(com.projectseele.registry.ModItems.SATELLITE_PHONE.get()))
                || player.getOffhandItem().is(com.projectseele.registry.ModItems.SATELLITE_PHONE.get())) return true;
        if (EvaPilotResolver.controlTarget(player) != null) return true;
        if (player.getVehicle() instanceof EntryPlugCarrierEntity plug
                && !plug.isIndependentUNPlug() && plug.getAssignedVariant() >= 0 && plug.getAssignedVariant() < 3
                && EntryPlugDirector.canonical(player.serverLevel(), plug.getAssignedVariant()) == plug) return true;
        for (int unit = 0; unit < 3; unit++)
        {
            BlockPos control = NervOperationsConsole.staffControl(player.serverLevel(), "prepare", unit);
            if (control != null && player.distanceToSqr(control.getX() + .5, control.getY(), control.getZ() + .5) < 100) return true;
        }
        return false;
    }

    private static boolean available(ServerPlayer player, NervStaffEntity npc, Session session)
    {
        return npc.isAlive() && player.level() == npc.level()
                && (session.radio ? radioAllowed(player) : player.distanceToSqr(npc) <= 100);
    }

    public static void open(ServerPlayer player, NervStaffEntity npc, boolean radio)
    {
        if (player.level() != npc.level() || radio && !radioAllowed(player) || !radio && player.distanceToSqr(npc) > 100) return;
        var session = new Session(npc, radio, StaffDialogueCatalogR24.line(StaffDialogueCatalogR24.profile(npc), npc.staffRole(), "greeting", player.tickCount / 100));
        sessions(player).put(player.getUUID(), session); send(player, npc, session, true);
    }

    private static String role(NervStaffEntity npc)
    {
        if (npc.skin().equals("fuyutsuki")) return "副司令";
        return switch (npc.staffRole())
        {
            case "commander" -> "作战指挥"; case "scientist" -> "技术负责人";
            case "operator" -> "监视操作员"; case "medic" -> "医疗值班";
            case "guard", "un_guard" -> "安保值勤"; case "un_crew" -> "UN 基地勤务";
            default -> "设施技术员";
        };
    }

    private static void send(ServerPlayer player, NervStaffEntity npc, Session session, boolean open)
    {
        List<String> units = new ArrayList<>();
        for (int i = 0; i < 3; i++)
        {
            var state = EvaLogisticsDirector.status(player.serverLevel(), i);
            units.add(NervStaffDialogue.unitName(i) + " · " + NervStaffDialogue.stage(state.phase())
                    + (state.loaded() ? "" : " / 远端信号待接入"));
        }
        var job = StaffCommandBookR24.order(npc);
        String order = job == null ? "" : NervStaffDialogue.unitName(job.unit) + " · " + job.message;
        boolean canCommand = NervStaffDialogue.authorized(player) && StaffAuthorityR25.commandContact(npc);
        if (!canCommand && order.isEmpty()) order = "本次对话可查询信息，出动指令需要相应岗位与通行权限";
        var coordination=CityCoordinationSavedDataR44.get(player.serverLevel());
        boolean current=coordination.active&&session.coordinationInstance!=null&&session.coordinationInstance.equals(coordination.instance);
        List<String> participants=new ArrayList<>();
        if(current)for(int unit=0;unit<5;unit++)
        {
            var binding=coordination.binding(unit);String row=TvSortiesR32.name(unit)+" / 尚未编入";
            if(binding!=null)
            {
                var actual=player.server.getPlayerList().getPlayer(binding.pilot());
                String who=binding.kind().equals("npc")?com.projectseele.entity.TrainingPilotEntity.pilotName(unit):actual==null?"离线驾驶员":actual.getName().getString();
                String role=switch(binding.role()){case "cover"->"掩护";case "shooter"->"射击";default->"支援";};
                row=TvSortiesR32.name(unit)+" / "+who+" / "+role+(coordination.confirmationCurrent(unit)?" / 已确认":" / 待本人确认");
            }
            participants.add(row);
        }
        var packet = new ClientboundStaffConversationPacket(session.nonce, npc.getUUID(), npc.getId(),
                npc.getName().getString(), role(npc), npc.skin(), open, true, canCommand, session.radio,
                session.reply, order, List.copyOf(units),current?coordination.formationRevisionR45:0,
                current?coordination.evidenceRevisionR45:0,List.copyOf(participants));
        SeeleNetwork.CHANNEL.send(PacketDistributor.PLAYER.with(() -> player), packet);
    }

    public static void note(ServerPlayer player, NervStaffEntity npc, String line)
    {
        Session session = sessions(player).get(player.getUUID());
        if (session != null && session.actor.equals(npc.getUUID()) && available(player, npc, session))
        { session.reply = line; send(player, npc, session, false); }
    }

    public static void receive(ServerPlayer player, UUID nonce, String request)
    {
        if (nonce.equals(new UUID(0, 0)) && request.equals("RADIO"))
        { contact(player, "美里"); return; }
        Session session = sessions(player).get(player.getUUID());
        if (session == null || !session.nonce.equals(nonce) || request.length() > 160) return;
        if (request.equals("CLOSE")) { sessions(player).remove(player.getUUID()); return; }
        var entity = session.level.getEntity(session.actor);
        if (!(entity instanceof NervStaffEntity npc) || !available(player, npc, session))
        {
            sessions(player).remove(player.getUUID());
            SeeleNetwork.CHANNEL.send(PacketDistributor.PLAYER.with(() -> player), new ClientboundStaffConversationPacket(
                    nonce, session.actor, -1, "NERV", "", "", false, false, false, session.radio,
                    "对话链路已结束。已经下达的指令仍按原联锁流程执行。", "", List.of()));
            return;
        }
        long tick = player.server.getTickCount();
        if (request.equals("REFRESH"))
        {
            if (tick - session.lastRefresh < 20) return;
            session.lastRefresh = tick; if (session.radio) load(session.level, npc.blockPosition());
            if(session.pilotContact>=0)session.reply=pilotStatus(player,session.pilotContact);
            send(player, npc, session, false); return;
        }
        // Permit ordinary short bursts such as cancel -> new order. Drop
        // excess traffic with a visible reply instead of a dead-looking UI.
        if (tick - session.requestWindow >= 20) { session.requestWindow = tick; session.requestCount = 0; }
        if (++session.requestCount > 8)
        {
            session.reply = "指令输入过快，请稍候再试。已有指令的状态仍显示在上方。";
            if (tick - session.lastAction >= 5) { session.lastAction = tick; send(player, npc, session, false); }
            return;
        }
        session.lastAction = tick;
        if (request.startsWith("CONTACT:"))
        { contact(player, request.substring(8)); return; }
        if(request.startsWith("COORD:"))
        {
            String action=request.substring(6);
            if(action.equals("status"))session.coordinationInstance=CityCoordinationR44.instance(player);
            session.reply=CityCoordinationR44.request(player,npc,action,session.coordinationInstance);
            if(action.equals("start"))session.coordinationInstance=CityCoordinationR44.instance(player);
            send(player,npc,session,false);return;
        }
        if(request.startsWith("ARMEDSORTIE:")||request.startsWith("UNDERGROUND:"))
        {
            try
            {
                String[] parts=request.split(":",-1);
                if(parts.length!=3)throw new IllegalArgumentException();
                int variant=Integer.parseInt(parts[1]);
                boolean armed=parts[0].equals("ARMEDSORTIE");
                if(armed&&(variant!=0&&variant!=2||!Set.of("human","npc").contains(parts[2]))
                        ||!armed&&(variant<0||variant>2||!Set.of("open","close").contains(parts[2])))
                    throw new IllegalArgumentException();
                session.pilotContact=-1;
                var result=armed
                        ?StaffOperationsR48.armedSortie(player,npc,variant,parts[2].equals("npc"))
                        :StaffOperationsR48.undergroundExit(player,npc,variant,parts[2].equals("open"));
                session.reply=result.message();
            }
            catch(IllegalArgumentException error)
            {session.reply="请选择有效的机体、驾驶员和操作。";}
            send(player,npc,session,false);return;
        }
        if (request.equals("WEAPONS"))
        {
            if (!NervStaffDialogue.authorized(player) || !StaffAuthorityR25.allows(npc, "weapons"))
                session.reply = "武器部署由作战指挥下令。";
            else
            {
                var eva = EvaPilotResolver.controlTarget(player);
                var centre = eva == null ? player.position() : eva.position();
                var station = player.serverLevel().getEntitiesOfClass(com.projectseele.entity.NervArmamentStationEntity.class,
                        new net.minecraft.world.phys.AABB(centre,centre).inflate(768,40,768),
                        rack->rack.payloadR47()==com.projectseele.entity.EvaUnit01Entity.WEAPON_RIFLE&&!TvMissionEquipmentR45.missionRack(rack)).stream()
                        .min(Comparator.comparingDouble(rack->rack.position().subtract(centre).horizontalDistanceSqr())).orElse(null);
                session.reply = station != null && station.deploy()
                        ? "就近武器井正在升起，坐标：" + station.blockPosition().toShortString() + "。"
                        : "附近没有可部署的武器井，或武器井已展开。";
            }
            send(player, npc, session, false); return;
        }
        if(request.equals("WEAPONS:shield")||request.equals("WEAPONS:sword"))
        {
            if(!NervStaffDialogue.authorized(player)||!StaffAuthorityR25.allows(npc,"weapons"))session.reply="专用武器井部署请联络作战指挥。";
            else
            {
                boolean shield=request.endsWith("shield");
                int payload=shield?com.projectseele.entity.EvaUnit01Entity.WEAPON_SHIELD_R45:com.projectseele.entity.EvaUnit01Entity.WEAPON_SWORD_R45;
                var station=EquipmentVaultsR47.recordedStationR47(player.serverLevel(),payload);
                String purpose=shield?"零号机专用盾井":"二号机专用长剑井";
                session.reply=station==null?purpose+"信号尚未接通，请稍后查看。"
                        :station.deploy()?purpose+"正在升起，坐标："+station.blockPosition().toShortString()+"。"
                        :station.isReadyAndStocked()?purpose+"已展开，等待对应机体领取。"
                        :!station.isStocked()?purpose+"当前空载，请联系整备部门。":purpose+"仍在进行机械作业，请保持净空。";
            }
            send(player,npc,session,false);return;
        }
        if(request.startsWith("TRANSPORT:"))
        {
            if(!NervStaffDialogue.authorized(player)||!StaffAuthorityR25.commandContact(npc))session.reply="本岗位无权调度运输机，请联络指挥或技术负责人。";
            else try
            {
                String[] parts=request.split(":");
                session.reply=switch(parts[1])
                {
                    case "status" -> NervAirLiftR30.status(player.serverLevel());
                    case "cancel" -> NervAirLiftR30.cancel(player);
                    case "recover" -> NervAirLiftR30.request(player,Integer.parseInt(parts[2]),true,0,0);
                    case "deliver" -> NervAirLiftR30.request(player,Integer.parseInt(parts[2]),false,Integer.parseInt(parts[3]),Integer.parseInt(parts[4]));
                    default -> "请选择运输操作。";
                };
            }
            catch(IllegalArgumentException|IndexOutOfBoundsException error){session.reply="请填写有效的机体编号与整数 X、Z 坐标。";}
            send(player,npc,session,false);return;
        }
        if(request.startsWith("PILOTCHAT:"))
        {
            try
            {
                int unit=Integer.parseInt(request.substring(10));
                if(unit<0||unit>2)return;
                EvaLogisticsDirector.loadControlTarget(player.serverLevel(),unit);
                var pilot=TrainingPilotDirector.existingPilotR45(player.serverLevel(),unit);
                session.pilotContact=-1;
                session.reply=com.projectseele.entity.TrainingPilotEntity.pilotName(unit)+"："
                        +(pilot==null?"频道待接入。":PilotRadioR28.chat(player,pilot));
                send(player,npc,session,false);return;
            }
            catch(NumberFormatException ignored){return;}
        }
        if (request.startsWith("BOARD:") || request.startsWith("PILOT:") || request.startsWith("STANDBY:"))
        {
            try
            {
                int unit = Integer.parseInt(request.substring(request.indexOf(':')+1));
                if (unit < 0 || unit > 2) return;
                if (request.startsWith("BOARD:") || request.startsWith("STANDBY:"))
                {
                    if (!NervStaffDialogue.authorized(player) || !StaffAuthorityR25.allows(npc, "board"))
                        session.reply = "本岗位无权调遣驾驶员，请联络美里、律子或冬月。";
                    else
                    {
                        session.reply = request.startsWith("STANDBY:")
                                ? StaffPilotOrdersR25.returnToStandby(player,npc,unit)
                                : StaffPilotOrdersR25.request(player,npc,unit);
                    }
                }
                else
                {
                    session.pilotContact=unit;session.reply=pilotStatus(player,unit);
                }
                send(player, npc, session, false); return;
            }
            catch (NumberFormatException ignored) { return; }
        }
        session.pilotContact=-1;
        NervStaffDialogue.converse(player, npc, request);
        send(player, npc, session, false);
    }

    private static String pilotStatus(ServerPlayer player,int unit)
    {
        EvaLogisticsDirector.loadControlTarget(player.serverLevel(),unit);
        var pilot=TrainingPilotDirector.existingPilotR45(player.serverLevel(),unit);
        return com.projectseele.entity.TrainingPilotEntity.pilotName(unit)+"："+(pilot==null?"频道待接入。":PilotRadioR28.response(player,pilot,false));
    }

    public static int contact(ServerPlayer player, String name)
    {
        if (!radioAllowed(player))
        {
            player.sendSystemMessage(Component.literal("请携带 NERV 通行证和卫星电话，或在指挥台附近、已登上的插入栓及机体内使用指挥通信。")); return 0;
        }
        String contactName = name.strip().toLowerCase(Locale.ROOT).replaceFirst("^dummy[ :：]*", "");
        int pilot = switch (contactName)
        {
            case "碇真嗣", "真嗣", "shinji" -> 1;
            case "绫波丽", "绫波", "丽", "rei" -> 0;
            case "明日香", "惣流明日香", "asuka" -> 2;
            default -> -1;
        };
        if (pilot >= 0)
        {
            player.sendSystemMessage(Component.literal(pilotStatus(player, pilot)));
            return 1;
        }
        String skin = switch (contactName)
        {
            case "美里", "葛城美里", "misato" -> "misato";
            case "律子", "赤木律子", "ritsuko" -> "ritsuko";
            case "冬月", "冬月司令", "fuyutsuki" -> "fuyutsuki";
            case "摩耶", "伊吹摩耶", "maya" -> "maya";
            default -> "";
        };
        if (skin.isEmpty()) { player.sendSystemMessage(Component.literal("可联络：美里、律子、冬月、摩耶。")); return 0; }
        if (connect(player, skin)) return 1;
        PENDING.computeIfAbsent(player.server, key -> new HashMap<>()).put(player.getUUID(), new Pending(skin, player.server.getTickCount() + 200));
        player.sendSystemMessage(Component.literal("正在连接指挥频道……")); return 1;
    }

    private static boolean connect(ServerPlayer player, String skin)
    {
        var level = player.serverLevel();
        var station = NervStaffDirector.roster(level).stream().filter(post -> post.skin().equals(skin)).findFirst().orElse(null);
        if (station == null) return false;
        UUID id = NervStaffSavedData.get(level).identity(station.id());
        load(level, station.feet());
        if (id != null && level.getEntity(id) instanceof NervStaffEntity npc)
        { open(player, npc, true); return true; }
        if (System.getProperty("projectseele.regionalBuild", "").startsWith("r24-") && player.server.getTickCount() % 20 == 0)
            ProjectSeele.LOGGER.info("R24 RADIO LOAD person={} uuid={} post={} entityTicking={} loadedNPCs={}",
                    station.id(), id, station.feet(), level.isPositionEntityTicking(station.feet()),
                    level.getEntitiesOfClass(NervStaffEntity.class, new net.minecraft.world.phys.AABB(station.feet()).inflate(32)).stream().map(n -> n.memberId()+":"+n.getUUID()).toList());
        return false;
    }
    private static void load(ServerLevel level, BlockPos at)
    {
        for (int x = (at.getX() >> 4) - 1; x <= (at.getX() >> 4) + 1; x++)
            for (int z = (at.getZ() >> 4) - 1; z <= (at.getZ() >> 4) + 1; z++)
            { var chunk = new ChunkPos(x, z); level.getChunkSource().addRegionTicket(TICKET, chunk, 2, chunk); level.getChunk(x, z); }
    }

    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if (event.phase != TickEvent.Phase.END || event.getServer().getTickCount() % 5 != 0) return;
        if (event.getServer().getTickCount() % 200 == 0)
        {
            var active = SESSIONS.get(event.getServer());
            if (active != null) active.keySet().removeIf(id -> event.getServer().getPlayerList().getPlayer(id) == null);
        }
        var pending = PENDING.get(event.getServer()); if (pending == null) return;
        for (var entry : List.copyOf(pending.entrySet()))
        {
            var player = event.getServer().getPlayerList().getPlayer(entry.getKey());
            if (player == null || !radioAllowed(player)) { pending.remove(entry.getKey()); continue; }
            if (connect(player, entry.getValue().skin())) { pending.remove(entry.getKey()); continue; }
            if (event.getServer().getTickCount() > entry.getValue().until())
            {
                pending.remove(entry.getKey()); player.sendSystemMessage(Component.literal("该岗位暂时无法接通，请稍后再试。"));
            }
        }
    }
    private StaffConversationR24() {}
}
