import org.mtr.core.data.TransportMode;

/** The finite station envelope assumes the installed cable cabin stays upright. */
public class InspectCableMode {
    public static void main(String[] args) {
        var mode = TransportMode.CABLE_CAR;
        if (mode.hasPitchAscending || mode.hasPitchDescending)
            throw new IllegalStateException("Envelope requires upright cable cabin");
        System.out.println("Installed native cable mode retains upright cabin geometry");
    }
}
