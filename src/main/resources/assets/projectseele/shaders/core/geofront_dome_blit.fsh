#version 150

// The far view's resolved target laid over the picture: premultiplied colour (the background was transparent black),
// blended ONE, ONE_MINUS_SRC_ALPHA, so the anti-aliased edges fade into the sky behind them.
uniform sampler2D Sampler0;

in vec2 texCoord;

out vec4 fragColor;

void main() {
    vec4 color = texture(Sampler0, texCoord);
    if (color.a <= 0.0) {
        discard;
    }
    fragColor = color;
}
