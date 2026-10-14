package com.projectseele.world;

import com.google.gson.*;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.*;
import java.util.*;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.world.phys.*;
import org.joml.Quaternionf;

/** The original ball joint turns only its retractable captured head. The deck never turns. */
public final class NervBankHeadTransferR53
{
    public static final String SOURCE="mesh/outer_head_transfer_r53.json",SOURCE_SHA="235eaec91ea7e269305a73e819fc3f9a94335d281444cdc819b98d96f48f182b",KEY="BankHeadTransferR53";
    public static final int TICKS=120;
    public static final double RETRACT=.65;
    public record Pose(Vec3 direction,double slide){}
    private static List<NervOuterCarrierGuideR52.Template> parts;
    public static synchronized List<NervOuterCarrierGuideR52.Template> templates()throws IOException
    {
        if(parts!=null)return parts;var bytes=EvaOriginalMeshGeometryR52.classpathBytes(SOURCE);
        try{if(!HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes)).equals(SOURCE_SHA))throw new IllegalStateException("Selected actual head slide source changed");}catch(NoSuchAlgorithmException impossible){throw new IllegalStateException(impossible);}
        var j=JsonParser.parseString(new String(bytes,StandardCharsets.UTF_8)).getAsJsonObject();if(!j.get("schema").getAsString().equals("projectseele.r53.actual-outer-head-slide.v1")||!j.get("outer_source_sha256").getAsString().equals(NervOuterCarrierGuideR52.SOURCE_SHA)||j.get("retraction_metres").getAsDouble()!=RETRACT)throw new IllegalStateException("Exact original capture and bounded slide required");
        var all=j.getAsJsonArray("parts").deepCopy();all.addAll(j.getAsJsonArray("socket_overrides"));var out=new ArrayList<NervOuterCarrierGuideR52.Template>();for(var raw:all){var p=raw.getAsJsonObject();var values=p.getAsJsonArray("triangles_rgb");double[] rgb=new double[values.size()],xyz=new double[values.size()/2];if(rgb.length==0||rgb.length%18!=0)throw new IllegalStateException("Actual complete slide triangles required");for(int i=0,k=0;i<rgb.length;i+=6){for(int c=0;c<6;c++)rgb[i+c]=values.get(i+c).getAsDouble();xyz[k++]=rgb[i];xyz[k++]=rgb[i+1];xyz[k++]=rgb[i+2];}out.add(new NervOuterCarrierGuideR52.Template(p.get("name").getAsString(),p.get("frame").getAsString(),p.get("role").getAsString(),new NervRigidMeshSweepR52(xyz),rgb));}parts=List.copyOf(out);return parts;
    }
    public static boolean slides(String role){return Set.of("capture_structure","upper_bearing","lower_bearing","side_bearing","transfer_slider").contains(role);}
    private static double ease(double t){t=Math.max(0,Math.min(1,t));return t*t*t*(10+t*(-15+6*t));}
    public static Pose sample(Vec3 from,Vec3 to,double clock)
    {
        if(from==null||to==null||!Double.isFinite(from.lengthSqr())||!Double.isFinite(to.lengthSqr())||!Double.isFinite(clock)||clock<0||clock>TICKS||Math.abs(from.length()-1)>1e-8||Math.abs(to.length()-1)>1e-8||Math.abs(from.dot(to))>1e-7)throw new IllegalArgumentException("Actual perpendicular stopped-bank guide axes and bounded clock required");
        double slide=clock<30?-RETRACT*ease(clock/30):clock<=90?-RETRACT:-RETRACT*(1-ease((clock-90)/30));
        double turn=ease((clock-30)/60);Vec3 direction=turn==0?from:turn==1?to:from.scale(Math.cos(turn*Math.PI/2)).add(to.scale(Math.sin(turn*Math.PI/2))).normalize();
        return new Pose(direction,slide);
    }
    public static CompoundTag begin(UUID task,String directory,String route,Vec3 from,Vec3 to)
    {
        sample(from,to,0);var t=new CompoundTag();t.putString("Source",SOURCE_SHA);t.putUUID("Task",task);t.putString("Directory",directory);t.putString("Route",route);t.putInt("Clock",0);t.put("From",point(from));t.put("To",point(to));return t;
    }
    public static Pose pose(CompoundTag state,double clock)
    {if(!state.getString("Source").equals(SOURCE_SHA))throw new IllegalStateException("Actual local head source changed");return sample(point(state.getCompound("From")),point(state.getCompound("To")),clock);}
    public static boolean unfinished(CompoundTag state){return !state.isEmpty()&&state.getInt("Clock")<TICKS&&!state.getBoolean("AbortedToStart");}
    public static CompoundTag advance(CompoundTag state,int direction,long at)
    {
        int clock=state.getInt("Clock"),next=clock+direction;if((direction!=1&&direction!=-1)||next<0||next>TICKS)throw new IllegalArgumentException("One actual bounded local head step required");pose(state,clock);pose(state,next);var t=state.copy();t.putInt("PreviousClock",clock);t.putInt("Clock",next);t.putLong("At",at);t.putBoolean("AbortedToStart",direction<0&&next==0);return t;
    }
    public static CompoundTag point(Vec3 p){var t=new CompoundTag();t.putDouble("X",p.x);t.putDouble("Y",p.y);t.putDouble("Z",p.z);return t;}
    public static Vec3 point(CompoundTag p){if(!p.contains("X")||!p.contains("Y")||!p.contains("Z"))throw new IllegalStateException("Explicit stored guide axis required");return new Vec3(p.getDouble("X"),p.getDouble("Y"),p.getDouble("Z"));}
    /** Actual finite source facets bound the ball inside every socket orientation. */
    private static Boolean internalBearingProof;
    public static synchronized boolean internalBearings()throws IOException
    {
        if(internalBearingProof!=null)return internalBearingProof;
        var source=NervOuterCarrierGuideR52.templates();
        for(int side:new int[]{-1,1})
        {
            String prefix="outer/"+side+"/";var ball=source.stream().filter(p->p.name().equals(prefix+"ball")).findFirst().orElseThrow();var socket=source.stream().filter(p->p.name().equals(prefix+"ball_socket")).findFirst().orElseThrow();double radius=0,inner=Double.POSITIVE_INFINITY;var centre=NervOuterCarrierGuideR52.ballLocal(side);var xyz=ball.mesh().triangles();for(int n=0;n<xyz.length;n+=3)radius=Math.max(radius,new Vec3(xyz[n],xyz[n+1],xyz[n+2]).distanceTo(centre));xyz=socket.mesh().triangles();var local=new Vec3(0,.35,0);
            for(int n=0;n<xyz.length;n+=9){var a=new Vec3(xyz[n],xyz[n+1],xyz[n+2]);var b=new Vec3(xyz[n+3],xyz[n+4],xyz[n+5]);var c=new Vec3(xyz[n+6],xyz[n+7],xyz[n+8]);if(Math.max(a.distanceTo(local),Math.max(b.distanceTo(local),c.distanceTo(local)))>.19)continue;var normal=b.subtract(a).cross(c.subtract(a));if(normal.lengthSqr()<1e-20)continue;inner=Math.min(inner,Math.abs(a.subtract(local).dot(normal.scale(1/normal.length()))));}
            if(!Double.isFinite(inner)||inner-radius<.000005)return false;
            double inscribed=Double.POSITIVE_INFINITY,opening=0;xyz=ball.mesh().triangles();for(int n=0;n<xyz.length;n+=9){var a=new Vec3(xyz[n],xyz[n+1],xyz[n+2]);var b=new Vec3(xyz[n+3],xyz[n+4],xyz[n+5]);var c=new Vec3(xyz[n+6],xyz[n+7],xyz[n+8]);var normal=b.subtract(a).cross(c.subtract(a));if(normal.lengthSqr()>1e-20)inscribed=Math.min(inscribed,Math.abs(a.subtract(centre).dot(normal.scale(1/normal.length()))));}
            xyz=socket.mesh().triangles();for(int n=0;n<xyz.length;n+=3){var v=new Vec3(xyz[n],xyz[n+1],xyz[n+2]);if(Math.abs(v.x+side*.03)<1e-9&&v.distanceTo(local)<.19)opening=Math.max(opening,Math.hypot(v.y-.35,v.z));}if(!Double.isFinite(inscribed)||opening<=0||inscribed-opening<.002)return false;
        }
        // Four genuine sleeve faces surround the full source stator; this
        // interval proves finite face overlap throughout the entire stroke.
        var selected=templates();for(int side:new int[]{-1,1}){String prefix="outer/"+side+"/transfer/";var rail=selected.stream().filter(p->p.name().equals(prefix+"stator")).findFirst().orElseThrow().mesh().bounds();for(String name:List.of("lower","left","right","upper")){var b=selected.stream().filter(p->p.name().equals(prefix+name)).findFirst().orElseThrow().mesh().bounds();if(b.minZ-RETRACT<rail.minZ||b.maxZ>rail.maxZ)return false;double fit=switch(name){case "lower"->Math.abs(b.maxY-rail.minY);case "upper"->Math.abs(b.minY-rail.maxY);case "left"->Math.abs(b.maxX-rail.minX);default->Math.abs(b.minX-rail.maxX);};double area=(b.maxZ-b.minZ)*(name.equals("lower")||name.equals("upper")?rail.getXsize():rail.getYsize());if(fit>1e-7||area<.0025)return false;}}
        internalBearingProof=true;return true;
    }
    private NervBankHeadTransferR53(){}
}
