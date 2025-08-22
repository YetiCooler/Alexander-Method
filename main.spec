# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_all
from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT

# ─── collect your libraries/data as before ─────────────────────────────────────
datas, binaries, hiddenimports = [], [], []
tmp = collect_all('wordsegment')
datas += tmp[0]; binaries += tmp[1]; hiddenimports += tmp[2]

# filter out notebooks
notebooks_path = os.path.join('notebooks')
datas = [d for d in datas if not d[0].startswith(notebooks_path)]

# ─── first app: main.py ────────────────────────────────────────────────────────
a1 = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz1 = PYZ(a1.pure,  a1.zipped_data, cipher=None)
exe1 = EXE(
    pyz1,
    a1.scripts,
    [],
    exclude_binaries=True,
    name='main',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)

# ─── second app: commands/add_pt_components.py ─────────────────────────────────
# Re-use the same libs/data/hiddenimports in case your script needs them. 
a2 = Analysis(
    ['commands/add_pt_components.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz2 = PYZ(a2.pure,  a2.zipped_data, cipher=None)
exe2 = EXE(
    pyz2,
    a2.scripts,
    [],
    exclude_binaries=True,
    name='load-pt-components',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)

# ─── collect both into the same dist folder ────────────────────────────────────
coll = COLLECT(
    exe1, exe2,
    a1.binaries + a2.binaries,
    a1.datas    + a2.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='main'
)