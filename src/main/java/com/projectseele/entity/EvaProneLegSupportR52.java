package com.projectseele.entity;

import com.google.gson.JsonParser;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.*;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/** Original prone legs: swivel the intact hinge chain around its fixed hip/ankle
 * axis until every original thigh/shin vertex clears the support plane. */
public final class EvaProneLegSupportR52
{
    private static final float CLEARANCE=.006F,MAXIMUM=(float)Math.toRadians(75);
    private static final Map<Integer,Map<String,Vector3f[]>> SOURCES=new HashMap<>();
    private static com.google.gson.JsonObject sourceData;

    public static void apply(EvaUnit01Entity e,EvaBodyPose.Sample pose,float partial)
    {
        if(!eligible(e,partial))return;
        apply(e.getUnitVariant(),pose,e.rifleStanceLevel(partial),EvaTerrainSupport.sample(e));
    }

    static boolean eligible(EvaUnit01Entity e,float partial)
    {
        return !(e.isExperimentalUnit()||!e.isPoweredOn()||e.isBerserk()||e.isCrucified()||e.isFirstBattleActive()
                ||e.isNervLogisticsLocked()||EvaMechanicalFrameR52.serviceSourceHeldR52(e)||EvaAirTransportR31.active(e)
                ||e.isVisuallyAirborneForRender()
                ||CombatReactionsR36.active(e)||com.projectseele.physics.CombatBodyDynamics.active(e));
    }

    /** Explicit original stance/plane also supplies a pure ordinary release
     * target while the live actor remains held by its mechanical owner. */
    public static void apply(int variant,EvaBodyPose.Sample pose,float stance,Vector3f terrain)
    {
        // Standing/crouching are 0/1. Every value above 1 belongs to the
        // existing continuous transition to or from the prone endpoint at 3.
        if(variant<0||variant>2||stance<=1)return;
        var source=sourceVerticesR52(variant);
        // The contact-feasible swivel interval can appear away from zero as
        // the original knee lowers. Turn before contact, on the same stance
        // clock, instead of jumping to that interval on its first frame. The
        // anticipation disappears before the final prone pose, which retains
        // its smallest exact full-surface support angle.
        float anticipation=(float)Math.toRadians(50)*EvaPoseBlendR51.smooth((stance-1)/.8F)
                *(1-EvaPoseBlendR51.smooth((stance-2)/.6F));
        var normal=new Quaternionf().rotationX(terrain.x).rotateZ(terrain.y).transform(new Vector3f(0,1,0));
        float plane=normal.y*terrain.z/EvaScale.RENDER_SCALE;
        for(String side:List.of("l","r"))
            supportChain(pose,source,"leg_"+side,"shin_"+side,"foot_"+side,
                    side.equals("l")?-1:1,anticipation,normal,plane);
    }

    /** Rotate an intact chain around fixed endpoints; retain its end surface. */
    static boolean supportChain(EvaBodyPose.Sample pose,Map<String,Vector3f[]> source,
                             String upper,String lower,String foot,float sign,float anticipation,
                             Vector3f normal,float plane)
    {
        if(!pose.rig.containsKey(upper)||!pose.rig.containsKey(lower)||!pose.rig.containsKey(foot))return false;
        var upperMatrix=pose.matrix(upper);var footMatrix=pose.matrix(foot);
        var origin=upperMatrix.transformPosition(new Vector3f(pose.rig.get(upper).pivot()));
        var end=footMatrix.transformPosition(new Vector3f(pose.rig.get(foot).pivot()));
        var axis=new Vector3f(end).sub(origin);if(axis.lengthSquared()<1e-8F)return false;axis.normalize();
        // Rodrigues' formula gives each full source vertex's signed height
        // as constant + cosine*cos(swivel) + sine*sin(swivel).
        var heights=new float[(source.get(upper).length+source.get(lower).length)*3];int at=0;float lowest=Float.POSITIVE_INFINITY;
        float normalAxis=normal.dot(axis);
        var cosineDirection=new Vector3f(normal).fma(-normalAxis,axis);
        var sineDirection=new Vector3f(normal).cross(axis);
        for(String name:List.of(upper,lower))
        {
            var matrix=pose.matrix(name);
            float tx=matrix.m30()-origin.x,ty=matrix.m31()-origin.y,tz=matrix.m32()-origin.z;
            float constantBase=normal.dot(origin)-plane+normalAxis*(axis.x*tx+axis.y*ty+axis.z*tz);
            float cosineBase=cosineDirection.x*tx+cosineDirection.y*ty+cosineDirection.z*tz;
            float sineBase=sineDirection.x*tx+sineDirection.y*ty+sineDirection.z*tz;
            float ax=normalAxis*(axis.x*matrix.m00()+axis.y*matrix.m01()+axis.z*matrix.m02());
            float ay=normalAxis*(axis.x*matrix.m10()+axis.y*matrix.m11()+axis.z*matrix.m12());
            float az=normalAxis*(axis.x*matrix.m20()+axis.y*matrix.m21()+axis.z*matrix.m22());
            float bx=cosineDirection.x*matrix.m00()+cosineDirection.y*matrix.m01()+cosineDirection.z*matrix.m02();
            float by=cosineDirection.x*matrix.m10()+cosineDirection.y*matrix.m11()+cosineDirection.z*matrix.m12();
            float bz=cosineDirection.x*matrix.m20()+cosineDirection.y*matrix.m21()+cosineDirection.z*matrix.m22();
            float cx=sineDirection.x*matrix.m00()+sineDirection.y*matrix.m01()+sineDirection.z*matrix.m02();
            float cy=sineDirection.x*matrix.m10()+sineDirection.y*matrix.m11()+sineDirection.z*matrix.m12();
            float cz=sineDirection.x*matrix.m20()+sineDirection.y*matrix.m21()+sineDirection.z*matrix.m22();
            for(var vertex:source.get(name))
            {
                float constant=constantBase+ax*vertex.x+ay*vertex.y+az*vertex.z;
                float cosine=cosineBase+bx*vertex.x+by*vertex.y+bz*vertex.z;
                float sine=sineBase+cx*vertex.x+cy*vertex.y+cz*vertex.z;
                heights[at++]=constant;heights[at++]=cosine;heights[at++]=sine;lowest=Math.min(lowest,constant+cosine);
            }
        }
        if(lowest>=CLEARANCE&&anticipation<=0)return false;
        float angle=sign*supportAngle(heights,sign,anticipation);
        // The smallest outward rotation retains the authored limb hinge,
        // link lengths and proximal joint. No root/limb translation is added.
        if(!Float.isFinite(angle))return false;
        var swivel=new Quaternionf().rotationAxis(angle,axis);
        var world=swivel.mul(upperMatrix.getUnnormalizedRotation(new Quaternionf()).normalize());
        String parent=pose.rig.get(upper).parent();
        if(parent!=null)world=pose.matrix(parent).getUnnormalizedRotation(new Quaternionf()).normalize().invert().mul(world);
        pose.rotations.put(upper,world.normalize());pose.dirty();
        // The end joint lies on the swivel axis. Counter-rotate its surface,
        // retaining the original shoe/hand world matrix and contact anchor.
        parent=pose.rig.get(foot).parent();
        var orientation=footMatrix.getUnnormalizedRotation(new Quaternionf()).normalize();
        if(parent!=null)orientation=pose.matrix(parent).getUnnormalizedRotation(new Quaternionf()).normalize().invert().mul(orientation);
        pose.rotations.put(foot,orientation.normalize());pose.dirty();
        return true;
    }

