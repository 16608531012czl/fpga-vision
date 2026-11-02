#!/usr/bin/env python3
"""Portable PYNQ validation helpers. Python >=3.6; no bitstream download."""
import argparse
import hashlib
import importlib
import json
import math
import platform
import re
import sys
from pathlib import Path, PurePosixPath


def read_json(path):
    with Path(path).open(encoding='utf-8-sig') as stream:
        return json.load(stream)


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def member(root, name):
    if not isinstance(name, str) or not name or '\\' in name or ':' in name:
        raise ValueError('invalid root-relative POSIX path: {!r}'.format(name))
    rel = PurePosixPath(name)
    if rel.is_absolute() or '..' in rel.parts or str(rel) != name or name == '.':
        raise ValueError('non-canonical or escaping path: ' + name)
    root = Path(root).resolve()
    path = root.joinpath(*rel.parts).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        raise ValueError('resolved path escapes root: ' + name)
    if not path.is_file():
        raise ValueError('missing file: ' + name)
    return path


def seal(root, files):
    if not files or len(set(files)) != len(files):
        raise ValueError('provide a nonempty list of unique relative files')
    return {'schema': 1, 'files': {name: digest(member(root, name)) for name in files}}


def verify(root, manifest):
    if not isinstance(manifest, dict) or manifest.get('schema') != 1:
        raise ValueError('manifest schema must be 1')
    files = manifest.get('files')
    if not isinstance(files, dict) or not files:
        raise ValueError('manifest files must be nonempty object')
    errors = []
    for name, expected in files.items():
        try:
            if not isinstance(expected, str) or not re.fullmatch(r'[0-9a-f]{64}', expected):
                raise ValueError('invalid SHA-256: ' + str(name))
            if digest(member(root, name)) != expected:
                errors.append('hash mismatch: ' + name)
        except (ValueError, OSError) as exc:
            errors.append(str(exc))
    return {'passed': not errors, 'files_checked': len(files), 'errors': errors,
            'scope': 'manifest members only; neither authenticity nor hardware compatibility'}


def environment(modules):
    result = {'python': platform.python_version(), 'system': platform.system(),
              'machine': platform.machine(), 'executable': sys.executable,
              'overlay_downloaded': False, 'modules': {}, 'errors': []}
    if sys.version_info < (3, 6):
        result['errors'].append('Python >=3.6 required')
    for name in modules:
        try:
            module = importlib.import_module(name)
            result['modules'][name] = {'version': str(getattr(module, '__version__', 'unknown'))}
        except Exception as exc:
            result['errors'].append('{}: {}: {}'.format(name, type(exc).__name__, exc))
    result['passed'] = not result['errors']
    return result


def integer(value):
    if type(value) is int and value >= 0:
        return value
    if isinstance(value, str) and re.fullmatch(r'(0[xX][0-9a-fA-F]+|[0-9]+)', value):
        return int(value, 16 if value.lower().startswith('0x') else 10)
    raise ValueError('expected nonnegative integer/address, got {!r}'.format(value))


def check_ips(actual, expected):
    if not isinstance(expected, dict) or not expected:
        raise ValueError('expected_ips must be a nonempty object')
    errors = []
    for name, contract in expected.items():
        if not isinstance(contract, dict) or not contract:
            raise ValueError('IP contract must specify at least one field: ' + name)
        unknown = set(contract) - {'type', 'phys_addr', 'addr_range'}
        if unknown:
            raise ValueError('unknown IP fields: ' + ', '.join(sorted(unknown)))
        if name not in actual:
            errors.append('missing IP: ' + name)
            continue
        for key, value in contract.items():
            found = actual[name].get(key)
            if key in ('phys_addr', 'addr_range'):
                value = integer(value)
                if found is not None:
                    found = integer(found)
                if key == 'addr_range' and value == 0:
                    raise ValueError('addr_range must be positive')
            elif not isinstance(value, str) or not value:
                raise ValueError('IP type must be a nonempty VLNV string')
            if found != value:
                errors.append('{} {}: expected {!r}, got {!r}'.format(name, key, value, found))
    return {'passed': not errors, 'errors': errors, 'expected_ip_count': len(expected),
            'scope': 'required metadata fields only; extra IPs allowed; not a live ABI read'}


