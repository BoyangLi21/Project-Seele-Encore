package com.projectseele.entity;

import com.projectseele.entity.EvaMoveTableR64.Row;
import com.projectseele.entity.EvaRowClockR64.Clock;
import com.projectseele.entity.EvaRowClockR64.View;

import java.util.ArrayList;
import java.util.List;
import java.util.Random;

/**
 * R64 (flow): a row's clock. The curve the stages lie on never turns back, keeps the stages' places and its pace
 * across them; and a client's view of a row, fed frames at any rate and packets when a frame lets them in, never
 * goes back, never jumps, draws all of the clip at a hit and is back on the server's time a tick after the hold.
 */
public final class EvaRowClockR64Test
{
    private static void check(boolean condition,String message)
    {
        if(!condition)throw new AssertionError(message);
    }

    private static Clock clock(Row r,float contact,boolean smooth,int hitAt,float hitPhase,int hold,int dueAt,float duePhase)
    {
        float open=Math.max(.02F,contact-r.lead()),close=contact+r.tail();
        return new Clock(1,r.name(),r.name(),r.startup(),r.active(),r.recovery(),open,close,smooth,hitAt,hitPhase,hold,dueAt,duePhase);
    }

    public static void main(String[] args)
    {
        int rows=0;
        for(Row r:EvaMoveTableR64.rows())
        {
            rows++;
            for(float contact:new float[]{.19F,.26F,.5F})
            {
                String n=r.name()+" with its contact at "+contact;
                Clock straight=clock(r,contact,false,-1,0,0,-1,0),smooth=clock(r,contact,true,-1,0,0,-1,0);
                int a=r.startup(),b=r.active(),total=r.total();
                for(int k=0;k<=total;k++)
                    check(Math.abs(straight.phase(k)-EvaMoveTableR64.phase(k,a,b,r.recovery(),straight.open(),straight.close()))<1.0e-6F,n+": the straight lines are the table's own at tick "+k);
                check(Math.abs(smooth.phase(a)-smooth.open())<1.0e-5F&&Math.abs(smooth.phase(a+b)-smooth.close())<1.0e-5F&&smooth.phase(total)==1&&smooth.phase(0)==0,
                        n+": the curve is at the stages' places where they meet");
                float before=0;
                for(double u=0;u<=total;u+=.01)
                {
                    float p=smooth.phase(u);
                    check(p>=before-1.0e-6F,n+": the curve never turns back (at "+u+")");before=p;
                }
                // Its pace is the same on both sides of where two stages meet; the straight lines' is not.
                for(int knot:new int[]{a,a+b})
                {
                    double left=(smooth.phase(knot)-smooth.phase(knot-.02))/.02,right=(smooth.phase(knot+.02)-smooth.phase(knot))/.02;
                    check(Math.abs(left-right)<=.06*Math.max(left,right)+1.0e-4,n+": one pace on both sides of tick "+knot+" ("+left+", "+right+")");
                }
                // A phase is found again at its place.
                for(double u=.5;u<total-1;u+=.7)
                    check(Math.abs(smooth.place(smooth.phase(u),0,total)-u)<.02||smooth.phase(u+.05)-smooth.phase(u-.05)<1.0e-4F,n+": the place of a phase at "+u);
            }
        }
        check(rows>=8,"the table's rows were read");

        Row jab=EvaMoveTableR64.get("jab"),kick=EvaMoveTableR64.get("kick"),slam=EvaMoveTableR64.get("slam");
        for(double fps:new double[]{24,30,45,60,72,144})
            for(long seed=1;seed<=4;seed++)
            {
                play(clock(jab,.225F,true,-1,0,0,-1,0),fps,seed,-1,0,0,false);
                play(clock(kick,.61F,true,-1,0,0,-1,0),fps,seed,-1,0,0,false);
                // A hit, told a tick ahead and then made; and one that comes untold.
                play(clock(jab,.225F,true,-1,0,0,-1,0),fps,seed,jab.startup()+1,.6,EvaMoveTableR64.pause(jab.level()),true);
                play(clock(kick,.61F,true,-1,0,0,-1,0),fps,seed,kick.startup()+2,.3,EvaMoveTableR64.pause(kick.level()),true);
                play(clock(slam,.222F,false,-1,0,0,-1,0),fps,seed,slam.startup()+1,.9,EvaMoveTableR64.pause(slam.level()),true);
                play(clock(kick,.61F,true,-1,0,0,-1,0),fps,seed,kick.startup()+2,.3,EvaMoveTableR64.pause(kick.level()),false);
                play(clock(jab,.225F,false,-1,0,0,-1,0),fps,seed,jab.startup()+1,.6,jab.stop(),false);
            }
        fades();
        leaves();
        kick();
        hardKick();
        body();
        System.out.println("EvaRowClockR64Test: "+rows+" rows' curves, a view at 24 to 144 frames a second with and without a hit, a blow out of another, a row left, and the kick's clip against its row");
    }

