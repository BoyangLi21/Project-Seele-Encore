package com.projectseele.entity;

/** Sachiel's strings (R64 M5): what it throws from where, and the tempo that leaves the Unit its turn. */
public final class SachielIntentR64Test
{
    private static void check(boolean condition,String message)
    {
        if(!condition)throw new AssertionError(message);
    }

    public static void main(String[] args)
    {
        int strings=0;
        for(boolean rage:new boolean[]{false,true})for(boolean low:new boolean[]{false,true})
            for(double range=8;range<=41;range+=1.5)for(int pick=0;pick<8;pick++)
            {
                int[] string=SachielIntentR64.string(range,low,rage,pick);strings++;
                String at="range "+range+" pick "+pick+(rage?" enraged":"")+(low?" low":"");
                check(string.length>=1&&string.length<=3,at+": one to three strikes");
                check(string.length<=(rage?3:2),at+": three strikes only when enraged");
                for(int mode:string)check(mode>=SachielStrike.JAB&&mode<=SachielStrike.STOMP,at+": a strike Sachiel has");
                // The first strike can be begun from where the string is chosen, or from a few steps in.
                check(SachielIntentR64.reach(string[0])>=SachielIntentR64.REACH_SHOVE,at+": reach");
                boolean stomp=false,crushing=false;
                for(int i=0;i<string.length;i++)
                {
                    stomp|=string[i]==SachielStrike.STOMP;
                    // The blow that fells a Unit ends a string: nothing is thrown at a Unit already on its way down.
                    if(string[i]==SachielStrike.OVERHEAD||string[i]==SachielStrike.STOMP)check(i==string.length-1,at+": the crushing strike is the last");
                    crushing|=string[i]==SachielStrike.OVERHEAD||string[i]==SachielStrike.STOMP;
                }
                check(!stomp||low&&range<SachielIntentR64.REACH_STOMP,at+": the stomp is for a Unit on the ground, in reach");
                check(!(low&&range<SachielIntentR64.REACH_STOMP)||stomp,at+": a Unit on the ground in reach is stamped on");
                if(!low&&range>SachielIntentR64.LANCE)check(string[0]==SachielStrike.PILE,at+": beyond the hands' reach the string opens with the lance");
                if(!low&&range<SachielIntentR64.CLOSE)check(string[0]!=SachielStrike.PILE&&string[0]!=SachielStrike.OVERHEAD,at+": close in, a string opens with a fast strike");
            }
        check(strings>500,"strings checked");
        // The breath is longer than any one strike, and shorter when enraged; a punish cannot follow a punish at once.
        check(SachielIntentR64.BREATH>27&&SachielIntentR64.BREATH_RAGE<SachielIntentR64.BREATH,"breath (a jab is 27 ticks long)");
        check(SachielIntentR64.PUNISH_EVERY>=SachielIntentR64.BREATH_RAGE,"punishes are spaced");
        check(SachielIntentR64.NEAR<SachielIntentR64.FAR&&SachielIntentR64.FAR<SachielIntentR64.ENGAGE&&SachielIntentR64.ENGAGE<SachielIntentR64.AWAY,"ranges in order");
        System.out.println("Sachiel intent strings: "+strings+" cases PASS");
    }

    private SachielIntentR64Test(){}
}
