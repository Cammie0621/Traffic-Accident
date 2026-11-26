import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class ParticipantsPageTests(unittest.TestCase):
    def setUp(self):
        accidents = pd.DataFrame({
            "accident_id": ["A1", "A2", "A3"],
            "year": [2024, 2025, 2025],
            "city": ["臺北市", "臺北市", "臺南市"],
            "accident_type": ["A2", "A2", "A1"],
            "deaths": [0, 0, 1],
            "injuries": [1, 1, 0],
        })
        participants = pd.DataFrame({
            "accident_id": ["A1", "A1", "A2", "A3"],
            "vehicle_type": ["機車", "小客車", "小客車", "機車"],
            "age": [25, 40, 35, 60],
        })
        loader = patch("utils.data_loader.load_data", return_value=(accidents, participants, True))
        loader.start()
        self.addCleanup(loader.stop)

    def test_vehicle_selection_and_age_counts_survive_page_roundtrip(self):
        cases = [(["小客車", "機車"], "4 人次"), (["機車"], "2 人次"), ([], "0 人次")]
        for selected, expected_count in cases:
            with self.subTest(selected=selected):
                app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=15).run()
                app.switch_page("pages/4_participants.py").run()
                self.assertEqual(list(app.exception), [])
                self.assertEqual(app.multiselect(key="participants_vehicles").value, ["小客車", "機車"])
                app.multiselect(key="participants_vehicles").set_value(selected).run()
                self.assertEqual(app.metric[0].value, expected_count)

                app.switch_page("pages/1_overview.py").run()
                app.switch_page("pages/4_participants.py").run()

                self.assertEqual(list(app.exception), [])
                self.assertEqual(app.multiselect(key="participants_vehicles").value, selected)
                self.assertEqual(app.metric[0].value, expected_count)

    def test_sidebar_filters_survive_page_roundtrip(self):
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=15).run()
        app.switch_page("pages/4_participants.py").run()
        app.multiselect(key="participants_vehicles").set_value(["機車"]).run()
        filters = {"sb_years": [2025], "sb_cities": ["臺南市"], "sb_types": ["A1"]}
        for key, selected in filters.items():
            app.multiselect(key=key).set_value(selected).run()
        self.assertEqual(app.metric[0].value, "1 人次")

        app.switch_page("pages/1_overview.py").run()
        for key, selected in filters.items():
            self.assertEqual(app.multiselect(key=key).value, selected)
        app.switch_page("pages/4_participants.py").run()

        self.assertEqual(list(app.exception), [])
        for key, selected in filters.items():
            self.assertEqual(app.multiselect(key=key).value, selected)
        self.assertEqual(app.multiselect(key="participants_vehicles").value, ["機車"])
        self.assertEqual(app.metric[0].value, "1 人次")

        app.multiselect(key="sb_years").set_value([]).run()
        self.assertEqual(app.multiselect(key="sb_years").value, [])
        self.assertEqual(app.metric[0].value, "0 人次")
        app.button[0].click().run()
        self.assertEqual(list(app.exception), [])
        self.assertEqual(app.multiselect(key="sb_years").value, [2024, 2025])
        self.assertEqual(len(app.multiselect(key="sb_cities").value), 6)
        self.assertEqual(app.multiselect(key="sb_types").value, ["A1", "A2"])
        self.assertEqual(app.metric[0].value, "2 人次")


if __name__ == "__main__":
    unittest.main()
