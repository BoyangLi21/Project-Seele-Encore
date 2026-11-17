# Cockpit preview and review tools (R64 first person)

The pilot's first-person cockpit (the seat's front, the two yokes, the hands, the LCL) is built in
`src/main/java/com/projectseele/client/cockpit/CockpitMeshR64.java` from boxes, with no game classes.
Two tools use that:

## `tools/cockpit_preview/CockpitPreview.java`: pictures without the game

Draws the same vertices the game draws, with a small software rasteriser, over a plain picture of a city under a
sky. A change to the layout can be looked at in a few seconds.

```
JOML=<a joml-1.10.5.jar, e.g. from the Minecraft libraries folder>
javac -encoding UTF-8 -cp "$JOML" -d out src/main/java/com/projectseele/client/cockpit/CockpitMeshR64.java tools/cockpit_preview/CockpitPreview.java
java -cp "out;$JOML" CockpitPreview <output folder>
```

It writes one PNG for each line of the `shots` table in `main` (level view, yokes pushed, a blow, looking down
and up, the other units' colours, the dark plug, and the LCL at five heights).

## `tools/cockpit_review/view_metrics.py`: how much the view moves

The game writes `view.csv` (one row per drawn frame: the camera, the head's optical point, the unit, the view's
angles) when it is started with `-Dprojectseele.cockpitReviewR64=true` in a disposable review save
(`PilotCockpitReviewR64`). The script prints, for the walk, the run, the blows, the jump and the look round, the
eye's bob, its speed, and the view's pitch and roll. Run the same drive with `-Dprojectseele.cockpitR64=false`
for the view as it was up to R63.

```
python tools/cockpit_review/view_metrics.py <before>/view.csv <after>/view.csv
```
