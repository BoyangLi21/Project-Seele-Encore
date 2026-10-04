package com.projectseele.network;

import java.util.function.Supplier;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.NervArmamentStationEntity;
import com.projectseele.world.EvaPilotResolver;
import net.minecraft.network.FriendlyByteBuf;
import net.minecraft.server.level.ServerPlayer;
import net.minecraftforge.network.NetworkEvent;

/**
 * Pilot input from the entry plug. The server validates that the sender is
 * actually riding a Unit before dispatching — clients are never trusted.
 */
public class ServerboundEvaControlPacket
{
    public static final int ACTION_CYCLE_WEAPON = 0;
    public static final int ACTION_TOGGLE_AT_FIELD = 1;
    public static final int ACTION_MELEE = 2;
    public static final int ACTION_CHARGE_START = 3;
    public static final int ACTION_CHARGE_STOP = 4;
    public static final int ACTION_SMASH = 5;
    public static final int ACTION_CROUCH_START = 6;
    public static final int ACTION_CROUCH_STOP = 7;
    public static final int ACTION_SPRINT_START = 8;
    public static final int ACTION_SPRINT_STOP = 9;
    public static final int ACTION_JUMP = 10;
    public static final int ACTION_EXIT = 11;
    public static final int ACTION_STOMP = 12;
    public static final int ACTION_TOGGLE_PRONE = 13;
    public static final int ACTION_RIFLE_FIRE = 14;
    public static final int ACTION_CANCEL_LAUNCH = 15;
    public static final int ACTION_SELF_LAUNCH = 16;
    public static final int ACTION_TAKE_ARMAMENT = 17;
    public static final int ACTION_SKIP_FIRST_BATTLE = 18;
    public static final int ACTION_UN_EYE_LASER=19;
    public static final int ACTION_UN_FLIGHT=20;
    public static final int ACTION_UN_FLIGHT_INPUT=21;
    public static final int ACTION_GRAPPLE=22;
    public static final int ACTION_RIFLE_SIGHT_START_R45=23;
    public static final int ACTION_RIFLE_SIGHT_STOP_R45=24;

    public final int action;
    public final int requestId;

    public ServerboundEvaControlPacket(int action)
    {
        this(action, -1);
    }

    public ServerboundEvaControlPacket(int action, int requestId)
    {
        this.action = action;
        this.requestId = requestId;
    }

    public ServerboundEvaControlPacket(FriendlyByteBuf buf)
    {
        this(buf.readVarInt(), buf.readVarInt());
    }

    public void encode(FriendlyByteBuf buf)
    {
        buf.writeVarInt(this.action);
        buf.writeVarInt(this.requestId);
    }

    public void handle(Supplier<NetworkEvent.Context> ctx)
    {
        NetworkEvent.Context context = ctx.get();
        ServerPlayer sender = context.getSender();
        // Entity data, animation triggers and movement all belong to the
        // authoritative server thread. Running this switch directly on
        // Netty made rapid weapon/attack/jump input race the entity tick:
        // effects could appear while the corresponding animation or impulse
        // was lost. Queue the complete validation + dispatch atomically.
        context.enqueueWork(() ->
        {
            EvaUnit01Entity eva = sender == null
                    ? null : EvaPilotResolver.controlTarget(sender);
            if (sender != null && eva != null
                    && EvaPilotResolver.pilot(eva) == sender)
            {
                if (Boolean.getBoolean("projectseele.visualCapture"))
                {
                    ProjectSeele.LOGGER.info(
                            "Visual live server dispatch action={} pose={} vehicle={} onGround={} velocityY={}",
                            this.action, eva.getVisualPose(), eva.getStringUUID(),
                            eva.onGround(), eva.getDeltaMovement().y);
                }
                switch (this.action)
                {
                    case ACTION_CYCLE_WEAPON -> eva.cycleWeapon(sender);
                    case ACTION_TOGGLE_AT_FIELD -> eva.toggleAtField(sender);
                    case ACTION_MELEE -> eva.meleeAttack(sender);
                    case ACTION_GRAPPLE -> com.projectseele.entity.EvaCombatR31.grapple(eva,sender);
                    case ACTION_SMASH -> eva.smashAttack(sender);
                    case ACTION_CHARGE_START -> eva.setChargingHeld(true);
                    case ACTION_CHARGE_STOP -> eva.releaseCannon(sender);
                    case ACTION_CROUCH_START -> eva.setPilotCrouching(sender, true);
                    case ACTION_CROUCH_STOP -> eva.setPilotCrouching(sender, false);
                    case ACTION_SPRINT_START -> eva.setPilotSprinting(sender, true);
                    case ACTION_SPRINT_STOP -> eva.setPilotSprinting(sender, false);
                    case ACTION_JUMP -> {
                        if (this.requestId >= 0)
                        {
                            eva.pilotJump(sender, this.requestId);
                        }
                        else
                        {
                            eva.pilotJump(sender);
                        }
                    }
                    case ACTION_EXIT -> eva.exitEva(sender);
                    case ACTION_STOMP -> eva.stompAttack(sender);
                    case ACTION_TOGGLE_PRONE -> eva.toggleProne(sender);
                    case ACTION_RIFLE_FIRE -> eva.fireRifle(sender);
                    case ACTION_RIFLE_SIGHT_START_R45 -> eva.setRifleSightHeldR45(sender,true);
                    case ACTION_RIFLE_SIGHT_STOP_R45 -> eva.setRifleSightHeldR45(sender,false);
                    case ACTION_CANCEL_LAUNCH -> eva.contextualPilotCR45(sender,this.requestId);
                    case ACTION_SELF_LAUNCH -> eva.releaseLaunchFromPilot(sender);
                    case ACTION_SKIP_FIRST_BATTLE -> com.projectseele.event.FirstBattleDirector.skip(sender);
                    case ACTION_UN_EYE_LASER -> {if(eva instanceof com.projectseele.entity.EvaPrototypeEntity un)un.requestEyeLaser(sender);}
                    case ACTION_UN_FLIGHT -> {if(eva instanceof com.projectseele.entity.EvaPrototypeEntity un)un.toggleUNFlight(sender);}
                    case ACTION_UN_FLIGHT_INPUT -> {if(eva instanceof com.projectseele.entity.EvaPrototypeEntity un&&un.isUNFlying()&&requestId>=0&&requestId<=3)un.setFlightInput(requestId);}
                    case ACTION_TAKE_ARMAMENT ->
                    {
                        if (eva.level() instanceof net.minecraft.server.level.ServerLevel level)
                        {
                            NervArmamentStationEntity.acquireNearest(
                                    level, sender, eva);
                        }
                    }
                    default -> { }
                }
            }
            else if (Boolean.getBoolean("projectseele.visualCapture"))
            {
                ProjectSeele.LOGGER.warn(
                        "Visual live server rejected action={} sender={} vehicle={}",
                        this.action,
                        sender == null ? "null" : sender.getGameProfile().getName(),
                        sender == null || sender.getVehicle() == null
                                ? "null" : sender.getVehicle().getType().toString());
            }
        });
        context.setPacketHandled(true);
    }
}
