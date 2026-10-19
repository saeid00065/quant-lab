import math
import unittest

from metrics import max_drawdown, total_return, win_rate


class MetricsTest(unittest.TestCase):
    def test_total_return(self):
        self.assertAlmostEqual(total_return([100, 110, 121]), 0.21, places=12)

    def test_max_drawdown(self):
        # peak 120 -> trough 90 = -25%
        self.assertAlmostEqual(max_drawdown([100, 120, 90, 130]), -0.25, places=12)

    def test_win_rate(self):
        self.assertAlmostEqual(win_rate([0.1, -0.05, 0.02, -0.01]), 0.5, places=12)
        self.assertTrue(math.isnan(win_rate([])))


if __name__ == "__main__":
    unittest.main()