    /**
     * A row played to a client. The server makes a tick every tick (but for the hold); what it tells reaches the
     * client at the first frame after 0.3 of a tick; frames come at the rate, a fifth uneven.
     * hitAt: the tick of the row the blow lands in, or -1; back: how far before that tick's place the limb met its
     * mark, in ticks; ahead: the contact is told a tick before.
     */
    private static void play(Clock told,double fps,long seed,int hitAt,double back,int hold,boolean ahead)
    {
        String n=told.row()+" at "+fps+" frames a second"+(hitAt<0?"":ahead?", a hit told ahead":", a hit untold")+" (seed "+seed+")";
        var random=new Random(seed);
        var view=new View();
        double begun=100+random.nextDouble(),lag=.3,frame=20/fps,time=begun-2;
        float metPhase=hitAt<0?0:told.phase(hitAt-back);
        // What the server has told by a time: the clock, and the phases it sent (one a tick).
        List<double[]> phases=new ArrayList<>();   // {time told, phase}
        int total=told.total();
        for(int k=1;k<=total;k++)
        {
            double when=begun+(k-1)+(hitAt>=0&&k>hitAt?hold:0);
            phases.add(new double[]{when+lag,hitAt>=0&&k==hitAt?metPhase:told.phase(k)});
        }
        double hitTime=hitAt<0?Double.MAX_VALUE:begun+(hitAt-1);
        int sent=0;double last=-1,lastTime=0,most=0;boolean seen=false;
        double end=begun+total+(hitAt>=0?hold:0)+1;
        double metPlace=hitAt<0?0:told.place(metPhase,hitAt-3,hitAt);
        List<double[]> drawn=new ArrayList<>();
        while(time<end)
        {
            time+=frame*(.8+.4*random.nextDouble());
            // packets are taken in at the frame
            Clock now=null;
            if(time>=begun+lag)
            {
                boolean hitTold=hitAt>=0&&time>=hitTime+lag,dueTold=ahead&&hitAt>=0&&time>=hitTime-1+lag;
                now=new Clock(told.serial(),told.row(),told.clip(),told.startup(),told.live(),told.recovery(),told.open(),told.close(),told.smooth(),
                        hitTold?hitAt:-1,hitTold?metPhase:0,hitTold?hold:0,dueTold?hitAt:-1,dueTold?metPhase:0);
            }
            while(sent<phases.size()&&phases.get(sent)[0]<=time)
            {
                if(seen)view.heard((float)phases.get(sent)[1],time);
                sent++;
            }
            float phase=view.frame(now,time);
            if(now==null){check(phase==-1,n+": nothing is drawn before the row is told");continue;}
            seen=true;
            double place=view.place();
            check(Math.abs(told.phase(place)-phase)<1.0e-6F,n+": the phase drawn is the place's");
            if(last>=0)
            {
                double step=place-last,dt=time-lastTime;
                check(step>=-1.0e-9,n+": the place drawn never goes back (at "+time+")");
                // never more than twice the row's pace and what it makes up: a jump would be many times that
                check(step<=(2+EvaRowClockR64.CATCH)*dt+1.0e-6,n+": no jump: "+step+" ticks of the row in "+dt+" ticks at "+(time-begun));
                most=Math.max(most,step/dt);
            }
            last=place;lastTime=time;
            drawn.add(new double[]{time,place});
            // Told ahead, the limb is not drawn past its mark before the hit is made.
            if(hitAt>=0&&ahead&&time<hitTime+lag)check(place<=metPlace+.05,n+": the limb is drawn "+(place-metPlace)+" ticks past its mark before the hit");
        }
        // It is back on the server's count a tick after the hold, and stays on it at an even pace.
        // (A packet is heard a frame late at the most, so the view's count may be that much behind the server's.)
        double settled=hitAt<0?begun+7:hitTime+hold+1+lag+.5;
        for(int i=1;i<drawn.size();i++)
        {
            double t=drawn.get(i)[0],place=drawn.get(i)[1];
            if(t<settled||place>=total-.5)continue;
            double count=t-lag-begun+1-(hitAt>=0?hold:0);
            check(Math.abs(place-count)<.35+frame*1.2,n+": at "+(t-begun)+" the place drawn is "+place+", the server's count "+count);
            if(t<settled+3)continue;
            double pace=(place-drawn.get(i-1)[1])/(t-drawn.get(i-1)[0]);
            check(pace>.8&&pace<1.2,n+": an even pace once it is on the row's time, not "+pace+" at "+(t-begun));
        }
        check(last>=total-.6,n+": the row is drawn to its end ("+last+" of "+total+")");
        if(hitAt>=0)
        {
            // Nothing of the clip is stepped over: between the mark and the next tick's place every part is drawn in some frame's reach.
            double biggest=0;
            for(int i=1;i<drawn.size();i++)if(drawn.get(i)[1]>metPlace&&drawn.get(i-1)[1]<hitAt+1)biggest=Math.max(biggest,drawn.get(i)[1]-drawn.get(i-1)[1]);
            check(biggest<=(2+EvaRowClockR64.CATCH)*frame*1.2+1.0e-6,n+": the blow goes through its mark in steps of a frame, not "+biggest);
        }
    }

