package com.projectseele.entity;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * R64 (M4): the blows of the frames core, one row each.
 * <p>
 * A row is everything the machine needs to play a blow: how many ticks it winds up, is live and recovers; which
 * part of its clip the live ticks cover; what it strikes with; how hard it lands and how long both bodies are held
 * on it; how far the body may turn onto its target while it winds up; when it may be left for another blow, an
 * evade or a step; and what a light or a heavy press goes to from it. Ticks are at synchronisation 1; the machine
 * shortens them by the pilot's attack speed.
 * <p>
 * The clips, the limbs they strike with and the damage are the old core's: only the timing and what follows what
 * are new. Damage and cooldowns keep their R63 values (the owner's decision); every tick count here is new and is
 * listed against the old one in the hand-in.
 */
public final class EvaMoveTableR64
{
    /** What drives the body through the blow: a punch clip by its stage, the two-handed slam, the side kick, a knife clip. */
    public static final int PUNCH=0,SLAM=1,KICK=2,KNIFE=3;
    /** How hard it lands: a flinch, a stagger caught in two steps, a knock-back caught in four, a fall. */
    public static final int LIGHT=0,MEDIUM=1,HEAVY=2,FINISHER=3;

    /**
     * @param stage       PUNCH: 0 jab, 1 cross, 2 hook. KNIFE: 0 the thrust in the forward grip, 1 the reverse grip,
     *                    2 the cut, 3 the cut back (EvaGameplayMotionR32.knifeClip).
     * @param startup     ticks before the blow can land
     * @param active      ticks it can land in (the limb's swept capsule is tested on each until it lands)
     * @param recovery    ticks after that
     * @param lead        clip phase before the clip's contact that the live ticks begin at
     * @param tail        clip phase after it that they end at
     * @param damage      before the Unit's multiplier
     * @param radius      of the swept capsule, blocks
     * @param knock       vanilla knock-back handed to the struck body
     * @param level       LIGHT, MEDIUM, HEAVY, FINISHER
     * @param stop        ticks both bodies are held when it lands (hit-stop "tiered")
     * @param push        how far the pilot's view is pushed in when it lands, a fraction of the field of view
     * @param track       degrees a tick the body turns onto its target while it winds up
     * @param feint       a step back in its first ticks, up to this one, withdraws it (0: never)
     * @param cancelHit   first tick a buffered blow may take its place once it has landed (-1: never)
     * @param cancelWhiff the same when it has not landed
     * @param evadeHit    first tick an evade or a jump may take its place once it has landed
     * @param evadeWhiff  the same when it has not landed
     * @param moveFrom    first tick a step back or aside ends it
     * @param armorFrom   from this tick to armorTo a blow that would stagger the Unit only makes it flinch (-1: never)
     * @param cooldown    ticks from its start before it may start again
     * @param slow        an Angel has time to answer it (what Sachiel reads)
     * @param light       the row a light press goes to from it, or null
     * @param heavy       the row a heavy press goes to from it, or null
     */
    public record Row(String name,int kind,int stage,int startup,int active,int recovery,float lead,float tail,
            float damage,float radius,double knock,int level,int stop,float push,float track,int feint,
            int cancelHit,int cancelWhiff,int evadeHit,int evadeWhiff,int moveFrom,int armorFrom,int armorTo,
            int cooldown,boolean slow,String light,String heavy)
    {
        public int total(){return startup+active+recovery;}
    }

    private static final Map<String,Row> ROWS=new LinkedHashMap<>();
    private static void row(Row r){ROWS.put(r.name(),r);}
    static
    {
        // Bare hands. The string is jab, cross, a second and harder jab, slam on the light press; the heavy press is
        // the side kick, from standing or out of any of the first three. The slam and the kick end a string.
        // (The bundle's hook clip was tried as the third blow and left out: it is an older, upright clip, and between
        // the cross and the slam the body stood up for it, knees from 40 degrees to 11, and sank again.)
        //      name     kind  st  su ac rec  lead   tail   dmg  rad  knock level    stop push   track feint cH  cW  eH  eW  move armor    cd  slow   light    heavy
        row(new Row("jab",   PUNCH,0,  3, 3, 11, .066F,.093F, 20, 3.2F,1.1, LIGHT,   2,  .012F, 9,    2,    7,  10, 6,  8,  10,  2,9,    0,  false, "cross", "kick"));
        row(new Row("cross", PUNCH,1,  4, 3, 12, .091F,.047F, 20, 3.2F,1.1, LIGHT,   3,  .014F, 8,    2,    8,  12, 7,  10, 12,  3,10,   0,  false, "jab2",  "kick"));
        row(new Row("jab2",  PUNCH,0,  4, 3, 10, .066F,.093F, 20, 3.2F,1.1, MEDIUM,  4,  .018F, 7,    2,    8,  12, 7,  10, 12,  3,10,   0,  false, "slam",  "kick"));
        row(new Row("slam",  SLAM, 0,  9, 4, 25, .030F,.055F, 35, 4F,  2.0, FINISHER,8,  .030F, 5,    4,    -1, -1, 18, 22, 24,  5,13,   0,  true,  null,    null));
        row(new Row("kick",  KICK, 0,  7, 4, 7,  .078F,.142F, 50, 4F,  2.4, HEAVY,   5,  .022F, 6,    3,    -1, -1, 12, 14, 15,  -1,-1,  44, true,  null,    null));
        // The knife. Up to R63 and in the first frames core the light press was the thrust (wound up from behind
        // the hip, driven in and held: 44 ticks) and the heavy press the reverse grip. The owner after his second
        // play (2026-11-16): what the light press does belongs on the heavy one, and the light press is to be an
        // ordinary knife attack. So: the light press is the cut and, out of it, the cut back (tools/finale/slash.py);
        // the heavy press is the thrust and, out of it late in its recovery, the reverse grip as before. A heavy
        // press out of either cut is the thrust. The two cuts make 55 points in 29 ticks, 38 a second, where the
        // thrust and the reverse grip make 39 and the thrust alone 27: no more than the knife had.
        // A light press within twelve ticks of an evade is the counter: the thrust with half its wind-up.
        //      name          kind  st  su ac rec  lead   tail   dmg  rad  knock level    stop push   track feint cH  cW  eH  eW  move armor    cd  slow   light         heavy
        row(new Row("knife_cut",    KNIFE,2, 5, 3, 10, .100F,.100F, 25, 3.2F,0.8, LIGHT,  2, .012F, 8,  2, 10, 13, 8,  10, 12, -1,-1, 0,  false, "knife_back","knife_slash"));
        row(new Row("knife_back",   KNIFE,3, 5, 3, 11, .100F,.100F, 30, 3.2F,1.0, MEDIUM, 3, .016F, 7,  2, 11, 14, 8,  11, 13, -1,-1, 0,  false, null,"knife_slash"));
        row(new Row("knife_slash",  KNIFE,0, 11,3, 30, .035F,.025F, 60, 3.2F,1.1, MEDIUM, 4, .018F, 6,  4, 28, 34, 15, 18, 26, -1,-1, 0,  false, null,"knife_reverse"));
        row(new Row("knife_reverse",KNIFE,1, 6, 3, 24, .030F,.051F, 80, 4F,  2.0, HEAVY,  6, .022F, 6,  3, -1, -1, 12, 15, 22, -1,-1, 53, false, null,null));
        row(new Row("knife_counter",KNIFE,0, 6, 3, 26, .035F,.025F, 60, 3.2F,1.1, MEDIUM, 5, .020F, 12, 0, 22, 28, 12, 16, 24, -1,-1, 0,  false, null,"knife_reverse"));
    }

    /**
     * Where in its clip a row is after this many ticks: the wind-up runs to the opening of the live part of the
     * clip, the live ticks across it, the recovery to the clip's end.
     */
    public static float phase(int elapsed,int startup,int active,int recovery,float open,float close)
    {
        if(elapsed<=0)return 0;
        if(elapsed<=startup)return open*elapsed/startup;
        if(elapsed<=startup+active)return open+(close-open)*(elapsed-startup)/active;
        return Math.min(1F,close+(1-close)*(elapsed-startup-active)/Math.max(1,recovery));
    }

    public static Row get(String name){return name==null?null:ROWS.get(name);}
    public static Iterable<Row> rows(){return ROWS.values();}

    /**
     * The row a press begins with nothing in hand to follow.
     * @param cuts the Unit has the knife's cuts (EvaGameplayMotionR32.knifeCutsReadyR64); without them the knife is
     *             as it was, the thrust on the light press and the reverse grip on the heavy
     */
    public static Row opener(int weapon,boolean heavy,boolean afterEvade,boolean cuts)
    {
        if(weapon==EvaUnit01Entity.WEAPON_KNIFE)
            return get(cuts?heavy?"knife_slash":afterEvade?"knife_counter":"knife_cut":heavy?"knife_reverse":afterEvade?"knife_counter":"knife_slash");
        return get(heavy?"kick":"jab");
    }

    private EvaMoveTableR64(){}
}