def metadata(root, profile, overlay_factory=None):
    bit = member(root, profile['bit'])
    hwh = member(root, profile['hwh'])
    if bit.suffix != '.bit' or hwh != bit.with_suffix('.hwh'):
        raise ValueError('bit and HWH must be same-stem adjacent .bit/.hwh files')
    # Validate the contract before importing PYNQ or constructing Overlay.
    expected = profile['expected_ips']
    check_ips({name: contract for name, contract in expected.items()}, expected)
    if overlay_factory is None:
        from pynq import Overlay
        overlay_factory = Overlay
    overlay = overlay_factory(str(bit), download=False)
    result = check_ips(overlay.ip_dict, expected)
    result.update(overlay_downloaded=False, bit_sha256=digest(bit), hwh_sha256=digest(hwh),
                  board_tested=False)
    return result


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def timing(metrics, min_setup=0.0, min_hold=0.0):
    if not finite(min_setup) or not finite(min_hold) or min_setup < 0 or min_hold < 0:
        raise ValueError('slack thresholds must be finite and nonnegative')
    if not isinstance(metrics, dict):
        raise ValueError('timing metrics must be an object')
    errors = []
    for key, limit in [('setup_ns', min_setup), ('hold_ns', min_hold)]:
        value = metrics.get(key)
        if not finite(value) or value < limit:
            errors.append(key + ' missing, non-finite or below threshold')
    for key in ('drc_errors', 'unconstrained_internal_endpoints'):
        if type(metrics.get(key)) is not int or metrics[key] != 0:
            errors.append(key + ' must be integer zero')
    return {'passed': not errors, 'errors': errors,
            'scope': 'user-supplied metrics only; inspect original timing/CDC/I/O constraints'}


def words(path, bits):
    text = Path(path).read_text(encoding='ascii')
    tokens = text.split()
    if not tokens:
        raise ValueError('empty word file: ' + str(path))
    values = []
    for index, token in enumerate(tokens):
        if not re.fullmatch(r'(?:0[xX])?[0-9a-fA-F]+', token):
            raise ValueError('invalid hex word at index {} in {}'.format(index, path))
        value = int(token, 16)
        if value >= (1 << bits):
            raise ValueError('word exceeds {} bits at index {}'.format(bits, index))
        values.append(value)
    return values


def compare(expected, actual, bits):
    if type(bits) is not int or not 1 <= bits <= 4096:
        raise ValueError('word width must be 1..4096 bits')
    left, right = words(expected, bits), words(actual, bits)
    mismatch = next((i for i, (a, b) in enumerate(zip(left, right)) if a != b), None)
    return {'passed': len(left) == len(right) and mismatch is None,
            'expected_words': len(left), 'actual_words': len(right),
            'first_mismatch_index': mismatch,
            'expected_value': left[mismatch] if mismatch is not None else None,
            'actual_value': right[mismatch] if mismatch is not None else None,
            'scope': 'exact unsigned hex words; order/packing/scaling must be agreed separately'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command')
    p = sub.add_parser('seal', help='create NEW manifest; never overwrites')
    p.add_argument('root'); p.add_argument('manifest'); p.add_argument('files', nargs='+')
    p = sub.add_parser('verify')
    p.add_argument('root'); p.add_argument('manifest')
    p = sub.add_parser('env')
    p.add_argument('--modules', nargs='*', default=[])
    p = sub.add_parser('metadata', help='PYNQ only; Overlay(download=False)')
    p.add_argument('root'); p.add_argument('profile')
    p = sub.add_parser('timing')
    p.add_argument('metrics'); p.add_argument('--min-setup', type=float, default=0.0)
    p.add_argument('--min-hold', type=float, default=0.0)
    p = sub.add_parser('compare')
    p.add_argument('expected'); p.add_argument('actual'); p.add_argument('--bits', type=int, required=True)
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help(); return 2
    try:
        if args.command == 'seal':
            result = seal(args.root, args.files)
            target = Path(args.manifest)
            if target.resolve() in [member(args.root, name) for name in args.files]:
                raise ValueError('manifest cannot be one of its own payload files')
            with target.open('x', encoding='utf-8') as stream:
                json.dump(result, stream, indent=2, allow_nan=False)
                stream.write('\n')
            result = {'passed': True, 'files_sealed': len(result['files']), 'manifest': str(target)}
        elif args.command == 'verify':
            result = verify(args.root, read_json(args.manifest))
        elif args.command == 'env':
            result = environment(args.modules)
        elif args.command == 'metadata':
            result = metadata(args.root, read_json(args.profile))
        elif args.command == 'timing':
            result = timing(read_json(args.metrics), args.min_setup, args.min_hold)
        else:
            result = compare(args.expected, args.actual, args.bits)
        code = 0 if result['passed'] else 1
    except Exception as exc:
        result = {'passed': False, 'error': '{}: {}'.format(type(exc).__name__, exc)}
        code = 2
    print(json.dumps(result, ensure_ascii=True, indent=2, allow_nan=False))
    return code


if __name__ == '__main__':
    sys.exit(main())
