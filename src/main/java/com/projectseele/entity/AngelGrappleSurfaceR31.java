package com.projectseele.entity;

import com.google.gson.*;
import com.projectseele.ProjectSeele;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.phys.Vec3;
import org.joml.Matrix4f;
import org.joml.Quaternionf;
import org.joml.Vector3f;
import java.nio.file.*;
import java.util.*;

/** Six measured material vertices per Angel, evaluated by the same four-weight DQS as the visible skin. */
public final class AngelGrappleSurfaceR31
{
    public record Contact(Vec3 position,Vec3 outwardNormal,int triangle,String meshSha256) {}
    private record Bone(String parent,Vector3f pivot,Vector3f idle) {}
    private record Vertex(Vector3f point,int[] indices,float[] weights) {}
    private record Anchor(Vertex[] triangle,float[] bary,float sign,int index) {}
    private record Profile(Map<String,Bone> bones,String[] palette,Anchor left,Anchor right,String hash) {}
    private record PoseState(float partial,float held,EvaImpactResponse.Pose impact,CombatFeelR31.Beat beat) {}
    private static volatile Map<String,Profile> profiles;
    private static Vector3f vector(JsonArray a){return new Vector3f(a.get(0).getAsFloat(),a.get(1).getAsFloat(),a.get(2).getAsFloat());}
    private static Anchor anchor(JsonObject a)
    {
        var vertices=a.getAsJsonArray("vertices");Vertex[] triangle=new Vertex[3];float[] bary=new float[3];
        for(int i=0;i<3;i++)
        {
            var v=vertices.get(i).getAsJsonObject();int[] ids=new int[4];float[] weights=new float[4];
            for(int k=0;k<4;k++){ids[k]=v.getAsJsonArray("indices").get(k).getAsInt();weights[k]=v.getAsJsonArray("weights").get(k).getAsFloat();}
            triangle[i]=new Vertex(vector(v.getAsJsonArray("point")),ids,weights);bary[i]=a.getAsJsonArray("barycentric").get(i).getAsFloat();
        }
        return new Anchor(triangle,bary,a.get("normal_sign").getAsFloat(),a.get("triangle").getAsInt());
    }
    private static Map<String,Profile> profiles()
    {
        if(profiles!=null)return profiles;Map<String,Profile> loaded=new HashMap<>();
        Path path=CombatMotionResourcesR44.instancePath(System.getProperty("projectseele.angelGripProfile","projectseele-local-maps/angel_grip_r31.json"));
        try
        {
            var all=JsonParser.parseString(Files.readString(path)).getAsJsonObject();
            if(!all.get("schema").getAsString().equals("projectseele.angel_grip_surface_r31/v1"))throw new IllegalArgumentException("Grip surface schema");
            for(var entry:all.getAsJsonObject("profiles").entrySet())
            {
                var p=entry.getValue().getAsJsonObject();Map<String,Bone> bones=new HashMap<>();
                for(var item:p.getAsJsonArray("bones")){var b=item.getAsJsonObject();bones.put(b.get("name").getAsString(),new Bone(b.get("parent").isJsonNull()?null:b.get("parent").getAsString(),vector(b.getAsJsonArray("pivot")),vector(b.getAsJsonArray("idle"))));}
                var names=p.getAsJsonArray("skin_bones");String[] palette=new String[names.size()];for(int i=0;i<palette.length;i++)palette[i]=names.get(i).getAsString();
                loaded.put(entry.getKey(),new Profile(Map.copyOf(bones),palette,anchor(p.getAsJsonObject("anchors").getAsJsonObject("left")),anchor(p.getAsJsonObject("anchors").getAsJsonObject("right")),p.get("mesh_sha256").getAsString()));
            }
        }
        catch(Exception error){ProjectSeele.LOGGER.warn("Measured Angel grip profile unavailable: {}",path,error);}
        profiles=Map.copyOf(loaded);return profiles;
    }
    public static float heldWeight(LivingEntity victim,float partial)
    {
        var owner=EvaCombatR31.grappler(victim);if(owner==null)return 0;
        return EvaCombatR31.action(owner)==EvaCombatR31.THROW?1:(float)CombatMotionR29.ease(EvaCombatR31.age(owner,partial)/10);
    }
    /** leftHand is the grabber's left hand; the victim must face its grabber. */
    public static Contact contact(LivingEntity victim,boolean leftHand,float partial)
    {
        String name=victim instanceof SachielEntity?"sachiel":victim instanceof ShamshelEntity?"shamshel":"";Profile p=profiles().get(name);if(p==null)return null;
        var beat=CombatFeelR31.beat(victim);float held=heldWeight(victim,partial);if(beat!=null&&(beat.kind()==CombatFeelR31.DOWN||beat.kind()==CombatFeelR31.THROWN)&&held<=0)return null;
        var pose=new PoseState(partial,held,EvaImpactResponse.sample(victim,partial),beat);
        Map<String,Matrix4f> cache=new HashMap<>();Quaternionf[] real=new Quaternionf[p.palette.length],dual=new Quaternionf[p.palette.length];
        for(int i=0;i<real.length;i++)
        {
            Matrix4f m=matrix(victim,p,p.palette[i],pose,cache);real[i]=m.getUnnormalizedRotation(new Quaternionf()).normalize();Vector3f t=m.getTranslation(new Vector3f());dual[i]=new Quaternionf(t.x,t.y,t.z,0).mul(real[i]).mul(.5F);
        }
        Anchor anchor=leftHand?p.left:p.right;Vector3f[] points=new Vector3f[3];Vector3f surface=new Vector3f();
        for(int i=0;i<3;i++){points[i]=skin(anchor.triangle[i],real,dual);surface.fma(anchor.bary[i],points[i]);}
        Vector3f normal=new Vector3f(points[1]).sub(points[0]).cross(new Vector3f(points[2]).sub(points[0])).normalize().mul(anchor.sign);
        Vec3 at=victim.level().isClientSide?victim.getPosition(partial):victim.position();float yaw=victim.level().isClientSide?net.minecraft.util.Mth.rotLerp(partial,victim.yBodyRotO,victim.yBodyRot):victim.yBodyRot;
        Matrix4f world=new Matrix4f().translation(at.toVector3f()).rotateY((float)Math.toRadians(180-yaw)).scale(5);
        return new Contact(new Vec3(world.transformPosition(surface)),new Vec3(world.transformDirection(normal).normalize()),anchor.index,p.hash);
    }
    private static Matrix4f matrix(LivingEntity victim,Profile p,String name,PoseState pose,Map<String,Matrix4f> cache)
    {
        Matrix4f old=cache.get(name);if(old!=null)return old;Bone bone=p.bones.get(name);Vector3f start=new Vector3f(bone.idle),offset=new Vector3f();
        if(victim instanceof SachielEntity s&&s.isStrikeActive()&&SachielGameplayMotionR32.ready())
        {var shared=SachielGameplayMotionR32.pose(s,s.strikeAge(pose.partial));if(shared.rotations.containsKey(name)){shared.rotations.get(name).getEulerAnglesZYX(start);offset.set(shared.positions.get(name));}}
        Vector3f r=rotation(victim,name,start,pose),q=bone.pivot;
        Matrix4f m=new Matrix4f().translation(offset).translate(q).rotateZYX(r.z,r.y,r.x).translate(-q.x,-q.y,-q.z);
        if(bone.parent!=null)m=new Matrix4f(matrix(victim,p,bone.parent,pose,cache)).mul(m);cache.put(name,m);return m;
    }
    private static Vector3f rotation(LivingEntity v,String name,Vector3f r,PoseState pose)
    {
        float partial=pose.partial;
        if(v instanceof SachielEntity sachiel&&sachiel.isStrikeActive()&&!SachielGameplayMotionR32.ready())
        {
            float age=sachiel.strikeAge(partial),weight=SachielStrike.weight(sachiel.strikeMode(),age);
            if(name.equals("torso_lower")||name.equals("torso_upper"))r.lerp(SachielStrike.torsoRotation(sachiel.strikeMode(),age,name.equals("torso_upper")),weight);
            if(name.equals("head"))r.x-=.07F*weight;
        }
        if(v instanceof ShamshelEntity shamshel&&name.equals("body")){float age=shamshel.isSweeping()?shamshel.sweepAge(partial):-1;r.set(ShamshelWhipMotion.bodyPitch(shamshel.sweepMode(),age),ShamshelWhipMotion.bodyYaw(shamshel.sweepSide(),shamshel.sweepMode(),age),0);}
        var impact=pose.impact;float iw=name.equals("torso_lower")?.25F:name.equals("head")?.35F:.75F;
        if(Set.of("torso_lower","torso_upper","body","head").contains(name)){r.x+=impact.pitch()*iw;r.z+=impact.roll()*iw;if(name.equals("head"))r.x+=impact.head();}
        float held=pose.held;
        if(held>0)
        {if(name.equals("torso_upper")||name.equals("body"))r.x-=.18F*held;if(name.equals("head"))r.x-=.12F*held;}
        else
        {
            var b=pose.beat;if(b!=null&&b.kind()!=CombatFeelR31.CONTACT&&b.kind()<CombatFeelR31.DOWN)
            {
                float accent=(float)CombatMotionR29.recoil(CombatFeelR31.age(v,partial))*b.strength()*(b.kind()==CombatFeelR31.STAGGER?.28F:.12F);
                var d=b.direction().toVector3f().rotateY((float)-Math.toRadians(180-v.yBodyRot));float length=(float)Math.sqrt(d.x*d.x+d.z*d.z),dx=length<.001F?0:d.x/length,dz=length<.001F?1:d.z/length;
                float weight=name.equals("torso_lower")?.3F:name.equals("torso_upper")?.7F:name.equals("body")?1:0;r.x+=accent*dz*weight;r.z-=accent*dx*weight;if(name.equals("head")){r.x-=accent*.45F;r.z+=accent*dx*.25F;}
            }
        }
        return r;
    }
    private static Vector3f skin(Vertex vertex,Quaternionf[] real,Quaternionf[] dual)
    {
        Quaternionf q=new Quaternionf(0,0,0,0),d=new Quaternionf(0,0,0,0),reference=real[vertex.indices[0]];
        for(int k=0;k<4;k++)
        {
            int i=vertex.indices[k];float w=vertex.weights[k]*(reference.dot(real[i])<0?-1:1);
            q.x+=real[i].x*w;q.y+=real[i].y*w;q.z+=real[i].z*w;q.w+=real[i].w*w;d.x+=dual[i].x*w;d.y+=dual[i].y*w;d.z+=dual[i].z*w;d.w+=dual[i].w*w;
        }
        float length=(float)Math.sqrt(q.lengthSquared());q.mul(1/length);d.mul(1/length);float dot=q.dot(d);d.x-=q.x*dot;d.y-=q.y*dot;d.z-=q.z*dot;d.w-=q.w*dot;
        Quaternionf t=d.mul(new Quaternionf(q).conjugate());return q.transform(new Vector3f(vertex.point)).add(2*t.x,2*t.y,2*t.z);
    }
    private AngelGrappleSurfaceR31() {}
}
