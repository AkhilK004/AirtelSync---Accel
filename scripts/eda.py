import sys; sys.path.insert(0, ".")
import pandas as pd, numpy as np
from app.data.loaders import get_data
D = get_data(); L = D.leads.copy()
pd.set_option("display.width", 200); pd.set_option("display.max_columns", 30)
def rate(g, col="activated"): return g.groupby(col if isinstance(col,str) else col)["activated"].agg(["size","mean"]).round(3) 
for c in ["segment","city_tier","lead_source","has_gstin","has_udyam","preferred_language","current_internet","num_sites"]:
    print("\n##",c); print(L.groupby(c)["activated"].agg(["size","mean"]).round(3).to_string())
L["emp_band"]=pd.cut(L.employee_count,[0,2,5,10,25,50,200]); print(L.groupby("emp_band",observed=True)["activated"].agg(["size","mean"]).round(3))
# stage conv by source / segment
order=["Lead","Contacted","Needs assessed","Quote accepted","KYC complete","Activated"]
L["si"]=L.stage_reached.map({s:i for i,s in enumerate(order)})
for c in ["lead_source","segment","has_gstin"]:
    t=pd.DataFrame({f"s{i}":L.groupby(c)["si"].apply(lambda x:(x>=i).sum()) for i in range(6)})
    for i in range(1,6): t[f"c{i}"]=(t[f"s{i}"]/t[f"s{i-1}"]).round(2)
    print("\n## stage conv by",c); print(t[[f"c{i}" for i in range(1,6)]].to_string())
print("\n## drop reasons by stage"); print(pd.crosstab(L.drop_reason,L.stage_reached).to_string())
# quote delay
L["q_delay"]=(L.quote_accepted_date-L.needs_assessed_date).dt.days
L["n_delay"]=(L.needs_assessed_date-L.contacted_date).dt.days
L["c_delay"]=(L.contacted_date-L.created_date).dt.days
print("\n## stage durations (days) mean by outcome"); print(L.groupby("outcome")[["c_delay","n_delay","q_delay"]].mean())
# follow-up calls
print(L.groupby("activated").customer_follow_up_calls.mean())
A=L[L.activated].copy()
print("\n## activated: days,calls,churn,nps by segment"); print(A.groupby("segment").agg(n=("lead_id","size"),days=("days_lead_to_activation","mean"),calls=("customer_follow_up_calls","mean"),val=("monthly_bundle_value_inr","median"),churn=("churned_within_6_months","mean"),nps=("nps_score","mean")).round(2))
for c in ["lead_source","city_tier","has_gstin"]:
    print(A.groupby(c).agg(n=("lead_id","size"),churn=("churned_within_6_months","mean"),nps=("nps_score","mean"),days=("days_lead_to_activation","mean")).round(2))
# bundle-fit: bundle skus vs catalogue target segments
seg_map={"Micro retail & services":"micro","Professional offices":"prof","Small multi-site businesses":"multi","Small manufacturers":"mfg"}
prod=D.products
def fit(r):
    skus=[x.split("x")[0] for x in r.bundle_products.split(";")]
    return np.mean([seg_map[r.segment] in prod[s].target_segments for s in skus])
A["fit"]=A.apply(fit,axis=1); A["fit_band"]=pd.cut(A.fit,[-.01,.5,.99,1],labels=["<=50%","50-99%","100%"])
print("\n## bundle-fit vs churn/nps"); print(A.groupby("fit_band",observed=True).agg(n=("fit","size"),churn=("churned_within_6_months","mean"),nps=("nps_score","mean")).round(3))
A["nskus"]=A.bundle_products.str.count(";")+1
A["has_conn"]=A.bundle_products.str.contains(r"P0[1-6]x|P10x")
print(A.groupby("nskus").agg(n=("fit","size"),churn=("churned_within_6_months","mean"),nps=("nps_score","mean")).round(3))
# per-sku churn
rows=[]
for r in A.itertuples():
    for s in r.bundle_products.split(";"): rows.append((s.split("x")[0],r.churned_within_6_months,r.nps_score))
S=pd.DataFrame(rows,columns=["sku","ch","nps"]).groupby("sku").agg(n=("ch","size"),churn=("ch","mean"),nps=("nps","mean")).round(3); print(S.sort_values("churn",ascending=False).head(8))
# interest vs bought; mis-pitch
L["interest_first"]=L.products_of_interest.str.split(";").str[0]
print("\n## mobile-only drop by segment"); print(pd.crosstab(L.segment,L.drop_reason=="Only wanted a mobile plan",normalize="index").round(3))
print(pd.crosstab(L.drop_reason,L.lead_source).loc[["Price too high","Quote too complex to understand","Quote took too long to arrive","Visit not scheduled by sales","Unreachable after 3 attempts","Wrong or invalid number"]])
# GSTIN registry status
m=L.merge(pd.DataFrame([r.model_dump() for r in D.gstin.values()])[["gstin","status"]],on="gstin",how="left")
print("\n## gstin status"); print(m.groupby(m.status.fillna("none")).activated.agg(["size","mean"]).round(3))
print(pd.crosstab(m.status.fillna("none"),m.drop_reason.fillna("-")).T.sort_values("Cancelled",ascending=False).head(6))
# telecom spend, turnover
print(L.groupby("annual_turnover_band").activated.agg(["size","mean"]).round(3))
L["spend_q"]=pd.qcut(L.monthly_telecom_spend_inr,5,duplicates="drop"); print(L.groupby("spend_q",observed=True).activated.agg(["size","mean"]).round(3))
# dq
print("\n## dq: activated with churn flag nulls", A.churned_within_6_months.isna().sum(), "| bundle-value<=0", (A.monthly_bundle_value_inr<=0).sum(), "| nps range",A.nps_score.min(),A.nps_score.max())
print("dup business_name", L.business_name.duplicated().sum(), "| dup phone n/a | CAC by source"); print(L.groupby("lead_source").acquisition_cost_inr.agg(["mean","sum"]).round(0)); print((L.groupby("lead_source").acquisition_cost_inr.sum()/L.groupby("lead_source").activated.sum()).round(0))
# gstin requires products in bundles of no-gstin
