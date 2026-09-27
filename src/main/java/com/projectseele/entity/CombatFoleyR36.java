package com.projectseele.entity;

import com.projectseele.registry.ModSounds;
import com.projectseele.util.WeakIdentityMap;
import net.minecraft.sounds.SoundEvent;
import net.minecraft.sounds.SoundSource;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.phys.Vec3;

/** Sparse positional cues. Contact, air and material sounds have distinct roles. */
public final class CombatFoleyR36
{
    private static final WeakIdentityMap<LivingEntity,Long> STEPS=new WeakIdentityMap<>();
    private static void play(LivingEntity actor,Vec3 point,SoundEvent sound,float volume,float pitch)
    {
        if(actor.level().isClientSide||actor.isSilent())return;
        actor.level().playSound(null,point.x,point.y,point.z,SoundEvent.createFixedRangeEvent(sound.getLocation(),384),actor instanceof SachielEntity?SoundSource.HOSTILE:SoundSource.PLAYERS,volume,pitch);
    }
    public static void step(LivingEntity actor,Vec3 foot,boolean soil,float load)
    {
        long now=actor.level().getGameTime();if(now-STEPS.getOrDefault(actor,-100L)<3)return;STEPS.put(actor,now);
        var ground=actor.level().getBlockState(net.minecraft.core.BlockPos.containing(foot.x,foot.y-.2,foot.z));
        soil|=ground.is(net.minecraft.tags.BlockTags.DIRT)||ground.is(net.minecraft.tags.BlockTags.SAND)||ground.is(net.minecraft.tags.BlockTags.LEAVES);
        play(actor,foot,actor instanceof SachielEntity?ModSounds.SACHIEL_FOOT.get():soil?ModSounds.EVA_FOOT_SOIL.get():ModSounds.EVA_FOOT_CONCRETE.get(),2.5F*load,1);
    }
    public static void load(EvaUnit01Entity actor)
    {play(actor,actor.position().add(0,actor.getBbHeight()*.57,0),ModSounds.EVA_JOINT_LOAD.get(),.8F,1);}
    /** Called once by a transport job after stable physical bearing contact. */
    public static void airliftTouchdown(EvaUnit01Entity actor,Vec3 contact)
    {
        play(actor,contact,ModSounds.EVA_LAND.get(),4.2F,.92F);
        play(actor,contact.add(0,actor.getBbHeight()*.18,0),
                ModSounds.EVA_JOINT_LOAD.get(),.9F,.86F);
        com.projectseele.ProjectSeele.LOGGER.info("EVA transport load transferred: unit={} contact={}",actor.getUUID(),contact);
        com.projectseele.visual.AirLiftR30Review.touchdown(actor);
    }
    public static void swing(SachielEntity actor)
    {play(actor,SachielStrike.sample(actor,0).hand(),ModSounds.SACHIEL_SWING.get(),1.5F,1);}
    public static void impact(LivingEntity actor,LivingEntity target,Vec3 point,boolean field,boolean heavy)
    {
        var sound=field?ModSounds.EVA_AT_PRESSURE.get():heavy?ModSounds.EVA_IMPACT_HEAVY.get():target instanceof EvaUnit01Entity?ModSounds.EVA_ARMOR_IMPACT.get():ModSounds.EVA_IMPACT.get();
        play(actor,point,sound,field?1.7F:heavy?4.4F:3.2F,1);
    }
    private CombatFoleyR36(){}
}
