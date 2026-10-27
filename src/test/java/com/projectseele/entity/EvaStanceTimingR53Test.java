package com.projectseele.entity;

public final class EvaStanceTimingR53Test
{
    public static void main(String[] args)
    {
        for(float start:new float[]{0,1,3})for(float target:new float[]{0,1,3})
        {
            float phase=start,velocity=0;
            int ticks=0;
            while((phase!=target||velocity!=0)&&ticks++<160)
            {
                var step=EvaStanceTimingR53.advance(phase,target,velocity);
                if(step.phase()<Math.min(start,target)||step.phase()>Math.max(start,target))
                    throw new AssertionError("Overshot stance endpoint");
                if(Math.abs(step.phase()-phase)>.08001F)throw new AssertionError("Unbounded phase step");
                if(Math.abs(step.velocity()-velocity)>.00601F)throw new AssertionError("Velocity snapped at normal endpoint");
                if(phase<=1&&Math.abs(step.phase()-phase)>.03501F)
                    throw new AssertionError("Fast knee-bend playback");
                phase=step.phase();velocity=step.velocity();
            }
            if(phase!=target||velocity!=0)throw new AssertionError("Stance never settled");
            System.out.println(start+" -> "+target+": "+ticks+" ticks");
        }
        // Releasing crouch while still accelerating down used to snap to
        // standing when the remaining distance was smaller than velocity.
        var reverse=EvaStanceTimingR53.advance(.01F,0,.035F);
        if(reverse.phase()<=.01F)throw new AssertionError("Reversal discarded existing velocity");
        float p=reverse.phase(),v=reverse.velocity();
        for(int tick=0;tick<160;tick++)
        {
            float target=tick<90?(tick%7<4?3:0):0;
            var next=EvaStanceTimingR53.advance(p,target,v);
            if(next.phase()<0||next.phase()>3||Math.abs(next.phase()-p)>.08001F)
                throw new AssertionError("Interrupted transition escaped bounds");
            p=next.phase();v=next.velocity();
        }
        if(p!=0||v!=0)throw new AssertionError("Interrupted stance did not settle");
        // Switching from prone to crouch while crossing phase 1 is an
        // interior target, not a physical boundary that can absorb momentum.
        for(float initial:new float[]{-.08F,.08F})
        {
            p=1;v=initial;
            var first=EvaStanceTimingR53.advance(p,1,v);
            if(Math.abs(first.velocity()-(initial-Math.copySign(.006F,initial)))>.00001F)
                throw new AssertionError("Exact intermediate target discarded momentum");
            for(int tick=0;tick<120;tick++)
            {
                var next=EvaStanceTimingR53.advance(p,1,v);
                if(Math.abs(next.velocity()-v)>.00601F)throw new AssertionError("Intermediate target snapped braking velocity");
                if(next.phase()<0||next.phase()>3)throw new AssertionError("Reversal escaped physical phase limits");
                p=next.phase();v=next.velocity();
            }
            if(p!=1||v!=0)throw new AssertionError("Crossed target did not settle");
        }
        for(float invalid:new float[]{Float.NaN,Float.NEGATIVE_INFINITY,Float.POSITIVE_INFINITY})
        {
            try{EvaStanceTimingR53.advance(invalid,1,0);throw new AssertionError("Invalid phase accepted");}
            catch(IllegalArgumentException expected){}
        }
        System.out.println("Stance clock endpoints, reversal and interruption PASS");
    }
}
