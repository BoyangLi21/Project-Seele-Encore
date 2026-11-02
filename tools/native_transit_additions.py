"""Exact-byte preservation checks for adding native services to a cold world."""
from pathlib import Path

KINDS={'rails','platforms','sidings','stations','routes','depots'}


def inventory(root):
    return {p.relative_to(root).as_posix():p.read_bytes()for p in root.rglob('*')if p.is_file()}


def assert_preserved(world,baseline,additions=()):
    root=world/'mtr';current=inventory(root);allowed=set(additions)
    if set(current)!=set(baseline)|allowed:raise ValueError('Native member set changed outside the declared additions')
    for name,content in baseline.items():
        if current[name]!=content:raise ValueError('Existing native member changed: '+name)


def prepare(candidate,world,names):
    baseline=inventory(candidate/'preserved-native')
    if not baseline:raise ValueError('New native services require a complete existing-member snapshot')
    assert_preserved(world,baseline)
    pairs=[];added=[]
    for name in names:
        relative=Path(name)
        if (relative.is_absolute()or'..'in relative.parts or len(relative.parts)!=6
                or relative.parts[:3]!=('mtr','projectseele','geofront')or relative.parts[3]not in KINDS):
            raise ValueError('Unexpected new native member destination')
        target=world/relative;source=candidate/'after'/relative
        if target.exists():raise ValueError('New native member already exists: '+name)
        if not source.is_file():raise ValueError('Missing prepared native member: '+name)
        if relative.as_posix()in added:raise ValueError('Duplicate new native member')
        added.append(relative.as_posix());pairs.append((target,source))
    return pairs,baseline,[Path(n).relative_to('mtr').as_posix()for n in added]