    /** A blow begun out of another: the other runs on while the new one takes its place, and is let go when it has. */
    private static void fades()
    {
        Row jab=EvaMoveTableR64.get("jab"),cross=EvaMoveTableR64.get("cross");
        Clock first=clock(jab,.225F,true,-1,0,0,-1,0);
        Clock second=new Clock(2,"cross","cross",cross.startup(),cross.active(),cross.recovery(),.184F,.322F,true,-1,0,0,-1,0);
        var view=new View();
        double time=50;
        for(;time<57;time+=.33)view.frame(first,time);
        check(view.fade(time)==null&&!view.outOfAnother(),"a blow from standing takes no other's place");
        double from=time;float weight=0,other=-1;
        for(;time<from+6;time+=.33)
        {
            view.frame(second,time);
            var fade=view.fade(time);
            if(time-from<EvaRowClockR64.fade(cross.startup())-.34)
            {
                check(fade!=null&&fade.clip().equals("jab"),"the jab is still in the pose "+(time-from)+" ticks into the cross");
                check(fade.weight()>=weight&&fade.weight()<=1,"the cross's share only grows");
                check(fade.phase()>=other,"the jab runs on while it fades");
                weight=fade.weight();other=fade.phase();
            }
            check(view.outOfAnother(),"the cross is known to have begun out of the jab");
        }
        check(view.fade(time)==null,"the jab is let go when the cross has taken its place");
        check(weight>.6F,"the cross had most of the pose before the jab was let go ("+weight+")");
        check(view.frame((Clock)null,time)==-1&&!view.playing(),"no row, nothing drawn");
    }

