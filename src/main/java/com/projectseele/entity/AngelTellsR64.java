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
 * The owner's rule (2026-11-16): what is shown has to belong to the world of the original, not to an action game's
 * interface. So there are no marks, lines or rings drawn for the player's benefit. Each tell is something the
 * Angel itself does in the original:
 * <ul>
 * <li>Sachiel's lance is light: before it is driven out, light gathers in the palm it comes from. Its other
 * strikes have no light; they are heard, a low note of the moving limb, on their first tick.</li>
 * <li>Ramiel gathers light where its body faces its target before it fires, and its crystal rings higher as the
 * charge completes. Its open core bleeds a thin ring of light that fades as it closes; its field, struck, rings.</li>
 * <li>A giant thrown into a building or onto the ground raises a cloud of dust and debris.</li>
 * </ul>
 */
public final class AngelTellsR64
{
    /** The light of Sachiel's lance, and of Ramiel's charge as it gathers and when it is about to go. */
    private static final DustParticleOptions LANCE=new DustParticleOptions(new Vector3f(1F,.82F,.95F),4F);
    private static final DustParticleOptions GATHER=new DustParticleOptions(new Vector3f(1F,.55F,.70F),3F);
    private static final DustParticleOptions READY=new DustParticleOptions(new Vector3f(1F,.95F,.95F),4F);
    /** Review only: -Dprojectseele.combatDiagR64=true tells every tell (R64TELL). */
    private static final boolean DIAG=Boolean.getBoolean("projectseele.combatDiagR64");
    private static void told(ServerLevel level,String what)
    {if(DIAG)com.projectseele.ProjectSeele.LOGGER.info("R64TELL tick {} {}",level.getGameTime(),what);}

    /** Sachiel, each tick of a strike's wind-up. */
    public static void strike(SachielEntity actor,int mode,int age)
    {
        if(!EvaCombatModelR64.angels()||!(actor.level() instanceof ServerLevel level)||age>SachielStrike.windup(mode))return;
        boolean lance=mode==SachielStrike.PILE,heavy=lance||mode==SachielStrike.OVERHEAD||mode==SachielStrike.STOMP;
        Vec3 limb=SachielStrike.sample(actor,age,1,SachielStrike.strikingLeft(mode)).hand();
        if(age==1)
        {
            // The limb is heard as it begins to move: low and long for a heavy strike, short for the palm.
            CombatFoleyR36.angelSwing(actor,limb,heavy?2.8F:1.5F,lance?.62F:heavy?.5F:1.2F);
            told(level,"sachiel strike "+mode+(lance?" lance":heavy?" heavy":" light")+": called "+SachielStrike.windup(mode)+" ticks before it can land");
        }
        if(lance)
        {
            // Light gathers in the palm: more of it, and closer in, as the lance is about to be driven out.
            float done=age/(float)SachielStrike.windup(mode);
            double spread=2.4-1.7*done;
            GiantParticles.send(level,LANCE,limb.x,limb.y,limb.z,8+Math.round(28*done),spread,spread,spread,.01);
        }
    }

    /** Ramiel, each tick of its charge: light gathers where its body faces its target. */
    public static void charge(ServerLevel level,Vec3 core,LivingEntity target,int left)
    {
        if(!EvaCombatModelR64.angels()||target==null)return;
        Vec3 line=target.position().add(0,target.getBbHeight()*.5,0).subtract(core);double length=line.length();
        if(length<1)return;
        Vec3 face=core.add(line.scale(7/length));
        boolean last=left<=20;
        // Drawn in from a wide shell to a point: the shell closes as the charge runs out.
        double shell=last?2.0:3+9*Math.min(1,left/50D);
        GiantParticles.send(level,last?READY:GATHER,face.x,face.y,face.z,last?40:16,shell,shell,shell,.01);
        if(left==20||left==10||left==5)
        {
            told(level,"ramiel charge "+left+" ticks to go: light at the face toward its target "+Math.round(length)+" blocks off, crystal rings");
            level.playSound(null,BlockPos.containing(face),ModSounds.CRYSTAL_HIT.get(),SoundSource.HOSTILE,3.5F,left==20?1.25F:left==10?1.55F:1.9F);
        }
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
            GiantParticles.send(level,ParticleTypes.END_ROD,core.x+Math.cos(a)*7,core.y,core.z+Math.sin(a)*7,1,0,0,0,0);
        }
    }
    /** Ramiel's core has closed. */
    public static void sealed(ServerLevel level,Vec3 core)
    {
        if(!EvaCombatModelR64.angels())return;
        told(level,"ramiel core sealed");
        level.playSound(null,BlockPos.containing(core),ModSounds.CRYSTAL_HIT.get(),SoundSource.HOSTILE,3.5F,.42F);
    }
    /** Ramiel's sealed field has taken the blow before the one it throws back: it rings, and flares toward the striker. */
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
        streaks(level,new Vec3(at.x,y+2,at.z),new Vec3(0,1,0),Math.min(1.2F,strength));
    }

    /**
     * The mod's own impact streaks at a point. Vanilla particles are drawn for a world of two-block bodies: a puff
     * two blocks across is six pixels on a body seventy blocks tall seen whole, and in three captures of a body
     * driven into a wall nothing of the chips, puffs and cloud above was to be made out. The streaks are drawn at
     * the giants' scale. A cloud of dust at that scale needs an effect of its own and is not made here.
     */
    private static void streaks(ServerLevel level,Vec3 at,Vec3 direction,float strength)
    {
        com.projectseele.network.SeeleNetwork.CHANNEL.send(
                net.minecraftforge.network.PacketDistributor.NEAR.with(()->new net.minecraftforge.network.PacketDistributor.TargetPoint(at.x,at.y,at.z,192,level.dimension())),
                new com.projectseele.network.ClientboundCombatImpactR36(at,direction,strength,false));
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
        streaks(level,at,direction.scale(-1),1.2F);
    }

    private AngelTellsR64(){}
}
