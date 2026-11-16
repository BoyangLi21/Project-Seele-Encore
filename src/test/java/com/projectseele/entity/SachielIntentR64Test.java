package com.projectseele.entity;

/** Sachiel's strings (R64 M5): only what it does in the original, thrown from where it would throw it. */
public final class SachielIntentR64Test
{
    private static void check(boolean condition,String message)
    {
        if(!condition)throw new AssertionError(message);
    }

    public static void main(String[] args)
    {
        int strings=0;
        for(boolean low:new boolean[]{false,true})
            for(double range=8;range<=41;range+=1.5)for(int pick=0;pick<9;pick++)
            {
                int[] string=SachielIntentR64.string(range,low,pick);strings++;
                String at="range "+range+" pick "+pick+(low?" low":"");
                // Too near for the lance, a Unit on the ground is only looked at.
                if(string==null){check(low&&range<SachielIntentR64.LANCE_MIN,at+": no string only for a fallen Unit too near for the lance");continue;}
                for(int mode:string)if(mode==SachielStrike.PILE&&string[0]==SachielStrike.PILE)check(range>=SachielIntentR64.LANCE_MIN,at+": the lance is not begun nearer than it can land");
                check(string.length>=1&&string.length<=3,at+": one to three strikes");
                for(int i=0;i<string.length;i++)
                {
                    int mode=string[i];
                    // The lance, the palm, the downward blow. No jab, no hook, no stomp.
                    check(mode==SachielStrike.PILE||mode==SachielStrike.SHOVE||mode==SachielStrike.OVERHEAD,at+": a strike of Sachiel's own");
                    // The palm seizes: it opens a string and nothing leads into it. The downward blow fells: it is thrown alone.
                    if(mode==SachielStrike.SHOVE)check(i==0,at+": the palm opens a string");
                    if(mode==SachielStrike.OVERHEAD)check(string.length==1,at+": the downward blow is thrown alone");
                    // What follows the first strike is the lance.
                    if(i>0)check(mode==SachielStrike.PILE,at+": the lance follows");
                }
                check(SachielIntentR64.reach(string[0])>=SachielIntentR64.REACH_PALM,at+": reach");
                if(low)check(string.length==2&&string[0]==SachielStrike.PILE,at+": a Unit on the ground is given the lance twice");
                else if(range>SachielIntentR64.LANCE)check(string[0]==SachielStrike.PILE,at+": beyond the hands' reach it is the lance");
                else if(range<SachielIntentR64.CLOSE)check(string[0]!=SachielStrike.PILE,at+": close in, the palm or the downward blow comes first");
            }
        check(strings>300,"strings checked");
        // It regards for longer than its lance takes to land (30 ticks), longer still when it has been hurt; it
        // walks at one slow pace; seizures are spaced by more than a stare.
        check(SachielIntentR64.STARE>30&&SachielIntentR64.STARE_HURT>SachielIntentR64.STARE,"the stare");
        check(SachielIntentR64.SEIZE_EVERY>=SachielIntentR64.STARE,"seizures are spaced");
        check(SachielIntentR64.STARE_IDLE<SachielIntentR64.STARE&&SachielIntentR64.STARE_IDLE>18,"an idle Unit is regarded for less, and for longer than the old pause");
        check(SachielIntentR64.PACE>.3&&SachielIntentR64.PACE<.8,"one slow pace");
        check(SachielIntentR64.CLOSE<SachielIntentR64.LANCE&&SachielIntentR64.LANCE<SachielIntentR64.ENGAGE&&SachielIntentR64.ENGAGE<SachielIntentR64.REACH_LANCE,"ranges in order");
        System.out.println("Sachiel intent strings: "+strings+" cases PASS");
    }

    private SachielIntentR64Test(){}
}
