import unittest

from stats import median


class TestMedian(unittest.TestCase):
    def test_odd_length(self):
        self.assertEqual(median([3, 1, 2]), 2)

    def test_even_length_averages_two_middles(self):
        self.assertEqual(median([1, 2, 3, 4]), 2.5)

    def test_even_length_unsorted(self):
        self.assertEqual(median([10, 2, 8, 4]), 6.0)

    def test_single(self):
        self.assertEqual(median([42]), 42)

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            median([])


if __name__ == "__main__":
    unittest.main()
