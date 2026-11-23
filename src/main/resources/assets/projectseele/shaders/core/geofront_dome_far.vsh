#version 150

// R65 GeoFront far view: the cavity silhouette in mesh-local block coordinates. Camera is the eye in the same frame.
in vec3 Position;
in vec4 Color;

uniform mat4 ModelViewMat;
uniform mat4 ProjMat;
uniform vec3 Camera;

out vec4 vertexColor;
out vec3 relative;

void main() {
    gl_Position = ProjMat * ModelViewMat * vec4(Position, 1.0);
    relative = Position - Camera;
    vertexColor = Color;
}
