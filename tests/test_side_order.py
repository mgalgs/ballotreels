import hashlib
import subprocess
import sys
import unittest
from pathlib import Path

from ballotreels import side_order


class SideOrderTest(unittest.TestCase):
    def test_prop_2(self):
        # sha256("ca-2026-11-03-prop-2")[0] == 0xbd, odd: no plays first.
        self.assertEqual(
            hashlib.sha256(b"ca-2026-11-03-prop-2").digest()[0], 0xBD)
        self.assertEqual(side_order("ca-2026-11-03-prop-2"), ("no", "yes"))

    def test_rule(self):
        for i in range(200):
            cid = f"contest-{i}"
            first = hashlib.sha256(cid.encode()).digest()[0]
            want = ("yes", "no") if first % 2 == 0 else ("no", "yes")
            self.assertEqual(side_order(cid), want, cid)

    def test_both_orders_occur(self):
        orders = {side_order(f"ca-2026-11-03-prop-{n}") for n in range(1, 20)}
        self.assertEqual(orders, {("yes", "no"), ("no", "yes")})

    def test_deterministic_across_processes(self):
        # A fresh interpreter has a different str-hash seed; the order
        # must not depend on it.
        ids = [f"ca-2026-11-03-prop-{n}" for n in range(1, 20)]
        code = ("import sys; from ballotreels import side_order; "
                "print(' '.join(side_order(i)[0] for i in sys.argv[1:]))")
        out = subprocess.run([sys.executable, "-c", code, *ids],
                             capture_output=True, text=True, check=True,
                             cwd=Path(__file__).resolve().parent.parent,
                             env={"PYTHONHASHSEED": "random"})
        self.assertEqual(out.stdout.split(), [side_order(i)[0] for i in ids])

    def test_utf8(self):
        cid = "ca-2026-11-03-propuesta-ñ"
        first = hashlib.sha256(cid.encode("utf-8")).digest()[0]
        self.assertEqual(side_order(cid)[0], "yes" if first % 2 == 0 else "no")


if __name__ == "__main__":
    unittest.main()
