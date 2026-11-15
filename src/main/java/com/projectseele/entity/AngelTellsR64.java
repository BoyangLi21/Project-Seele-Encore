package com.projectseele.entity;

import com.projectseele.registry.ModSounds;
import com.projectseele.world.GiantParticles;
import net.minecraft.core.BlockPos;
import net.minecraft.core.particles.BlockParticleOption;
import net.minecraft.core.particles.DustParticleOptions;
import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.sounds.SoundSource;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.level.ClipContext;
import net.minecraft.world.phys.HitResult;
import net.minecraft.world.phys.Vec3;
import org.joml.Vector3f;

/**
 * R64 (M5): what an Angel's attack lets the pilot see and hear before it lands, and what a body lets him see and
 * hear when it meets the ground or a wall. Particles and sounds only, sent by the server: nothing here changes a
 * block or a number of the fight. All of it is on where the server runs the frames core (EvaCombatModelR64.angels).
 * <p>
 * Sachiel: up to M4 a strike made its first sound on the tick it could land. Now every strike is called on its
 * first tick: a light one with a short high note of its own air sound, a heavy one (overhead, lance, stomp) with a
 * long low one and with red dust at the hand or foot it is thrown with for as long as it winds up.
 * <p>
 * Ramiel: the charge draws a dotted line from the core to where the beam would land now and, in its last second,
 * a ring on the ground there, with three rising notes at 20, 10 and 5 ticks to go. The open core is ringed with
 * light that thins as the window runs out, and seals with a low note. The second blow of three on its sealed field
 * rings a warning: the third is thrown back.
 */
public final class AngelTellsR64
{
    private static final DustParticleOptions HEAVY=new DustParticleOptions(new Vector3f(1F,.10F,.06F),4.5F);
    private static final DustParticleOptions AIM=new DustParticleOptions(new Vector3f(1F,.55F,.70F),3F);
    private static final DustParticleOptions LOCKED=new DustParticleOptions(new Vector3f(1F,.95F,.95F),3.5F);
    /** Review only: -Dprojectseele.combatDiagR64=true tells every tell (R64TELL). */
    private static final boolean DIAG=Boolean.getBoolean("projectseele.combatDiagR64");
    private static void told(ServerLevel level,String what)
    {if(DIAG)com.projectseele.ProjectSeele.LOGGER.info("R64TELL tick {} {}",level.getGameTime(),what);}

    /** Sachiel, each tick of a strike. */
    public static void strike(SachielEntity actor,int mode,int age)
    {
        if(!EvaCombatModelR64.angels()||!(actor.level() instanceof ServerLevel level)||age>SachielStrike.windup(mode))return;
        boolean heavy=mode==SachielStrike.OVERHEAD||mode==SachielStrike.PILE||mode==SachielStrike.STOMP;
        Vec3 limb=SachielStrike.sample(actor,age,1,SachielStrike.strikingLeft(mode)).hand();
        if(age==1)
        {
            CombatFoleyR36.angelSwing(actor,limb,heavy?2.8F:1.5F,heavy?.5F:1.75F);
            told(level,"sachiel strike "+mode+(heavy?" heavy":" light")+": called "+SachielStrike.windup(mode)+" ticks before it can land");
        }
        if(heavy&&age%2==1)GiantParticles.send(level,HEAVY,limb.x,limb.y,limb.z,18,2.4,2.4,2.4,.02);
    }

    /** Sachiel's stomp comes down. */
    public static void stomp(SachielEntity actor,int mode,int age)
    {
        if(!EvaCombatModelR64.angels()||mode!=SachielStrike.STOMP||age!=SachielStrike.contactStart(mode)||!(actor.level() instanceof ServerLevel level))return;
        Vec3 sole=SachielStrike.sample(actor,age,1,SachielStrike.strikingLeft(mode)).hand();
        told(level,"sachiel stomp comes down");
        ground(level,new Vec3(sole.x,actor.getY(),sole.z),1F);
    }

    /** Ramiel, each tick of its charge: where the beam would land now. */
    public static void charge(ServerLevel level,Vec3 core,LivingEntity target,int left)
    {
        if(!EvaCombatModelR64.angels()||target==null)return;
        Vec3 mark=target.position().add(0,target.getBbHeight()*.5,0),line=mark.subtract(core);double length=line.length();
        if(length<1)return;
        boolean last=left<=20;
        // A dotted line, running toward the mark; solid and white through the last second.
        if(last||left%2==0)
        {
            double gap=last?4:7,run=(level.getGameTime()%4)/4D*gap;
            for(double d=6+run;d<length;d+=gap)
            {
                Vec3 p=core.add(line.scale(d/length));
                GiantParticles.send(level,last?LOCKED:AIM,p.x,p.y,p.z,3,.35,.35,.35,0);
            }
        }
        if(last&&left%2==0)
        {
            double y=target.getY()+.3;
            for(int i=0;i<16;i++)
            {
                double a=i*Math.PI/8+left*.2;
                GiantParticles.send(level,LOCKED,target.getX()+Math.cos(a)*9,y,target.getZ()+Math.sin(a)*9,3,.3,.1,.3,0);
            }
        }
        if(left==20||left==10||left==5)told(level,"ramiel charge "+left+" ticks to go: line "+Math.round(length)+" blocks, ring and note");
        if(left==20||left==10||left==5)
            level.playSound(null,BlockPos.containing(mark),ModSounds.CRYSTAL_HIT.get(),SoundSource.HOSTILE,3.5F,left==20?1.25F:left==10?1.55F:1.9F);
    }

