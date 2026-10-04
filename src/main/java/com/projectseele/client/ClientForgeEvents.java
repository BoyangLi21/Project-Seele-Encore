package com.projectseele.client;

import com.projectseele.ProjectSeele;
import com.mojang.math.Axis;
import com.projectseele.client.visual.VisualCaptureManager;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.EvaScale;
import com.projectseele.entity.EntryPlugCarrierEntity;
import com.projectseele.entity.NervArmamentStationEntity;
import com.projectseele.network.SeeleNetwork;
import com.projectseele.network.ServerboundEntryPlugPacket;
import com.projectseele.network.ServerboundCommandSeatPosePacket;
import com.projectseele.network.ServerboundEvaControlPacket;
import com.projectseele.network.ServerboundUltramanTogglePacket;
import com.projectseele.world.EntryPlugKinematics;
import com.projectseele.world.EvaPilotResolver;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.screens.inventory.AbstractContainerScreen;
import net.minecraft.client.player.LocalPlayer;
import net.minecraft.client.player.AbstractClientPlayer;
import net.minecraft.sounds.SoundEvent;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.sounds.SoundSource;
import net.minecraft.util.Mth;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.level.ClipContext;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraft.world.phys.HitResult;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.ComputeFovModifierEvent;
import net.minecraftforge.client.event.ClientPlayerNetworkEvent;
import net.minecraftforge.client.event.InputEvent;
import net.minecraftforge.client.event.RenderHandEvent;
import net.minecraftforge.client.event.RenderGuiOverlayEvent;
import net.minecraftforge.client.event.RenderPlayerEvent;
import net.minecraftforge.client.event.ScreenEvent;
import net.minecraftforge.event.entity.EntityEvent;
import net.minecraft.client.model.PlayerModel;
import net.minecraft.world.InteractionHand;
import com.projectseele.client.render.GendoPoseArmLayer;
import net.minecraftforge.client.gui.overlay.VanillaGuiOverlay;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import org.lwjgl.glfw.GLFW;
import org.joml.Quaternionf;

