package com.projectseele.entity;

import com.google.gson.JsonObject;
import com.google.gson.JsonArray;
import com.google.gson.JsonParser;
import com.projectseele.physics.AnatomicalLimbConstraints;
import com.projectseele.physics.CombatBodyProfiles;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import net.minecraft.world.level.ClipContext;
import net.minecraft.world.phys.HitResult;
import net.minecraft.world.phys.Vec3;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/** Ordinary step-to-idle support of both original shoes; no action or owner pose. */
public final class EvaOrdinaryStandingSupportR52
{
    // Preserve the existing 3cm model support margin (the renderer adds 5cm).
    private static final float CLEARANCE=.006F;
    private static final Map<Integer,Map<String,Vector3f[]>> SOURCES=new HashMap<>();
    private static final com.projectseele.util.WeakIdentityMap<EvaUnit01Entity,MotionMemory> MEMORY=new com.projectseele.util.WeakIdentityMap<>();
    private static final Map<CombatBodyProfiles.Profile,CombatBodyProfiles.Profile> LEG_PROFILES=new java.util.IdentityHashMap<>();
    private static JsonObject data;

    public static void apply(EvaUnit01Entity e,EvaBodyPose.Sample pose,float partial)
    {
        if(e.isExperimentalUnit()||!e.isPoweredOn()||e.isBerserk()||e.isCrucified()||e.getPilotEntity()==null
                ||e.isFirstBattleActive()||e.isNervLogisticsLocked()||EvaMechanicalFrameR52.serviceSourceHeldR52(e)
                ||EvaAirTransportR31.active(e)||e.hasFixedCannonR52()||e.fixedCannonOperatingR52()
                ||e.ordinaryStandingSupportLockedR52()||EvaShutdownR30.disabled(e)
                ||e.isVisuallyAirborneForRender()||e.isPilotCrouching()||e.isPilotProne()||e.rifleStanceLevel(partial)>.01F
                ||EvaGameplayMotionR32.airAge(e,partial)>=0
                ||EvaCombatR31.action(e)!=EvaCombatR31.NONE||CombatReactionsR36.active(e)
                ||com.projectseele.physics.CombatBodyDynamics.active(e)||CombatFeelR31.beat(e)!=null)
        {MEMORY.remove(e);return;}
        double rootY=e.level().isClientSide?e.yOld+(e.getY()-e.yOld)*partial:e.getY();
        var memory=MEMORY.get(e);
        // Client level time is periodically synchronized and can jump in
        // either direction. The entity's own tick clock remains the pose
        // clock; shadow/main samples within a frame cannot reverse it.
        double rawClock=e.tickCount+(double)Math.max(0,Math.min(1,partial));
        double now=memory==null?rawClock:memory.sampleClockR52(rawClock);
        // Ordinary handling can briefly clear onGround while the same root
        // remains at its preceding floor contact. Retain only that recent,
        // stationary contact; real air/owner guards above still discard it.
        if(!e.onGround()&&(memory==null||!memory.retainsGroundContactR52(now,rootY)))
        {MEMORY.remove(e);return;}
        if(memory==null){memory=new MotionMemory(now);MEMORY.put(e,memory);}
        if(e.onGround())memory.rememberGroundContactR52(now,rootY);
        boolean action=e.hasLiveActionForRender(partial)||EvaFieldActionsR45.active(e)||EvaSwordActionsR45.active(e);
        float envelope=memory.update(now,action);
        var profile=CombatBodyProfiles.get(e);if(profile==null)return;
        if(action)
        {
            // Fade the actual preceding standing correction; no new floor
            // targets or support IK are imposed on a genuine attack pose.
            memory.applyCached(pose,profile,envelope);return;
        }
        float amount=settleWeight(e.rifleMoveBlend(partial))*envelope;if(amount<=0){memory.correction=null;return;}
        // Match LevelRenderer's baseline, including a just-landed or corrected
        // rider; getPosition uses a different previous-position triplet.
        var origin=e.level().isClientSide?new Vec3(e.xOld+(e.getX()-e.xOld)*partial,
                e.yOld+(e.getY()-e.yOld)*partial,e.zOld+(e.getZ()-e.zOld)*partial):e.position();
        float[] floor=new float[2];int index=0;
        for(String side:List.of("l","r"))
        {
            var low=lowest(e.getUnitVariant(),pose,side);if(low==null)return;
            var world=new Vector3f(low).mul(EvaScale.RENDER_SCALE)
                    .rotateY((180-EvaAirTransportR31.frameYaw(e,partial))*(float)Math.PI/180)
                    .add((float)origin.x,(float)origin.y,(float)origin.z);
            var point=new Vec3(world.x,world.y,world.z);
            var hit=e.level().clip(new ClipContext(point.add(0,4,0),point.add(0,-80,0),
                    ClipContext.Block.COLLIDER,ClipContext.Fluid.NONE,e));
            if(hit.getType()!=HitResult.Type.BLOCK)
            {if(!e.onGround())MEMORY.remove(e);return;}
            floor[index++]=(float)((hit.getLocation().y-origin.y)/EvaScale.RENDER_SCALE);
        }
        double leftFloor=origin.y+floor[0]*EvaScale.RENDER_SCALE,rightFloor=origin.y+floor[1]*EvaScale.RENDER_SCALE;
        if(!e.onGround()&&!memory.retainsGroundFloorR52(leftFloor,rightFloor))
        {MEMORY.remove(e);return;}
        if(e.onGround())memory.rememberGroundFloorR52(leftFloor,rightFloor);
        var previous=new Correction(pose);
        apply(e.getUnitVariant(),pose,amount,floor,profile);
        previous.finish(pose);memory.correction=previous;
    }

