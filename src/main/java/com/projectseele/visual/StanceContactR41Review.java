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
        JsonObject fingers=new JsonObject();
        for(String side:List.of("l","r"))for(String digit:List.of("index","middle","thumb"))
        {
            String name="finger_"+digit+"_"+side;if(!pose.rig.containsKey(name))continue;
            var q=pose.rotations.get(name);var a=new JsonArray();for(float f:new float[]{q.x,q.y,q.z,q.w})a.add(f);fingers.add(name,a);
        }
        row.add("fingers",fingers);POSES.add(row);
    }
    public static boolean passed(){return passed&&(POSE_ONLY||CONTACTS.size()==RANGES.length)&&EVENTS.size()>=4&&poseSamples>=300&&crawlDistance>1&&maxRotation<35;}
    public static JsonObject details()
    {
        JsonObject result=new JsonObject();result.addProperty("passed",passed());result.addProperty("pose_samples",poseSamples);result.addProperty("maximum_joint_delta_degrees",maxRotation);result.addProperty("crawl_distance",crawlDistance);
        result.add("events",EVENTS);result.add("poses",POSES);result.add("contact_cases",CONTACTS);return result;
    }
    private StanceContactR41Review(){}
}
