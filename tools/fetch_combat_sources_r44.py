"""Fetch explicitly licensed author recordings into the private audition directory."""
from pathlib import Path
import hashlib, json, re, urllib.parse
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/rebuild_r44/audio/source_audition'
SOURCES = [
    ('metal_interactions.7z', 'qubodup', 'CC0-1.0',
     'https://opengameart.org/content/metal-interactions',
     'https://opengameart.org/sites/default/files/metal_interactions.7z'),
    ('monster_sfx_pack_2.zip', 'Ogrebane', 'CC0-1.0',
     'https://opengameart.org/content/monster-sound-effects-2',
     'https://opengameart.org/sites/default/files/monster_sfx_pack_2.zip'),
    ('Monster.wav', 'mikeask', 'CC0-1.0',
     'https://opengameart.org/content/monster-5',
     'https://opengameart.org/sites/default/files/Monster.wav'),
]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers['User-Agent'] = 'Project-SEEELE asset research/1.0'
    rows = []
    for name, author, license_id, page_url, url in SOURCES:
        page = session.get(page_url, timeout=60); page.raise_for_status()
        assert 'CC0' in page.text, 'Licence no longer present at author page'
        (OUT / (name + '.source.html')).write_text(page.text, 'utf8')
        path = OUT / name
        if not path.exists():
            data = session.get(url, timeout=60); data.raise_for_status()
            assert len(data.content) < 16_000_000
            path.write_bytes(data.content)
        rows.append(dict(file=name, author=author, license=license_id, source=page_url,
                         download=url, bytes=path.stat().st_size,
                         sha256=hashlib.sha256(path.read_bytes()).hexdigest(), selected=False))
    page_url = 'https://opengameart.org/content/screaming'
    page = session.get(page_url, timeout=60); page.raise_for_status()
    assert 'CC-BY 3.0' in page.text
    (OUT / 'Dan_Knoflicek.source.html').write_text(page.text, 'utf8')
    for encoded_url in re.findall(r'href="([^\"]+)"', page.text):
        url = urllib.parse.urljoin(page_url, encoded_url)
        name = urllib.parse.unquote(url.rsplit('/', 1)[-1])
        if not name.startswith('Scream ') or not name.endswith('.wav'): continue
        path = OUT / name
        if not path.exists():
            data = session.get(url, timeout=60); data.raise_for_status()
            assert len(data.content) < 8_000_000
            path.write_bytes(data.content)
        rows.append(dict(file=name, author='Dan Knoflicek', license='CC-BY-3.0',
                         attribution='SFX by Dan Knoflicek', source=page_url, download=url,
                         bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest(), selected=False))
    (OUT / 'manifest.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), 'utf8')
    print('Downloaded author recordings for audition:', len(rows), 'None installed', flush=True)


if __name__ == '__main__': main()
