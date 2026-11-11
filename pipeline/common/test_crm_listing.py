"""CRM allowlist and image-suffix rules (no network)."""
import unittest
from pipeline.common import crm_listing as crm


class CrmListingTests(unittest.TestCase):
    def test_sanitize_drops_private_fields_and_unit_numbers(self):
        raw = {"listing_id": "1", "community": "成发紫东阳光", "layout": "3室1厅1卫", "area_sqm": 74.6,
               "monthly_rent_yuan": 3000, "orientation": "南", "floor_desc": "3单元601室",
               "maintainer_phone": "13800000000", "title_image_url": "https://img.example/a.jpg"}
        out = crm.sanitize(raw)
        self.assertNotIn("maintainer_phone", out)
        self.assertEqual(out["floor_desc"], crm.PLACEHOLDER)
        self.assertEqual(out["title_image_url"], "https://img.example/a.jpg.1500x.jpg")
        self.assertEqual(crm.sanitize({})["community"], crm.PLACEHOLDER)

    def test_cdn_suffix_not_doubled(self):
        self.assertEqual(crm.cdn("u.jpg.450x.jpg"), "u.jpg.450x.jpg")
        self.assertIsNone(crm.cdn(None))


if __name__ == "__main__":
    unittest.main()
