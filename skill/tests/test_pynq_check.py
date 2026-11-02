import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'pynq_check.py'
SPEC = importlib.util.spec_from_file_location('pynq_check', str(SCRIPT))
check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check)


class PortableChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / 'design.bit').write_bytes(b'synthetic-bit-not-programmable')
        (self.root / 'design.hwh').write_text('<synthetic/>', encoding='utf-8')
        self.manifest = check.seal(self.root, ['design.bit', 'design.hwh'])

    def tearDown(self):
        self.temp.cleanup()

    def run_cli(self, args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = check.main(args)
        return code, json.loads(output.getvalue())

    def profile(self):
        return {'bit': 'design.bit', 'hwh': 'design.hwh',
                'expected_ips': {'fir_0': {'type': 'team:user:fir:1.0',
                                         'phys_addr': '0x40000000', 'addr_range': '0x10000'}}}

    def test_payload_pass(self):
        self.assertTrue(check.verify(self.root, self.manifest)['passed'])

    def test_tampered_file(self):
        (self.root / 'design.bit').write_bytes(b'changed')
        self.assertFalse(check.verify(self.root, self.manifest)['passed'])

    def test_missing_file(self):
        (self.root / 'design.hwh').unlink()
        self.assertFalse(check.verify(self.root, self.manifest)['passed'])

    def test_path_escape_and_absolute(self):
        for name in ('../outside', '/etc/passwd', 'C:/outside', 'a\\b', './design.bit', '.'):
            with self.subTest(path=name):
                with self.assertRaises(ValueError):
                    check.member(self.root, name)

    def test_symlink_escape_when_supported(self):
        with tempfile.TemporaryDirectory() as outside:
            target = Path(outside) / 'external'
            target.write_bytes(b'external')
            link = self.root / 'escape'
            try:
                link.symlink_to(target)
            except OSError:
                self.skipTest('OS does not permit creating symlinks')
            with self.assertRaises(ValueError):
                check.member(self.root, 'escape')

    def test_invalid_hash_and_empty_manifest(self):
        self.assertFalse(check.verify(self.root, {'schema': 1, 'files': {'design.bit': 'bad'}})['passed'])
        with self.assertRaises(ValueError):
            check.verify(self.root, {'schema': 1, 'files': {}})

    def test_manifest_does_not_overwrite(self):
        manifest = self.root / 'manifest.json'
        args = ['seal', str(self.root), str(manifest), 'design.bit']
        self.assertEqual(self.run_cli(args)[0], 0)
        before = manifest.read_bytes()
        self.assertEqual(self.run_cli(args)[0], 2)
        self.assertEqual(before, manifest.read_bytes())

    def test_manifest_additional_files_are_out_of_scope(self):
        (self.root / 'extra.py').write_text('print(1)', encoding='utf-8')
        self.assertTrue(check.verify(self.root, self.manifest)['passed'])

    def test_env_missing_module(self):
        result = check.environment(['_pynq_skill_nonexistent_module_7281'])
        self.assertFalse(result['passed'])
        self.assertFalse(result['overlay_downloaded'])

    def test_metadata_disables_download(self):
        calls = []
        profile = self.profile()
        def factory(path, **kwargs):
            calls.append((path, kwargs))
            class FakeOverlay:
                ip_dict = {'fir_0': {'type': 'team:user:fir:1.0',
                                      'phys_addr': 0x40000000, 'addr_range': 65536}}
            return FakeOverlay()
        result = check.metadata(self.root, profile, factory)
        self.assertTrue(result['passed'])
        self.assertEqual(calls[0][1], {'download': False})
        self.assertFalse(result['board_tested'])

    def test_metadata_wrong_pair(self):
        profile = self.profile()
        (self.root / 'other.hwh').write_text('<synthetic/>')
        profile['hwh'] = 'other.hwh'
        with self.assertRaises(ValueError):
            check.metadata(self.root, profile, lambda *a, **k: self.fail('must not instantiate'))

    def test_missing_ip(self):
        self.assertFalse(check.check_ips({}, self.profile()['expected_ips'])['passed'])

    def test_changed_ip_type_address_and_range(self):
        expected = self.profile()['expected_ips']
        actual = {'fir_0': {'type': 'team:user:other:2.0', 'phys_addr': 0x80000000, 'addr_range': 4096}}
        result = check.check_ips(actual, expected)
        self.assertFalse(result['passed'])
        self.assertEqual(len(result['errors']), 3)

    def test_two_topic_profiles_same_validator(self):
        profiles = [self.profile()['expected_ips'],
                    {'spectral/fft': {'type': 'lab:dsp:fft:2.1', 'phys_addr': '0xA0000000', 'addr_range': 4096}}]
        for expected in profiles:
            actual = {name: dict(contract) for name, contract in expected.items()}
            self.assertTrue(check.check_ips(actual, expected)['passed'])

    def test_contract_typo_rejected(self):
        with self.assertRaises(ValueError):
            check.check_ips({'ip': {}}, {'ip': {'address_typo': 1}})

    def good_timing(self):
        return {'setup_ns': 0.1, 'hold_ns': 0.01, 'drc_errors': 0, 'unconstrained_internal_endpoints': 0}

    def test_timing_pass_and_custom_threshold(self):
        self.assertTrue(check.timing(self.good_timing())['passed'])
        self.assertFalse(check.timing(self.good_timing(), min_setup=0.2)['passed'])

    def test_timing_negative_nonfinite_missing_and_bool(self):
        for value in (-0.1, float('nan'), float('inf'), None, True):
            data = self.good_timing(); data['setup_ns'] = value
            self.assertFalse(check.timing(data)['passed'])
        self.assertFalse(check.timing({})['passed'])

    def test_drc_and_unconstrained_rejected(self):
        for key in ('drc_errors', 'unconstrained_internal_endpoints'):
            for value in (1, -1, True, None):
                data = self.good_timing(); data[key] = value
                self.assertFalse(check.timing(data)['passed'])

    def test_bad_threshold_rejected(self):
        for threshold in (float('nan'), float('inf'), -1):
            with self.assertRaises(ValueError):
                check.timing(self.good_timing(), min_setup=threshold)

    def word_files(self, left, right):
        expected, actual = self.root / 'golden.mem', self.root / 'dut.mem'
        expected.write_text(left, encoding='ascii'); actual.write_text(right, encoding='ascii')
        return expected, actual

    def test_word_equivalence(self):
        files = self.word_files('00 0xFF 10', '0 ff 0010\n')
        self.assertTrue(check.compare(*files, bits=8)['passed'])

    def test_first_mismatch(self):
        files = self.word_files('0 1 2', '0 3 2')
        result = check.compare(*files, bits=8)
        self.assertFalse(result['passed']); self.assertEqual(result['first_mismatch_index'], 1)

    def test_truncated_and_extra_words(self):
        for left, right in [('0 1', '0'), ('0', '0 1')]:
            self.assertFalse(check.compare(*self.word_files(left, right), bits=8)['passed'])

    def test_empty_xz_negative_overwidth_rejected(self):
        for bad in ('', 'xx', 'zz', '-1', '100'):
            with self.assertRaises(ValueError):
                check.compare(*self.word_files('0', bad), bits=8)

    def test_cli_exit_codes_and_malformed_json(self):
        manifest = self.root / 'manifest.json'
        manifest.write_text(json.dumps(self.manifest), encoding='utf-8')
        self.assertEqual(self.run_cli(['verify', str(self.root), str(manifest)])[0], 0)
        (self.root / 'design.bit').write_bytes(b'tampered')
        self.assertEqual(self.run_cli(['verify', str(self.root), str(manifest)])[0], 1)
        manifest.write_text('{broken', encoding='utf-8')
        self.assertEqual(self.run_cli(['verify', str(self.root), str(manifest)])[0], 2)


if __name__ == '__main__':
    unittest.main()
