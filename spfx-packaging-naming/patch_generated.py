#!/usr/bin/env python3
import json, pathlib, re, shutil, sys

if len(sys.argv) != 2:
    raise SystemExit('usage: patch_generated.py <generated-project-dir>')
root = pathlib.Path(sys.argv[1]).resolve()
repo_root = pathlib.Path(__file__).resolve().parents[1]
source_ts = repo_root / 'spfx-packaging-naming' / 'PackagingNamingWebPart.ts'

def strip_jsonc(text: str) -> str:
    out = []
    i = 0
    in_string = False
    escape = False
    while i < len(text):
        ch = text[i]
        if in_string:
            out.append(ch)
            if escape:
                escape = False
            elif ch == '\\':
                escape = True
            elif ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue
        if ch == '/' and i + 1 < len(text) and text[i + 1] == '/':
            i += 2
            while i < len(text) and text[i] not in '\r\n':
                i += 1
            continue
        if ch == '/' and i + 1 < len(text) and text[i + 1] == '*':
            i += 2
            while i + 1 < len(text) and not (text[i] == '*' and text[i + 1] == '/'):
                i += 1
            i += 2
            continue
        out.append(ch)
        i += 1
    return re.sub(r',\s*([}\]])', r'\1', ''.join(out))

def load_jsonc(path: pathlib.Path):
    return json.loads(strip_jsonc(path.read_text(encoding='utf-8')))

webparts = list(root.glob('src/webparts/**/*WebPart.ts'))
if len(webparts) != 1:
    raise SystemExit(f'expected exactly one WebPart.ts, found {len(webparts)}: {webparts}')
shutil.copy2(source_ts, webparts[0])

manifests = list(root.glob('src/webparts/**/*.manifest.json'))
if len(manifests) != 1:
    raise SystemExit(f'expected exactly one webpart manifest, found {len(manifests)}')
manifest_path = manifests[0]
manifest = load_jsonc(manifest_path)
manifest['supportedHosts'] = ['SharePointWebPart', 'TeamsTab']
manifest['canUpdateConfiguration'] = False
for entry in manifest.get('preconfiguredEntries', []):
    entry['title'] = {'default': '신규 패키징 기술 Naming 공모'}
    entry['description'] = {'default': '이름 제안, 투표, 최종 결과를 Teams 안에서 진행합니다.'}
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')

pkg_path = root / 'config' / 'package-solution.json'
pkg = load_jsonc(pkg_path)
sol = pkg.setdefault('solution', {})
sol['name'] = 'packaging-naming-client-side-solution'
sol['version'] = '1.0.0.0'
sol['includeClientSideAssets'] = True
sol['skipFeatureDeployment'] = True
sol['isDomainIsolated'] = False
pkg.setdefault('paths', {})['zippedPackage'] = 'solution/packaging-naming.sppkg'
pkg_path.write_text(json.dumps(pkg, ensure_ascii=False, indent=2), encoding='utf-8')

print('patched webpart:', webparts[0])
print('patched manifest:', manifest_path)
print('patched package:', pkg_path)