/** Client-side pilot input: keybinds, attack interception, sniper zoom. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, bus = Mod.EventBusSubscriber.Bus.FORGE, value = Dist.CLIENT)
public final class ClientForgeEvents
{
    private static final ThreadLocal<ArmVisibility> COMMANDER_ARM_VISIBILITY =
            new ThreadLocal<>();
    /** Tracks the held use-key for cannon charge or N2 arming edges. */
    private static boolean chargeHeld;
    /** Local optical sight state; rifle fire itself remains server-authoritative. */
    private static boolean rifleAimHeld;
    private static int rifleAimEntityR45=-1;
    private static boolean crouchHeld;
    private static boolean sprintHeld;
    private static boolean jumpHeld;
    /** A held jump stays pending until the EVA's synchronized sequence acknowledges it. */
    private static boolean jumpRequestPending;
    private static int jumpRequestSequence;
    private static int jumpRequestId;
    private static int jumpRequestIdCounter;
    private static int jumpRequestRetryTicks;
    private static int jumpRequestEvaId = -1;
    /** A held key may create one new request only after leaving and re-touching ground. */
    private static boolean jumpRepeatArmed;
    private static final int JUMP_REQUEST_RETRY_INTERVAL = 4;
    /**
     * Last observed continuous cabin progress. It begins in the suspended
     * capsule and survives the passenger transfer into the EVA, preventing the
     * old six-second sound sequence from restarting halfway through insertion.
     */
    private static float cabinSequenceProgress = -1.0F;
    private static int pilotTicks;
    private static int damageFlashTicks;
    private static float lastEvaHealth = -1.0F;
    private static boolean wasPiloting;
    /** Forge may report the same use press once for each hand. */
    private static int lastEntryPlugRequestTick = Integer.MIN_VALUE;

    private ClientForgeEvents() {}

    /** 0..1 elapsed progress of the plug-insertion overlay, or -1 when idle. */
    public static float insertionProgress(float partialTick)
    {
        return cabinSequenceProgress;
    }

    public static int pilotTicks()
    {
        return pilotTicks;
    }

    public static float damageFlash(float partialTick)
    {
        return Mth.clamp((damageFlashTicks - partialTick) / 18.0F, 0.0F, 1.0F);
    }

    /** Immediate local input state, used so optical/N2 overlays do not wait for a round trip. */
    public static boolean isWeaponUseHeld()
    {
        return chargeHeld;
    }

    public static boolean isCannonScopeActive(EvaUnit01Entity eva)
    {
        return opticsAvailable(eva) && eva.getWeapon() == EvaUnit01Entity.WEAPON_CANNON
                && (chargeHeld || eva.getCannonCharge() > 0);
    }

    public static boolean isRifleSightActive(EvaUnit01Entity eva)
    {
        return opticsAvailable(eva) && eva.getWeapon() == EvaUnit01Entity.WEAPON_RIFLE
                &&(eva.isExperimentalUnit()||!eva.isPilotSprinting())
                && rifleAimHeld;
    }

    private static boolean opticsAvailable(EvaUnit01Entity eva)
    {
        return eva!=null&&eva.isPoweredOn()&&!eva.isNervLogisticsLocked()
                &&!eva.isLaunchSequenceActive()&&!eva.isActivationCinematicActive()
                &&!eva.isFirstBattleActive()&&!eva.isBerserk()
                &&!com.projectseele.physics.CombatBodyDynamics.active(eva)
                &&!com.projectseele.entity.EvaAirTransportR31.active(eva);
    }

    private static void send(int action)
    {
        SeeleNetwork.CHANNEL.sendToServer(new ServerboundEvaControlPacket(action));
    }

    private static EvaUnit01Entity ridden(LocalPlayer player)
    {
        return player == null ? null : EvaPilotResolver.controlTarget(player);
    }

    @SubscribeEvent
    public static void onClientTick(TickEvent.ClientTickEvent event)
    {
        Minecraft minecraft = Minecraft.getInstance();
        LocalPlayer player = minecraft.player;
        if (player == null)
        {
            // Forge can emit client ticks while a world connection is being
            // assembled or torn down. No pilot/cabin state is meaningful in
            // that window, and dereferencing the not-yet-created LocalPlayer
            // would crash before the joining packet finishes.
            if (event.phase == TickEvent.Phase.END)
            {
                wasPiloting = false;
                pilotTicks = 0;
                lastEvaHealth = -1.0F;
                damageFlashTicks = 0;
                cabinSequenceProgress = -1.0F;
                crouchHeld = false;
                sprintHeld = false;
                chargeHeld = false;
                rifleAimHeld = false;
                clearJumpRequest();
                UltramanClientState.clear();
            }
            return;
        }
        EvaUnit01Entity eva = ridden(player);
        if(eva!=null
                && (eva.getWeapon()==EvaUnit01Entity.WEAPON_RIFLE||eva.getWeapon()==EvaUnit01Entity.WEAPON_CANNON))
        {
            player.setXRot(eva.clampPilotViewPitch(player.getXRot(),1));
            player.setYRot(eva.clampPilotViewYaw(player.getYRot(),1));
        }

        // While piloting, Shift belongs to the Unit's legs. Clear vanilla's
        // dismount input before LocalPlayer processes it; V is the explicit
        // entry-plug eject key.
        boolean rawCrouch = eva != null && rawKey(minecraft,
                GLFW.GLFW_KEY_LEFT_SHIFT, GLFW.GLFW_KEY_RIGHT_SHIFT);
        if (event.phase == TickEvent.Phase.START)
        {
            if (eva != null)
            {
                minecraft.options.keyShift.setDown(false);
                minecraft.options.keyInventory.setDown(false);
                while (minecraft.options.keyInventory.consumeClick())
                {
                    // The entry plug owns input while the pilot is sealed in.
                }
                player.setShiftKeyDown(false);
            }
            return;
        }
        // Boarding transition: pilot HUD lifetime is independent from the
        // capsule sequence, which may already be 70% complete at EVA transfer.
        boolean piloting = eva != null;
        if (piloting && !wasPiloting)
        {
            pilotTicks = 0;
            lastEvaHealth = eva.getHealth();
        }
        pilotTicks = piloting ? pilotTicks + 1 : 0;
        wasPiloting = piloting;
        tickCabinAudio(minecraft, player, eva);
        if (damageFlashTicks > 0 && !minecraft.isPaused())
        {
            damageFlashTicks--;
        }
        if (eva != null)
        {
            if (lastEvaHealth >= 0.0F && eva.getHealth() < lastEvaHealth)
            {
                damageFlashTicks = 18;
            }
            lastEvaHealth = eva.getHealth();
        }
        else
        {
            lastEvaHealth = -1.0F;
            damageFlashTicks = 0;
        }

        while (Keybinds.COMMAND_RADIO.consumeClick())
        {
            if(eva instanceof com.projectseele.entity.EvaPrototypeEntity)
                SeeleNetwork.CHANNEL.sendToServer(new com.projectseele.network.ServerboundUNCommandPacket("open",0,0,0));
            else SeeleNetwork.CHANNEL.sendToServer(new com.projectseele.network.ServerboundStaffConversationPacket(new java.util.UUID(0,0), "RADIO"));
        }
        while (Keybinds.CYCLE_WEAPON.consumeClick())
        {
            if (eva != null)
            {
                send(ServerboundEvaControlPacket.ACTION_CYCLE_WEAPON);
            }
        }
        while (Keybinds.TOGGLE_AT_FIELD.consumeClick())
        {
            if (eva != null)
            {
                send(ServerboundEvaControlPacket.ACTION_TOGGLE_AT_FIELD);
            }
        }
        while (Keybinds.EXIT_EVA.consumeClick())
        {
            if (eva != null)
            {
                send(ServerboundEvaControlPacket.ACTION_EXIT);
            }
        }
        while (Keybinds.STOMP.consumeClick())
        {
            if (eva != null && eva.isMeleeWeapon())
            {
                send(ServerboundEvaControlPacket.ACTION_STOMP);
            }
        }
        while (Keybinds.TOGGLE_PRONE.consumeClick())
        {
            if (eva != null)
            {
                send(ServerboundEvaControlPacket.ACTION_TOGGLE_PRONE);
            }
        }
        int contextualCClicksR45=0;
        while (Keybinds.CANCEL_LAUNCH.consumeClick())contextualCClicksR45++;
        while (Keybinds.SELF_LAUNCH.consumeClick())
        {
            if (eva != null)
            {
                send(ServerboundEvaControlPacket.ACTION_SELF_LAUNCH);
            }
        }
        while(Keybinds.UN_EYE_LASER.consumeClick())if(eva instanceof com.projectseele.entity.EvaPrototypeEntity)send(ServerboundEvaControlPacket.ACTION_UN_EYE_LASER);
        while(Keybinds.UN_FLIGHT.consumeClick())if(eva instanceof com.projectseele.entity.EvaPrototypeEntity)send(ServerboundEvaControlPacket.ACTION_UN_FLIGHT);
        while(Keybinds.EVA_GRAPPLE.consumeClick())if(eva!=null)send(ServerboundEvaControlPacket.ACTION_GRAPPLE);
        while (Keybinds.COMMANDER_POSE.consumeClick())
        {
            if (player.isPassenger())
            {
                SeeleNetwork.CHANNEL.sendToServer(
                        new ServerboundCommandSeatPosePacket());
            }
        }
        while (Keybinds.ULTRAMAN_TRANSFORM.consumeClick())
        {
            if (eva == null && !player.isPassenger())
            {
                SeeleNetwork.CHANNEL.sendToServer(
                        new ServerboundUltramanTogglePacket());
            }
        }
        UltramanClientState.tick(minecraft.level);

        if (eva != null && minecraft.screen == null)
        {
            if (eva.getWeapon() == EvaUnit01Entity.WEAPON_CANNON
                    || eva.getWeapon() == EvaUnit01Entity.WEAPON_RIFLE)
            {
                // Keep the camera, server ray and physical aim parent on one
                // mechanical elevation envelope. Without this, the optical
                // crosshair can look beyond the barrel's clamped hit ray.
                float pitch = Mth.clamp(player.getXRot(),
                        EvaUnit01Entity.MIN_CANNON_AIM_PITCH,
                        EvaUnit01Entity.MAX_CANNON_AIM_PITCH);
                player.setXRot(pitch);
                player.xRotO = pitch;
            }
            // Respect the player's configured sprint binding. The raw Ctrl
            // fallback remains for installs where vanilla consumes the key
            // while the player is mounted in the entry plug.
            boolean rawSprint = minecraft.options.keySprint.isDown()
                    || rawKey(minecraft, GLFW.GLFW_KEY_LEFT_CONTROL,
                            GLFW.GLFW_KEY_RIGHT_CONTROL);
            boolean rawJump = minecraft.options.keyJump.isDown();
            if (rawCrouch != crouchHeld)
            {
                crouchHeld = rawCrouch;
                send(rawCrouch ? ServerboundEvaControlPacket.ACTION_CROUCH_START
                        : ServerboundEvaControlPacket.ACTION_CROUCH_STOP);
            }
            if (rawSprint != sprintHeld)
            {
                sprintHeld = rawSprint;
                send(rawSprint ? ServerboundEvaControlPacket.ACTION_SPRINT_START
                        : ServerboundEvaControlPacket.ACTION_SPRINT_STOP);
            }
            else if (rawSprint != eva.isPilotSprinting()
                    && player.tickCount % 5 == 0)
            {
                // A press that began during A10/launch lock was formerly
                // consumed once and then forgotten. Reconcile the held input
                // after authority unlock so run cannot silently remain walk.
                send(rawSprint ? ServerboundEvaControlPacket.ACTION_SPRINT_START
                        : ServerboundEvaControlPacket.ACTION_SPRINT_STOP);
            }
            if(eva instanceof com.projectseele.entity.EvaPrototypeEntity un&&un.isUNFlying())
            {
                int mask=(rawJump?1:0)|(rawCrouch?2:0);un.setFlightInput(mask);
                if(player.tickCount%3==0)SeeleNetwork.CHANNEL.sendToServer(new ServerboundEvaControlPacket(ServerboundEvaControlPacket.ACTION_UN_FLIGHT_INPUT,mask));
                clearJumpRequest();
            }
            else handleJumpInput(eva, rawJump);
            minecraft.options.keyShift.setDown(false);
            player.setShiftKeyDown(false);
        }
        else
        {
            // Send release edges before clearing the client cache. Otherwise
            // opening a menu while Shift/Ctrl is held can leave the server
            // EVA permanently crouched or sprinting after the key is released
            // behind the GUI.
            if (eva != null)
            {
                if(eva instanceof com.projectseele.entity.EvaPrototypeEntity un&&un.isUNFlying())
                {un.setFlightInput(0);if(player.tickCount%3==0)SeeleNetwork.CHANNEL.sendToServer(new ServerboundEvaControlPacket(ServerboundEvaControlPacket.ACTION_UN_FLIGHT_INPUT,0));}
                if (crouchHeld)
                {
                    send(ServerboundEvaControlPacket.ACTION_CROUCH_STOP);
                }
                if (sprintHeld)
                {
                    send(ServerboundEvaControlPacket.ACTION_SPRINT_STOP);
                }
            }
            crouchHeld = false;
            sprintHeld = false;
            clearJumpRequest();
        }

        // Send sprint start/stop before C on the same channel, including Ctrl+C's first frame.
        while(contextualCClicksR45-->0)
        {
            if(eva==null)continue;
            boolean originalCancel=eva.isExperimentalUnit()||eva.isNervLogisticsLocked()||eva.isLaunchSequenceActive();
            if(!originalCancel&&minecraft.screen!=null)continue;
            int directions=originalCancel?-1:(minecraft.options.keyUp.isDown()?1:0)
                    |(minecraft.options.keyDown.isDown()?2:0)|(minecraft.options.keyLeft.isDown()?4:0)
                    |(minecraft.options.keyRight.isDown()?8:0);
            SeeleNetwork.CHANNEL.sendToServer(new ServerboundEvaControlPacket(
                    ServerboundEvaControlPacket.ACTION_CANCEL_LAUNCH,directions));
        }

        // Hold-to-use: cannon optical charge and N2 arming share one validated
        // server edge, but expose different synchronized progress values.
        boolean wantCharge = eva != null
                && (eva.getWeapon() == EvaUnit01Entity.WEAPON_CANNON
                    || eva.getWeapon() == EvaUnit01Entity.WEAPON_N2)
                && minecraft.screen == null
                && minecraft.options.keyUse.isDown();
        if (wantCharge != chargeHeld)
        {
            chargeHeld = wantCharge;
            send(wantCharge
                    ? ServerboundEvaControlPacket.ACTION_CHARGE_START
                    : ServerboundEvaControlPacket.ACTION_CHARGE_STOP);
        }
        boolean wantRifleSight = opticsAvailable(eva)
                && eva.getWeapon() == EvaUnit01Entity.WEAPON_RIFLE
                && minecraft.screen == null
                && minecraft.options.keyUse.isDown();
        if(wantRifleSight!=rifleAimHeld||wantRifleSight&&eva.getId()!=rifleAimEntityR45)
            send(wantRifleSight?ServerboundEvaControlPacket.ACTION_RIFLE_SIGHT_START_R45
                    :ServerboundEvaControlPacket.ACTION_RIFLE_SIGHT_STOP_R45);
        rifleAimHeld=wantRifleSight;rifleAimEntityR45=eva==null?-1:eva.getId();

        // The pallet SMG is automatic. The client may request every tick;
        // the entity's authoritative cooldown determines the actual fire rate.
        if (eva != null && eva.getWeapon() == EvaUnit01Entity.WEAPON_RIFLE
                && minecraft.screen == null && minecraft.options.keyAttack.isDown())
        {
            send(ServerboundEvaControlPacket.ACTION_RIFLE_FIRE);
        }
    }

    private static boolean rawKey(Minecraft minecraft, int left, int right)
    {
        long window = minecraft.getWindow().getWindow();
        return GLFW.glfwGetKey(window, left) == GLFW.GLFW_PRESS
                || GLFW.glfwGetKey(window, right) == GLFW.GLFW_PRESS;
    }

    private static void playPlugSound(Minecraft minecraft, SoundEvent sound, float volume, float pitch)
    {
        if (minecraft.level != null && minecraft.player != null)
        {
            minecraft.level.playLocalSound(minecraft.player.getX(), minecraft.player.getY(), minecraft.player.getZ(),
                    sound, SoundSource.PLAYERS, volume, pitch, false);
        }
    }

    /** Personal inventories and mod backpacks are unavailable in the plug. */
    @SubscribeEvent
    public static void onScreenOpening(ScreenEvent.Opening event)
    {
        Minecraft minecraft = Minecraft.getInstance();
        LocalPlayer player = minecraft.player;
        if (ridden(player) != null
                && event.getNewScreen() instanceof AbstractContainerScreen<?>)
        {
            event.setCanceled(true);
            if (player != null)
            {
                player.closeContainer();
            }
        }
    }

    private static void tickCabinAudio(Minecraft minecraft, LocalPlayer player,
                                       EvaUnit01Entity eva)
    {
        if (player == null)
        {
            cabinSequenceProgress = -1.0F;
            return;
        }
        float current = -1.0F;
        if (player.getVehicle() instanceof EntryPlugCarrierEntity plug)
        {
            if (plug.isLockedToEva() && eva != null
                    && eva.isActivationCinematicActive())
            {
                current = eva.getActivationProgress(0.0F);
            }
            else if (!plug.isLockedToEva())
            {
                current = plug.getCabinStage()
                        == EntryPlugCarrierEntity.CABIN_RECOVERED_IDLE
                        ? -1.0F
                        : plug.getCabinStage()
                                == EntryPlugCarrierEntity.CABIN_SEALED_DARK
                                ? 0.0F
                                : plug.getCabinProgress() / 100.0F;
            }
            else
            {
                cabinSequenceProgress = -1.0F;
                return;
            }
        }
        else if (eva != null && eva.isActivationCinematicActive())
        {
            current = eva.getActivationProgress(0.0F);
        }
        if (current < 0.0F)
        {
            cabinSequenceProgress = -1.0F;
            return;
        }
        if (minecraft.isPaused())
        {
            return;
        }
        float previous = cabinSequenceProgress;
        if (crossed(previous, current, 0.01F))
        {
            playPlugSound(minecraft, SoundEvents.PISTON_EXTEND,
                    1.4F, 0.55F);
        }
        if (crossed(previous, current, 0.30F))
        {
            playPlugSound(minecraft, SoundEvents.IRON_DOOR_CLOSE,
                    1.2F, 0.72F);
        }
        if (crossed(previous, current, 0.45F))
        {
            playPlugSound(minecraft, SoundEvents.BEACON_POWER_SELECT,
                    1.0F, 0.62F);
        }
        if (crossed(previous, current, 0.78F))
        {
            playPlugSound(minecraft, SoundEvents.BEACON_ACTIVATE,
                    1.0F, 1.18F);
        }
        // Recovery deliberately runs the same physical sequence backwards.
        // Retaining the historical maximum pinned audio/UI state at 70% even
        // after the capsule returned to its cage.
        cabinSequenceProgress = current;
    }

    private static boolean crossed(float previous, float current,
                                   float threshold)
    {
        return previous < threshold && current >= threshold;
    }

    /**
     * From the plug the mouse drives the Unit, not the pilot's own hands:
     * left-click swings and right-click slams. With the cannon out,
     * right-click is the charge trigger handled by the hold-tracking above.
     */
    @SubscribeEvent
    public static void onInteractionKey(InputEvent.InteractionKeyMappingTriggered event)
    {
        LocalPlayer player = Minecraft.getInstance().player;
        EvaUnit01Entity eva = ridden(player);
        if (eva == null)
        {
            if (player != null && event.isUseItem() && !player.isShiftKeyDown())
            {
                com.projectseele.visual.StanceContactR41Review.shutdownEntryTraceR45(player,null,"client_use_event_before_find",true,null);
                Entity entryTarget = findEntryPlugTarget(player);
                com.projectseele.visual.StanceContactR41Review.shutdownEntryTraceR45(player,entryTarget,"client_use_event_target",true,null);
                if (entryTarget != null)
                {
                    // The external capsule has a real hatch and passenger
                    // space. Prefer it over the old synthetic EVA socket; the
                    // server repeats the hatch, distance and sight gates.
                    event.setCanceled(true);
                    event.setSwingHand(false);
                    if (lastEntryPlugRequestTick != player.tickCount)
                    {
                        lastEntryPlugRequestTick = player.tickCount;
                        SeeleNetwork.CHANNEL.sendToServer(
                                new ServerboundEntryPlugPacket(entryTarget.getId()));
                    }
                }
            }
            return;
        }
        if (event.isAttack())
        {
            event.setCanceled(true);
            event.setSwingHand(false);
            if (eva.isMeleeWeapon())
            {
                send(ServerboundEvaControlPacket.ACTION_MELEE);
            }
        }
        else if (event.isUseItem())
        {
            // Never let the pilot eat/place things through the plug wall.
            event.setCanceled(true);
            event.setSwingHand(false);
            NervArmamentStationEntity station = Minecraft.getInstance().level
                    == null ? null : NervArmamentStationEntity.nearest(
                            Minecraft.getInstance().level, eva.position(),
                            NervArmamentStationEntity.EVA_PICKUP_RANGE, true);
            if (station != null)
            {
                send(ServerboundEvaControlPacket.ACTION_TAKE_ARMAMENT);
            }
            else if (eva.isMeleeWeapon())
            {
                send(ServerboundEvaControlPacket.ACTION_SMASH);
            }
        }
    }

    @SubscribeEvent
    public static void onRenderHand(RenderHandEvent event)
    {
        Minecraft minecraft = Minecraft.getInstance();
        if (minecraft.player != null
                && minecraft.options.getCameraType().isFirstPerson()
                && UltramanClientState.hayataPose(minecraft.player))
        {
            if (event.getHand() == InteractionHand.OFF_HAND)
            {
                event.setCanceled(true);
                return;
            }
            // Lift the real held Beta Capsule into Hayata's overhead line in
            // first person; third person uses the synchronized arm pose.
            event.getPoseStack().translate(0.36D, -0.18D, -0.58D);
            event.getPoseStack().mulPose(
                    Axis.XP.rotationDegrees(-68.0F));
            event.getPoseStack().mulPose(
                    Axis.ZP.rotationDegrees(-18.0F));
            return;
        }
        if (minecraft.player != null
                && minecraft.options.getCameraType().isFirstPerson()
                && CommanderPoseClient.isActive(minecraft.player))
        {
            event.setCanceled(true);
            if (event.getHand() == InteractionHand.MAIN_HAND)
            {
                GendoPoseArmLayer.renderFirstPerson(event.getPoseStack(),
                        event.getMultiBufferSource(), event.getPackedLight(),
                        minecraft.player);
            }
            return;
        }
        EvaUnit01Entity eva = ridden(minecraft.player);
        if (eva == null || !minecraft.options.getCameraType().isFirstPerson())
        {
            return;
        }
        // Suppress the player's normal item/skin hands. The EVA is already
        // rendered once in world space by EvaUnit01Renderer; drawing it again
        // here would create a second camera-space pose that can never remain
        // identical to the third-person skeleton.
        event.setCanceled(true);
    }

    @SubscribeEvent
    public static void onRenderGuiOverlay(RenderGuiOverlayEvent.Pre event)
    {
        if (VisualCaptureManager.isSuppressingGui())
        {
            event.setCanceled(true);
            return;
        }
        Minecraft minecraft = Minecraft.getInstance();
        EvaUnit01Entity eva = ridden(minecraft.player);
        boolean insideExternalPlug = minecraft.player != null
                && minecraft.player.getVehicle()
                        instanceof EntryPlugCarrierEntity;
        boolean opticalSight = isCannonScopeActive(eva) || isRifleSightActive(eva);
        if(EvaCombatHudR31.shouldHideVanilla(event))event.setCanceled(true);
        if (minecraft.screen==null&&(opticalSight || insideExternalPlug)
                && (event.getOverlay() == VanillaGuiOverlay.HOTBAR.type()
                || event.getOverlay() == VanillaGuiOverlay.CROSSHAIR.type()))
        {
            event.setCanceled(true);
        }
    }

    /**
     * Do not consume a jump press merely because activation, launch interlock,
     * or a transient server ground check prevents it on the first tick. The
     * synchronized jump sequence is the acknowledgement; until it changes a
     * held key retries at a low rate once local control is available.
     */
    private static void handleJumpInput(EvaUnit01Entity eva, boolean rawJump)
    {
        if (!rawJump)
        {
            clearJumpRequest();
            return;
        }

        if (!jumpHeld || jumpRequestEvaId != eva.getId())
        {
            jumpHeld = true;
            jumpRequestPending = true;
            jumpRequestSequence = eva.getJumpSequence();
            jumpRequestId = ++jumpRequestIdCounter;
            jumpRequestRetryTicks = 0;
            jumpRequestEvaId = eva.getId();
            jumpRepeatArmed = false;
        }

        if (!jumpRequestPending)
        {
            if (!eva.onGround())
            {
                jumpRepeatArmed = true;
                return;
            }
            if (!jumpRepeatArmed)
            {
                return;
            }
            // Minecraft's normal held-space behaviour repeats only after the
            // previous jump has actually left the ground and landed again.
            jumpRequestPending = true;
            jumpRequestSequence = eva.getJumpSequence();
            jumpRequestId = ++jumpRequestIdCounter;
            jumpRequestRetryTicks = 0;
            jumpRepeatArmed = false;
        }
        if (eva.getJumpSequence() != jumpRequestSequence)
        {
            jumpRequestPending = false;
            return;
        }

        boolean locallyUnlocked = eva.getActivationTicks() <= 20
                && !eva.isLaunchSequenceActive() && eva.getCannonCharge() <= 0;
        if (!locallyUnlocked)
        {
            // Leave the request armed. A key held through entry-plug startup
            // is sent on the first unlocked client tick instead of vanishing.
            jumpRequestRetryTicks = 0;
            return;
        }
        if (jumpRequestRetryTicks > 0)
        {
            jumpRequestRetryTicks--;
            return;
        }

        SeeleNetwork.CHANNEL.sendToServer(new ServerboundEvaControlPacket(
                ServerboundEvaControlPacket.ACTION_JUMP, jumpRequestId));
        jumpRequestRetryTicks = JUMP_REQUEST_RETRY_INTERVAL - 1;
    }

    private static void clearJumpRequest()
    {
        jumpHeld = false;
        jumpRequestPending = false;
        jumpRequestRetryTicks = 0;
        jumpRequestEvaId = -1;
        jumpRequestId = -1;
        jumpRepeatArmed = false;
    }

    private static Entity findEntryPlugTarget(LocalPlayer player)
    {
        double interactionRange = EvaScale.ENTRY_PLUG_INTERACTION_RANGE;
        AABB carrierSearch = player.getBoundingBox().inflate(interactionRange);
        EntryPlugCarrierEntity carrier = player.level().getEntitiesOfClass(
                        EntryPlugCarrierEntity.class, carrierSearch,
                        plug -> plug.isAlive() && plug.isHatchOpen()
                                && isExternalPlugTargeted(player, plug)
                                && hasClearExternalPlugPath(player, plug)).stream()
                .min((left, right) -> Double.compare(
                        left.distanceToSqr(player), right.distanceToSqr(player)))
                .orElse(null);
        if (carrier != null)
        {
            return carrier;
        }

        // Compatibility path for the isolated launch-silo prototype, which has
        // no physical overhead capsule. Canonical GeoFront cages always expose
        // the carrier above and therefore take the branch above.
        AABB search = player.getBoundingBox().inflate(18.0D, 48.0D, 18.0D);
        return player.level().getEntitiesOfClass(EvaUnit01Entity.class, search,
                        unit -> unit.isAlive() && !unit.isVehicle()
                                && !unit.isNervLogisticsLocked()
                                && !unit.isLaunchSequenceActive()
                                && unit.isEntryPlugTargeted(player)
                                && hasClearEntryPlugPath(player, unit)).stream()
                .min((left, right) -> Double.compare(
                        left.getEntryPlugSocketPosition().distanceToSqr(player.getEyePosition()),
                        right.getEntryPlugSocketPosition().distanceToSqr(player.getEyePosition())))
                .orElse(null);
    }

    private static boolean isExternalPlugTargeted(LocalPlayer player,
                                                   EntryPlugCarrierEntity plug)
    {
        Vec3 eye = player.getEyePosition();
        // The carrier entity origin is the insertion tip and its vanilla AABB
        // remains vertical even while the capsule rotates. Target the authored
        // hatch portal instead: using the AABB centre made players aim at an
        // invisible point above/below the visible shell.
        Vec3 target = plug.hasCanonicalPose()
                ? plug.transformPlugMarker(
                        EntryPlugKinematics.HATCH_PORTAL_CENTRE_P)
                : plug.getBoundingBox().getCenter();
        Vec3 direction = target.subtract(eye);
        double interactionRange = EvaScale.ENTRY_PLUG_INTERACTION_RANGE;
        return direction.lengthSqr() <= interactionRange * interactionRange
                && direction.lengthSqr() > 1.0E-4D
                && direction.normalize().dot(player.getViewVector(1.0F))
                        >= 0.35D;
    }

    private static boolean hasClearExternalPlugPath(LocalPlayer player,
                                                     EntryPlugCarrierEntity plug)
    {
        Vec3 eye = player.getEyePosition();
        Vec3 target = plug.hasCanonicalPose()
                ? plug.transformPlugMarker(
                        EntryPlugKinematics.HATCH_PORTAL_CENTRE_P)
                : plug.getBoundingBox().getCenter();
        BlockHitResult hit = player.level().clip(new ClipContext(
                eye, target, ClipContext.Block.COLLIDER,
                ClipContext.Fluid.NONE, player));
        return hit.getType() == HitResult.Type.MISS
                || hit.getLocation().distanceToSqr(target) <= 3.0D * 3.0D;
    }

    /**
     * Do not consume a normal right-click merely because an EVA socket lies
     * behind a wall. The server repeats this trace before authorizing entry.
     */
    private static boolean hasClearEntryPlugPath(LocalPlayer player, EvaUnit01Entity unit)
    {
        Vec3 eye = player.getEyePosition();
        Vec3 socket = unit.getEntryPlugSocketPosition();
        BlockHitResult hit = player.level().clip(new ClipContext(
                eye, socket, ClipContext.Block.COLLIDER, ClipContext.Fluid.NONE, player));
        return hit.getType() == HitResult.Type.MISS
                || hit.getLocation().distanceToSqr(socket) <= 0.75D * 0.75D;
    }

    @SubscribeEvent
    public static void onRenderPlayer(RenderPlayerEvent.Pre event)
    {
        if (EvaPilotResolver.sealedInAirframe(event.getEntity()))
        {
            event.setCanceled(true);
            return;
        }
        if (event.getEntity() instanceof AbstractClientPlayer clientPlayer
                && UltramanClientState.hidePlayer(clientPlayer))
        {
            event.setCanceled(true);
            return;
        }
        if (CommanderPoseClient.isActive(event.getEntity()))
        {
            PlayerModel<?> model = event.getRenderer().getModel();
            COMMANDER_ARM_VISIBILITY.set(new ArmVisibility(
                    model.rightArm.visible, model.leftArm.visible,
                    model.rightSleeve.visible, model.leftSleeve.visible));
            // Lean the complete player around the hips. Applying one render
            // transform keeps head, torso, legs and the custom elbow layer in
            // the same coordinate frame instead of tearing the waist apart.
            float bodyYaw = Mth.rotLerp(event.getPartialTick(),
                    event.getEntity().yBodyRotO, event.getEntity().yBodyRot);
            float facingRadians = (float)Math.toRadians(bodyYaw);
            double forwardX = -Math.sin(facingRadians) * 0.25D;
            double forwardZ = Math.cos(facingRadians) * 0.25D;
            float renderYaw = (float)Math.toRadians(180.0F - bodyYaw);
            float axisX = (float)Math.cos(renderYaw);
            float axisZ = (float)-Math.sin(renderYaw);
            Quaternionf lean = new Quaternionf().fromAxisAngleRad(
                    axisX, 0.0F, axisZ, (float)Math.toRadians(-20.0D));
            event.getPoseStack().pushPose();
            // The authored top slab sits slightly above the vanilla seated
            // model's visual origin. Raise the complete rendered player by
            // 1/8 block so the elbow centres rest on, not inside, the slab.
            event.getPoseStack().translate(forwardX, 0.125D, forwardZ);
            event.getPoseStack().translate(0.0D, 0.75D, 0.0D);
            event.getPoseStack().mulPose(lean);
            event.getPoseStack().translate(0.0D, -0.75D, 0.0D);
        }
    }

    @SubscribeEvent
    public static void onRenderPlayerPost(RenderPlayerEvent.Post event)
    {
        ArmVisibility visibility = COMMANDER_ARM_VISIBILITY.get();
        if (visibility != null)
        {
            PlayerModel<?> model = event.getRenderer().getModel();
            model.rightArm.visible = visibility.rightArm();
            model.leftArm.visible = visibility.leftArm();
            model.rightSleeve.visible = visibility.rightSleeve();
            model.leftSleeve.visible = visibility.leftSleeve();
            event.getPoseStack().popPose();
            COMMANDER_ARM_VISIBILITY.remove();
        }
    }

    @SubscribeEvent
    public static void onClientPlayerSize(EntityEvent.Size event)
    {
        if (!(event.getEntity() instanceof AbstractClientPlayer player))
        {
            return;
        }
        float scale = UltramanClientState.scale(player, 0.0F);
        if (scale <= 1.001F)
        {
            return;
        }
        event.setNewSize(event.getNewSize().scale(scale));
        event.setNewEyeHeight(event.getNewEyeHeight() * scale);
    }

    @SubscribeEvent
    public static void onClientLogout(ClientPlayerNetworkEvent.LoggingOut event)
    {
        EvaCommandFeedClient.resetConnectionState();
        CockpitFeedbackClient.resetConnectionR45();
        ClientAlarmState.resetConnectionR45();
        AlarmOverlay.INSTANCE.resetConnectionR45();
        com.projectseele.client.fx.ClientFxManager.clear();
    }

    private record ArmVisibility(boolean rightArm, boolean leftArm,
                                 boolean rightSleeve, boolean leftSleeve)
    {
    }

    @SubscribeEvent
    public static void onComputeFovModifier(ComputeFovModifierEvent event)
    {
        if(!Minecraft.getInstance().options.getCameraType().isFirstPerson())return;
        // Sniper zoom: the scope narrows as the positron cannon charges.
        if (event.getPlayer() instanceof LocalPlayer player)
        {
            EvaUnit01Entity eva = ridden(player);
            if (isCannonScopeActive(eva))
            {
                event.setNewFovModifier(Mth.lerp(eva.chargeProgress(), 1.0F, 0.16F));
            }
            else if (isRifleSightActive(eva))
            {
                event.setNewFovModifier(eva.isExperimentalUnit()?0.72F:Mth.lerp(eva.rifleSightBlendR45(0),1F,.72F));
            }
        }
    }
}
