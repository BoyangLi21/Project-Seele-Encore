package com.projectseele.entity;

import com.projectseele.config.SeeleConfig;
import com.projectseele.registry.ModSounds;
import com.projectseele.util.WeakIdentityMap;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.protocol.game.ClientboundStopSoundPacket;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.sounds.SoundSource;
import net.minecraft.util.Mth;
import net.minecraft.world.phys.Vec3;

/**
 * Sound for pilot actions that played none, all on recorded events the game
 * already loads. Volume at or above 1 only widens the audible radius (the
 * mixer clamps gain to 1), so anything meant to sit under the main cue
 * stays below 1. Timings come from each action's own clock or clip contacts.
 */
final class EvaActionFoleyR61
{
    private static final WeakIdentityMap<EvaUnit01Entity,Boolean> DASHING=new WeakIdentityMap<>();
    private static final WeakIdentityMap<EvaUnit01Entity,Long> DASH_AT=new WeakIdentityMap<>();
    private static final WeakIdentityMap<EvaUnit01Entity,Integer> CANNON=new WeakIdentityMap<>();
    private static final WeakIdentityMap<EvaUnit01Entity,boolean[]> PLANTS=new WeakIdentityMap<>();
    /** Length of beam_charge at pitch 1 (ticks), to fit it to the cannon's own charge time. */
    private static final float CHARGE_CLIP_TICKS=52;

    private static Vec3 chest(EvaUnit01Entity e){return e.position().add(0,e.getBbHeight()*.57,0);}
    private static boolean crossed(float before,float now,float at){return before<at&&now>=at;}

    /** The sole leaving the ground as the body is thrown upward. */
    static void takeoff(EvaUnit01Entity e)
    {EvaMovementSounds.play(e,e.position(),ModSounds.EVA_LAND.get(),.75F,1.18F);}

    /** Tick of a stroke's air sound: the same lead over contact the punches use. */
    static int strokeTick(float duration,int contactTick)
    {return Math.max(1,contactTick-Math.round(duration*.19F));}

    static void knifeStroke(EvaUnit01Entity e,boolean reverse,int elapsed,float duration)
    {
        if(!EvaGameplayMotionR32.knifeReady(e))return;
        float phase=EvaGameplayMotionR32.swingSoundPhaseR45(e,reverse?"knife_reverse":"knife_forward");
        if(elapsed==Math.max(1,Mth.ceil(duration*phase)))EvaMovementSounds.swing(e,reverse?2.4F:2F);
    }

    /** The air sound already played on a live kick or knife stroke, so a miss stays quiet. */
    static boolean strokeSwung(EvaUnit01Entity e)
    {return e.isKickMotionActive(0)||e.getKnifeMotionType(0)>=0&&EvaGameplayMotionR32.knifeReady(e);}

    static void dash(EvaUnit01Entity e,boolean enabled)
    {
        Boolean was=DASHING.get(e);DASHING.put(e,enabled);
        // The stride blend is still rising on the tick a dash starts from rest.
        if(was==null||was==enabled||!e.onGround()||!e.pilotLocomotionRequestedR45()&&e.rifleMoveBlend(1)<.2F)return;
        long now=e.level().getGameTime();
        if(now-DASH_AT.getOrDefault(e,-100L)<8)return;DASH_AT.put(e,now);
        if(enabled)
        {
            CombatFoleyR36.load(e);
            EvaMovementSounds.play(e,chest(e),ModSounds.EVA_SWING.get(),1.4F,.66F);
            EvaMovementSounds.play(e,e.position(),ModSounds.EVA_LAND.get(),.7F,1.22F);
        }
        else EvaMovementSounds.play(e,e.position(),ModSounds.EVA_LAND.get(),.9F,.88F);
    }

    /** Lying down there is no sole contact to test: one drag of the body per half gait cycle. */
    static void crawl(EvaUnit01Entity e,float previous,float phase,boolean moving)
    {
        if(moving&&Math.floor(previous*2)!=Math.floor(phase*2))CombatFoleyR36.step(e,e.position(),false,.24F);
    }

    static void fieldStart(EvaUnit01Entity e,String clip)
    {
        PLANTS.remove(e);
        CombatFoleyR36.load(e);
        if(EvaFieldActionsR45.CLIMB.equals(clip))return;
        boolean roll=clip.startsWith("roll");
        EvaMovementSounds.play(e,chest(e),ModSounds.EVA_SWING.get(),roll?2.2F:1.6F,roll?.72F:.82F);
        EvaMovementSounds.play(e,e.position(),ModSounds.EVA_LAND.get(),roll?.6F:.55F,roll?1.1F:1.18F);
    }

