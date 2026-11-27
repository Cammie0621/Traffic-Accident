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
        self.participants = participants
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

    def test_age_controls_and_counts_survive_page_roundtrip(self):
        # 0 與 100 歲預設有效，但勾選排除待覆核值後應由 4 人次降為 2 人次。
        self.participants["age"] = [0, 40, 100, 60]
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=15).run()
        app.switch_page("pages/4_participants.py").run()
        self.assertEqual(app.radio(key="participants_age_bin_width").value, 5)
        self.assertFalse(app.checkbox(key="participants_age_exclude_review").value)
        # 同一工作階段依序更改兩組設定，亦驗證取消勾選會覆蓋先前保存的 True。
        for width, exclude_review in [(10, True), (5, False)]:
            with self.subTest(width=width, exclude_review=exclude_review):
                app.radio(key="participants_age_bin_width").set_value(width).run()
                app.checkbox(key="participants_age_exclude_review").set_value(exclude_review).run()
                expected_count = "2 人次" if exclude_review else "4 人次"
                self.assertEqual(app.metric[0].value, expected_count)

                for page in ["pages/1_overview.py", "pages/5_methods.py", "app.py"]:
                    app.switch_page(page).run()
                    self.assertEqual(list(app.exception), [])
                app.switch_page("pages/4_participants.py").run()

                self.assertEqual(list(app.exception), [])
                self.assertEqual(app.radio(key="participants_age_bin_width").value, width)
                self.assertEqual(app.checkbox(key="participants_age_exclude_review").value, exclude_review)
                self.assertEqual(app.metric[0].value, expected_count)

    def test_age_controls_survive_empty_results_and_reset(self):
        self.participants["age"] = [0, 40, 100, 60]
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=15).run()
        app.switch_page("pages/4_participants.py").run()
        app.radio(key="participants_age_bin_width").set_value(10).run()
        app.checkbox(key="participants_age_exclude_review").check().run()
        app.multiselect(key="sb_years").set_value([]).run()
        self.assertEqual(app.metric[0].value, "0 人次")
        app.switch_page("pages/1_overview.py").run()
        app.switch_page("pages/4_participants.py").run()
        self.assertEqual(app.multiselect(key="sb_years").value, [])
        app.button[0].click().run()

        self.assertEqual(list(app.exception), [])
        self.assertEqual(app.radio(key="participants_age_bin_width").value, 10)
        self.assertTrue(app.checkbox(key="participants_age_exclude_review").value)
        self.assertEqual(app.metric[0].value, "2 人次")

    def test_city_sort_survives_page_roundtrip(self):
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=15).run()
        app.switch_page("pages/1_overview.py").run()
        fixed_order = "固定城市順序（北到南）"
        app.radio(key="overview_city_sort").set_value(fixed_order).run()
        app.switch_page("pages/4_participants.py").run()
        app.switch_page("pages/1_overview.py").run()

        self.assertEqual(list(app.exception), [])
        self.assertEqual(app.radio(key="overview_city_sort").value, fixed_order)

        # 再改回另一選項，確認保存的是最新選擇。
        count_order = "依事故件數排序"
        app.radio(key="overview_city_sort").set_value(count_order).run()
        app.switch_page("pages/2_time.py").run()
        app.switch_page("pages/1_overview.py").run()
        self.assertEqual(list(app.exception), [])
        self.assertEqual(app.radio(key="overview_city_sort").value, count_order)

    def test_city_sort_survives_hidden_widget_and_reset(self):
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=15).run()
        app.switch_page("pages/1_overview.py").run()
        fixed_order = "固定城市順序（北到南）"
        app.radio(key="overview_city_sort").set_value(fixed_order).run()
        app.multiselect(key="sb_years").set_value([]).run()
        self.assertEqual(len(app.radio), 0)
        self.assertEqual(list(app.exception), [])

        app.button[0].click().run()

        self.assertEqual(list(app.exception), [])
        self.assertEqual(app.radio(key="overview_city_sort").value, fixed_order)


if __name__ == "__main__":
    unittest.main()
