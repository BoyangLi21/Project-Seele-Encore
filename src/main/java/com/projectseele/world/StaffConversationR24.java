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
        long lastAction = -100, lastRefresh = -100;
        long requestWindow = -100;
        int requestCount;
        String reply;
        int pilotContact=-1;
        UUID coordinationInstance;
        Session(NervStaffEntity npc, String reply)
        { actor = npc.getUUID(); level = (ServerLevel) npc.level(); this.reply = reply; }
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

    private static boolean available(ServerPlayer player, NervStaffEntity npc)
    {
        return npc.isAlive() && radioAllowed(player);
    }

    private static void open(ServerPlayer player, NervStaffEntity npc)
    {
        if (!radioAllowed(player)) return;
        var session = new Session(npc, StaffDialogueCatalogR24.line(StaffDialogueCatalogR24.profile(npc), npc.staffRole(), "greeting", player.tickCount / 100));
        sessions(player).put(player.getUUID(), session); send(player, npc, session, true);
    }

    private static String role(NervStaffEntity npc)
    {
        if (npc.skin().equals("fuyutsuki")) return "staff.projectseele.deputy";
        return switch (npc.staffRole())
        {
            case "commander" -> "staff.projectseele.operations"; case "scientist" -> "staff.projectseele.science";
            case "operator" -> "staff.projectseele.operator"; case "medic" -> "staff.projectseele.medic";
            case "guard", "un_guard" -> "staff.projectseele.guard"; case "un_crew" -> "staff.projectseele.un_crew";
            default -> "staff.projectseele.technician";
        };
    }

    private static void send(ServerPlayer player, NervStaffEntity npc, Session session, boolean open)
    {
        List<String> units = new ArrayList<>();
        for (int i = 0; i < 3; i++)
        {
            var state = EvaLogisticsDirector.status(player.serverLevel(), i);
            units.add("unit:" + i + ":" + state.phase() + ":" + (state.loaded() ? "1" : "0"));
        }
        var job = StaffCommandBookR24.order(npc);
        String order = job == null ? "" : "order:" + job.unit + ":" + job.message;
        boolean authorized = NervStaffDialogue.authorized(player);
        boolean canCommand = authorized && StaffAuthorityR25.commandContact(npc);
        if (!canCommand && order.isEmpty())
            order = "staff.projectseele.information_only";
        var coordination=CityCoordinationSavedDataR44.get(player.serverLevel());
        boolean current=coordination.active&&session.coordinationInstance!=null&&session.coordinationInstance.equals(coordination.instance);
        List<String> participants=new ArrayList<>();
        if(current)for(int unit=0;unit<5;unit++)
        {
            var binding = coordination.binding(unit);
            String row = "crew:" + unit;
            if (binding != null)
            {
                var actual = player.server.getPlayerList().getPlayer(binding.pilot());
                String kind = binding.kind().equals("npc") ? "npc" : actual == null ? "offline" : "player";
                String name = kind.equals("player") ? actual.getName().getString() : "";
                row += ":" + binding.role() + ":" + (coordination.confirmationCurrent(unit) ? "1" : "0")
                        + ":" + kind + ":" + name;
            }
            participants.add(row);
        }
        var packet = new ClientboundStaffConversationPacket(session.nonce, npc.getUUID(), npc.getId(),
                npc.getName().getString(), role(npc), npc.skin(), open, true, canCommand, authorized,
                session.reply, order, List.copyOf(units),current?coordination.formationRevisionR45:0,
                current?coordination.evidenceRevisionR45:0,List.copyOf(participants),com.projectseele.event.TvCampaignDirector.selectedMissionR54(player));
        SeeleNetwork.CHANNEL.send(PacketDistributor.PLAYER.with(() -> player), packet);
    }

    public static void note(ServerPlayer player, NervStaffEntity npc, String line)
    {
        Session session = sessions(player).get(player.getUUID());
        if (session != null && session.actor.equals(npc.getUUID()) && available(player, npc))
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
        if (!(entity instanceof NervStaffEntity npc) || !available(player, npc))
        {
            sessions(player).remove(player.getUUID());
            SeeleNetwork.CHANNEL.send(PacketDistributor.PLAYER.with(() -> player), new ClientboundStaffConversationPacket(
                    nonce, session.actor, -1, "NERV", "", "", false, false, false, false,
                    "ops.projectseele.staff.call_ended_orders_already_issued_will_continue", "", List.of()));
            return;
        }
        long tick = player.server.getTickCount();
        if (request.equals("REFRESH"))
        {
            if (tick - session.lastRefresh < 20) return;
            session.lastRefresh = tick; load(session.level, npc.blockPosition());
            if(session.pilotContact>=0)session.reply=pilotStatus(player,session.pilotContact);
            send(player, npc, session, false); return;
        }
        // Permit ordinary short bursts such as cancel -> new order. Drop
        // excess traffic with a visible reply instead of a dead-looking UI.
        if (tick - session.requestWindow >= 20) { session.requestWindow = tick; session.requestCount = 0; }
        if (++session.requestCount > 8)
        {
            session.reply = "ops.projectseele.staff.commands_are_arriving_too_quickly_try_again_shortly";
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
        if(request.startsWith("OUTLET:"))
        {
            String[] choice=request.split(":");
            try{if(choice.length==3&&NervOutletControlsR53.TARGETS.contains(choice[2]))StaffCommandBookR24.request(player,npc,"deploy_"+choice[2],Integer.parseInt(choice[1]));}
            catch(NumberFormatException invalid){session.reply="ops.projectseele.nerv.invalid_unit_number";}
            return;
        }
        if(request.startsWith(StaffUndergroundChoiceR52.PREFIX))
        {
            try
            {
                var choice=StaffUndergroundChoiceR52.parse(request);session.pilotContact=-1;
                if(choice.prepareFirst())
                {StaffCommandBookR24.request(player,npc,StaffUndergroundChoiceR52.PREPARE_AND_DEPLOY,choice.unit());return;}
                session.reply=StaffOperationsR48.undergroundDeploymentR52(player,npc,choice.unit()).message();
            }
            catch(IllegalArgumentException error){session.reply="ops.projectseele.staff.select_a_valid_unit_and_an_underground_deployment";}
            send(player,npc,session,false);return;
        }
        if(request.startsWith("ARMEDSORTIE:"))
        {
            try
            {
                String[] parts=request.split(":",-1);
                if(parts.length!=3)throw new IllegalArgumentException();
                int variant=Integer.parseInt(parts[1]);
                if ((variant != 0 && variant != 2) || !Set.of("human", "npc").contains(parts[2]))
                    throw new IllegalArgumentException();
                session.pilotContact=-1;
                var result=StaffOperationsR48.armedSortie(player,npc,variant,parts[2].equals("npc"));
                session.reply=result.message();
            }
            catch(IllegalArgumentException error)
            {session.reply="ops.projectseele.staff.select_a_valid_unit_pilot_and_operation";}
            send(player,npc,session,false);return;
        }
        if (request.equals("WEAPONS"))
        {
            if (!NervStaffDialogue.authorized(player) || !StaffAuthorityR25.allows(npc, "weapons"))
                session.reply = "ops.projectseele.staff.combat_command_authorizes_weapons_deployment";
            else
            {
                var eva = EvaPilotResolver.controlTarget(player);
                var centre = eva == null ? player.position() : eva.position();
                var station = player.serverLevel().getEntitiesOfClass(com.projectseele.entity.NervArmamentStationEntity.class,
                        new net.minecraft.world.phys.AABB(centre,centre).inflate(768,40,768),
                        rack->rack.payloadR47()==com.projectseele.entity.EvaUnit01Entity.WEAPON_RIFLE&&!TvMissionEquipmentR45.missionRack(rack)).stream()
                        .min(Comparator.comparingDouble(rack->rack.position().subtract(centre).horizontalDistanceSqr())).orElse(null);
                session.reply = station != null && station.deploy()
                        ? OperationText.format("ops.projectseele.staff.silo_coordinates", station.blockPosition().toShortString())
                        : "ops.projectseele.staff.no_deployable_weapons_silo_is_nearby_or_the";
            }
            send(player, npc, session, false); return;
        }
        if(request.equals("WEAPONS:shield")||request.equals("WEAPONS:sword"))
        {
            if(!NervStaffDialogue.authorized(player)||!StaffAuthorityR25.allows(npc,"weapons"))session.reply="ops.projectseele.staff.contact_combat_command_to_deploy_a_dedicated_weapons";
            else
            {
                boolean shield=request.endsWith("shield");
                int payload=shield?com.projectseele.entity.EvaUnit01Entity.WEAPON_SHIELD_R45:com.projectseele.entity.EvaUnit01Entity.WEAPON_SWORD_R45;
                var station=EquipmentVaultsR47.recordedStationR47(player.serverLevel(),payload);
                Component purpose = Component.translatable(shield ? "ops.projectseele.staff.shield_silo" : "ops.projectseele.staff.sword_silo");
                session.reply = station == null ? OperationText.format("ops.projectseele.staff.silo_offline", purpose)
                        : station.deploy() ? OperationText.format("ops.projectseele.staff.silo_rising", purpose, station.blockPosition().toShortString())
                        : OperationText.format(station.isReadyAndStocked() ? "ops.projectseele.staff.silo_ready"
                                : !station.isStocked() ? "ops.projectseele.staff.silo_empty"
                                : "ops.projectseele.staff.silo_moving", purpose);
            }
            send(player,npc,session,false);return;
        }
        if(request.startsWith("TRANSPORT:"))
        {
            if(!NervStaffDialogue.authorized(player)||!StaffAuthorityR25.commandContact(npc))session.reply="ops.projectseele.staff.this_station_cannot_dispatch_transport_aircraft_contact_command";
            else try
            {
                String[] parts=request.split(":");
                session.reply=switch(parts[1])
                {
                    case "status" -> {
                        // R65: the shaft between the surface and the GeoFront is part of the transport picture.
                        String flights=NervAirLiftR30.status(player.serverLevel()),shaft=NervAirTransportRuntimeR52.shaftStatus(player.serverLevel());
                        yield shaft.isEmpty()?flights:OperationText.encode(Component.empty().append(OperationText.read(flights)).append(" | ").append(OperationText.read(shaft)));
                    }
                    case "shaft" -> {
                        if(parts.length!=3||!Set.of("open","close").contains(parts[2]))throw new IllegalArgumentException("Ambiguous shaft order");
                        yield NervAirTransportRuntimeR52.shaft(player,parts[2]);
                    }
                    case "cancel" -> {
                        if(parts.length==2)yield NervAirLiftR30.cancel(player);
                        if(parts.length!=3)throw new IllegalArgumentException("Ambiguous transport cancellation");
                        yield NervAirLiftR30.cancel(player,Integer.parseInt(parts[2]));
                    }
                    case "recover" -> {
                        if(parts.length==3)yield NervAirLiftR30.request(player,Integer.parseInt(parts[2]),true,0,0);
                        if(parts.length!=4)throw new IllegalArgumentException("Ambiguous recovery receiver");
                        yield NervAirTransportRuntimeR52.requestRecoveryReceiver(player,Integer.parseInt(parts[2]),parts[3]);
                    }
                    case "deliver" -> parts.length==6?NervAirTransportRuntimeR52.requestXYZ(player,Integer.parseInt(parts[2]),Integer.parseInt(parts[3]),Integer.parseInt(parts[4]),Integer.parseInt(parts[5])):NervAirLiftR30.request(player,Integer.parseInt(parts[2]),false,Integer.parseInt(parts[3]),Integer.parseInt(parts[4]));
                    default -> "ops.projectseele.staff.select_a_transport_operation";
                };
            }
            catch(IllegalArgumentException|IndexOutOfBoundsException error){session.reply="ops.projectseele.staff.enter_a_valid_unit_number_and_integer_x";}
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
                session.reply=StaffDialogueCatalogR24.pilotReply(unit, pilot == null ? "dialogue.projectseele.awaiting_channel" : PilotRadioR28.chat(player,pilot));
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
                        session.reply = "ops.projectseele.staff.this_station_cannot_dispatch_pilots_contact_misato_ritsuko";
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
        return StaffDialogueCatalogR24.pilotReply(unit, pilot == null ? "dialogue.projectseele.awaiting_channel" : PilotRadioR28.response(player,pilot,false));
    }

    public static int contact(ServerPlayer player, String name)
    {
        if (!radioAllowed(player))
        {
            player.sendSystemMessage(Component.translatable("message.projectseele.phone.requirements")); return 0;
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
            player.sendSystemMessage(StaffDialogueCatalogR24.replyComponent(pilotStatus(player, pilot)));
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
        if (skin.isEmpty()) { player.sendSystemMessage(Component.translatable("message.projectseele.phone.contacts")); return 0; }
        var pending=PENDING.computeIfAbsent(player.server, key -> new HashMap<>());
        if (connect(player, skin)) { pending.remove(player.getUUID()); return 1; }
        var previous=pending.get(player.getUUID());
        if(previous!=null&&previous.skin().equals(skin))return 1;
        pending.put(player.getUUID(), new Pending(skin, System.nanoTime() + 10_000_000_000L));
        player.sendSystemMessage(Component.translatable("message.projectseele.phone.connecting")); return 1;
    }

    private static boolean connect(ServerPlayer player, String skin)
    {
        if(connect(player,skin,player.serverLevel()))return true;
        for(var level:player.server.getAllLevels())
            if(level!=player.serverLevel()&&connect(player,skin,level))return true;
        return false;
    }
    private static boolean connect(ServerPlayer player,String skin,ServerLevel level)
    {
        var station = NervStaffDirector.roster(level).stream().filter(post -> post.skin().equals(skin)).findFirst().orElse(null);
        if (station == null) return false;
        UUID id = NervRouteRuntimeR52.claimed(level)?NervOriginalActorsR52.staffIdentity(level,station.id())
                :NervStaffSavedData.get(level).identity(station.id());
        if(id==null)return false;
        if (level.getEntity(id) instanceof NervStaffEntity npc&&npc.isAlive())
        { load(level,npc.blockPosition()); open(player, npc); return true; }
        load(level, station.feet());
        return false;
    }
    private static void load(ServerLevel level, BlockPos at)
    {
        // One entity-ticking ticket already retains its neighbours. Never wait
        // for disk/generation from the radio request or its retry tick.
        var chunk = new ChunkPos(at);level.getChunkSource().addRegionTicket(TICKET, chunk, 2, chunk);
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
            if (System.nanoTime() > entry.getValue().until())
            {
                pending.remove(entry.getKey()); player.sendSystemMessage(Component.translatable("message.projectseele.phone.unavailable"));
            }
        }
    }
    private StaffConversationR24() {}
}
