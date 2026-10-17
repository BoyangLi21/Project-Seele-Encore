package com.projectseele.world;

import java.util.*;
import net.minecraft.world.level.ChunkPos;

public final class NervChunkAdmissionR53Test
{
    private static int checks;
    private static void check(boolean okay,String reason){checks++;if(!okay)throw new AssertionError(reason);}
    public static void main(String[] args)
    {
        var admission=new NervChunkAdmissionR53();var issued=new LinkedHashMap<ChunkPos,Integer>();var ready=new HashSet<ChunkPos>();
        for(int i=0;i<168;i++)admission.request(new ChunkPos(i,20),2);
        for(int tick=0;tick<20;tick++)admission.advance(tick,(chunk,radius)->ready.contains(chunk),issued::put);
        check(issued.size()==4,"Cold loading grew beyond four outstanding actor chunks");
        check(!admission.admittedAll(),"Pending original actors were reported admitted");
        for(int tick=20;tick<200&&!admission.admittedAll();tick++)
        {
            ready.addAll(issued.keySet());int before=issued.size();admission.advance(tick,(chunk,radius)->ready.contains(chunk),issued::put);
            check(issued.size()-before<=2,"More than two new origins were admitted in one tick");
            int after=issued.size();admission.advance(tick,(chunk,radius)->true,issued::put);check(after==issued.size(),"Repeated caller bypassed same-tick budget");
        }
        check(admission.admittedAll()&&issued.size()==168,"A retained original actor was dropped");
        var renewed=new LinkedHashMap<ChunkPos,Integer>();admission.refresh(renewed::put);check(renewed.equals(issued),"Ticket refresh omitted original actors");
        var feet=new ChunkPos(-2,-3);admission.request(feet,0);admission.advance(201,(chunk,radius)->true,issued::put);check(issued.get(feet)==0,"Read-only foundation requested entity ticking");
        admission.request(feet,2);admission.request(feet,0);check(!admission.admittedAll(),"Actor promotion was lost");admission.advance(202,(chunk,radius)->true,issued::put);check(issued.get(feet)==2&&admission.admittedAll(),"Original actor was downgraded by overlapping foundation");
        System.out.println("Bounded original chunk admission PASS checks="+checks);
    }
}
