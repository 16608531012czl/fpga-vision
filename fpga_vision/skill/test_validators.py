import unittest,tempfile,hashlib
from pathlib import Path
from verify_hashes import verify
from check_timing import check
from compare_words import compare
class Validators(unittest.TestCase):
    def test_hash_integrity_and_tamper(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'payload.bin';p.write_bytes(b'known payload');h={'payload.bin':hashlib.sha256(p.read_bytes()).hexdigest()}
            self.assertEqual(verify(d,h),[]);p.write_bytes(b'changed');self.assertTrue(verify(d,h));p.unlink();self.assertTrue(verify(d,h))
    def test_path_escape(self):
        self.assertTrue(verify('.',{'../outside':'0'*64}));self.assertTrue(verify('.',{'c:/outside':'0'*64}))
    def test_timing_pass(self):self.assertTrue(check({'setup_ns':.189,'hold_ns':.014,'drc_errors':0})['passed'])
    def test_negative_slack(self):self.assertFalse(check({'setup_ns':-.001,'hold_ns':.01,'drc_errors':0})['passed'])
    def test_missing_and_nan(self):
        self.assertFalse(check({})['passed']);self.assertFalse(check({'setup_ns':float('nan'),'hold_ns':.1,'drc_errors':0})['passed'])
    def test_drc_error(self):self.assertFalse(check({'setup_ns':.1,'hold_ns':.1,'drc_errors':1})['passed'])
    def test_pixel_match(self):self.assertTrue(compare('00 ff 1a','0 FF 1A')['passed'])
    def test_pixel_mismatch(self):self.assertEqual(compare('0 1','0 2')['first_mismatch'],1)
    def test_truncated_and_empty(self):self.assertFalse(compare('0 1','0')['passed']);self.assertFalse(compare('','')['passed'])
if __name__=='__main__':unittest.main(verbosity=2)
