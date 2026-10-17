"""Replace selected archive entries without recompressing unrelated assets."""
from pathlib import Path
import copy, os, zipfile


def replace_entries(path, changes, remove=()):
    path=Path(path);temporary=path.with_suffix(path.suffix+'.entry-update')
    with zipfile.ZipFile(path) as original, zipfile.ZipFile(temporary,'w') as target:
        entries=sorted(original.infolist(),key=lambda item:item.header_offset)
        assert len({i.filename for i in entries})==len(entries),'Ambiguous duplicate archive entries'
        for index,info in enumerate(entries):
            if info.filename in remove:continue
            if info.filename in changes:
                target.writestr(copy.copy(info),changes[info.filename],compresslevel=1)
                continue
            end=entries[index+1].header_offset if index+1<len(entries) else original.start_dir
            original.fp.seek(info.header_offset);offset=target.fp.tell();left=end-info.header_offset
            while left:
                chunk=original.fp.read(min(left,1024*1024))
                if not chunk:raise EOFError(info.filename)
                target.fp.write(chunk);left-=len(chunk)
            retained=copy.copy(info);retained.header_offset=offset
            target.filelist.append(retained);target.NameToInfo[retained.filename]=retained
            target.start_dir=target.fp.tell();target._didModify=True
        for name,raw in changes.items():
            if name not in original.NameToInfo:target.writestr(name,raw,compress_type=zipfile.ZIP_DEFLATED,compresslevel=1)
        target.comment=original.comment
    with zipfile.ZipFile(temporary) as back:
        assert all(back.read(name)==raw for name,raw in changes.items()),'Changed archive entry readback differs'
        assert set(back.namelist())==(set(original.NameToInfo)-set(remove))|set(changes)
    os.replace(temporary,path)


if __name__=='__main__':
    import argparse,json
    parser=argparse.ArgumentParser();parser.add_argument('archive',type=Path);parser.add_argument('entries',type=Path)
    args=parser.parse_args();entries=json.loads(args.entries.read_text('utf8'))
    replace_entries(args.archive,{name:Path(source).read_bytes() for name,source in entries.items()})
    print('Archive entries updated and read back:',len(entries))