    /** Project directly to the first allowed angular interval of a violated
     * hull point. This is scalar plane math, with no angular/IK enumeration. */
    private static float supportAngle(float[] heights,float sign,float angle)
    {
        float cosine=(float)Math.cos(angle),sine=(float)Math.sin(angle),target=CLEARANCE+.00001F;
        int at=0,changes=0;
        while(at<heights.length)
        {
            float a=heights[at],b=heights[at+1],c=sign*heights[at+2];
            if(a+b*cosine+c*sine>=target){at+=3;continue;}
            float radius=(float)Math.hypot(b,c),value=target-a;
            if(value>radius||radius<1e-9F)return Float.NaN;
            if(value<=-radius){at+=3;continue;}
            float phase=(float)Math.atan2(c,b),width=(float)Math.acos(Math.max(-1,Math.min(1,value/radius))),next=Float.POSITIVE_INFINITY;
            for(int turn=-1;turn<=1;turn++)
            {
                float low=phase-width+turn*(float)(Math.PI*2),high=phase+width+turn*(float)(Math.PI*2);
                float candidate=Math.max(angle,low)+.000002F;
                if(candidate<=high&&candidate<=MAXIMUM)next=Math.min(next,candidate);
            }
            if(!Float.isFinite(next)||++changes>heights.length)return Float.NaN;
            angle=next;cosine=(float)Math.cos(angle);sine=(float)Math.sin(angle);at=0;
        }
        return angle;
    }

    /** Exact original rest convex-hull vertices suffice for every directional
     * support query. Source hashes are checked once; runtime never loads a
     * complete posed mesh. The renderer retains its automatic ankle seam. */
    public static synchronized Map<String,Vector3f[]> sourceVerticesR52(int variant)
    {
        var cached=SOURCES.get(variant);if(cached!=null)return cached;
        try
        {
            if(sourceData==null)try(var stream=EvaProneLegSupportR52.class.getResourceAsStream("/assets/projectseele/eva/prone_leg_support_hulls_r52.json"))
            {
                if(stream==null)throw new IllegalStateException("Original prone support hulls missing");
                sourceData=JsonParser.parseReader(new InputStreamReader(stream,StandardCharsets.UTF_8)).getAsJsonObject();
                if(!sourceData.get("schema").getAsString().equals("projectseele.prone-support-hulls.r52.v1"))throw new IllegalStateException("Original prone support schema differs");
            }
            var row=sourceData.getAsJsonObject("rigs").getAsJsonObject(""+variant);
            try(var stream=EvaProneLegSupportR52.class.getResourceAsStream("/assets/projectseele/"+row.get("source_resource").getAsString()))
            {
                if(stream==null||!row.get("source_sha256").getAsString().equals(java.util.HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(stream.readAllBytes()))))throw new IllegalStateException("Original prone source/hull hash differs");
            }
            var result=new HashMap<String,Vector3f[]>();
            for(String side:List.of("l","r"))for(String family:List.of("leg_","shin_"))
            {
                String name=family+side;var vertices=row.getAsJsonObject("parts").getAsJsonArray(name);var points=new Vector3f[vertices.size()];
                for(int i=0;i<points.length;i++){var v=vertices.get(i).getAsJsonArray();points[i]=new Vector3f(v.get(0).getAsFloat(),v.get(1).getAsFloat(),v.get(2).getAsFloat());}
                result.put(name,points);
            }
            cached=Map.copyOf(result);SOURCES.put(variant,cached);return cached;
        }
        catch(Exception failure){throw new IllegalStateException("Original prone source could not load",failure);}
    }

    private EvaProneLegSupportR52(){}
}
