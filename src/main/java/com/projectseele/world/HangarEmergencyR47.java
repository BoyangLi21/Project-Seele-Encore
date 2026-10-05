package com.projectseele.world;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.NervHangarDoorEntity;
import net.minecraft.commands.Commands;
import net.minecraft.core.BlockPos;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.level.saveddata.SavedData;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.event.RegisterCommandsEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.util.Map;
import java.util.WeakHashMap;

/** Manual override for the original three rear pressure gates into the transfer corridor. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID)
public final class HangarEmergencyR47
{
    private static final class State extends SavedData
    {
        final boolean[] requested = new boolean[3], held = new boolean[3];
        static State load(CompoundTag tag)
        {
            var state = new State();
            for (int i = 0; i < 3; i++)
            {
                state.requested[i] = tag.getBoolean("Open" + i);
                state.held[i] = tag.getBoolean("Held" + i);
            }
            return state;
        }
        @Override public CompoundTag save(CompoundTag tag)
        {
            for (int i = 0; i < 3; i++)
            {
                tag.putBoolean("Open" + i, requested[i]);
                tag.putBoolean("Held" + i, held[i]);
            }
            return tag;
        }
    }
    private static final Map<ServerLevel, boolean[]> APPLIED = new WeakHashMap<>();
    private static State state(ServerLevel level)
    {
        return level.getDataStorage().computeIfAbsent(State::load, State::new,
                "projectseele_hangar_emergency_r47");
    }
    private static boolean retainedPlant(ServerLevel level)
    {
        return level.dimension().equals(FacilitySchemaV2.DIMENSION)
                && FacilityLayoutR29.active(level.getServer());
    }
    private static boolean loadedEnvelope(ServerLevel level, BlockPos bed)
    {
        // The same finite vessel/apron bounds used by countLclEnvelope.
        for (int x = (bed.getX() - 19) >> 4; x <= (bed.getX() + 19) >> 4; x++)
            for (int z = (bed.getZ() - 26) >> 4; z <= (bed.getZ() + 35) >> 4; z++)
                if (!level.hasChunk(x, z)) return false;
        return true;
    }
    private static Vec3 centre(ServerLevel level, int variant)
    {
        BlockPos origin = RegionalFacilityLayout.evaOrigin(level);
        BlockPos bed = EvaHangarBuilder.hangarBed(origin, variant);
        return new Vec3(bed.getX() + .5, bed.getY() + 1,
                EvaHangarBuilder.gateZ(origin) + .5);
    }
    private static boolean occupied(ServerLevel level, Vec3 centre)
    {
        double height = Math.max(65, -370 - centre.y);
        var opening = new AABB(centre.x - 17, centre.y, centre.z - 2,
                centre.x + 17, centre.y + height, centre.z + 2);
        return !level.getEntities((net.minecraft.world.entity.Entity)null, opening, entity -> entity.isAlive()
                && !entity.isSpectator() && !(entity instanceof NervHangarDoorEntity)).isEmpty();
    }
    private static boolean idleDryReceipt(ServerLevel level, int variant)
    {
        var receipt = EvaFleetSavedData.get(level.getServer()).entry(variant).orElse(null);
        var original = EvaLogisticsDirector.canonicalUnit(level, variant);
        return receipt != null && receipt.phase() == EvaFleetSavedData.Phase.DEPLOYED
                && receipt.lclLayers() == 0 && original != null
                && receipt.canonicalId().equals(original.getUUID())
                && !NervAirLiftR30.ownsMotion(original)
                && !com.projectseele.entity.EvaAirTransportR31.active(original);
    }
    private static String request(ServerPlayer player, int variant, boolean open)
    {
        ServerLevel level = player.serverLevel();
        if (!retainedPlant(level) || !NervStaffDialogue.authorized(player))
            return "需要原机库操作权限。";
        var state = state(level);
        BlockPos origin = RegionalFacilityLayout.evaOrigin(level);
        BlockPos bed = EvaHangarBuilder.hangarBed(origin, variant);
        if (!loadedEnvelope(level, bed)) return "原机库门域尚未加载，紧急开闭保持原状态。";
        if (open)
        {
            if (!idleDryReceipt(level, variant))
                return "机库后门只在原机出库、干池且无运输动作时允许紧急开启；本操作不排液。";
            if (EvaHangarBuilder.countLclEnvelope(level, origin, variant) != 0)
                return "池内或门前仍有实际 LCL，后门保持关闭；请先完成正常排液。";
            state.requested[variant] = true;
            state.held[variant] = true;
        }
        else state.requested[variant] = false;
        state.setDirty();
        boolean actual = desiredOpenR47(level, variant, centre(level, variant), false);
        return open ? "机库后门紧急开启：通往原机库转移廊。"
                : actual ? "门域有人员、机体或载具，后门保持开启；清空后自动关闭。"
                : "机库后门已请求关闭。";
    }
    /** Call before the original installed-control switch, avoiding a second cancel request. */
    public static boolean handleUse(ServerPlayer player, BlockPos position)
    {
        if (!player.isShiftKeyDown() || player.isSpectator()) return false;
        var control = HangarOperationsR44.match(player.serverLevel(), position).orElse(null);
        if (control == null || control.action() != HangarOperationsR44.Action.CANCEL) return false;
        if (player.distanceToSqr(Vec3.atCenterOf(position)) > 36) return true;
        var state = state(player.serverLevel());
        player.sendSystemMessage(Component.literal("[NERV 机库后门] "
                + request(player, control.variant(), !state.requested[control.variant()])));
        return true;
    }
    /** A normal recovery must not override an occupied manual passage or start filling it. */
    public static boolean releaseForRecoveryR47(ServerLevel level, int variant)
    {
        if (!retainedPlant(level) || variant < 0 || variant > 2) return true;
        var state = state(level);
        if (!state.requested[variant] && !state.held[variant]) return true;
        BlockPos bed = EvaHangarBuilder.hangarBed(RegionalFacilityLayout.evaOrigin(level), variant);
        if (!loadedEnvelope(level, bed) || occupied(level, centre(level, variant))) return false;
        state.requested[variant] = false;
        state.setDirty();
        return !desiredOpenR47(level, variant, centre(level, variant), false);
    }
    /** Call at the retained gate producer; ordinary moving transfer always owns its gate. */
    public static boolean desiredOpenR47(ServerLevel level, int variant, Vec3 centre, boolean moving)
    {
        if (!retainedPlant(level) || variant < 0 || variant > 2) return moving;
        var state = state(level);
        var applied = APPLIED.computeIfAbsent(level, key -> new boolean[3]);
        if (moving)
        {
            if (state.requested[variant] || state.held[variant])
            {
                state.requested[variant] = state.held[variant] = false;
                state.setDirty();
            }
            applied[variant] = false;
            return true;
        }
        if (!state.requested[variant] && !state.held[variant]) return false;
        if (state.requested[variant] && !idleDryReceipt(level, variant))
        {
            state.requested[variant] = false;
            state.setDirty();
        }
        BlockPos bed = EvaHangarBuilder.hangarBed(RegionalFacilityLayout.evaOrigin(level), variant);
        // Unknown entity sections cannot prove an empty closing sweep.
        boolean open = state.requested[variant] || !loadedEnvelope(level, bed) || occupied(level, centre);
        if (!applied[variant] || !open)
        {
            if (loadedEnvelope(level, bed))
            {
                // A restored override may meet liquid placed while its chunk was absent.
                // Never let setGate's normal drain behavior remove that liquid here.
                if (open && EvaHangarBuilder.countLclEnvelope(level,
                        RegionalFacilityLayout.evaOrigin(level), variant) != 0)
                {
                    state.requested[variant] = false;
                    state.setDirty();
                    open = occupied(level, centre);
                    if (open)
                    {
                        applied[variant] = true;
                        return true;
                    }
                }
                EvaHangarBuilder.setGate(level, RegionalFacilityLayout.evaOrigin(level), variant, open);
                applied[variant] = open;
            }
        }
        if (!open)
        {
            state.held[variant] = false;
            state.setDirty();
        }
        return open;
    }
    @SubscribeEvent public static void commands(RegisterCommandsEvent event)
    {
        var emergency = Commands.literal("emergency");
        for (String action : new String[] {"open", "close", "status"})
        {
            var branch = Commands.literal(action);
            for (int variant = 0; variant < 3; variant++)
            {
                final int selected = variant;
                branch.then(Commands.literal(Integer.toString(variant)).executes(context ->
                {
                    var player = context.getSource().getPlayerOrException();
                    String reply = action.equals("status")
                            ? "机库后门：" + (state(player.serverLevel()).held[selected] ? "保持开启" : "自动控制")
                            : request(player, selected, action.equals("open"));
                    player.sendSystemMessage(Component.literal("[NERV 机库后门] " + reply));
                    return 1;
                }));
            }
            emergency.then(branch);
        }
        event.getDispatcher().register(Commands.literal("nerv")
                .then(Commands.literal("hangar").then(emergency)));
    }
    private HangarEmergencyR47() {}
}
