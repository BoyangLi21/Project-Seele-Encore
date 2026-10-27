package com.projectseele.world;
public final class NervAssemblyClocksR52Test
{
 static
 {
  double quickPrevious=0;
  for(int age=0;age<=NervAssemblyClocksR52.QUICK_INSERTION_TICKS_R54;age++)
  {
   double progress=NervAssemblyClocksR52.insertionProgress(age,true);
   if(progress<quickPrevious||progress>1)throw new AssertionError("Retimed capsule overshot or reversed");
   if(age<=36&&progress!=0)throw new AssertionError("Capsule moved before the original crane grip");
   quickPrevious=progress;
  }
  if(quickPrevious!=1||NervAssemblyClocksR52.insertionProgress(NervAssemblyClocksR52.QUICK_HANDOFF_TICK_R54,true)
    !=NervAssemblyClocksR52.extractionProgress(NervAssemblyClocksR52.EXTRACT_HANDOFF_TICK))
   throw new AssertionError("Retimed insertion and original recovery lost their shared socket handoff");
  for(int age=0;age<=88;age++)
  {
   double visual=44-NervAssemblyClocksR52.liquidLayers(44,age);
   int remaining=44-NervAssemblyClocksR52.drainingLayers(44,age);
   if(remaining!=(int)Math.floor(visual))throw new AssertionError("A full physical layer masks the falling surface");
   if(visual>0&&visual+.93<=remaining+8D/9)throw new AssertionError("Continuous surface is beneath the native source-fluid top");
   if(NervAssemblyClocksR52.drainedLayers(44,age)!=age/2)throw new AssertionError("Refill cadence changed");
  }
  if(NervAssemblyClocksR52.liquidLayers(44,87)!=43.5F||NervAssemblyClocksR52.liquidLayers(44,88)!=44)
   throw new AssertionError("Drain duration changed from 88 ticks");
  double handoff=NervAssemblyClocksR52.CRANE_HANDOFF_PROGRESS;
  if(NervAssemblyClocksR52.insertionProgress(NervAssemblyClocksR52.INSERT_HANDOFF_TICK)!=handoff)
   throw new AssertionError("External crane must stop at the socket handoff");
  for(int age=NervAssemblyClocksR52.EXTRACT_HANDOFF_TICK;age<=NervAssemblyClocksR52.EXTRACT_GRIP_TICK;age++)
   if(NervAssemblyClocksR52.extractionProgress(age)!=handoff)
    throw new AssertionError("Capsule moved while the crane was approaching to grip");
  double previous=1;
  for(int age=0;age<=197;age++)
  {
   double progress=NervAssemblyClocksR52.extractionProgress(age);
   if(progress<0||progress>previous)throw new AssertionError("Extraction reversed or exceeded its physical endpoints");
   previous=progress;
  }
 }
 public static void main(String[] args){int checks=0;double previous=0;for(int age=0;age<=190;age++){double now=NervAssemblyClocksR52.insertionProgress(age);if(now<previous||now<0||now>1)throw new AssertionError("Original insertion clock reversal");previous=now;checks++;}if(NervAssemblyClocksR52.insertionProgress(36)!=0||NervAssemblyClocksR52.insertionProgress(190)!=1||NervAssemblyClocksR52.extractionProgress(36)!=1||NervAssemblyClocksR52.extractionProgress(141)!=0||NervAssemblyClocksR52.extractionProgress(197)!=0)throw new AssertionError("Original capsule timings changed");checks+=5;for(int age=0;age<=88;age++){if(NervAssemblyClocksR52.drainedLayers(44,age)!=age/2)throw new AssertionError("Physical LCL removed before its real two-tick step");checks++;}if(NervAssemblyClocksR52.bridgeRemaining(0)!=9||NervAssemblyClocksR52.bridgeRemaining(40)!=0)throw new AssertionError("Original nine bridge members changed");System.out.println("R52 original mechanical clocks PASS checks="+(checks+2));}
}
