package com.projectseele.world;

import com.google.gson.GsonBuilder;
import java.io.DataOutputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.zip.GZIPOutputStream;

/** Export the current production head addon without recapturing unchanged bodies. */
public final class ExportCurrentHeadTemplatesR53
{
    public static void main(String[] args) throws Exception
    {
        Path output = Path.of(args[0]);
        Files.createDirectories(output);
        var templates = NervOuterCarrierGuideR52.templates();
        var rows = new ArrayList<Object>();
        try (var data = new DataOutputStream(new GZIPOutputStream(Files.newOutputStream(
                output.resolve("ACTUAL_CURRENT_HEAD_TEMPLATES.bin.gz")))))
        {
            data.writeInt(templates.size());
            for (var part : templates)
            {
                double[] xyz = part.mesh().triangles();
                data.writeUTF(part.name());
                data.writeUTF(part.role());
                data.writeInt(xyz.length);
                for (double value : xyz) data.writeDouble(value);
                rows.add(Map.of("name", part.name(), "role", part.role(), "frame", part.frame(),
                        "triangles", xyz.length / 9, "local_bounds", part.mesh().bounds()));
            }
        }
        var mounts = new LinkedHashMap<String, Object>();
        for (int side : new int[]{-1, 1})
        {
            var point = NervOuterCarrierGuideR52.ballLocal(side);
            mounts.put(Integer.toString(side), new double[]{-point.x, point.y, -point.z});
        }
        var receipt = Map.of("world_written", false, "head_source_sha256", NervBankHeadTransferR53.SOURCE_SHA,
                "model_source_sha256", NervOuterCarrierGuideR52.SOURCE_SHA,
                "world_yaw180_mounts", mounts, "head_templates", rows);
        Files.writeString(output.resolve("CURRENT_PRODUCTION_HEAD_EXPORT.json"),
                new GsonBuilder().setPrettyPrinting().create().toJson(receipt));
        System.out.println("Current production templates exported: " + templates.size());
    }
}
