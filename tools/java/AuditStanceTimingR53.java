import com.google.gson.*;
import com.projectseele.entity.*;
import com.projectseele.physics.*;
import java.lang.reflect.*;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/** Read-only replay of the selected source curves and the production clock.
 * No entity, Level, input packet or saved-state mutation is used here. */
public final class AuditStanceTimingR53
{
    private static final Gson JSON=new GsonBuilder().setPrettyPrinting().create();
    private static final List<String> LEGS=List.of("leg_l","shin_l","foot_l","leg_r","shin_r","foot_r");
    private final Object data;
    private final Method sample;
    private final Map<Integer,CombatBodyProfiles.Profile> profiles=new HashMap<>();
    private final Map<Integer,Float> idleDurations=new HashMap<>();

    private static Vector3f vector(JsonArray a){return new Vector3f(a.get(0).getAsFloat(),a.get(1).getAsFloat(),a.get(2).getAsFloat());}
    private static String sha(Path path)throws Exception{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(path)));}
    private static Object access(Object o,String n)throws Exception{var m=o.getClass().getDeclaredMethod(n);m.setAccessible(true);return m.invoke(o);}
    private static double angle(Quaternionf a,Quaternionf b)
    {
        double dot=(double)a.x*b.x+(double)a.y*b.y+(double)a.z*b.z+(double)a.w*b.w;
        double norm=Math.sqrt(((double)a.x*a.x+(double)a.y*a.y+(double)a.z*a.z+(double)a.w*a.w)
                *((double)b.x*b.x+(double)b.y*b.y+(double)b.z*b.z+(double)b.w*b.w));
        return Math.toDegrees(2*Math.acos(Math.min(1,Math.abs(dot/norm))));
    }
    @SuppressWarnings("unchecked")
    private AuditStanceTimingR53(Path directory)throws Exception
    {
        var all=JsonParser.parseString(Files.readString(directory.resolve("eva_body_r44.json"))).getAsJsonObject();
        var physics=JsonParser.parseString(Files.readString(directory.resolve("articulated_bodies_r35.json"))).getAsJsonObject();
        var motion=all.getAsJsonObject("motion");String[] names=new Gson().fromJson(motion.get("bones"),String[].class);
        var reader=EvaBodyPose.class.getDeclaredMethod("readCombatClipsR31",JsonObject.class,String[].class);reader.setAccessible(true);
        var clips=(Map<String,Object>)reader.invoke(null,motion,names);
        var rigs=new HashMap<Integer,Map<String,EvaBodyPose.Bone>>();var byRig=new HashMap<Integer,Map<String,Object>>();
        for(int variant=0;variant<3;variant++)
        {
            var rig=new LinkedHashMap<String,EvaBodyPose.Bone>();
            for(var element:all.getAsJsonObject("rigs").getAsJsonArray(""+variant))
            {
                var row=element.getAsJsonObject();String name=row.get("name").getAsString();
                String parent=row.has("parent")&&!row.get("parent").isJsonNull()?row.get("parent").getAsString():null;
                Vector3f bind=row.has("rotation")?vector(row.getAsJsonArray("rotation")):row.has("bindRotationDegrees")?vector(row.getAsJsonArray("bindRotationDegrees")):new Vector3f();bind.mul((float)Math.PI/180);
                rig.put(name,new EvaBodyPose.Bone(name,parent,vector(row.getAsJsonArray("pivot")).mul(-1,1,1).div(16),new Quaternionf().rotationZYX(bind.z,-bind.y,-bind.x)));
            }
            rigs.put(variant,rig);
            var overrides=new HashMap<String,Object>();
            for(String file:List.of("eva_combat_capture_r31.json","eva_gameplay_r44_"+variant+".json"))
                if(Files.isRegularFile(directory.resolve(file)))overrides.putAll((Map<String,Object>)reader.invoke(null,JsonParser.parseString(Files.readString(directory.resolve(file))).getAsJsonObject(),names));
            overrides.putAll((Map<String,Object>)reader.invoke(null,all.getAsJsonObject("stance_clips_by_rig").getAsJsonObject(""+variant),names));
            byRig.put(variant,overrides);idleDurations.put(variant,(Float)access(overrides.getOrDefault("idle",clips.get("idle")),"duration"));
            profiles.put(variant,new CombatBodyProfiles.Profile("read-only-stance-"+variant,physics.getAsJsonObject("models").getAsJsonObject(""+variant),rig,null));
        }
        Class<?> type=Class.forName("com.projectseele.entity.EvaBodyPose$Data");var constructor=type.getDeclaredConstructors()[0];constructor.setAccessible(true);
        data=constructor.newInstance(names,Map.of(),clips,rigs,Map.of(),new JsonObject(),new JsonObject(),new JsonObject(),Map.of(),Map.of(),Map.of(),byRig,all.getAsJsonObject("locomotion_contract_r43"));
        sample=EvaBodyPose.class.getDeclaredMethod("ordinaryClipBaseR52",type,int.class,float.class,float.class,float.class,float.class,float.class,float.class,float.class,float.class,boolean.class);sample.setAccessible(true);
    }
    private EvaBodyPose.Sample sample(int variant,boolean rifle,float stance,double tick)throws Exception
    {
        float idle=(float)((tick/20/idleDurations.get(variant))%1);
        return (EvaBodyPose.Sample)sample.invoke(null,data,variant,0F,idle,0F,0F,Math.min(1,stance),Math.max(0,(stance-1)/2),stance,0F,rifle);
    }
    private static EvaStanceTimingR53.Step legacy(float phase,float target,float velocity)
    {
        float remaining=target-phase,desired=Math.copySign(Math.min(.08F,(float)Math.sqrt(2*.012F*Math.abs(remaining))),remaining);
        velocity+=Math.max(-.012F,Math.min(.012F,desired-velocity));
        if(Math.abs(remaining)<Math.abs(velocity)||Math.abs(remaining)<.001F)return new EvaStanceTimingR53.Step(target,0);
        return new EvaStanceTimingR53.Step(Math.max(0,Math.min(3,phase+velocity)),velocity);
    }
    private Map<String,Object> sequence(int variant,boolean rifle,float start,float target,boolean old)throws Exception
    {
        var ticks=new ArrayList<Float>();float phase=start,velocity=0;ticks.add(phase);
        for(int tick=0;tick<300&&(phase!=target||velocity!=0);tick++)
        {var next=old?legacy(phase,target,velocity):EvaStanceTimingR53.advance(phase,target,velocity);phase=next.phase();velocity=next.velocity();ticks.add(phase);}
        if(phase!=target||velocity!=0)throw new AssertionError("Unsettled clock");
        EvaBodyPose.Sample prior=null,priorSupported=null;double max=0,maxSupported=0;float worst=0,worstSupport=0;String worstBone="",worstSupportBone="";
        float maxSole=0;double dt=.029292199999872537;
        for(double time=0;time<=(ticks.size()-1)/20D;time+=dt)
        {
            double at=time*20;int i=(int)at;float stance=ticks.get(i)+(ticks.get(Math.min(i+1,ticks.size()-1))-ticks.get(i))*(float)(at-i);
            var pose=sample(variant,rifle,stance,6454627+at);var supported=sample(variant,rifle,stance,6454627+at);
            EvaBodyPose.preserveJointCentres(supported);AnatomicalLimbConstraints.apply(supported,profiles.get(variant));
            // Deliberately a named flat-floor solver fixture, not a claim to
            // reproduce the complete native terrain/action composition.
            EvaOrdinaryStandingSupportR52.apply(variant,supported,EvaOrdinaryStandingSupportR52.stanceWeight(stance),new float[]{0,0},profiles.get(variant));
            if(stance<=1)for(String side:List.of("l","r"))maxSole=Math.max(maxSole,Math.abs(EvaOrdinaryStandingSupportR52.lowest(variant,supported,side).y-.006F));
            if(prior!=null)for(String bone:LEGS)
            {
                double a=angle(prior.rotations.get(bone),pose.rotations.get(bone));if(a>max){max=a;worst=stance;worstBone=bone;}
                double s=angle(priorSupported.rotations.get(bone),supported.rotations.get(bone));if(s>maxSupported){maxSupported=s;worstSupport=stance;worstSupportBone=bone;}
            }
            prior=pose;priorSupported=supported;
        }
        return Map.of("variant",variant,"rifle",rifle,"from",start,"to",target,"legacy",old,"ticks",ticks.size()-1,
                "maximum_source_leg_step_deg",max,"maximum_flat_solver_leg_step_deg",maxSupported,
                "worst_source",Map.of("phase",worst,"bone",worstBone,"support_phase",worstSupport,"support_bone",worstSupportBone),"maximum_full_support_sole_error_blocks",maxSole*5);
    }
    public static void main(String[] args)throws Exception
    {
        Path directory=Path.of(args[0]),nativeLayers=Path.of(args[1]),out=Path.of(args[2]);var audit=new AuditStanceTimingR53(directory);
        var rows=new ArrayList<Object>();for(int variant=0;variant<3;variant++)for(boolean rifle:new boolean[]{false,true})for(float[] endpoints:new float[][]{{0,1},{1,0},{0,3},{3,0}})for(boolean old:new boolean[]{true,false})rows.add(audit.sequence(variant,rifle,endpoints[0],endpoints[1],old));
        var dense=new ArrayList<Object>();
        for(int variant=0;variant<3;variant++)for(boolean rifle:new boolean[]{false,true})
        {
            EvaBodyPose.Sample prior=null;double max=0;float worst=0;String bone="";
            for(int i=0;i<=1250;i++)
            {
                float phase=i/1000F;var pose=audit.sample(variant,rifle,phase,6454627);
                EvaBodyPose.preserveJointCentres(pose);AnatomicalLimbConstraints.apply(pose,audit.profiles.get(variant));
                EvaOrdinaryStandingSupportR52.apply(variant,pose,EvaOrdinaryStandingSupportR52.stanceWeight(phase),new float[]{0,0},audit.profiles.get(variant));
                if(prior!=null)for(String name:LEGS){double a=angle(prior.rotations.get(name),pose.rotations.get(name));if(a>max){max=a;worst=phase;bone=name;}}
                prior=pose;
            }
            dense.add(Map.of("variant",variant,"rifle",rifle,"maximum_step_deg",max,"step_phase",.001,"phase",worst,"bone",bone));
        }
        var nativeData=JsonParser.parseString(Files.readString(nativeLayers)).getAsJsonObject().getAsJsonArray("samples");var sourceSteps=new ArrayList<Object>();
        for(int i=1;i<nativeData.size();i++)
        {
            var a=nativeData.get(i-1).getAsJsonObject();var b=nativeData.get(i).getAsJsonObject();
            float sa=a.get("stance").getAsFloat(),sb=b.get("stance").getAsFloat();if(sa==sb||Math.min(sa,sb)>1)continue;
            var layers=new LinkedHashMap<String,Double>();
            for(var layer:b.getAsJsonObject("layers").keySet())
            {
                if(!a.getAsJsonObject("layers").has(layer))continue;
                var qa=a.getAsJsonObject("layers").getAsJsonObject(layer).getAsJsonObject("shin_r").getAsJsonArray("quaternion_xyzw");
                var qb=b.getAsJsonObject("layers").getAsJsonObject(layer).getAsJsonObject("shin_r").getAsJsonArray("quaternion_xyzw");
                layers.put(layer,angle(new Quaternionf(qa.get(0).getAsFloat(),qa.get(1).getAsFloat(),qa.get(2).getAsFloat(),qa.get(3).getAsFloat()),new Quaternionf(qb.get(0).getAsFloat(),qb.get(1).getAsFloat(),qb.get(2).getAsFloat(),qb.get(3).getAsFloat())));
            }
            sourceSteps.add(Map.of("index",i,"from_stance",sa,"to_stance",sb,"seconds",(b.get("tick").getAsLong()-a.get("tick").getAsLong()+b.get("partial").getAsDouble()-a.get("partial").getAsDouble())/20,"right_shin_layer_step_deg",layers));
        }
        var result=new LinkedHashMap<String,Object>();result.put("body_sha256",sha(directory.resolve("eva_body_r44.json")));result.put("physics_sha256",sha(directory.resolve("articulated_bodies_r35.json")));result.put("native_layers_sha256",sha(nativeLayers));result.put("frame_step_seconds",.029292199999872537);result.put("native_counterexamples",sourceSteps);result.put("clock_source_and_flat_solver_replay",rows);result.put("native_candidate_verified",false);result.put("limits","Exact selected curves and production sampler/clock/solver; 29.2922ms regular resampling of server tick phase is not the client PoseSignalClock or the complete rendered stack. Source admission, dynamic support eligibility, terrain and native pixels require follow-up.");
        result.put("dense_flat_solver_grid",dense);Files.writeString(out,JSON.toJson(result));System.out.println("Read-only stance replay: "+rows.size()+" clock/source cases, "+sourceSteps.size()+" original native transition pairs; "+out);
    }
}
