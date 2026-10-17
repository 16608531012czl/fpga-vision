"""Verify that deployed scripts, assets and bit/HWH belong to one release."""
from pathlib import Path, PurePosixPath
import hashlib
import json


def verify_payload(root, bitfile=None):
    root = Path(root).resolve()
    manifest_path = root/'board/build_manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest.get('project') != 'visual_aid_v3' or manifest.get('abi') != 0x56410300:
        raise ValueError('Wrong enhanced-project manifest')
    hashes = manifest.get('payload_sha256', {})
    if not hashes:
        raise ValueError('Empty release manifest')
    for name, expected in hashes.items():
        rel = PurePosixPath(name)
        if rel.is_absolute() or '..' in rel.parts or '\\' in name or ':' in name:
            raise ValueError('Unsafe manifest path: '+name)
        p = (root/str(rel)).resolve()
        if root not in p.parents or not p.is_file():
            raise IOError('Missing release file: '+name)
        if hashlib.sha256(p.read_bytes()).hexdigest() != expected:
            raise IOError('Release hash mismatch: '+name)
    if bitfile is not None:
        bit = Path(bitfile).resolve()
        if root not in bit.parents:
            raise ValueError('Bitstream must belong to this deployed bundle')
        for p in (bit, bit.with_suffix('.hwh')):
            if p.relative_to(root).as_posix() not in hashes:
                raise ValueError('Bit/HWH pair is not in the current release manifest')
    return manifest