    /** Source correction envelope: six ticks into an action, twelve back to
     * ordinary support. All repeated samples use the same monotonic pose clock. */
    public static final class MotionMemory
    {
        private double changed,last;private float from,target=1,actionFrom;private boolean action;
        private double groundTime=Double.NEGATIVE_INFINITY,groundY,lastPoseClock;
        private double leftGround,rightGround;private boolean groundFloor;
        private Correction correction;
        public MotionMemory(double now){changed=last=lastPoseClock=now;}
        public double sampleClockR52(double entityTickAndPartial)
        {lastPoseClock=Math.max(lastPoseClock,entityTickAndPartial);return lastPoseClock;}
        public void rememberGroundContactR52(double now,double rootY)
        {groundTime=now;groundY=rootY;}
        public boolean retainsGroundContactR52(double now,double rootY)
        {return now>=groundTime&&now-groundTime<=4&&Math.abs(rootY-groundY)<=.01D;}
        public void rememberGroundFloorR52(double left,double right)
        {leftGround=left;rightGround=right;groundFloor=true;}
        public boolean retainsGroundFloorR52(double left,double right)
        {return groundFloor&&Double.isFinite(left)&&Double.isFinite(right)
                &&Math.abs(left-leftGround)<=.01D&&Math.abs(right-rightGround)<=.01D;}
        public float update(double now,boolean nextAction)
        {
            now=Math.max(last,now);last=now;
            float current=value(now);
            if(nextAction!=action){action=nextAction;from=current;target=action?0:1;changed=now;if(action)actionFrom=current;}
            return value(now);
        }
        private float value(double now)
        {
            float t=(float)Math.max(0,Math.min(1,(now-changed)/(target==0?6:12)));
            return from+(target-from)*t*t*(3-2*t);
        }
        public void remember(EvaBodyPose.Sample before,EvaBodyPose.Sample after)
        {correction=new Correction(before);correction.finish(after);}
        public void clearCached(){correction=null;}
        public void applyCached(EvaBodyPose.Sample pose,CombatBodyProfiles.Profile profile,float envelope)
        {if(correction!=null&&actionFrom>0)correction.apply(pose,profile,Math.max(0,Math.min(1,envelope/actionFrom)));}
    }
    private static final class Correction
    {
        private static final List<String> BONES=List.of("leg_l","shin_l","foot_l","leg_r","shin_r","foot_r");
        private EvaBodyPose.Sample source;
        Correction(EvaBodyPose.Sample pose){source=copy(pose);}
        void finish(EvaBodyPose.Sample pose){source=copy(pose);}
        void apply(EvaBodyPose.Sample pose,CombatBodyProfiles.Profile profile,float weight)
        {
            if(weight<=0)return;
            // Blend from the last presented feet into the CURRENT authored
            // attack contacts, rather than transplanting a local delta into
            // another bend. Upper-body timing and floor targets are untouched.
            var target=copy(pose);float amount=1-weight;
            pose.positions.get("root").lerp(source.positions.get("root"),weight);
            for(String name:BONES)pose.rotations.put(name,new Quaternionf(source.rotations.get(name)).slerp(target.rotations.get(name),amount));
            pose.dirty();var legs=legProfile(profile);
            AnatomicalLimbConstraints.restoreAuthoredJointCentres(pose,legs);
            if(amount>0)AnatomicalLimbConstraints.blendAuthoredContacts(pose,source,target,amount,legs);
            else for(String side:List.of("l","r"))
            {
                String foot="foot_"+side;var matrix=source.matrix(foot);
                AnatomicalLimbConstraints.reachAuthoredFoot(pose,legs,side,
                        matrix.transformPosition(new Vector3f(source.rig.get(foot).pivot())),
                        matrix.getUnnormalizedRotation(new Quaternionf()).normalize());
            }
            pose.dirty();
        }
        private static EvaBodyPose.Sample copy(EvaBodyPose.Sample pose)
        {
            var result=new EvaBodyPose.Sample(pose.rig);
            for(String name:pose.rig.keySet())
            {
                result.rotations.put(name,new Quaternionf(pose.rotations.get(name)));
                result.positions.put(name,new Vector3f(pose.positions.get(name)));
            }
            return result;
        }
    }
    private static synchronized CombatBodyProfiles.Profile legProfile(CombatBodyProfiles.Profile profile)
    {
        return LEG_PROFILES.computeIfAbsent(profile,original->{
            var definition=original.definition().deepCopy();var bodies=new JsonArray();
            for(var element:definition.getAsJsonArray("bodies"))
                if(element.getAsJsonObject().get("name").getAsString().startsWith("shin_"))bodies.add(element);
            definition.add("bodies",bodies);
            return new CombatBodyProfiles.Profile(original.key()+":ordinary-entry-legs",definition,original.rig(),null);
        });
    }