    /** STAND: a row's share of the pose, and a row left before it had played out giving its place to what follows. */
    private static void leaves()
    {
        float last=0;
        for(float phase=0;phase<=.159F;phase+=.004F)
        {
            float share=EvaRowClockR64.share(.159F,.318F,phase);
            check(share>=last&&share<=1,"a blow's share of the pose only grows through its start-up");last=share;
        }
        check(EvaRowClockR64.share(.159F,.318F,0)==0,"a blow begins where the Unit stands");
        for(float phase=.159F;phase<=.318F;phase+=.004F)check(EvaRowClockR64.share(.159F,.318F,phase)==1,"through its live part the pose is the clip's alone");
        last=1;
        for(float phase=.318F;phase<=1;phase+=.004F)
        {
            float share=EvaRowClockR64.share(.159F,.318F,phase);
            check(share<=last&&share>=0,"a blow's share of the pose only falls through its recovery");last=share;
        }
        check(EvaRowClockR64.share(.159F,.318F,1)==0,"a blow ends where the Unit stands");
        check(EvaRowClockR64.share(0,.318F,0)==1&&EvaRowClockR64.share(.159F,1,1)==1,"a row without a start-up or a recovery on its clip keeps the whole pose there");

        Row jab=EvaMoveTableR64.get("jab");
        Clock row=clock(jab,.225F,true,-1,0,0,-1,0);
        var view=new View();
        double time=80;
        for(;time<89;time+=.33)view.frame(row,time);
        check(view.leave(time)==null,"a row in hand has not been left");
        double from=time;float weight=0,phase=-1;
        view.frame((Clock)null,time);
        for(;time<from+EvaRowClockR64.LEAVE-.34;time+=.33)
        {
            view.frame((Clock)null,time);
            var leave=view.leave(time);
            check(leave!=null&&leave.clip().equals("jab"),"the jab left at its ninth tick is still in the pose "+(time-from)+" ticks on");
            check(leave.weight()>=weight&&leave.weight()<=1,"what follows only gains of the pose");
            check(leave.phase()>=phase&&leave.phase()<=1,"the row left runs on along its clip");
            check(leave.share()>=0&&leave.share()<1,"it was on its way back into the stand");
            weight=leave.weight();phase=leave.phase();
        }
        check(weight>.8F,"what follows had most of the pose before the row was let go ("+weight+")");
        check(view.leave(from+EvaRowClockR64.LEAVE+.01)==null,"the row is let go after its ticks");

        var whole=new View();
        for(time=120;time<120+row.total()+2;time+=.33)whole.frame(row,time);
        whole.frame((Clock)null,time);
        check(whole.leave(time)==null,"a row that played out leaves nothing behind");
    }

