"""Bounded diagnostic export; prefer JfrSummaryR45.java for large recordings.

JDK JSON recursively expands recorded type graphs. Even gzip can exceed the
original recording by orders of magnitude; this exporter has a hard bound.
"""
from pathlib import Path
import argparse,gzip,hashlib,json,subprocess,time

p=argparse.ArgumentParser();p.add_argument('--jfr',type=Path,required=True)
p.add_argument('--input',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();assert a.jfr.is_file()and a.input.is_file()and not a.out.exists()
assert a.out.suffixes[-2:]==['.json','.gz'];a.out.parent.mkdir(parents=True,exist_ok=True)
command=[str(a.jfr),'print','--json','--events','jdk.ExecutionSample,jdk.NativeMethodSample,jdk.GCPhasePause',
         '--stack-depth','24',str(a.input.resolve())]
start=time.monotonic();size=0
with a.out.with_suffix('.stderr.txt').open('wb')as error,gzip.open(a.out,'wb',compresslevel=3)as sink:
    process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=error)
    for block in iter(lambda:process.stdout.read(65536),b''):
        sink.write(block);size+=len(block)
        if size>64*1024*1024:
            process.terminate();process.wait()
            raise RuntimeError('Expanded JFR JSON exceeds 64MiB; partial export is invalid. Use JfrSummaryR45.java.')
    status=process.wait()
receipt=dict(input=str(a.input.resolve()),input_sha256=hashlib.sha256(a.input.read_bytes()).hexdigest(),
    command=command,exit_code=status,json_bytes=size,gzip_bytes=a.out.stat().st_size,seconds=time.monotonic()-start,
    scope='Read-only events from original JVM flight recording; analysis still required')
a.out.with_suffix('.receipt.json').write_text(json.dumps(receipt,indent=2),'utf8')
assert status==0,'JFR export failed; preserve stderr and partial output'
print(json.dumps(receipt))