    /** Uses the existing continuous gait blend throughout deceleration. */
    public static float settleWeight(float move)
    {
        float x=Math.max(0,Math.min(1,move));return 1-x*x*(3-2*x);
    }

    /** Pure production solver entry for replaying the actual native bone pose. */
    public static void apply(int variant,EvaBodyPose.Sample pose,float amount,float[] floor,CombatBodyProfiles.Profile profile)
    {
        if(variant<0||variant>2||amount<=0||profile==null||floor.length!=2)return;
        amount=Math.max(0,Math.min(1,amount));
        var targets=new Vector3f[2];var orientation=new Quaternionf[2];var knees=new Vector3f[2];
        int at=0;
        for(String side:List.of("l","r"))
        {
            String foot="foot_"+side;var matrix=pose.matrix(foot);var low=lowest(variant,pose,side);if(low==null)return;
            targets[at]=matrix.transformPosition(new Vector3f(pose.rig.get(foot).pivot()));
            targets[at].y+=(floor[at]+CLEARANCE-low.y)*amount;
            orientation[at]=matrix.getUnnormalizedRotation(new Quaternionf()).normalize();
            knees[at]=joint(profile,pose,side);at++;
        }
        // A full extension cannot reach a lower ankle by stretching the shin.
        // Lower only the local pelvis enough to put both fixed targets within
        // their original two-link reach; the entity/world root never changes.
        float drop=0;at=0;
        for(String side:List.of("l","r"))
        {
            String upper="leg_"+side,foot="foot_"+side;
            var hip=pose.matrix(upper).transformPosition(new Vector3f(pose.rig.get(upper).pivot()));
            float reach=(knees[at].distance(pose.rig.get(upper).pivot())+knees[at].distance(pose.rig.get(foot).pivot()))*.9999F;
            float dx=hip.x-targets[at].x,dz=hip.z-targets[at].z,horizontal=dx*dx+dz*dz;
            if(horizontal>=reach*reach)return;
            float highest=targets[at].y+(float)Math.sqrt(reach*reach-horizontal);
            drop=Math.min(drop,highest-hip.y);at++;
        }
        if(drop<0){pose.positions.get("root").y+=drop;pose.dirty();}
        at=0;
        for(String side:List.of("l","r"))
            AnatomicalLimbConstraints.reachAuthoredFoot(pose,profile,side,targets[at],orientation[at++]);
    }

