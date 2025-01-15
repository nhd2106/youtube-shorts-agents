# -*- mode: python ; coding: utf-8 -*-
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Collect all necessary hidden imports
hidden_imports = [
    'engineio.async_drivers.threading',
    'flask_cors',
    'dotenv',
    'numpy',
    'imageio',
    'moviepy',
    'moviepy.editor',
    'moviepy.video.io.VideoFileClip',
    'moviepy.video.VideoClip',
    'moviepy.video.compositing.CompositeVideoClip',
    'moviepy.video.fx.all',
    'moviepy.audio.fx.all',
    'PIL',
    'requests',
    'openai',
    'together',
    'edge_tts',
    'gtts',
    'librosa',
    'deepfilternet',
    'cutlet',
    'aiohttp',
] + collect_submodules('numpy') + collect_submodules('moviepy')

# Collect data files
datas = [
    ('templates', 'templates'),
    ('static', 'static'),
    ('.env', '.')
]

# Add additional data files from packages
datas += collect_data_files('numpy')
datas += collect_data_files('moviepy')

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='youtube-shorts-agent',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=True,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
