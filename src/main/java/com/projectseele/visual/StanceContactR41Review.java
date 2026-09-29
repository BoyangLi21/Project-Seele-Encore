package com.projectseele.visual;

import com.google.gson.*;
import com.projectseele.entity.*;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.phys.Vec3;
import org.joml.Quaternionf;
import java.util.*;

/** Opt-in real-input stance and stationary-target contact regression. */
public final class StanceContactR41Review
{
    public static final boolean ENABLED=CombatR31Review.ENABLED&&Boolean.getBoolean("projectseele.r41StanceContacts");
    public static final boolean ARTICULATION=ENABLED&&Boolean.getBoolean("projectseele.r42Locomotion");
    public static final boolean GAIT_R43=ARTICULATION&&Boolean.getBoolean("projectseele.r43Gait");
    private static final boolean POSE_ONLY=Boolean.getBoolean("projectseele.r41PoseOnly");
    private static final JsonArray EVENTS=new JsonArray(),POSES=new JsonArray(),CONTACTS=new JsonArray();
    private static final Map<String,Quaternionf> PREVIOUS=new HashMap<>();
    private static float maxRotation,healthBefore;
    private static Vec3 crawlStart;
    private static double crawlDistance;
    private static int poseSamples,contactCase=-1,caseStarted;
    private static boolean strikeStarted,passed=true;
    private static final double[] RANGES={12,18,23,23,16,39};
    private static final int[] MODES={SachielStrike.SHOVE,SachielStrike.JAB,SachielStrike.HOOK,SachielStrike.OVERHEAD,SachielStrike.STOMP,SachielStrike.PILE};
    public static void sound(EvaUnit01Entity eva,String name,Vec3 at)
    {
        if(!ENABLED||!CombatR31Review.ownsFixture(eva))return;
        JsonObject row=new JsonObject();row.addProperty("event",name);row.addProperty("tick",CombatR31Review.stageTicks);
        row.addProperty("stance",eva.rifleStanceLevel(0));row.addProperty("x",at.x);row.addProperty("y",at.y);row.addProperty("z",at.z);EVENTS.add(row);
    }
    public static boolean tick(EvaUnit01Entity eva,SachielEntity angel,ServerPlayer pilot,int tick)
    {
        if(GAIT_R43)return gaitR43(eva,angel,pilot,tick);
        if(ARTICULATION)return locomotion(eva,angel,pilot,tick);
        if(tick<=360)
        {
            if(tick==1)
            {
                CombatR31Review.arrangeR41(90);
                int weapon=Integer.getInteger("projectseele.r41PoseWeapon",0);
                if(weapon!=0&&!eva.selectMotionLabWeapon(weapon))throw new IllegalStateException("Pose review weapon rejected");
            }
            if(tick==30)eva.setPilotCrouching(pilot,true);
            if(tick==90)eva.toggleProne(pilot);
            if(tick==220)eva.toggleProne(pilot);
            if(tick==232)eva.setPilotCrouching(pilot,true);
            if(tick==280)eva.setPilotCrouching(pilot,false);
            CombatR31Review.forward=tick>=160&&tick<210?1:0;
            if(tick==160)crawlStart=eva.position();
            if(tick==210&&crawlStart!=null)crawlDistance=eva.position().distanceTo(crawlStart);
            sample(eva,tick);
            if(Set.of(25,70,145,190,250,320).contains(tick))CombatR31Review.photo="r41_stance_"+tick;
            return false;
        }
        if(POSE_ONLY)return true;
        int requested=(tick-361)/140;
        if(requested>=RANGES.length)return true;
        if(requested!=contactCase)
        {
            contactCase=requested;caseStarted=tick;strikeStarted=false;
            CombatR31Review.arrangeR41(90);eva.setHealth(eva.getMaxHealth());
            if(eva.isPilotProne())eva.toggleProne(pilot);
            eva.setPilotCrouching(pilot,requested==3);
            if(requested==4)eva.toggleProne(pilot);
            healthBefore=eva.getHealth();
        }
        int age=tick-caseStarted;
        if(age==55)
        {
            float wanted=requested==4?3:requested==3?1:0;
            if(Math.abs(eva.rifleStanceLevel(0)-wanted)>.01F)throw new IllegalStateException("Contact fixture stance did not settle: "+requested);
            CombatR31Review.arrangeR41(RANGES[requested]);
        }
        if(age==65)strikeStarted=angel.beginStrike(eva,MODES[requested]);
        if(age==135)
        {
            JsonObject row=new JsonObject();row.addProperty("mode",MODES[requested]);row.addProperty("range",RANGES[requested]);
            row.addProperty("stance",eva.rifleStanceLevel(0));row.addProperty("started",strikeStarted);
            row.addProperty("damage",healthBefore-eva.getHealth());row.addProperty("connected",angel.lastStrikeConnectedR36());
            boolean success=strikeStarted&&angel.lastStrikeConnectedR36();row.addProperty("passed",success);passed&=success;CONTACTS.add(row);
        }
        return false;
    }
    private static void sample(EvaUnit01Entity eva,int tick)
    {
        var pose=EvaBodyPose.sample(eva,0);poseSamples++;
        float worst=0;String worstBone="";
        for(String name:pose.rig.keySet())
        {
            var now=pose.rotations.get(name);var old=PREVIOUS.put(name,new Quaternionf(now));
            if(old!=null){float angle=(float)Math.toDegrees(2*Math.acos(Math.min(1,Math.abs(old.dot(now)))));if(angle>worst){worst=angle;worstBone=name;}}
        }
        maxRotation=Math.max(maxRotation,worst);
        JsonObject row=new JsonObject();row.addProperty("tick",tick);row.addProperty("stance",eva.rifleStanceLevel(0));row.addProperty("joint_delta_degrees",worst);
        row.addProperty("worst_bone",worstBone);
        row.addProperty("sprinting",eva.isPilotSprinting());row.addProperty("ground",eva.onGround());
        row.addProperty("guard_weight",EvaGameplayMotionR32.guardWeight(eva));row.addProperty("server_movement",EvaGameplayMotionR32.serverMovement(eva));
        row.addProperty("gait",eva.rifleGaitPhase(0));row.addProperty("move",eva.rifleMoveBlend(0));row.addProperty("run",eva.rifleRunBlend(0));
        var position=new JsonArray();position.add(eva.getX());position.add(eva.getY());position.add(eva.getZ());row.add("position",position);
        JsonObject fingers=new JsonObject();
        for(String side:List.of("l","r"))for(String digit:List.of("index","middle","thumb"))
        {
            String name="finger_"+digit+"_"+side;if(!pose.rig.containsKey(name))continue;
            var q=pose.rotations.get(name);var a=new JsonArray();for(float f:new float[]{q.x,q.y,q.z,q.w})a.add(f);fingers.add(name,a);
        }
        row.add("fingers",fingers);POSES.add(row);
    }
    private static int flightTicks,jumps;
    private static boolean inFlight;
    private static double jumpFloor,peak;
    private static int sprintTicks;
    private static final net.minecraft.server.level.TicketType<net.minecraft.world.level.ChunkPos> GAIT_TARGET=net.minecraft.server.level.TicketType.create("r43_gait_target",Comparator.comparingLong(net.minecraft.world.level.ChunkPos::toLong));
    private static net.minecraft.world.level.ChunkPos gaitTargetChunk;
    private static boolean gaitR43(EvaUnit01Entity eva,SachielEntity angel,ServerPlayer pilot,int tick)
    {
        if(tick==1)
        {
            CombatR31Review.arrangeR41(240);gaitTargetChunk=angel.chunkPosition();
            if(Boolean.getBoolean("projectseele.r43GuardLocomotion"))
            {angel.teleportTo(eva.getX()+50,CombatR31Review.FLOOR+1,eva.getZ()+100);gaitTargetChunk=angel.chunkPosition();}
            pilot.serverLevel().getChunkSource().addRegionTicket(GAIT_TARGET,gaitTargetChunk,3,gaitTargetChunk);
        }
        // One continuous trajectory: no teleport between gait transitions.
        CombatR31Review.forward=tick>=20&&tick<135||tick>=330&&tick<380?1:tick>=260&&tick<295?-1:0;
        CombatR31Review.sprint=tick>=65&&tick<120;
        if(tick>=90&&tick<=120)CombatR31Review.heading=(tick-90)*6;
        CombatR31Review.jump=tick>=180&&tick<184;
        if(eva.isPilotSprinting())sprintTicks++;
        if(tick==175){jumpFloor=eva.getY();peak=jumpFloor;}
        if(tick>=180&&tick<250)
        {
            if(!eva.onGround()){if(!inFlight)jumps++;inFlight=true;flightTicks++;peak=Math.max(peak,eva.getY());}
            else inFlight=false;
        }
        if(tick==305)eva.setPilotCrouching(pilot,true);
        if(tick==390)eva.toggleProne(pilot);
        if(tick==440)crawlStart=eva.position();
        if(tick>=440&&tick<485)CombatR31Review.forward=1;
        if(tick==485)crawlDistance=eva.position().distanceTo(crawlStart);
        if(tick==495)eva.toggleProne(pilot);
        if(tick==520)eva.setPilotCrouching(pilot,false);
        if(tick!=1)sample(eva,tick);else PREVIOUS.clear();
        if(Set.of(18,42,80,100,140,182,188,195,210,280,352,415,465,548).contains(tick))CombatR31Review.photo="r43_gait_"+tick;
        if(tick>=560)pilot.serverLevel().getChunkSource().removeRegionTicket(GAIT_TARGET,gaitTargetChunk,3,gaitTargetChunk);
        return tick>=560;
    }
    private static boolean locomotion(EvaUnit01Entity eva,SachielEntity angel,ServerPlayer pilot,int tick)
    {
        if(tick==1)CombatR31Review.arrangeR41(240);
        if(tick==110)CombatR31Review.arrangeR41(32);
        CombatR31Review.forward=tick>=20&&tick<80||tick>=120&&tick<132||tick>=385&&tick<430?1:0;
        CombatR31Review.jump=tick>=165&&tick<169;
        if(tick==160){jumpFloor=eva.getY();peak=jumpFloor;}
        if(tick>=165&&tick<250)
        {
            if(!eva.onGround()) {if(!inFlight)jumps++;inFlight=true;flightTicks++;peak=Math.max(peak,eva.getY());}
            else if(inFlight)inFlight=false;
        }
        if(tick==270||tick==286)CombatR31Review.inputR42(1);
        // The low-stance traversal case needs unobstructed terrain. Keep the
        // EVA continuous; move only the separate strike target out of its path.
        if(tick==312)angel.setPos(eva.getX()+70,CombatR31Review.FLOOR+1,eva.getZ()-50);
        if(tick==315)eva.setPilotCrouching(pilot,true);
        if(tick==350)eva.toggleProne(pilot);
        if(tick==385)crawlStart=eva.position();
        if(tick==430)crawlDistance=eva.position().distanceTo(crawlStart);
        if(tick==440)eva.toggleProne(pilot);
        if(tick==465)eva.setPilotCrouching(pilot,false);
        if(tick!=1&&tick!=110)sample(eva,tick);else PREVIOUS.clear();
        if(Set.of(50,90,141,178,185,205,285,338,379,410,485).contains(tick))CombatR31Review.photo="r42_motion_"+tick;
        return tick>=510;
    }
    public static boolean passed(){return ARTICULATION?(!GAIT_R43||sprintTicks>=40)&&jumps==1&&flightTicks>=10&&flightTicks<=35&&peak-jumpFloor>10&&crawlDistance>1:passed&&(POSE_ONLY||CONTACTS.size()==RANGES.length)&&EVENTS.size()>=4&&poseSamples>=300&&crawlDistance>1&&maxRotation<35;}
    public static JsonObject details()
    {
        JsonObject result=new JsonObject();result.addProperty("passed",passed());result.addProperty("pose_samples",poseSamples);result.addProperty("maximum_joint_delta_degrees",maxRotation);result.addProperty("crawl_distance",crawlDistance);
        result.addProperty("r42_locomotion",ARTICULATION);result.addProperty("r43_fullbody_gait",GAIT_R43);result.addProperty("sprint_ticks",sprintTicks);result.addProperty("jump_count",jumps);result.addProperty("airborne_ticks",flightTicks);result.addProperty("jump_height",peak-jumpFloor);
        result.add("events",EVENTS);result.add("poses",POSES);result.add("contact_cases",CONTACTS);return result;
    }
    private StanceContactR41Review(){}
}
