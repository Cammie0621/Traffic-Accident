"""全站共用的圖表配色與樣式常數。"""

PRIMARY_COLOR = "#2B6CB0"

# A1 / A2 固定配色（全站圖表與地圖共用）
ACCIDENT_TYPE_COLORS = {
    "A1": "#E53E3E",  # 紅色：死亡事故
    "A2": "#DD6B20",  # 橘色：受傷事故
}

ACCIDENT_TYPE_DOMAIN = ["A1", "A2"]
ACCIDENT_TYPE_RANGE = [
    ACCIDENT_TYPE_COLORS["A1"],
    ACCIDENT_TYPE_COLORS["A2"],
]