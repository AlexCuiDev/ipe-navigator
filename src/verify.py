"""确认 dist 内容"""
import os, zipfile, hashlib

DST = r'D:\.0WORK\GiteeCode\dne-code\IPE\tools\ipe-stats\dist\IPE-Navigator-v2.9'
ZIP = r'D:\.0WORK\GiteeCode\dne-code\IPE\tools\ipe-stats\dist\IPE-Navigator-v2.9.zip'

print('=== dist 内容 ===')
for root, _, files in os.walk(DST):
    for f in sorted(files):
        full = os.path.join(root, f)
        rel = os.path.relpath(full, DST)
        size = os.path.getsize(full)
        print(f'  {rel:50} {size:>10,} bytes')

print('\n=== ZIP 内容 ===')
with zipfile.ZipFile(ZIP, 'r') as z:
    for info in z.infolist():
        print(f'  {info.filename:55} {info.file_size:>10,} bytes  compressed={info.compress_size:,}')

print('\n=== ZIP SHA256 ===')
h = hashlib.sha256(open(ZIP, 'rb').read()).hexdigest()
print(f'  {h}')
