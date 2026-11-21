import java.util.*;

/** Pure decision logic for independently observed frames; never queries a game. */
public final class R52TerrainReadinessDecision {
    private final int minimumFrames, stableSamples;
    private long arrivalFrame = -1, lastFrame = -1, lastClient = -1, lastServer = -1;
    private int stable;
    public R52TerrainReadinessDecision(int minimumFrames, int stableSamples) {
        if (minimumFrames < 100 || minimumFrames > 1200 || stableSamples < 3 || stableSamples > 30)
            throw new IllegalArgumentException("Bounded real frame warmup and stable samples required");
        this.minimumFrames = minimumFrames; this.stableSamples = stableSamples;
    }
    public Map<String,Object> observe(boolean camera, boolean unpaused, boolean terrain,
                                      long frame, long client, long server) {
        boolean newFrame = frame >= 0 && frame != lastFrame;
        boolean clocksAdvance = client > lastClient && server > lastServer && lastClient >= 0 && lastServer >= 0;
        if (!camera) { arrivalFrame = -1; stable = 0; }
        else if (arrivalFrame < 0 || frame < arrivalFrame) { arrivalFrame = frame; stable = 0; }
        long rendered = arrivalFrame < 0 ? 0 : Math.max(0, frame - arrivalFrame);
        boolean current = camera && unpaused && terrain && rendered >= minimumFrames && clocksAdvance;
        if (newFrame) stable = current ? stable + 1 : 0;
        else if (!camera || !unpaused || !terrain) stable = 0;
        var result = new LinkedHashMap<String,Object>();
        result.put("new_render_frame", newFrame); result.put("client_and_server_clocks_advance", clocksAdvance);
        result.put("rendered_frames_after_actual_camera_arrival", rendered);
        result.put("stable_observed_frames", stable); result.put("required_stable_frames", stableSamples);
        result.put("ready", current && newFrame && stable >= stableSamples);
        lastFrame = frame; lastClient = client; lastServer = server;
        return result;
    }
}
