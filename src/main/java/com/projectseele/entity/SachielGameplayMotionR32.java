package com.projectseele.entity;

import com.google.gson.*;
import net.minecraft.util.Mth;
import net.minecraft.world.phys.Vec3;
import org.joml.Quaternionf;
import org.joml.Vector3f;
import java.nio.file.*;
import java.util.*;

/** One calibrated skeleton supplies both the displayed attack and its contact sweep. */
public final class SachielGameplayMotionR32
{
    private record Clip(Quaternionf[][] rotations,Vector3f[][] positions,Vec3[] travel,float contact,String side) {}
    private record Data(String[] names,Map<String,EvaBodyPose.Bone> rig,Map<String,Clip> clips,boolean directed,float stride) {}
    private static Optional<Data> cached;
    private static Vector3f vector(JsonElement value){var a=value.getAsJsonArray();return new Vector3f(a.get(0).getAsFloat(),a.get(1).getAsFloat(),a.get(2).getAsFloat());}
    private static synchronized Data data()
    {
        if(cached!=null)return cached.orElse(null);
        var file=Path.of("projectseele-local-maps/sachiel_gameplay_r32.json");
        if(!Files.isRegularFile(file)){cached=Optional.empty();return null;}
        try
        {
            var json=JsonParser.parseString(Files.readString(file)).getAsJsonObject();
            if(json.get("schema").getAsInt()!=2||!json.get("rig_key").getAsString().equals("sachiel"))throw new IllegalArgumentException("Sachiel motion contract");
            var names=new ArrayList<String>();for(var n:json.getAsJsonArray("bones"))names.add(n.getAsString());
            Map<String,EvaBodyPose.Bone> rig=new LinkedHashMap<>();
            for(var row:json.getAsJsonArray("rig"))
            {var b=row.getAsJsonObject();String n=b.get("name").getAsString();rig.put(n,new EvaBodyPose.Bone(n,b.has("parent")?b.get("parent").getAsString():null,vector(b.get("pivot")).mul(-1,1,1).div(16),new Quaternionf()));}
            Map<String,Clip> clips=new HashMap<>();
            for(var entry:json.getAsJsonObject("clips").entrySet())
            {
                var c=entry.getValue().getAsJsonObject();var frames=c.getAsJsonArray("frames");var rotations=new Quaternionf[frames.size()][names.size()];var positions=new Vector3f[frames.size()][names.size()];var travel=new Vec3[frames.size()];
                for(int f=0;f<frames.size();f++)
                {
                    var frame=frames.get(f).getAsJsonObject();var qs=frame.getAsJsonArray("rotation_wxyz");
                    for(int b=0;b<names.size();b++)
                    {
                        var q=qs.get(b).getAsJsonArray();rotations[f][b]=new Quaternionf(-q.get(1).getAsFloat(),-q.get(2).getAsFloat(),q.get(3).getAsFloat(),q.get(0).getAsFloat()).normalize();
                        String n=names.get(b);var p=n.equals("root")?vector(frame.get("root_m")).mul(112):frame.has("bone_position_xyz")&&frame.getAsJsonObject("bone_position_xyz").has(n)?vector(frame.getAsJsonObject("bone_position_xyz").get(n)):new Vector3f();
                        positions[f][b]=p.mul(-1,1,1).div(16);
                    }
                    travel[f]=new Vec3(vector(c.getAsJsonArray("trajectory_m").get(f)));
                }
                clips.put(entry.getKey().substring(4),new Clip(rotations,positions,travel,c.get("contact_phase").getAsFloat(),c.get("leading_side").getAsString()));
            }
            boolean directed=json.has("combat_foundation")&&json.get("combat_foundation").getAsInt()>=34;
            PHRASES=json.has("combat_foundation")&&json.get("combat_foundation").getAsInt()>=36;
            NATURAL_RECOVERY=json.has("natural_recovery")&&json.get("natural_recovery").getAsBoolean();
            float stride=directed?json.getAsJsonObject("clips").getAsJsonObject("r32_advance").get("stride_blocks").getAsFloat():15;
            cached=Optional.of(new Data(names.toArray(String[]::new),Map.copyOf(rig),Map.copyOf(clips),directed,stride));return cached.get();
        }
        catch(Exception error){throw new IllegalStateException("Rejected calibrated Sachiel motion",error);}
    }
    public static boolean ready(){return data()!=null;}
    public static boolean directed(){return ready()&&data().directed;}
    public static boolean phrases(){return ready()&&data().clips.containsKey("guard")&&PHRASES;}
    private static boolean PHRASES;
    private static boolean NATURAL_RECOVERY;
    public static boolean naturalRecovery(){return ready()&&NATURAL_RECOVERY;}
    public static EvaBodyPose.Sample released(SachielEntity actor,EvaBodyPose.Sample destination,float partial)
    {
        var tag=actor.strikeEntryR36();
        if(!naturalRecovery()||!tag.contains("r40_release_at"))return destination;
        float age=actor.level().getGameTime()-tag.getLong("r40_release_at")+partial;
        if(age<0||age>=6)return destination;
        var from=new EvaBodyPose.Sample(destination.rig);EvaShutdownR30.decode(tag,from);
        var turn=new Quaternionf().rotationY((actor.getYRot()-tag.getFloat("r40_release_yaw"))*Mth.DEG_TO_RAD);
        var pivot=from.rig.get("root").pivot();
        from.rotations.put("root",turn.mul(from.rotations.get("root"),new Quaternionf()));
        from.positions.put("root",turn.transform(new Vector3f(from.positions.get("root")).add(pivot)).sub(pivot));
        var current=actor.level().isClientSide?actor.getPosition(partial):actor.position();
        var shift=new Vector3f((float)(tag.getDouble("r40_release_x")-current.x),0,(float)(tag.getDouble("r40_release_z")-current.z))
                .rotateY(-(180-actor.getYRot())*Mth.DEG_TO_RAD).div(EvaScale.RENDER_SCALE);
        from.positions.get("root").add(shift);from.dirty();
        float t=age/6;t=t*t*t*(10+t*(-15+6*t));return blend(from,destination,t);
    }
    public static float stride(){return data().stride;}
    public static String name(int mode){return switch(mode){case SachielStrike.PILE->"cross";case SachielStrike.HOOK->"hook";case SachielStrike.OVERHEAD->"heavy";case SachielStrike.SHOVE->"shove";case SachielStrike.STOMP->"stomp";default->"jab";};}
    public static boolean left(int mode){return data().clips.get(name(mode)).side.equals("l");}
    private static float phase(int mode,float age)
    {
        var c=data().clips.get(name(mode));float contact=SachielStrike.contactStart(mode)+2,progress=Mth.clamp(age,0,SachielStrike.duration(mode));
        return progress<contact?c.contact*progress/contact:Mth.lerp((progress-contact)/(SachielStrike.duration(mode)-contact),c.contact,1);
    }
    public static EvaBodyPose.Sample pose(SachielEntity e,float age)
    {
        return sample(name(e.strikeMode()),phase(e.strikeMode(),age));
    }
    private static EvaBodyPose.Sample sample(String name,float phase)
    {
        var d=data();var c=d.clips.get(name);float at=Mth.clamp(phase,0,1)*(c.rotations.length-1);int a=(int)at,b=Math.min(a+1,c.rotations.length-1);var sample=new EvaBodyPose.Sample(d.rig);
        for(int i=0;i<d.names.length;i++){sample.rotations.put(d.names[i],new Quaternionf(c.rotations[a][i]).slerp(c.rotations[b][i],at-a));sample.positions.put(d.names[i],new Vector3f(c.positions[a][i]).lerp(c.positions[b][i],at-a));}
        return sample;
    }
    public static EvaBodyPose.Sample locomotion(SachielEntity e,float partial)
    {
        if(!directed())return sample("guard",(e.tickCount+partial)%60/60);
        var m=SachielTacticsR34.motion(e);float phase=SachielTacticsR34.phase(e,partial);
        var guard=sample("guard",(e.tickCount+partial)%60/60);
        var front=sample(m.z>=0?"advance":"retreat",phase);var side=sample(m.x>=0?"right":"left",phase);
        return blend(guard,blend(front,side,Math.abs(m.x)/Math.max(.001F,Math.abs(m.x)+Math.abs(m.z))),Mth.clamp(m.length()/.35F,0,1));
    }
    private static EvaBodyPose.Sample blend(EvaBodyPose.Sample a,EvaBodyPose.Sample b,float weight)
    {
        // Sachiel has anatomical pivots already. EVA's knee/elbow correction
        // must never be applied to this unrelated skeleton.
        for(String n:a.rig.keySet()){a.rotations.get(n).slerp(b.rotations.get(n),weight);a.positions.get(n).lerp(b.positions.get(n),weight);}a.dirty();return a;
    }
    public static Vec3 travel(int mode,float age)
    {
        var c=data().clips.get(name(mode));float at=phase(mode,age)*(c.travel.length-1);int a=(int)at,b=Math.min(a+1,c.travel.length-1);return c.travel[a].lerp(c.travel[b],at-a);
    }
    public static void adaptContact(SachielEntity actor,EvaBodyPose.Sample pose,float age,float partial)
    {
        if(!actor.isStrikeActive())return;
        int mode=actor.strikeMode();float weight=SachielStrike.prepare(mode,age)*(1-SachielStrike.release(mode,age));if(weight<.001F)return;
        var profile=com.projectseele.physics.CombatBodyProfiles.get(actor);if(profile==null)return;
        var reference=pose(actor,SachielStrike.contactStart(mode)+2);var inverse=SachielStrike.root(actor,partial).invert();
        boolean stomp=mode==SachielStrike.STOMP;int count=SachielStrike.bothHands(mode)?2:1;
        for(int i=0;i<count;i++)
        {
            boolean left=count==2?i==1:left(mode);String side=left?"l":"r",bone=(stomp?"foot_":"hand_")+side;
            Vec3 goal=actor.strikeAim();var forward=actor.getForward().multiply(1,0,1).normalize();
            if(count==2)goal=goal.add(new Vec3(forward.z,0,-forward.x).scale(left?-3.5:3.5));
            Vector3f local=inverse.transformPosition(goal.toVector3f());
            Vector3f atContact=stomp?com.projectseele.physics.CombatBodyContacts.soleLocal(actor,reference,side)
                    :reference.matrix(bone).transformPosition(new Vector3f(reference.rig.get(bone).pivot()));
            if(mode==SachielStrike.PILE)
            {
                var joint=com.projectseele.physics.AnatomicalLimbConstraints.elbowJoint(profile,side,pose.rig.get("forearm_"+side).pivot());
                var referenceElbow=reference.matrix("forearm_"+side).transformPosition(new Vector3f(joint));
                var referenceTip=new Vector3f(atContact).add(new Vector3f(atContact).sub(referenceElbow).normalize().mul(5));
                var offset=local.sub(referenceTip);if(offset.length()>5.6F)offset.normalize().mul(5.6F);
                var hand=pose.matrix(bone).transformPosition(new Vector3f(pose.rig.get(bone).pivot()));
                var elbow=pose.matrix("forearm_"+side).transformPosition(new Vector3f(joint));
                float extension=extension(age)*5;
                var tip=new Vector3f(hand).add(new Vector3f(hand).sub(elbow).normalize().mul(extension)).fma(weight,offset);
                com.projectseele.physics.AnatomicalLimbConstraints.reachForearmTip(pose,profile,side,tip,extension);
                continue;
            }
            Vector3f offset=local.sub(atContact);if(offset.length()>5.6F)offset.normalize().mul(5.6F);
            Vector3f current=pose.matrix(bone).transformPosition(new Vector3f(pose.rig.get(bone).pivot())).fma(weight,offset);
            if(stomp)com.projectseele.physics.AnatomicalLimbConstraints.reachFoot(pose,profile,side,current,pose.matrix(bone).getUnnormalizedRotation(new Quaternionf()).normalize());
            else com.projectseele.physics.AnatomicalLimbConstraints.reachHand(pose,profile,side,current);
        }
    }
    public static SachielStrike.Frame contact(SachielEntity e,float age,float partial,boolean left)
    {
        var pose=SachielBodyPoseR35.sampleAt(e,age,partial);String side=left?"l":"r",name=e.strikeMode()==SachielStrike.STOMP?"foot_"+side:"hand_"+side;
        var matrix=SachielStrike.root(e,partial);var local=e.strikeMode()==SachielStrike.STOMP?com.projectseele.physics.CombatBodyContacts.soleLocal(e,pose,side)
                :pose.matrix(name).transformPosition(new Vector3f(pose.rig.get(name).pivot()));var hand=new Vec3(matrix.transformPosition(local));
        String upstream=e.strikeMode()==SachielStrike.STOMP?"shin_"+side:"forearm_"+side;
        Vector3f joint=e.strikeMode()==SachielStrike.PILE?com.projectseele.physics.AnatomicalLimbConstraints.elbowJoint(com.projectseele.physics.CombatBodyProfiles.get(e),side,pose.rig.get(upstream).pivot()):new Vector3f(pose.rig.get(upstream).pivot());
        var elbow=new Vec3(matrix.transformPosition(pose.matrix(upstream).transformPosition(joint)));
        Vec3 direction=hand.subtract(elbow).normalize();float extension=e.strikeMode()==SachielStrike.PILE?extension(age):0;
        return new SachielStrike.Frame(hand,hand.add(direction.scale(extension*25)),direction,1,extension);
    }
    private static float extension(float age)
    {return EvaDorsalMechanism.smooth((age-21)/5)*(1-EvaDorsalMechanism.smooth((age-30)/7));}
    private SachielGameplayMotionR32(){}
}