    /** Evade and roll soles follow the clip's own contacts; the climb follows its authored beats. */
    static void fieldTick(EvaUnit01Entity e,CompoundTag state,int elapsed,int duration)
    {
        float now=elapsed/(float)duration,before=(elapsed-1)/(float)duration;
        String clip=state.getString("clip");
        if(EvaFieldActionsR45.CLIMB.equals(clip)){climb(e,state,before,now);return;}
        if(clip.startsWith("roll")&&crossed(before,now,.5F))
            EvaMovementSounds.play(e,e.position(),ModSounds.EVA_LAND.get(),1F,.92F);
        boolean[] last=PLANTS.get(e);
        boolean[] plants={EvaGameplayMotionR32.planted(e,"l",0),EvaGameplayMotionR32.planted(e,"r",0)};
        PLANTS.put(e,plants);
        if(last==null)return;
        for(int i=0;i<2;i++)if(plants[i]&&!last[i])CombatFoleyR36.step(e,e.position(),false,.6F);
    }

    private static void climb(EvaUnit01Entity e,CompoundTag state,float before,float now)
    {
        Vec3 forward=Vec3.directionFromRotation(0,state.getFloat("facing")).multiply(1,0,1).normalize();
        double advance=state.getDouble("advance");
        Vec3 top=new Vec3(state.getDouble("x0")+forward.x*advance,state.getDouble("y0")+state.getDouble("rise"),state.getDouble("z0")+forward.z*advance);
        if(EvaClimbChoreographyR57.stepUp(state.getDouble("rise")))
        {
            if(crossed(before,now,.3F))CombatFoleyR36.step(e,top,false,1F);
            if(crossed(before,now,.8F))CombatFoleyR36.step(e,top,false,.8F);
            return;
        }
        if(crossed(before,now,.2F))EvaMovementSounds.play(e,top,ModSounds.EVA_LAND.get(),.7F,1.12F);
        if(crossed(before,now,.45F))CombatFoleyR36.load(e);
        if(crossed(before,now,.82F))CombatFoleyR36.step(e,top,false,.9F);
        if(crossed(before,now,.91F))CombatFoleyR36.step(e,top,false,.8F);
    }

    /** Knife rack beats, matching the hatch and handoff curves in EvaWeaponHandlingR45. */
    static void weaponTick(EvaUnit01Entity e,CompoundTag state,float t)
    {
        boolean draw=state.getBoolean("draw");
        float before=t-1F/Math.max(1,state.getInt("duration"));
        Vec3 rack=e.position().add(0,e.getBbHeight()*.72,0);
        var latch=ModSounds.FACILITY.get("facility_lock").get();
        if(crossed(before,t,draw?.06F:.16F))EvaMovementSounds.play(e,rack,latch,.8F,1.25F);
        if(crossed(before,t,draw?.78F:.9F))EvaMovementSounds.play(e,rack,latch,.7F,1.1F);
        if(crossed(before,t,draw?.54F:.46F))
        {
            if(draw)EvaMovementSounds.play(e,rack,ModSounds.EVA_KNIFE_CUT.get(),.55F,1.35F);
            else EvaMovementSounds.play(e,rack,ModSounds.EVA_ARMOR_IMPACT.get(),.45F,1.45F);
        }
    }

    /** Charge sound runs at the cannon's charge length and is cut if the pilot lets go early. */
    static void cannonCharge(EvaUnit01Entity e)
    {
        if(!(e.level() instanceof ServerLevel level))return;
        int now=e.getCannonCharge();int before=CANNON.getOrDefault(e,0);
        if(now==before)return;CANNON.put(e,now);
        int full=SeeleConfig.CANNON_CHARGE_TICKS.get();
        if(before==0&&now>0)
        {
            Vec3 at=chest(e);
            level.playSound(null,at.x,at.y,at.z,ModSounds.BEAM_CHARGE.get(),SoundSource.PLAYERS,1.6F,Mth.clamp(CHARGE_CLIP_TICKS/full,.5F,2F));
        }
        else if(now>=full&&before<full&&e.getPilotEntity()!=null)
            EvaMovementSounds.play(e,e.getPilotCameraSeatPosition(e.getPilotEntity()),ModSounds.EVA_COCKPIT_CONFIRM.get(),.5F,1.2F);
        else if(now==0&&before<full)
        {
            var stop=new ClientboundStopSoundPacket(ModSounds.BEAM_CHARGE.getId(),SoundSource.PLAYERS);
            for(var player:level.players())if(player.distanceToSqr(e)<128*128)player.connection.send(stop);
        }
    }

    private EvaActionFoleyR61(){}
}
