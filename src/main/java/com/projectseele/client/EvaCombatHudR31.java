package com.projectseele.client;

import com.projectseele.entity.Angel;
import com.projectseele.entity.EntryPlugCarrierEntity;
import com.projectseele.entity.EvaAirTransportR31;
import com.projectseele.entity.EvaCombatR31;
import com.projectseele.entity.EvaPrototypeEntity;
import com.projectseele.entity.EvaShutdownR30;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.RamielEntity;
import com.projectseele.entity.SachielEntity;
import com.projectseele.entity.ShamshelEntity;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.Font;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.player.LocalPlayer;
import net.minecraft.network.chat.Component;
import net.minecraft.util.Mth;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.level.ClipContext;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.client.event.RenderGuiOverlayEvent;
import net.minecraftforge.client.gui.overlay.IGuiOverlay;
import net.minecraftforge.client.gui.overlay.VanillaGuiOverlay;
import org.jetbrains.annotations.Nullable;
import java.lang.ref.WeakReference;
import java.util.Locale;

/** Read-only chase-camera instruments. They neither select nor lock combat targets. */
public final class EvaCombatHudR31
{
    private static final int ORANGE=0xFFF59A45,WHITE=0xFFDEE5DF,MUTED=0xFF9BA9A7;
    private static final int GREEN=0xFF7FBF91,RED=0xFFEA6958,CYAN=0xFF75BDC5;
    private static WeakReference<LivingEntity> sighted=new WeakReference<>(null);
    private static WeakReference<LocalPlayer> sightOwner=new WeakReference<>(null);
    private static int sightTick=Integer.MIN_VALUE;

    /** An external docked/ejected capsule is not an active EVA pilot seat. */
    @Nullable
    public static EvaUnit01Entity piloted(LocalPlayer player)
    {
        if(player==null||player.isSpectator())return null;
        if(player.getVehicle() instanceof EvaUnit01Entity eva)
            return eva.getPilotEntity()==player?eva:null;
        if(player.getVehicle() instanceof EntryPlugCarrierEntity plug
                &&plug.getInsertionStage()==EntryPlugCarrierEntity.STAGE_LOCKED&&plug.isLockedToEva())
        {
            var eva=plug.getLinkedEva();
            return eva!=null&&eva.isEntryPlugInserted()&&eva.getPilotEntity()==player?eva:null;
        }
        return null;
    }

    public static boolean shouldHideVanilla(RenderGuiOverlayEvent.Pre event)
    {
        var mc=Minecraft.getInstance();
        if(mc.screen!=null||piloted(mc.player)==null)return false;
        var overlay=event.getOverlay();
        return overlay==VanillaGuiOverlay.HOTBAR.type()
                ||overlay==VanillaGuiOverlay.PLAYER_HEALTH.type()
                ||overlay==VanillaGuiOverlay.ARMOR_LEVEL.type()
                ||overlay==VanillaGuiOverlay.FOOD_LEVEL.type()
                ||overlay==VanillaGuiOverlay.MOUNT_HEALTH.type()
                ||overlay==VanillaGuiOverlay.AIR_LEVEL.type()
                ||overlay==VanillaGuiOverlay.EXPERIENCE_BAR.type()
                ||overlay==VanillaGuiOverlay.JUMP_BAR.type()
                ||mc.options.getCameraType().isFirstPerson()&&overlay==VanillaGuiOverlay.CROSSHAIR.type();
    }

    public static final IGuiOverlay OVERLAY=(gui,g,partial,width,height)->
    {
        var mc=Minecraft.getInstance();
        if(mc.screen!=null||mc.options.hideGui||mc.options.getCameraType().isFirstPerson()||FirstBattleClient.active())return;
        EvaUnit01Entity eva=piloted(mc.player);
        if(eva==null||mc.level==null)return;
        int panelWidth=Math.min(166,Math.max(120,width/3)),x=8,y=Math.max(8,height-79);
        Font font=gui.getFont();panel(g,x,y,panelWidth,70,ORANGE);
        String identity=eva instanceof EvaPrototypeEntity un?"UN / "+com.projectseele.entity.Unit03SourceRigR53.displayName(un.getUNSerial())
                :String.format(Locale.ROOT,"NERV / EVA-%02d",eva.getUnitVariant());
        text(g,font,identity,x+7,y+5,panelWidth-14,ORANGE);
        String hp=String.format(Locale.ROOT,"%.0f / %.0f",Math.max(0,eva.getHealth()),eva.getMaxHealth());
        text(g,font,"机体",x+7,y+17,35,MUTED);
        g.drawString(font,hp,x+panelWidth-7-font.width(hp),y+17,WHITE,false);
        float fraction=Mth.clamp(eva.getHealth()/Math.max(1,eva.getMaxHealth()),0,1);
        bar(g,x+7,y+28,panelWidth-14,fraction,fraction<.3F?RED:GREEN);
        text(g,font,power(eva),x+7,y+34,panelWidth-14,EvaShutdownR30.disabled(eva)?RED:MUTED);
        String weapon=Component.translatable(eva.getWeaponTranslationKey()).getString();
        text(g,font,weapon,x+7,y+45,panelWidth-14,WHITE);
        text(g,font,actionHint(mc,eva),x+7,y+57,panelWidth-14,ORANGE);
        var target=lookedAt(mc,eva);
        if(target!=null&&y>=54)target(g,font,target,x,y-45,panelWidth);
    };

