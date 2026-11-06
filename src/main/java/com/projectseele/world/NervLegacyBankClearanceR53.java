package com.projectseele.world;

import com.google.gson.*;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.*;

/** Original bank edge returns; drawing and collision consume these same facets. */
public final class NervLegacyBankClearanceR53
{
    public static final String SOURCE="mesh/legacy_bank_curb_clearance_r53.json";

    static void apply(JsonObject running) throws IOException
    {
        byte[] bytes=EvaOriginalMeshGeometryR52.classpathBytes(SOURCE);
        var overlay=JsonParser.parseString(new String(bytes,StandardCharsets.UTF_8)).getAsJsonObject();
        require(overlay.get("schema").getAsString().equals("projectseele.r53.original-bank-curb-return.v1"),
            "Explicit original-bank edge return required");
        var expected=Set.of("legacy_original_retained","level_actual/0/compact_96m",
            "level_actual/1/compact_96m","level_actual/2/compact_96m");
        var seen=new HashSet<String>();
        for (var raw:overlay.getAsJsonArray("targets"))
        {
            var row=raw.getAsJsonObject();String name=row.get("part").getAsString();
            require(expected.contains(name)&&seen.add(name),"Only four declared non-bearing edge sources may change");
            var source=running.getAsJsonObject("parts").getAsJsonArray(name);
            require(source!=null&&source.size()%18==0,
                "Exact post-service original source topology required");
            var removed=new HashSet<Integer>();int previous=-1;
            for (var entry:row.getAsJsonArray("removed"))
            {
                var item=entry.getAsJsonObject();int index=item.get("index").getAsInt();
                require(index>previous&&index<source.size()/18,
                    "Ordered complete original edge facets required");
                previous=index;removed.add(index);
            }
            var replacement=row.getAsJsonArray("replacement_rgb");
            require(!removed.isEmpty()&&!replacement.isEmpty()&&replacement.size()%18==0,
                "Complete continuous replacement edge facets required");
            for (var number:replacement) require(Double.isFinite(number.getAsDouble()),"Finite replacement source required");
            var result=new JsonArray();
            for (int n=0;n<source.size();n++) if(!removed.contains(n/18))result.add(source.get(n));
            result.addAll(replacement);running.getAsJsonObject("parts").add(name,result);
        }
        require(seen.equals(expected),"All three bank edge pairs must use the same declared refit");
    }

    private static void require(boolean okay,String why)
    { if(!okay)throw new IllegalStateException(why); }
    private NervLegacyBankClearanceR53() {}
}
