from __future__ import annotations

import unittest

from privhealth import AdaptiveAnonymizer, PrivacyConfig, direct_removal
from privhealth.demo_data import generate_demo_data
from privhealth.metrics import hierarchy_loss


class PrivHealthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = generate_demo_data(rows=400, seed=7)

    def test_excluded_release_columns_are_removed(self) -> None:
        result = direct_removal(self.data, PrivacyConfig(k=2, l=1))
        for column in (
            "patient_id",
            "first_name",
            "last_name",
            "birthdate",
            "city",
            "state",
        ):
            self.assertNotIn(column, result.data.columns)

    def test_adaptive_output_meets_targets_when_nonempty(self) -> None:
        config = PrivacyConfig(k=5, l=2)
        result = AdaptiveAnonymizer(config).fit_transform(self.data)
        self.assertGreater(len(result.data), 0)
        self.assertGreaterEqual(result.metrics["achieved_k"], 5)
        self.assertGreaterEqual(result.metrics["achieved_l"], 2)
        self.assertEqual(result.metrics["risk"], 0.0)

    def test_adaptive_is_deterministic(self) -> None:
        config = PrivacyConfig(k=3, l=2)
        first = AdaptiveAnonymizer(config).fit_transform(self.data)
        second = AdaptiveAnonymizer(config).fit_transform(self.data)
        self.assertEqual(first.levels, second.levels)
        self.assertTrue(first.data.equals(second.data))

    def test_adaptive_selects_lowest_loss_valid_checkpoint(self) -> None:
        config = PrivacyConfig(k=5, l=2)
        result = AdaptiveAnonymizer(config).fit_transform(self.data)
        selected = result.trace.loc[result.trace["selected"]].iloc[0]
        valid = result.trace[result.trace["retained_rows"] > 0]
        self.assertAlmostEqual(
            selected["release_information_loss"],
            valid["release_information_loss"].min(),
        )
        self.assertAlmostEqual(
            result.metrics["information_loss"],
            selected["release_information_loss"],
        )

    def test_hierarchy_loss_increases_with_generalization(self) -> None:
        initial = {"age": 0, "gender": 0, "zip_code": 0}
        changed = {"age": 1, "gender": 0, "zip_code": 1}
        self.assertLess(hierarchy_loss(initial), hierarchy_loss(changed))


if __name__ == "__main__":
    unittest.main()
