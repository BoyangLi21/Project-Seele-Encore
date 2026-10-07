package com.projectseele.entity;

import com.projectseele.ProjectSeele;
import net.minecraft.world.entity.MoverType;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.event.entity.living.LivingBreatheEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Heavy B-type bodies sink onto the real sea floor; sealed cabins keep air. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class EvaImmersionR50
{
    public static boolean travel(EvaUnit01Entity eva,Vec3 input)
    {
        if(eva.isExperimentalUnit()||!eva.isInWater()||eva.isNervLogisticsLocked()
                ||eva.isLaunchSequenceActive()||EvaAirTransportR31.active(eva)
                ||EvaShutdownR30.displayed(eva)||eva.isNoGravity())return false;
        if(!eva.isControlledByLocalInstance())return false;
        eva.moveRelative(eva.getSpeed()*.45F,input);
        Vec3 velocity=eva.getDeltaMovement();
        double falling=eva.onGround()?Math.min(0,velocity.y):Math.max(-.65,velocity.y-.065);
        velocity=new Vec3(velocity.x,falling,velocity.z);
        eva.move(MoverType.SELF,velocity);
        eva.setDeltaMovement(velocity.x*.8,eva.verticalCollision?0:velocity.y*.96,velocity.z*.8);
        eva.resetFallDistance();return true;
    }

    @SubscribeEvent public static void breathing(LivingBreatheEvent event)
    {
        var actor=event.getEntity();
        boolean sealed=actor instanceof EvaUnit01Entity
                ||actor instanceof EntryPlugCarrierEntity plug&&plug.isHatchFullySealed()
                ||actor.getVehicle() instanceof EntryPlugCarrierEntity plug&&plug.isHatchFullySealed();
        if(!sealed)return;
        event.setCanBreathe(true);event.setCanRefillAir(true);
        event.setConsumeAirAmount(0);event.setRefillAirAmount(4);
    }
    private EvaImmersionR50(){}
}
