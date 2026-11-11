"""Image requests preserve explicit owners; unpinned images use the MCP pool."""
import unittest
from pipeline.common.map_profile import resolve_map_profile


class MapProfileTests(unittest.TestCase):
    def test_explicit_owner_or_pool(self):
        existing = {"params": {"profile": "kid4", "original": True}}
        self.assertEqual(resolve_map_profile(existing, registry={"active_mother_profile": "kid9"}), "kid4")
        self.assertEqual(resolve_map_profile({"params": {"profile": " kid4 "}}), "kid4")
        self.assertIsNone(resolve_map_profile({}, registry={"active_mother_profile": "kid7"}))
        self.assertIsNone(resolve_map_profile({"params": {"profile": "   "}}, registry={"active_mother_profile": "kid7"}))
        self.assertIsNone(resolve_map_profile({}, registry={"accounts": [{"role": "mother", "api_key_ref": "flova-profile:kid4"}]}))
        self.assertIsNone(resolve_map_profile({}, registry={}, policy={"mother": {"default_profile": "prod"}}))
        self.assertIsNone(resolve_map_profile({}, registry={}, policy={}))
        self.assertIsNone(resolve_map_profile({"params": None}))


if __name__ == "__main__":
    unittest.main()
