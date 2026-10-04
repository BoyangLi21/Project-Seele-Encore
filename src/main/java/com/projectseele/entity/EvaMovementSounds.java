package com.projectseele.entity;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import com.projectseele.registry.ModSounds;
import net.minecraft.core.BlockPos;
import net.minecraft.sounds.SoundEvent;
import net.minecraft.sounds.SoundSource;
import net.minecraft.tags.BlockTags;
import net.minecraft.util.Mth;
import net.minecraft.world.phys.Vec3;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.WeakHashMap;

/** Foot contacts use the same server gait phase as the rendered body. */
public final class EvaMovementSounds
{
    private static final Map<EvaUnit01Entity,Float> PREVIOUS=new WeakHashMap<>();
    private static final boolean GEOMETRIC_CONTACTS=Boolean.parseBoolean(System.getProperty("projectseele.r45GeometricFootsteps","true"));
    private static final Map<EvaUnit01Entity,Map<String,SoleContact>> SOLES=new WeakHashMap<>();
    private static final class SoleContact {boolean raised;long tick=Long.MIN_VALUE;}
    private static final JsonObject CONTACTS=load();
    private static JsonObject load()
    {
        try(var in=EvaMovementSounds.class.getResourceAsStream("/assets/projectseele/motion/eva_gait_contacts_r10.json"))
        {
            if(in==null)throw new IllegalStateException("Missing gait sound contacts");
            return JsonParser.parseReader(new InputStreamReader(in,StandardCharsets.UTF_8)).getAsJsonObject().getAsJsonObject("contacts");
        }
        catch(Exception e){ProjectSeele.LOGGER.error("EVA gait sound contacts rejected",e);return new JsonObject();}
    }
    private static float contact(String clip,String side,boolean backwards)
    {
        if(!CONTACTS.has(clip))return side.equals("l")?.7F:.2F;
        var rows=CONTACTS.getAsJsonObject(clip).getAsJsonObject(side).getAsJsonArray(backwards?"reverse":"forward");
        return rows.isEmpty()?(side.equals("l")?.7F:.2F):rows.get(0).getAsFloat();
    }
    private static float mixContact(float from,float to,float weight)
    {
        return Mth.positiveModulo(from+(Mth.positiveModulo(to-from+.5F,1)-.5F)*weight,1);
    }
    public static void tick(EvaUnit01Entity eva,boolean moving)
    {
        if(eva.level().isClientSide||com.projectseele.physics.CombatBodyDynamics.active(eva))return;
        float phase=eva.rifleGaitPhase(1);Float previous=PREVIOUS.put(eva,phase);
        if(previous==null||!eva.onGround()||!eva.isPoweredOn()||eva.isNervLogisticsLocked()||eva.isPilotProne()||eva.isSilent()||EvaCombatSupportR33.strike(eva))
        {SOLES.remove(eva);return;}
        if(GEOMETRIC_CONTACTS&&!eva.isExperimentalUnit()
                &&(eva.getWeapon()==EvaUnit01Entity.WEAPON_FISTS||eva.getWeapon()==EvaUnit01Entity.WEAPON_KNIFE
                   ||eva.getWeapon()==EvaUnit01Entity.WEAPON_RIFLE||EvaCannonFrameR45.enabled(eva)))
        {
            // Mounted position updates can skip a tick while the visible gait
            // remains in motion. Do not forget a raised foot in that interval.
            if(!moving&&eva.rifleMoveBlend(1)<=.05F){SOLES.remove(eva);return;}
            geometricSteps(eva,phase);
            return;
        }
        if(!moving)return;
        float delta=phase-previous;if(delta>.5F)delta-=1;if(delta<-.5F)delta+=1;
        if(Math.abs(delta)<1e-5F||Math.abs(delta)>.3F)return;
        boolean backwards=delta<0;float run=eva.rifleRunBlend(1),low=Mth.clamp(eva.rifleStanceLevel(1),0,1);
        for(String side:new String[]{"l","r"})
        {
            float threshold=mixContact(
                    EvaBodyPose.locomotionContactR43(eva,"walk",side,backwards,contact("walk",side,backwards)),
                    EvaBodyPose.locomotionContactR43(eva,"run",side,backwards,contact("run",side,backwards)),run);
            threshold=mixContact(threshold,contact("crouch_walk",side,backwards),low);
            threshold=mixContact(threshold,side.equals("l")?0:.5F,EvaCombatSupportR33.gaitWeight(eva,1));
            float before=Mth.positiveModulo(previous-threshold,1),after=Mth.positiveModulo(phase-threshold,1);
            if(backwards?after<=before:after>=before)continue;
            Vec3 forward=eva.getForward().multiply(1,0,1).normalize(),lateral=new Vec3(forward.z,0,-forward.x);
            Vec3 foot=eva.position().add(lateral.scale((side.equals("l")?1:-1)*eva.getBbWidth()*.24)).add(forward.scale(backwards?-2:3));
            if(EvaGameplayMotionR32.phrases(eva))
            {
                var body=EvaBodyPose.sample(eva,0);String n="foot_"+side;
                var point=body.matrix(n).transformPosition(new org.joml.Vector3f(body.rig.get(n).pivot())).mul(5).rotateY((180-eva.getYRot())*Mth.DEG_TO_RAD);
                foot=eva.position().add(point.x,0,point.z);
            }
            var state=eva.level().getBlockState(BlockPos.containing(foot.x,foot.y-.2,foot.z));
            boolean soil=state.is(BlockTags.DIRT)||state.is(BlockTags.SAND)||state.is(BlockTags.LEAVES);
            CombatFoleyR36.step(eva,foot,soil,Mth.lerp(low,1+.28F*run,.5F));
            com.projectseele.visual.StanceContactR41Review.sound(eva,"legacy_foot_"+side,foot);
            if(eva.getTags().contains("seele_motion_lab"))ProjectSeele.LOGGER.info("EVA FOOT CONTACT side={} phase={} position={} material={}",side,phase,foot,state);
        }
    }
    /** Events follow an actual sole returning to a collision surface. */
    private static void geometricSteps(EvaUnit01Entity eva,float phase)
    {
        var pose=EvaBodyPose.sample(eva,1);var world=EvaRifleKinematics.world(eva,1);
        var contacts=SOLES.computeIfAbsent(eva,e->new java.util.HashMap<>());
        long now=eva.level().getGameTime();float run=eva.rifleRunBlend(1),low=Mth.clamp(eva.rifleStanceLevel(1),0,1);
        for(String side:new String[]{"l","r"})
        {
            var local=EvaBodyPose.lowestRigidFootR44(eva,pose,side);if(local==null)continue;
            var point=world.transformPosition(new org.joml.Vector3f(local));
            Vec3 foot=new Vec3(point.x,point.y,point.z);
            var hit=eva.level().clip(new net.minecraft.world.level.ClipContext(foot.add(0,.5,0),foot.add(0,-1,0),
                    net.minecraft.world.level.ClipContext.Block.COLLIDER,net.minecraft.world.level.ClipContext.Fluid.NONE,eva));
            boolean bearing=hit.getType()==net.minecraft.world.phys.HitResult.Type.BLOCK;
            double gap=bearing?foot.y-hit.getLocation().y:Double.POSITIVE_INFINITY;
            var state=contacts.computeIfAbsent(side,s->new SoleContact());
            if(state.tick!=now-1)state.raised=false;
            state.tick=now;
            if(!bearing||gap>.35){state.raised=true;continue;}
            if(!state.raised||gap<-.12||gap>.12)continue;
            state.raised=false;
            Vec3 contact=hit.getLocation();
            var bearingState=eva.level().getBlockState(hit.getBlockPos());
            boolean soil=bearingState.is(BlockTags.DIRT)||bearingState.is(BlockTags.SAND)||bearingState.is(BlockTags.LEAVES);
            CombatFoleyR36.step(eva,contact,soil,Mth.lerp(low,1+.28F*run,.5F));
            com.projectseele.visual.StanceContactR41Review.sound(eva,"geometric_foot_"+side,contact);
            if(eva.getTags().contains("seele_motion_lab"))
                ProjectSeele.LOGGER.info("EVA SOLE CONTACT side={} phase={} gap={} position={}",side,phase,gap,contact);
        }
    }
    public static void swing(EvaUnit01Entity eva,float volume)
    {
        play(eva,eva.position().add(0,eva.getBbHeight()*.62,0).add(eva.getForward().scale(10)),ModSounds.EVA_SWING.get(),volume,1);
    }
    public static void play(EvaUnit01Entity eva,Vec3 point,SoundEvent sound,float volume,float pitch)
    {
        if(!eva.level().isClientSide&&!eva.isSilent())eva.level().playSound(null,point.x,point.y,point.z,SoundEvent.createFixedRangeEvent(sound.getLocation(),384F),SoundSource.PLAYERS,volume,pitch);
    }
}