    /**
     * KICK: the kick's clip (tools/finale/kick.py) is laid on its frames for the row that plays it. A row whose
     * ticks or live part have been changed plays it at other paces than it was written with: write it again.
     */
    /**
     * R64 (flow, "body"): the Unit's own bare-handed blows (tools/finale/unarmed.py) against their rows. A clip is
     * laid on its row's curve, so the row it was made for is the row the table has; its live part lies inside it;
     * the body is never carried back, and its stride is made by the end of its live ticks; a foot is on the ground
     * at every frame but in the knee's spring and the charge's leap.
     */
    private static void body()
    {
        try(var stream=EvaRowClockR64Test.class.getResourceAsStream("/assets/projectseele/motion/eva_unarmed_r64.json"))
        {
            check(stream!=null,"the bare-handed blows' clips come with the mod");
            var doc=com.google.gson.JsonParser.parseReader(new java.io.InputStreamReader(stream,java.nio.charset.StandardCharsets.UTF_8)).getAsJsonObject();
            for(String name:new String[]{"pounce","knee","charge"})
            {
                Row row=EvaMoveTableR64.get(name);
                check(row!=null&&row.kind()==EvaMoveTableR64.PUNCH,name+" is a row of the table, in a punch's place");
                var clip=doc.getAsJsonObject("clips").getAsJsonObject("r32_"+name+"_r64");
                check(clip!=null,name+" has its clip");
                if(name.equals("knee")||name.equals("charge"))
                {
                    float modelX=clip.getAsJsonArray("contact_point_model").get(0).getAsFloat();
                    check(name.equals("knee")?modelX<0:modelX>0,name+": authored contact stays on the striking side after the model X mirror");
                }
                var made=clip.getAsJsonObject("row");
                check(made.get("startup").getAsInt()==row.startup()&&made.get("live").getAsInt()==row.active()&&made.get("recovery").getAsInt()==row.recovery()
                        &&Math.abs(made.get("lead").getAsFloat()-row.lead())<1.0e-6F&&Math.abs(made.get("tail").getAsFloat()-row.tail())<1.0e-6F,
                        name+"'s clip was made for the row the table has");
                float contact=clip.get("contact_phase").getAsFloat();
                check(contact-row.lead()>.02F&&contact+row.tail()<.98F,name+"'s live part lies inside its clip");
                check(Math.abs(clip.get("duration_seconds").getAsFloat()-row.total()/20F)<1.0e-4F,name+"'s clip is as long as its row");
                var frames=clip.getAsJsonArray("frames");var path=clip.getAsJsonArray("trajectory_m");
                int bones=clip.getAsJsonArray("bones").size(),close=Math.round((contact+row.tail())*(frames.size()-1));
                check(frames.size()>=40&&path.size()==frames.size()&&clip.has("contact_bone"),name+" has its frames, a place for each, and a bone its mark is on");
                double ahead=0,last=-path.get(frames.size()-1).getAsJsonArray().get(2).getAsDouble();
                for(int i=0;i<frames.size();i++)
                {
                    var frame=frames.get(i).getAsJsonObject();var feet=frame.getAsJsonArray("foot_contact");
                    check(frame.getAsJsonArray("rotation_delta_wxyz").size()==bones,name+": every frame turns every bone the clip names");
                    check(feet.get(0).getAsBoolean()||feet.get(1).getAsBoolean()||!name.equals("pounce"),name+": a foot is on the ground at every frame");
                    double now=-path.get(i).getAsJsonArray().get(2).getAsDouble();
                    check(now>=ahead-1.0e-6,name+": the body is never carried back");ahead=now;
                    if(i>=close)check(Math.abs(now-last)<1.0e-6,name+": its stride is made by the end of its live part");
                }
                check(ahead>.05,name+" has a stride");
                var first=frames.get(0).getAsJsonObject().getAsJsonArray("foot_contact");var end=frames.get(frames.size()-1).getAsJsonObject().getAsJsonArray("foot_contact");
                check(first.get(0).getAsBoolean()&&first.get(1).getAsBoolean()&&end.get(0).getAsBoolean()&&end.get(1).getAsBoolean(),name+" begins and ends on both feet");
            }
            check(EvaMoveTableR64.get("pounce").light().equals("knee")&&EvaMoveTableR64.get("knee").light().equals("slam"),"the string is pounce, knee, slam");
            check(EvaMoveTableR64.opener(0,false,false,false,true,false).name().equals("jab")
                    &&EvaMoveTableR64.opener(0,false,true,false,true,false).name().equals("pounce")&&EvaMoveTableR64.opener(0,false,false,false,true,true).name().equals("charge")
                    &&EvaMoveTableR64.opener(0,false,false,false,false,true).name().equals("jab")&&EvaMoveTableR64.opener(0,true,false,false,true,true).name().equals("kick"),
                    "standing light is a punch, light after an evade is a pounce, sprinting light is a charge, heavy is a kick");
        }
        catch(java.io.IOException e){throw new IllegalStateException(e);}
    }