    private static Vector3f joint(CombatBodyProfiles.Profile profile,EvaBodyPose.Sample pose,String side)
    {
        for(var element:profile.definition().getAsJsonArray("bodies"))
        {
            var row=element.getAsJsonObject();if(!row.get("name").getAsString().equals("shin_"+side))continue;
            var m=row.getAsJsonArray("joint");return new Vector3f(m.get(3).getAsFloat(),m.get(7).getAsFloat(),m.get(11).getAsFloat()).div(CombatBodyProfiles.MODEL_TO_PHYSICS);
        }
        String marker="r30_knee_socket_"+side;
        return pose.rig.containsKey(marker)?new Vector3f(pose.rig.get(marker).pivot()):new Vector3f(pose.rig.get("shin_"+side).pivot()).add(0,11.4F/16,0);
    }

    public static Vector3f lowest(int variant,EvaBodyPose.Sample pose,String side)
    {
        String name="foot_"+side;var matrix=pose.matrix(name);Vector3f low=null;
        for(var vertex:vertices(variant).get(name))
        {
            var point=matrix.transformPosition(new Vector3f(vertex));if(low==null||point.y<low.y)low=point;
        }
        return low;
    }

    private static synchronized Map<String,Vector3f[]> vertices(int variant)
    {
        var cached=SOURCES.get(variant);if(cached!=null)return cached;
        try
        {
            if(data==null)try(var stream=EvaOrdinaryStandingSupportR52.class.getResourceAsStream("/assets/projectseele/eva/ordinary_standing_support_hulls_r52.json"))
            {
                if(stream==null)throw new IllegalStateException("Original standing shoe hulls missing");
                data=JsonParser.parseReader(new InputStreamReader(stream,StandardCharsets.UTF_8)).getAsJsonObject();
                if(!"projectseele.ordinary-standing-hulls.r52.v1".equals(data.get("schema").getAsString()))throw new IllegalStateException("Standing shoe support schema differs");
            }
            var row=data.getAsJsonObject("rigs").getAsJsonObject(""+variant);
            try(var stream=EvaOrdinaryStandingSupportR52.class.getResourceAsStream("/assets/projectseele/"+row.get("source_resource").getAsString()))
            {
                if(stream==null||!row.get("source_sha256").getAsString().equals(HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(stream.readAllBytes()))))throw new IllegalStateException("Original standing shoe source hash differs");
            }
            var result=new HashMap<String,Vector3f[]>();
            for(String side:List.of("l","r"))
            {
                String name="foot_"+side;var json=row.getAsJsonObject("parts").getAsJsonArray(name);var points=new Vector3f[json.size()];
                for(int i=0;i<points.length;i++){var v=json.get(i).getAsJsonArray();points[i]=new Vector3f(v.get(0).getAsFloat(),v.get(1).getAsFloat(),v.get(2).getAsFloat());}
                result.put(name,points);
            }
            cached=Map.copyOf(result);SOURCES.put(variant,cached);return cached;
        }
        catch(Exception failure){throw new IllegalStateException("Original standing shoe hulls could not load",failure);}
    }
    private EvaOrdinaryStandingSupportR52(){}
}
