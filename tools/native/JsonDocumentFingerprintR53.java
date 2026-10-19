import com.google.gson.JsonParser;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HexFormat;

/** Match the production directory parser, including Gson number spelling. */
public final class JsonDocumentFingerprintR53
{
    public static void main(String[] args) throws Exception
    {
        String canonical = JsonParser.parseString(Files.readString(Path.of(args[0]))).toString();
        System.out.println(HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256")
                .digest(canonical.getBytes(StandardCharsets.UTF_8))));
    }
}