    private static void kick()
    {
        Row row=EvaMoveTableR64.get("kick");
        try(var stream=EvaRowClockR64Test.class.getResourceAsStream("/assets/projectseele/motion/eva_kick_r64.json"))
        {
            check(stream!=null,"the kick's clip comes with the mod");
            var doc=com.google.gson.JsonParser.parseReader(new java.io.InputStreamReader(stream,java.nio.charset.StandardCharsets.UTF_8)).getAsJsonObject();
            var made=doc.getAsJsonObject("row");
            check(made.get("startup").getAsInt()==row.startup()&&made.get("live").getAsInt()==row.active()&&made.get("recovery").getAsInt()==row.recovery()
                    &&Math.abs(made.get("lead").getAsFloat()-row.lead())<1.0e-4F&&Math.abs(made.get("tail").getAsFloat()-row.tail())<1.0e-4F,
                    "the kick's clip was written for the kick's row as the table has it (run tools/finale/kick.py again)");
            for(String name:new String[]{"r32_kick_r64","r32_kick_step_r64"})
            {
                boolean step=name.contains("step");
                var clip=doc.getAsJsonObject("clips").getAsJsonObject(name);
                check(clip!=null,name+" is in the kick's file");
                float contact=clip.get("contact_phase").getAsFloat();
                check(contact-row.lead()>.02F&&contact+row.tail()<.98F,"the row's live part lies inside the kick's clip");
                var frames=clip.getAsJsonArray("frames");var path=clip.getAsJsonArray("trajectory_m");
                int bones=clip.getAsJsonArray("bones").size(),air=0,open=Math.round((contact-row.lead())*(frames.size()-1));
                check(frames.size()>=40&&path.size()==frames.size(),"the kick has its frames and a place for each");
                double ahead=0;
                for(int i=0;i<frames.size();i++)
                {
                    var frame=frames.get(i).getAsJsonObject();var feet=frame.getAsJsonArray("foot_contact");
                    check(frame.getAsJsonArray("rotation_delta_wxyz").size()==bones,"every frame turns every bone the clip names");
                    check(feet.get(0).getAsBoolean()||feet.get(1).getAsBoolean(),"a foot is on the ground at every frame");
                    // In place the standing foot never leaves the ground; with the step in it is set down before the live part.
                    check(feet.get(1).getAsBoolean()||step&&i<open,"the standing foot is on the ground through the kick");
                    if(!feet.get(0).getAsBoolean())air++;
                    else check(air==0||i>frames.size()/2,"the kicking foot leaves the ground once");
                    double now=-path.get(i).getAsJsonArray().get(2).getAsDouble();
                    check(now>=ahead-1.0e-6,"the body is never carried back");ahead=now;
                    // (.004 of a metre is a seventh of a block)
                    if(step&&i<=Math.floor(EvaRowClockR64.STEP_IN*(contact-row.lead())*(frames.size()-1)))
                        check(now<.004,"the stride begins after the pose has come out of the stand");
                    if(i>=open)check(Math.abs(now-(-path.get(frames.size()-1).getAsJsonArray().get(2).getAsDouble()))<1.0e-6,"the step is made before the live part");
                }
                check(step?ahead>.1:ahead==0,step?"the step in carries the body ahead":"the kick in place carries the body nowhere");
                check(frames.get(0).getAsJsonObject().getAsJsonArray("foot_contact").get(0).getAsBoolean()
                        &&frames.get(frames.size()-1).getAsJsonObject().getAsJsonArray("foot_contact").get(0).getAsBoolean()&&air>frames.size()/3,
                        "the kick begins and ends on both feet, and is off one of them for a good part between");
            }
        }
        catch(java.io.IOException error){throw new java.io.UncheckedIOException(error);}
    }

