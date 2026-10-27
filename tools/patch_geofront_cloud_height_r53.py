"""Raise GeoFront surface clouds above tall bases and aircraft routes."""
import argparse
from pathlib import Path
import zipfile

OLD = "    const int cloudAlt1i = int(CLOUD_ALT1); // Old setting files can send float values\n    const int cloudAlt2i = int(CLOUD_ALT2);"
NEW = """    // GeoFront includes tall surface bases and aircraft above vanilla cloud height.
    #ifdef SEELE_GEOFRONT
        const int cloudAlt1i = max(int(CLOUD_ALT1), 448);
        const int cloudAlt2i = max(int(CLOUD_ALT2), cloudAlt1i + 128);
    #else
        const int cloudAlt1i = int(CLOUD_ALT1);
        const int cloudAlt2i = int(CLOUD_ALT2);
    #endif"""

def patch(source, output):
    if source.resolve() == output.resolve():
        raise ValueError("Write a separate candidate; active shader ZIPs may be locked")
    with zipfile.ZipFile(source) as old, zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as new:
        for info in old.infolist():
            data=old.read(info)
            if info.filename == 'shaders/lib/common.glsl':
                text=data.decode('utf-8').replace('\r\n', '\n')
                if OLD not in text and NEW not in text:
                    raise ValueError("Expected cloud altitude declarations are absent")
                data=text.replace(OLD, NEW).encode('utf-8')
            new.writestr(info,data)

if __name__ == '__main__':
    parser=argparse.ArgumentParser(__doc__)
    parser.add_argument('source',type=Path); parser.add_argument('output',type=Path)
    args=parser.parse_args(); patch(args.source,args.output)
