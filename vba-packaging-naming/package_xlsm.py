#!/usr/bin/env python3
from pathlib import Path
import hashlib, shutil, tempfile, zipfile
import xml.etree.ElementTree as ET

BASE = Path('base.xlsx')
VBA = Path('vbaProject.patched.bin')
OUT = Path('Packaging_Naming_VBA.xlsm')

CT_NS='http://schemas.openxmlformats.org/package/2006/content-types'
REL_NS='http://schemas.openxmlformats.org/package/2006/relationships'
SS_NS='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
ET.register_namespace('', CT_NS)
ET.register_namespace('', REL_NS)
ET.register_namespace('', SS_NS)

with tempfile.TemporaryDirectory() as td:
    root=Path(td)
    with zipfile.ZipFile(BASE,'r') as z:
        z.extractall(root)

    shutil.copy2(VBA, root/'xl'/'vbaProject.bin')

    # Macro-enabled content types. artifact_tool may declare workbook.xml only
    # through the generic XML Default, so add an explicit workbook Override.
    p=root/'[Content_Types].xml'
    tree=ET.parse(p); doc=tree.getroot()
    workbook_override=None
    for o in doc.findall(f'{{{CT_NS}}}Override'):
        if o.get('PartName')=='/xl/workbook.xml':
            workbook_override=o
            break
    if workbook_override is None:
        workbook_override=ET.SubElement(doc, f'{{{CT_NS}}}Override', {
            'PartName':'/xl/workbook.xml',
            'ContentType':'application/vnd.ms-excel.sheet.macroEnabled.main+xml'
        })
    else:
        workbook_override.set('ContentType','application/vnd.ms-excel.sheet.macroEnabled.main+xml')
    if not any(o.get('PartName')=='/xl/vbaProject.bin' for o in doc.findall(f'{{{CT_NS}}}Override')):
        ET.SubElement(doc, f'{{{CT_NS}}}Override', {
            'PartName':'/xl/vbaProject.bin',
            'ContentType':'application/vnd.ms-office.vbaProject'
        })
    tree.write(p,encoding='utf-8',xml_declaration=True)

    # Workbook relationship to VBA binary.
    p=root/'xl'/'_rels'/'workbook.xml.rels'
    tree=ET.parse(p); doc=tree.getroot()
    if not any(r.get('Type','').endswith('/vbaProject') for r in doc.findall(f'{{{REL_NS}}}Relationship')):
        used=[]
        for r in doc.findall(f'{{{REL_NS}}}Relationship'):
            rid=r.get('Id','')
            if rid.startswith('rId') and rid[3:].isdigit(): used.append(int(rid[3:]))
        rid=f'rId{max(used or [0])+1}'
        ET.SubElement(doc, f'{{{REL_NS}}}Relationship', {
            'Id':rid,
            'Type':'http://schemas.microsoft.com/office/2006/relationships/vbaProject',
            'Target':'vbaProject.bin'
        })
    tree.write(p,encoding='utf-8',xml_declaration=True)

    # Workbook codename + VeryHidden internal sheets.
    p=root/'xl'/'workbook.xml'
    tree=ET.parse(p); doc=tree.getroot()
    wp=doc.find(f'{{{SS_NS}}}workbookPr')
    if wp is None:
        wp=ET.Element(f'{{{SS_NS}}}workbookPr')
        doc.insert(0,wp)
    wp.set('codeName','ThisWorkbook')
    sheets=doc.find(f'{{{SS_NS}}}sheets')
    if sheets is not None:
        for idx,s in enumerate(list(sheets)):
            if idx==0:
                if 'state' in s.attrib: del s.attrib['state']
            else:
                s.set('state','veryHidden')
    tree.write(p,encoding='utf-8',xml_declaration=True)

    # Give every worksheet a stable VBA codename, like Excel/XlsxWriter do.
    wsdir=root/'xl'/'worksheets'
    for idx in range(1,6):
        sp=wsdir/f'sheet{idx}.xml'
        if not sp.exists(): continue
        st=ET.parse(sp); sd=st.getroot()
        pr=sd.find(f'{{{SS_NS}}}sheetPr')
        if pr is None:
            pr=ET.Element(f'{{{SS_NS}}}sheetPr')
            sd.insert(0,pr)
        pr.set('codeName',f'Sheet{idx}')
        st.write(sp,encoding='utf-8',xml_declaration=True)

    # Repack deterministically enough for Office; preserve all parts plus VBA.
    if OUT.exists(): OUT.unlink()
    with zipfile.ZipFile(OUT,'w',zipfile.ZIP_DEFLATED) as z:
        for f in sorted(root.rglob('*')):
            if f.is_file():
                z.write(f, f.relative_to(root).as_posix())

# Structural verification.
with zipfile.ZipFile(OUT,'r') as z:
    names=set(z.namelist())
    assert 'xl/vbaProject.bin' in names
    assert '[Content_Types].xml' in names
    embedded=z.read('xl/vbaProject.bin')
    assert hashlib.sha256(embedded).digest()==hashlib.sha256(VBA.read_bytes()).digest()
    ct=z.read('[Content_Types].xml').decode('utf-8')
    assert 'macroEnabled.main+xml' in ct and 'vbaProject' in ct
    wb=z.read('xl/workbook.xml').decode('utf-8')
    assert wb.count('veryHidden') >= 4
    assert 'codeName="ThisWorkbook"' in wb

print('XLSM package PASS', OUT, OUT.stat().st_size, hashlib.sha256(OUT.read_bytes()).hexdigest())
