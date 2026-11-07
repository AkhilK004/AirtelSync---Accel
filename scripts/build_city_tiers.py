"""Builds data/derived/city_tiers.json from leads (city -> tier). Run: cd api && python -m uv run python ../scripts/build_city_tiers.py"""
import json, sys
sys.path.insert(0, ".")
from app.data.loaders import get_data
d = get_data().leads.groupby("city").city_tier.agg(lambda s: int(s.iloc[0])).to_dict()
json.dump(d, open("../data/derived/city_tiers.json", "w"), indent=1)
print(len(d), "cities")
