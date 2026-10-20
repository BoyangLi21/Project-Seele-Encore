package com.projectseele.entity;

/** Packet tails from the native moving trace must not become frozen render frames. */
public final class EvaGaitPacketTailR53Test
{
    private static void close(float actual,float expected)
    {
        if(Math.abs(actual-expected)>1e-6F)
            throw new AssertionError(actual+" != "+expected);
    }

    public static void main(String[] args)
    {
        close(EvaGaitPacketTailR53.sample(.98F,.02F,1,1,1,.5),.04F);
        close(EvaGaitPacketTailR53.sample(.02F,.98F,1,1,1,.5),.96F);
        close(EvaGaitPacketTailR53.sample(.2F,.24F,1,1,1,20),.28F);
        close(EvaGaitPacketTailR53.sample(.24F,.24F,1,1,1,.5),.24F);
        close(EvaGaitPacketTailR53.sample(.2F,.24F,1,.84F,1,.5),.24F);
        close(EvaGaitPacketTailR53.sample(.2F,.24F,0,0,1,.5),.24F);
        close(EvaGaitPacketTailR53.sample(.2F,.8F,1,1,1,.5),.8F);
        close(EvaGaitPacketTailR53.sample(.2F,.24F,1,1,0,.5),.24F);
        close(EvaGaitPacketTailR53.sample(.2F,.24F,1,1,4,.5),.24F);
        close(EvaGaitPacketTailR53.sample(.2F,.24F,1,1,1,Double.NaN),.24F);
        close(EvaGaitPacketTailR53.sample(.2F,.24F,1,1,2,.5),.25F);
        // The next regular packet joins the one-tick tail without a jump.
        float endpoint=EvaGaitPacketTailR53.sample(.2F,.24F,1,1,1,1);
        close(endpoint,.28F);
        close(EvaGaitPacketTailR53.sample(.24F,.28F,1,1,1,0),endpoint);
        float prior=.24F;
        for(int i=1;i<=12;i++)
        {
            float current=EvaGaitPacketTailR53.sample(.2F,.24F,1,1,1,i/12D);
            if(current<=prior)throw new AssertionError("Moving sub-tick pose froze");
            prior=current;
        }
        // Native 22:16 trace: a one-tick travel gap followed a predicted tail.
        var cursor=new EvaGaitPacketTailR53.Cursor();
        close(cursor.accept(.898292F,.82868F,.8715185F,1,50),.898292F);
        close(cursor.accept(.8715185F,.8715185F,.8715185F,1,51),.898292F);
        close(cursor.accept(.902F,.8715185F,.900F,1,52),.902F);
        close(cursor.accept(.91F,.900F,.93F,1,53),.91F);
        // Deliberate reverse travel and an idle reset must still be admitted.
        close(cursor.accept(.89F,.93F,.89F,1,54),.89F);
        close(cursor.accept(.87F,.89F,.87F,1,55),.87F);
        close(cursor.accept(.9F,.9F,.9F,0,56),.9F);
        close(cursor.accept(.1F,.09F,.1F,1,80),.1F);
        System.out.println("Gait packet tail: wrap/reverse, stop/reset, silence limit and continuous arrival PASS");
    }
}