    /** Ramiel, each tick its core is open: left of total ticks of the window. */
    public static void exposed(ServerLevel level,Vec3 core,int left,int total)
    {
        if(!EvaCombatModelR64.angels()||left<=0||left%2!=0)return;
        int points=4+Math.round(12F*left/Math.max(1,total));
        told(level,"ramiel core open "+left+" of "+total+" ticks left: ring of "+points);
        for(int i=0;i<points;i++)
        {
            double a=i*2*Math.PI/points+left*.3;
            GiantParticles.send(level,ParticleTypes.END_ROD,core.x+Math.cos(a)*7,core.y+Math.sin(a*2)*1.5,core.z+Math.sin(a)*7,1,0,0,0,0);
        }
    }
    /** Ramiel's core has closed. */
    public static void sealed(ServerLevel level,Vec3 core)
    {
        if(!EvaCombatModelR64.angels())return;
        told(level,"ramiel core sealed");
        level.playSound(null,BlockPos.containing(core),ModSounds.CRYSTAL_HIT.get(),SoundSource.HOSTILE,3.5F,.42F);
    }
    /** Ramiel's sealed field has taken the blow before the one it throws back. */
    public static void fieldWarns(ServerLevel level,Vec3 core,Vec3 toward)
    {
        if(!EvaCombatModelR64.angels())return;
        told(level,"ramiel field warns: the next blow is thrown back");
        level.playSound(null,BlockPos.containing(core),ModSounds.CRYSTAL_HIT.get(),SoundSource.HOSTILE,3.5F,1.9F);
        Vec3 at=core.add(toward.scale(9));
        GiantParticles.send(level,ParticleTypes.ELECTRIC_SPARK,at.x,at.y,at.z,36,3,3,3,.3);
    }

    /**
     * A body, a foot or a pair of fists comes down on the ground: chips of the block under it, dust, and the
     * landing sound (which carries a piloted Unit's view when it is near).
     */
    public static void ground(ServerLevel level,Vec3 at,float strength)
    {
        BlockPos under=BlockPos.containing(at.x,at.y-.5,at.z);
        for(int i=0;i<6&&level.getBlockState(under).isAir();i++)under=under.below();
        var floor=level.getBlockState(under);
        told(level,"ground "+String.format(java.util.Locale.ROOT,"%.1f %.1f %.1f",at.x,at.y,at.z)+" strength "+strength+" on "+floor.getBlock().getName().getString());
        double y=under.getY()+1.4;
        if(!floor.isAir())GiantParticles.send(level,new BlockParticleOption(ParticleTypes.BLOCK,floor),at.x,y,at.z,Math.round(54*strength),5*strength,.6,5*strength,.16);
        GiantParticles.send(level,ParticleTypes.POOF,at.x,y+.6,at.z,Math.round(22*strength),4*strength,.6,4*strength,.12);
        // Chips of a block are a tenth of a block across: under bodies seventy blocks tall nothing of them was to be
        // seen four ticks after a finisher came down. Puffs two blocks across and a bank of cloud carry it.
        GiantParticles.send(level,ParticleTypes.EXPLOSION,at.x,y+1.5,at.z,Math.round(5*strength),4*strength,.8,4*strength,0);
        GiantParticles.send(level,ParticleTypes.CLOUD,at.x,y+1,at.z,Math.round(60*strength),5*strength,1.2,5*strength,.12);
        level.playSound(null,under.above(),ModSounds.EVA_LAND.get(),SoundSource.HOSTILE,4.5F*strength,.72F);
    }

    /** A body pushed back by a blow meets a wall: chips of what it met, dust, the heavy impact. */
    public static void wall(ServerLevel level,LivingEntity body,Vec3 direction)
    {
        Vec3 from=body.position().add(0,body.getBbHeight()*.45,0),to=from.add(direction.scale(body.getBbWidth()*.5+4));
        var hit=level.clip(new ClipContext(from,to,ClipContext.Block.COLLIDER,ClipContext.Fluid.NONE,body));
        Vec3 at=hit.getType()==HitResult.Type.MISS?from.add(direction.scale(body.getBbWidth()*.5)):hit.getLocation();
        var state=hit.getType()==HitResult.Type.MISS?level.getBlockState(BlockPos.containing(to)):level.getBlockState(hit.getBlockPos());
        told(level,"wall: "+body.getType().toShortString()+" pushed into "+state.getBlock().getName().getString()+" at "+String.format(java.util.Locale.ROOT,"%.1f %.1f %.1f",at.x,at.y,at.z));
        if(!state.isAir())GiantParticles.send(level,new BlockParticleOption(ParticleTypes.BLOCK,state),at.x,at.y,at.z,60,3,6,3,.2);
        GiantParticles.send(level,ParticleTypes.POOF,at.x,at.y,at.z,24,3,5,3,.14);
        GiantParticles.send(level,ParticleTypes.EXPLOSION,at.x,at.y,at.z,6,2.5,6,2.5,0);
        GiantParticles.send(level,ParticleTypes.CLOUD,at.x,at.y,at.z,70,3,7,3,.15);
        level.playSound(null,BlockPos.containing(at),ModSounds.EVA_IMPACT.get(),SoundSource.HOSTILE,5F,.66F);
        level.playSound(null,BlockPos.containing(at),ModSounds.EVA_LAND.get(),SoundSource.HOSTILE,3F,.6F);
    }

    private AngelTellsR64(){}
}
