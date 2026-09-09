#!/usr/bin/env python3
import json, pathlib, shutil, sys

if len(sys.argv) != 2:
    raise SystemExit('usage: patch_generated.py <generated-project-dir>')
root = pathlib.Path(sys.argv[1]).resolve()
repo_root = pathlib.Path(__file__).resolve().parents[1]
source_ts = repo_root / 'spfx-packaging-naming' / 'PackagingNamingWebPart.ts'

webparts = list(root.glob('src/webparts/**/*WebPart.ts'))
if len(webparts) != 1:
    raise SystemExit(f'expected exactly one WebPart.ts, found {len(webparts)}: {webparts}')
shutil.copy2(source_ts, webparts[0])

manifests = list(root.glob('src/webparts/**/*.manifest.json'))
if len(manifests) != 1:
    raise SystemExit(f'expected exactly one webpart manifest, found {len(manifests)}')
manifest_path = manifests[0]
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
manifest['supportedHosts'] = ['SharePointWebPart', 'TeamsTab']
manifest['canUpdateConfiguration'] = False
for entry in manifest.get('preconfiguredEntries', []):
    entry['title'] = {'default': '신규 패키징 기술 Naming 공모'}
    entry['description'] = {'default': '이름 제안, 투표, 최종 결과를 Teams 안에서 진행합니다.'}
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')

pkg_path = root / 'config' / 'package-solution.json'
pkg = json.loads(pkg_path.read_text(encoding='utf-8'))
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
