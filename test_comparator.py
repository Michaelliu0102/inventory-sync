#!/usr/bin/env python3
"""
comparator 模块的单元测试
"""

import unittest
from comparator import compare, DiffItem


class TestCompare(unittest.TestCase):

    def test_identical_inventory(self):
        """完全一致的库存"""
        ns = {"ItemA": 10, "ItemB": 20}
        ex = {"ItemA": 10, "ItemB": 20}
        result = compare(ns, ex, "TestLocation")
        self.assertFalse(result.has_diffs)
        self.assertEqual(len(result.diffs), 0)

    def test_quantity_mismatch(self):
        """数量不一致"""
        ns = {"ItemA": 10, "ItemB": 25}
        ex = {"ItemA": 10, "ItemB": 20}
        result = compare(ns, ex, "TestLocation")
        self.assertTrue(result.has_diffs)
        self.assertEqual(len(result.diffs), 1)
        self.assertEqual(result.diffs[0].diff_type, "mismatch")
        self.assertEqual(result.diffs[0].name, "ItemB")
        self.assertEqual(result.diffs[0].difference, 5)  # NS(25) - Excel(20)

    def test_netsuite_only(self):
        """仅 NetSuite 有的 SKU"""
        ns = {"ItemA": 10, "ItemB": 20}
        ex = {"ItemA": 10}
        result = compare(ns, ex, "TestLocation")
        self.assertTrue(result.has_diffs)
        self.assertEqual(result.diffs[0].diff_type, "netsuite_only")

    def test_excel_only(self):
        """仅 Excel 有的 SKU"""
        ns = {"ItemA": 10}
        ex = {"ItemA": 10, "ItemB": 20}
        result = compare(ns, ex, "TestLocation")
        self.assertTrue(result.has_diffs)
        self.assertEqual(result.diffs[0].diff_type, "excel_only")

    def test_empty_both(self):
        """两边都为空"""
        result = compare({}, {}, "TestLocation")
        self.assertFalse(result.has_diffs)

    def test_empty_netsuite(self):
        """NetSuite 为空，Excel 有数据"""
        ex = {"ItemA": 10}
        result = compare({}, ex, "TestLocation")
        self.assertTrue(result.has_diffs)
        self.assertEqual(result.diffs[0].diff_type, "excel_only")

    def test_floating_point_tolerance(self):
        """浮点数容差：差值极小应视为一致"""
        ns = {"ItemA": 10.0000001}
        ex = {"ItemA": 10.0}
        result = compare(ns, ex, "TestLocation")
        self.assertFalse(result.has_diffs)

    def test_multiple_diffs(self):
        """多种差异混合"""
        ns = {"ItemA": 10, "ItemB": 30, "ItemD": 5}
        ex = {"ItemA": 10, "ItemB": 20, "ItemC": 15}
        result = compare(ns, ex, "TestLocation")
        self.assertTrue(result.has_diffs)
        self.assertEqual(len(result.diffs), 3)  # ItemB mismatch, ItemC excel_only, ItemD netsuite_only

        diff_types = {d.name: d.diff_type for d in result.diffs}
        self.assertEqual(diff_types["ItemB"], "mismatch")
        self.assertEqual(diff_types["ItemC"], "excel_only")
        self.assertEqual(diff_types["ItemD"], "netsuite_only")

    def test_summary_no_diff(self):
        """无差异时的摘要"""
        result = compare({"A": 1}, {"A": 1}, "Italy - Grandate")
        self.assertIn("✅", result.summary)
        self.assertIn("Italy - Grandate", result.summary)

    def test_summary_with_diff(self):
        """有差异时的摘要"""
        result = compare({"A": 1}, {"A": 2}, "China - Jiaxing")
        self.assertIn("⚠️", result.summary)
        self.assertIn("China - Jiaxing", result.summary)


if __name__ == "__main__":
    unittest.main()
