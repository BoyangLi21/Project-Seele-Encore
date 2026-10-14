package com.projectseele.world;
import com.google.gson.JsonParser;
import java.nio.file.*;
/** Exact production Gson identity; no level, entity or installation access. */
public final class R52DirectoryFingerprint {
 public static void main(String[] args)throws Exception {
  var d=NervRouteDirectoryR52.parse(JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject());
  System.out.println("R52_DIRECTORY_FINGERPRINT="+d.fingerprint());
 }
}
