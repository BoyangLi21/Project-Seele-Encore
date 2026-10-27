package com.projectseele.world;

import java.util.*;
import net.minecraft.world.phys.*;

/** Standalone analytic contact exit candidate; success never asserts native pickup. */
public final class RescueTranslationEgressR53Test
{
    private static int checks;
    private static void check(boolean ok,String why){checks++;if(!ok)throw new AssertionError(why);}
    private static RescueTranslationEgressR53.Part panel(String name,double x)
    {return new RescueTranslationEgressR53.Part(name,new double[]{x,.2,.2,x,.8,.2,x,.2,.8});}
    private static RescueTranslationEgressR53.Result proof(List<RescueTranslationEgressR53.Part> p,List<AABB>b,Vec3 d)
    {return RescueTranslationEgressR53.prove(p,b,d,8);}
    public static void main(String[] args)
    {
        var block=new AABB(0,0,0,1,1,1);var blocks=List.of(block);var embedded=List.of(panel("actual_source",.9));
        var exit=proof(embedded,blocks,new Vec3(.5,0,0));
        check(exit.proved()&&exit.initialContacts()==1&&exit.reason().equals("monotone_source_exit"),"Valid bounded source contact must be recoverable");
        check(exit.outwardRounding()>0,"Rounding must expand obstacles");
        check(!proof(embedded,blocks,new Vec3(-.5,0,0)).proved(),"Deeper penetration is not escape");
        check(!proof(embedded,blocks,new Vec3(.05,0,0)).proved(),"Partial departure is not a completed egress");
        check(proof(List.of(panel("negative_side",.1)),blocks,new Vec3(-.5,0,0)).proved(),"Negative-axis departure must work");
        var newWall=new AABB(1.5,0,0,1.55,1,1);
        check(proof(embedded,List.of(block,newWall),new Vec3(1,0,0)).reason().equals("new_contact_in_sweep"),"Thin middle obstacle must block even when both endpoints clear it");
        check(!proof(List.of(panel("initial",.9),panel("later_same_block",-.2)),blocks,new Vec3(2,0,0)).proved(),"An old source block cannot exempt another triangle entering later");
        var spanning=new RescueTranslationEgressR53.Part("spanning_entry_face",new double[]{-.2,.2,.2,.8,.8,.2,.8,.2,.8});
        check(proof(List.of(spanning),blocks,new Vec3(2,0,0)).reason().equals("material_enters_before_exit"),"Endpoint separation alone does not prove monotone material departure");
        check(proof(embedded,blocks,new Vec3(.5,.5,0)).proved(),"Diagonal translation with no material entering any near face must be recoverable");
        check(!proof(List.of(spanning),blocks,new Vec3(2,.1,0)).proved(),"Diagonal path cannot admit more material through a swept entry face");
        check(!proof(embedded,List.of(block,newWall),new Vec3(1,.2,0)).proved(),"Diagonal path cannot skip a thin intermediate obstacle");
        check(proof(List.of(panel("clear",2)),blocks,new Vec3(.5,0,0)).reason().equals("strictly_clear"),"Ordinary clear path must remain usable");
        check(proof(List.of(panel("body",.9),panel("plug",2),panel("pilot",2.1)),blocks,new Vec3(.5,0,0)).proved(),"All supplied payload parts must remain checked");
        boolean invalid=false;try{proof(embedded,blocks,new Vec3(9,0,0));}catch(IllegalArgumentException expected){invalid=true;}check(invalid,"Finite escape travel bound must hold");
        invalid=false;try{proof(embedded,blocks,new Vec3(Double.NaN,0,0));}catch(IllegalArgumentException expected){invalid=true;}check(invalid,"Invalid translation must reject");
        System.out.println("Rescue bounded monotone translation candidate PASS "+checks+" (offline geometry only)");
    }
}