    private static String power(EvaUnit01Entity eva)
    {
        if(EvaShutdownR30.disabled(eva))return EvaShutdownR30.mode(eva)==EvaShutdownR30.POWER_LOCK?"动力  耗尽 / 姿态锁止":"动力  关闭";
        if(eva.isExperimentalUnit())return "动力  核能";
        if(eva.isUmbilicalConnected())return "动力  外部供电";
        int seconds=Math.max(0,eva.getPowerTicks()/20);
        return String.format(Locale.ROOT,"动力  内部 %d:%02d",seconds/60,seconds%60);
    }

    private static String actionHint(Minecraft mc,EvaUnit01Entity eva)
    {
        String key=Keybinds.EVA_GRAPPLE.getTranslatedKeyMessage().getString();
        String radio=Keybinds.COMMAND_RADIO.getTranslatedKeyMessage().getString();
        if(EvaAirTransportR31.active(eva))return "运输中  /  "+radio+" 通信";
        if(EvaShutdownR30.disabled(eva))return radio+" 呼叫回收";
        if(eva.isNervLogisticsLocked()||eva.isLaunchSequenceActive())return "机械联锁  /  "+radio+" 通信";
        return switch(EvaCombatR31.action(eva))
        {
            case EvaCombatR31.REACH -> "双手接近";
            case EvaCombatR31.HOLD -> key+" / "+mc.options.keyAttack.getTranslatedKeyMessage().getString()+" 投掷";
            case EvaCombatR31.THROW -> "投掷";
            case EvaCombatR31.AIR_STRIKE -> "跳击";
            case EvaCombatR31.AIR_SLAM -> com.projectseele.entity.EvaGameplayMotionR32.ready(eva)?"下踢":"下砸";
            case EvaCombatR31.LAND -> "落地制动";
            default -> eva.isPilotProne()||eva.isPilotCrouching()?"站立后可抓取":eva.getWeapon()!=EvaUnit01Entity.WEAPON_FISTS?key+" 抓取需空手":key+" 双手抓取";
        };
    }

    @Nullable
    private static LivingEntity lookedAt(Minecraft mc,EvaUnit01Entity eva)
    {
        var cached=sighted.get();
        if(sightOwner.get()==mc.player&&sightTick==mc.player.tickCount)
            return cached!=null&&cached.isAlive()&&cached.level()==mc.level?cached:null;
        sightOwner=new WeakReference<>(mc.player);sightTick=mc.player.tickCount;LivingEntity found=null;
        var camera=mc.gameRenderer.getMainCamera();Vec3 start=camera.getPosition();
        Vec3 end=start.add(new Vec3(camera.getLookVector()).scale(240));
        var block=mc.level.clip(new ClipContext(start,end,ClipContext.Block.COLLIDER,ClipContext.Fluid.NONE,eva));
        end=block.getLocation();double nearest=start.distanceToSqr(end);
        for(var candidate:mc.level.getEntitiesOfClass(LivingEntity.class,new AABB(start,end).inflate(24,80,24),
                e->e instanceof Angel&&e.isAlive()&&!e.isSpectator()))
        {
            var hit=candidate.getBoundingBox().inflate(.15).clip(start,end);
            if(hit.isEmpty())continue;
            double distance=start.distanceToSqr(hit.get());
            if(distance<nearest){nearest=distance;found=candidate;}
        }
        sighted=new WeakReference<>(found);return found;
    }

    private static void target(GuiGraphics g,Font font,LivingEntity target,int x,int y,int width)
    {
        panel(g,x,y,width,39,CYAN);
        text(g,font,target.getDisplayName().getString(),x+7,y+5,width-14,CYAN);
        String health=String.format(Locale.ROOT,"目标 %.0f / %.0f",Math.max(0,target.getHealth()),target.getMaxHealth());
        text(g,font,health,x+7,y+16,width-14,WHITE);
        bar(g,x+7,y+26,width-14,Mth.clamp(target.getHealth()/Math.max(1,target.getMaxHealth()),0,1),CYAN);
        Float field=null;
        if(target instanceof RamielEntity ramiel)field=ramiel.getAtFieldEnergy();
        else if(target instanceof SachielEntity sachiel)field=sachiel.getAtField();
        else if(target instanceof ShamshelEntity shamshel)field=shamshel.getAtField();
        // Other Angel implementations still keep field strength server-local.
        // A default client field would falsely look like live target telemetry.
        text(g,font,field==null?"AT  暂无遥测":String.format(Locale.ROOT,"AT  %.0f",Math.max(0,field)),x+7,y+30,width-14,MUTED);
    }

    private static void panel(GuiGraphics g,int x,int y,int width,int height,int colour)
    {
        g.fill(x,y,x+width,y+height,0xCB101918);
        g.fill(x,y,x+2,y+height,colour);
        g.fill(x+2,y,x+35,y+1,colour);
        g.fill(x+width-20,y+height-1,x+width,y+height,0x88677C72);
    }
    private static void bar(GuiGraphics g,int x,int y,int width,float value,int colour)
    {
        g.fill(x,y,x+width,y+3,0xFF283832);
        g.fill(x,y,x+Math.round(width*value),y+3,colour);
    }
    private static void text(GuiGraphics g,Font font,String value,int x,int y,int width,int colour)
    {g.drawString(font,font.plainSubstrByWidth(value,Math.max(1,width)),x,y,colour,false);}
    private EvaCombatHudR31() {}
}
