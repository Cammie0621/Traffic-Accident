import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.cleaning import RAW_COLUMNS, build_tables, clean_age, regions
from components.age_distribution import summarize_ages


def row(order=1, age="25", sex="男", **changes):
    result = {column:"" for column in RAW_COLUMNS}
    result.update({"發生年度":"2025", "發生月份":"1", "發生日期":"20250101", "發生時間":"033500", "事故類別名稱":"A1", "處理單位名稱警局層":"臺南市政府警察局", "發生地點":"臺南市安南區測試路口", "經度":"120.2", "緯度":"23.0", "當事者順位":str(order), "死亡受傷人數":"死亡1;受傷0", "當事者事故發生時年齡":age, "當事者屬-性-別名稱":sex, "當事者區分-類別-大類別名稱-車種":"機車", "當事者區分-類別-子類別名稱-車種":"普通重型", "肇因研判大類別名稱-主要":"駕駛者", "肇因研判子類別名稱-主要":"其他"})
    result.update(changes)
    return result


class CleaningTests(unittest.TestCase):
    def test_unique_case_can_have_second_party_before_first(self):
        acc,part,audit=build_tables(pd.DataFrame([row(2,"30"),row(1,"25")]),"unordered.csv",2025)
        self.assertEqual((len(acc),len(part)),(1,2))
        self.assertEqual(part.participant_order.tolist(),[2,1])
        self.assertEqual(int(acc.source_record.iloc[0]),2)
        self.assertTrue(part.participant_id.is_unique)
        self.assertEqual(audit['source_rows_before_unique_rank_one'],1)

    def test_missing_first_party_is_not_invented(self):
        with self.assertRaisesRegex(ValueError,"starts without ordinal 1"):
            build_tables(pd.DataFrame([row(2)]),"missing-first.csv",2025)

    def test_ambiguous_repeated_key_prefix_is_rejected(self):
        with self.assertRaisesRegex(ValueError,"starts without ordinal 1"):
            build_tables(pd.DataFrame([row(2),row(1),row(1)]),"ambiguous.csv",2025)

    def test_2024_leap_day_and_midnight(self):
        record=row(1, **{"發生年度":"2024", "發生月份":"2", "發生日期":"20240229", "發生時間":"000000"})
        acc,part,_=build_tables(pd.DataFrame([record]),"2024/fixture.csv",2024)
        self.assertEqual(int(acc.year.iloc[0]),2024)
        self.assertEqual(str(acc.date.iloc[0].date()),"2024-02-29")
        self.assertEqual((int(acc.weekday.iloc[0]),int(acc.hour.iloc[0])),(3,0))
        self.assertTrue(bool(acc.datetime_valid.iloc[0]))
        self.assertTrue(str(part.accident_id.iloc[0]).startswith("2024-"))

    def test_source_year_mismatch_is_rejected(self):
        with self.assertRaisesRegex(ValueError,"Source year does not match"):
            build_tables(pd.DataFrame([row(1)]),"2024/fixture.csv",2024)

    def test_cross_year_light_truck_names_share_category_and_keep_raw(self):
        for year,raw_type in [(2024,"小貨車(含客、貨兩用)"),(2025,"小貨車")]:
            record=row(1,**{"發生年度":str(year),"發生日期":f"{year}0101","當事者區分-類別-大類別名稱-車種":raw_type})
            _,part,_=build_tables(pd.DataFrame([record]),f"{year}/fixture.csv",year)
            self.assertEqual(part.vehicle_type.iloc[0],"小貨車")
            self.assertEqual(part.vehicle_type_raw.iloc[0],raw_type)

    def test_casualties_once_and_leading_zero_time(self):
        acc, part, _ = build_tables(pd.DataFrame([row(1), row(2)]), "fixture.csv", 2025)
        self.assertEqual((len(acc), len(part), int(acc.deaths.sum())), (1, 2, 1))
        self.assertEqual(int(acc.hour.iloc[0]), 3)
        self.assertEqual(acc.datetime.iloc[0].minute, 35)

    def test_same_place_time_two_cases_survive(self):
        records=[row(1, "25"), row(2, "30"), row(1, "45"), row(2, "50")]
        acc, part, audit=build_tables(pd.DataFrame(records), "fixture.csv", 2025)
        self.assertEqual(len(acc),2)
        self.assertEqual(len(part),4)
        self.assertEqual(audit["same_key_split_groups"],1)
        self.assertEqual(sorted(part.groupby("accident_id").size().tolist()),[2,2])

    def test_repeated_ordinal_keeps_distinct_passenger(self):
        records=[row(1), row(2,"68"), row(2,"22", **{"當事者區分-類別-大類別名稱-車種":"人","當事者區分-類別-子類別名稱-車種":"乘客"})]
        acc, part, audit=build_tables(pd.DataFrame(records), "fixture.csv", 2025)
        self.assertEqual((len(acc),len(part)),(1,3))
        self.assertTrue(part.participant_id.is_unique)
        self.assertEqual(audit["ordinal_repeated_rows"],2)
        self.assertIn("乘客",part.vehicle_type.tolist())

    def test_shared_casualty_conflict_stops_output(self):
        records=[row(1),row(2, **{"死亡受傷人數":"死亡2;受傷0"})]
        with self.assertRaisesRegex(ValueError,"conflicting shared fields"):
            build_tables(pd.DataFrame(records), "fixture.csv",2025)

    def test_bad_map_or_time_does_not_remove_case(self):
        acc,part,_=build_tables(pd.DataFrame([row(1,**{"經度":"999","發生時間":"250000"})]),"fixture.csv",2025)
        self.assertEqual((len(acc),len(part)),(1,1))
        self.assertFalse(bool(acc.coordinate_valid.iloc[0]))
        self.assertFalse(bool(acc.time_valid.iloc[0]))
        self.assertTrue(bool(acc.date_valid.iloc[0]))

    def test_age_zero_nonperson_and_extremes(self):
        age=clean_age(pd.Series(["0","0","-1","210","114","25","30"]),pd.Series(["女","無或物(動物、堆置物)","男","男","女","肇事逃逸尚未查獲","男"]))
        self.assertEqual(age.age_valid.tolist(),[True,False,False,False,True,False,True])
        self.assertEqual(age.age_invalid_reason.iloc[1],"non_person")
        self.assertEqual(int(age.age.iloc[0]),0)
        self.assertTrue(bool(age.age_review_required.iloc[4]))

    def test_physical_location_precedes_police_and_conflict_is_visible(self):
        frame=pd.DataFrame([row(**{"發生地點":"台北市測試路", "處理單位名稱警局層":"新北市政府警察局"})])
        region,location,police=regions(frame)
        self.assertEqual(region.iloc[0],"臺北市")
        self.assertNotEqual(location.iloc[0],police.iloc[0])

    def test_unmanned_vehicle_keeps_vehicle_involvement(self):
        record=row(1,"-1","無人駕駛自動車",**{"當事者區分-類別-大類別名稱-車種":"小客車(含客、貨兩用)"})
        acc,part,_=build_tables(pd.DataFrame([record]),"fixture.csv",2025)
        self.assertEqual(part.vehicle_type.iloc[0],"小客車")
        self.assertFalse(bool(part.is_person.iloc[0]))
        self.assertFalse(bool(part.age_valid.iloc[0]))


class HistogramTests(unittest.TestCase):
    def setUp(self):
        self.frame=pd.DataFrame({"age":pd.Series([0,4,5,9,10,120,pd.NA],dtype="Int16"),"age_valid":[True]*6+[False],"is_person":[True]*7})

    def test_bin_edges_and_totals_match_for_both_widths(self):
        for width in (5,10):
            hist,counts=summarize_ages(self.frame,width)
            self.assertEqual(int(hist["count"].sum()),6)
            self.assertEqual(counts["valid_age_records"],6)
            self.assertEqual(int(hist.loc[hist.age_start.eq(120),"count"].iloc[0]),1)

    def test_review_filter_updates_denominator(self):
        hist,counts=summarize_ages(self.frame,5,True)
        self.assertEqual(counts["review_excluded"],2)
        self.assertEqual(int(hist["count"].sum()),4)

    def test_empty_input_has_no_chart_rows(self):
        hist,counts=summarize_ages(self.frame.iloc[:0],5)
        self.assertTrue(hist.empty)
        self.assertEqual(counts["valid_age_records"],0)


if __name__ == "__main__":
    unittest.main()
