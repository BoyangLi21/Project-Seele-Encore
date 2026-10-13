"""All actual consecutive native frames in the rise/approach/contact window, with no skipped frames."""
from pathlib import Path
import argparse, json
from PIL import Image, ImageDraw

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--run', type=Path, required=True)
args = parser.parse_args()
run = args.run.resolve()
manifest = json.loads((run/'frames/frames.json').read_text('utf8'))
receipt = dict(native_only=True, skipped_or_interpolated_frames=0, sequences=[])
for sequence in (0, 1):
    rows = [row for row in manifest['frames'] if row.get('review_sequence_r52',0)==sequence
            and row.get('active') and 12 <= row['scene_seconds'] <= 18.65]
    pages = []
    for offset in range(0, len(rows), 20):
        selected = rows[offset:offset+20]
        sheet = Image.new('RGB', (1600, ((len(selected)+3)//4)*250), '#131820')
        draw = ImageDraw.Draw(sheet)
        for index, row in enumerate(selected):
            with Image.open(run/'frames'/row['file']) as image:
                tile = image.convert('RGB')
                tile.thumbnail((400,225))
            x,y = index%4*400,index//4*250
            sheet.paste(tile,(x,y))
            draw.text((x+5,y+228), f"{row['file']} age {row['synced_age_ticks']} t {row['scene_seconds']:.3f}", fill='white')
            draw.text((x+5,y+239), f"actual capture {row['seconds']:.3f}s  {row['review_view_r52']}", fill='white')
        path=run/f'NATIVE_ACTION_CONTIGUOUS_{sequence}_{offset//20:02d}.jpg'
        sheet.save(path,quality=93)
        pages.append(dict(path=str(path),actual_frames=selected))
    receipt['sequences'].append(dict(sequence=sequence,actual_native_frames=len(rows),
        maximum_actual_capture_gap_seconds=max((b['seconds']-a['seconds'] for a,b in zip(rows,rows[1:])),default=0),pages=pages))
(run/'NATIVE_ACTION_CONTIGUOUS_RECEIPT.json').write_text(json.dumps(receipt,indent=2),'utf8')
print([(row['sequence'],row['actual_native_frames'],len(row['pages'])) for row in receipt['sequences']])
