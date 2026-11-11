"""Official-price regression tests: no network, account calls, or generation."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import flova_pricing as p

def store(prices=None,kind="image"):
    return {"revision":"official-test","models":[{"key":"gpt_flare","type":kind,
        "params":[{"key":"resolution","default":"2K"},{"key":"duration","default":5}],
        "prices":prices if prices is not None else [
            {"resolution":"1k","variant":"price","normal":.05,"member":.05},
            {"resolution":"2k","variant":"price","normal":.07,"member":.07},
            {"resolution":"4k","variant":"price","normal":.15,"member":.15}]}]}

class OfficialPriceTests(unittest.TestCase):
    def quote(self,**kw):
        return p.quote("gpt_flare",store=kw.pop("store",store()),member=kw.pop("member",False),**kw)

    def test_old_16x_calibration_cannot_inflate_a_quote(self):
        with patch.object(p,"_calib_load",return_value={"gpt_flare|2k|price":16.857}):
            q=self.quote(resolution="2K")
        self.assertEqual((q.table_credits,q.estimated_credits,q.factor),(7,7,1))
        self.assertEqual(q.pricing_revision,"official-test")
        self.assertEqual(q.pricing_source,p.CONFIG_URL)

    def test_official_resolution_prices(self):
        for size,credits in [("1K",5),("2K",7),("4K",15)]:
            with self.subTest(size=size):
                self.assertEqual(self.quote(resolution=size).estimated_credits,credits)

    def test_batch_count_is_applied_exactly_once(self):
        q=self.quote(resolution="2K")
        self.assertEqual(p.assess(q,balance=30,count=3)["budget_credits"],21)
        self.assertEqual(p.assess(q,balance=120,count=16)["budget_credits"],112)

    def test_invalid_counts_do_not_silently_clamp_or_truncate(self):
        for count in [0,-1,1.5,True]:
            with self.subTest(count=count),self.assertRaises(ValueError):
                p.assess(self.quote(),balance=100,count=count)

    def test_missing_resolution_does_not_borrow_a_different_tier(self):
        with self.assertRaises(KeyError):self.quote(resolution="8K")

    def test_unavailable_non_member_price_is_not_replaced_with_member_price(self):
        data=store([{"resolution":"2k","variant":"price","normal":"unavailable","member":.07}])
        with self.assertRaises(ValueError):self.quote(store=data)
        self.assertEqual(self.quote(store=data,member=True).estimated_credits,7)

    def test_free_official_tier_is_zero(self):
        data=store([{"resolution":"2k","normal":0,"member":0}])
        self.assertEqual(self.quote(store=data).estimated_credits,0)

    def test_fractional_video_duration_uses_decimal_once(self):
        data=store([{"resolution":"2k","normal":.1,"member":.1}],kind="video")
        q=self.quote(store=data,seconds=1.1,ref_seconds=2.2)
        self.assertEqual(q.quantity,3.3)
        self.assertEqual(q.estimated_credits,33)

    def test_reference_video_tier_is_used_when_published(self):
        data=store([{"resolution":"2k","variant":"price","normal":.08,"member":.08},
                    {"resolution":"2k","variant":"priceWithRefVideo","normal":.1,"member":.1}],kind="video")
        self.assertEqual(self.quote(store=data,seconds=5,ref_seconds=2).estimated_credits,70)

    def test_unavailable_reference_tier_does_not_fall_back_to_base_price(self):
        data=store([{"resolution":"2k","variant":"price","normal":.08,"member":.08},
                    {"resolution":"2k","variant":"priceWithRefVideo","normal":"unavailable","member":.1}],kind="video")
        with self.assertRaises(ValueError):self.quote(store=data,seconds=5,ref_seconds=2)

    def test_wallet_difference_never_rewrites_model_price(self):
        q=self.quote()
        with patch.object(p,"load",return_value={"revision":"official-test"}),patch.object(p,"remote_revision",return_value="official-test"),patch.object(p,"_calib_save") as save:
            r=p.reconcile(q,balance_before=200,balance_after=82)
        self.assertIsNone(r["actual_credits"])
        self.assertEqual(r["observed_credits"],118)
        self.assertFalse(r["factor_updated"])
        self.assertTrue(r["needs_usage_review"])
        save.assert_not_called()
        self.assertEqual(self.quote().estimated_credits,7)

    def test_batch_postflight_compares_total_once(self):
        with patch.object(p,"quote",return_value=self.quote()),patch.object(p,"get_balance",return_value=79),patch.object(p,"load",return_value={"revision":"official-test"}):
            r=p.cmd_postflight("gpt_flare",count=3,balance_before=100)
        self.assertEqual(r["budget_estimate"],21)
        self.assertEqual(r["observed_credits"],21)
        self.assertTrue(r["matched"])
        self.assertIsNone(r["actual_credits"])

if __name__=="__main__":
    unittest.main()
