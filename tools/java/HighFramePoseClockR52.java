package com.projectseele.entity;
import java.util.*;

/** Exercise real clock kernels at high render cadence without any game/entity. */
public final class HighFramePoseClockR52 {
    static void check(boolean value,String why){if(!value)throw new AssertionError(why);}
    public static void main(String[] args) {
        int cases=0;
        for(int fps:new int[]{30,60,120,240}) {
            var action=new EvaPoseSignalClock();long origin=1_000_000_000L;
            action.acceptActionAt("same-action",0,true,origin);
            float last=0;int changed=0;long nextPacket=origin+50_000_000L;
            float endpoint=0;
            for(int i=1;i<=fps;i++) {
                long now=origin+Math.round(i*1_000_000_000D/fps);
                while(now>=nextPacket) {
                    float before=action.sample(nextPacket);endpoint+=.05F;
                    action.acceptActionAt("same-action",endpoint,true,nextPacket);
                    check(Math.abs(action.sample(nextPacket)-before)<1e-6F,"Packet broke presented C0 at "+fps);
                    nextPacket+=50_000_000L;
                }
                float value=action.sample(now);
                check(value+1e-6F>=last&&value<=endpoint+1e-6F,"Action backwards or beyond endpoint");
                if(value>last+1e-6F)changed++;
                check(action.sample(now)==value,"Duplicate frame changed sample");
                last=value;
            }
            check(changed>=fps*.8,"Render quantized to integral ticks at "+fps+": "+changed);
            action.acceptActionAt("new-action",0,true,origin+1_010_000_000L);
            check(action.sample(origin+1_010_000_000L)==0,"New source inherited prior phase");
            action.acceptActionAt("new-action",.05F,true,origin+1_050_000_000L);
            check(action.sample(origin+5_000_000_000L)==.05F,"Silent stream overran endpoint");
            var movie=new FirstBattleClock(360,origin);double prior=360;
            for(int i=1;i<=fps;i++) {
                long now=origin+Math.round(i*1_000_000_000D/fps);int confirmed=360+Math.min(19,(int)(i*20D/fps));
                double value=movie.sample(confirmed,now,false);
                check(value>=prior&&value<=confirmed+2+1e-6,"Firstbattle clock backwards/extrapolation");
                if(confirmed<372)check(value<372,"Death cue anticipated before server confirmation");
                check(movie.sample(confirmed,now,false)==value,"Paired actor same-frame clock differed");prior=value;
            }
            double paused=movie.sample(379,origin+1_020_000_000L,true);
            check(movie.sample(379,origin+2_020_000_000L,true)==paused,"Paused movie advanced");
            cases++;
        }
        System.out.println("PASS: "+cases+" render cadences (30/60/120/240 Hz), packet C0, duplicate frames, source restart, endpoint hold, paired clock, server death cue and pause; no game/entity instantiated.");
    }
}
