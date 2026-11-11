import unittest
from overlay_contract import validate_overlay_contract

class OverlayContractTests(unittest.TestCase):
    def test_real_room_names(self):
        self.assertEqual(validate_overlay_contract({"sampleData":False},{"rooms":[{"label":"客厅"}]},{"LR1":{"targets":[{"id":"ac","label":"美的空调","kf":[[0,.2,.3,.2,.1],[1,.3,.4,.2,.1]]}]}}),[])
    def test_real_demo_heading_is_rejected(self):
        self.assertTrue(validate_overlay_contract({"sampleData":False},{"clipTitles":{"LR1":"样板间 客厅"}},{}))
    def test_demo_needs_explicit_sample_flag(self):
        self.assertEqual(validate_overlay_contract({"sampleData":True},{"rooms":[{"label":"示例房源"}]},{}),[])
        self.assertTrue(validate_overlay_contract({},{"rooms":[{"label":"示例房源"}]},{}))
    def test_invalid_tracking_time_is_rejected(self):
        self.assertTrue(validate_overlay_contract({"sampleData":False},{},{"LR1":{"targets":[{"id":"a","label":"空调","kf":[[0,.2,.3,.1,.2],[0,.2,.3,.1,.2]]}]}}))

if __name__ == "__main__":
    unittest.main()