    /**
     * STEP without KICK: the hard kick (tools/finale/hardkick.py) is the captured kick laid on the kick's row. Its
     * frames are written whole; its body's path is the capture's own, with the stride of the step in beside it.
     */
    private static void hardKick()
    {
        Row row=EvaMoveTableR64.get("kick");
        try(var stream=EvaRowClockR64Test.class.getResourceAsStream("/assets/projectseele/motion/eva_kick_hard_r64.json"))
        {
            check(stream!=null,"the hard kick's clip comes with the mod");
            var doc=com.google.gson.JsonParser.parseReader(new java.io.InputStreamReader(stream,java.nio.charset.StandardCharsets.UTF_8)).getAsJsonObject();
            var made=doc.getAsJsonObject("row");
            check(made.get("startup").getAsInt()==row.startup()&&made.get("live").getAsInt()==row.active()&&made.get("recovery").getAsInt()==row.recovery()
                    &&Math.abs(made.get("lead").getAsFloat()-row.lead())<1.0e-4F&&Math.abs(made.get("tail").getAsFloat()-row.tail())<1.0e-4F,
                    "the hard kick's clip was written for the kick's row as the table has it (run tools/finale/hardkick.py again)");
            var clip=doc.getAsJsonObject("clips").getAsJsonObject("r32_kick_hard_r64");
            check(clip!=null,"r32_kick_hard_r64 is in the hard kick's file");
            float contact=clip.get("contact_phase").getAsFloat();
            check(contact-row.lead()>.02F&&contact+row.tail()<.98F,"the row's live part lies inside the hard kick's clip");
            var frames=clip.getAsJsonArray("frames");var path=clip.getAsJsonArray("trajectory_m");var stride=clip.getAsJsonArray("stride_m");
            int bones=clip.getAsJsonArray("bones").size(),last=frames.size()-1;
            int open=Math.round((contact-row.lead())*last),close=Math.round((contact+row.tail())*last);
            check(frames.size()>=40&&path.size()==frames.size()&&stride.size()==frames.size(),"the hard kick has its frames, and a place and a stride for each");
            double whole=-stride.get(last).getAsJsonArray().get(2).getAsDouble(),before=0;
            check(Math.abs(whole*EvaRootClosureR63.blocks(1)-doc.get("stride_blocks").getAsDouble())<.05,"the stride is as long as the file says");
            int air=0;
            for(int i=0;i<=last;i++)
            {
                var frame=frames.get(i).getAsJsonObject();var feet=frame.getAsJsonArray("foot_contact");
                check(frame.getAsJsonArray("rotation_wxyz").size()==bones&&frame.getAsJsonArray("root_m").size()==3,"every frame is written whole");
                // the standing foot is set down before the live part and stays down until the kicking foot is on the ground again
                if(i>=open&&i<=close)check(feet.get(1).getAsBoolean()&&!feet.get(0).getAsBoolean(),"through the live part the Unit stands on its right foot and kicks with its left");
                if(!feet.get(0).getAsBoolean()&&!feet.get(1).getAsBoolean())air++;
                double now=-stride.get(i).getAsJsonArray().get(2).getAsDouble();
                check(now>=before-1.0e-6,"the stride never carries the body back");before=now;
                if(i<=Math.floor(EvaRowClockR64.STEP_IN*(contact-row.lead())*last))
                    check(now<.004&&Math.abs(path.get(i).getAsJsonArray().get(2).getAsDouble())<.004,"the body is carried nowhere before the pose has come out of the stand");
                if(i>=open)check(Math.abs(now-whole)<1.0e-6,"the stride is made before the live part");
            }
            // (the feet are changed one after the other: both are off the ground only as the one is set down and the other leaves)
            check(air<=3,"the Unit is never off both feet for longer than a twentieth of a second");
            for(int i:new int[]{0,last})
            {
                var feet=frames.get(i).getAsJsonObject().getAsJsonArray("foot_contact");
                check(feet.get(0).getAsBoolean()&&feet.get(1).getAsBoolean(),"the hard kick begins and ends on both feet");
            }
            check(Math.abs(path.get(0).getAsJsonArray().get(0).getAsDouble())<1.0e-6&&Math.abs(path.get(0).getAsJsonArray().get(2).getAsDouble())<1.0e-6,"the body's path begins where the Unit stands");
        }
        catch(java.io.IOException error){throw new java.io.UncheckedIOException(error);}
    }

    private EvaRowClockR64Test(){}
}
