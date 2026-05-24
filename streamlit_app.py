import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px


# -----------------------------
# Page setup
# -----------------------------
st.set_page_config(
    page_title="Residual Uncertainty and WTP Adjustment Tool",
    layout="wide"
)

st.title("Residual Uncertainty and WTP Adjustment Tool")
st.markdown(
    """
This tool explores how residual uncertainty can affect effective willingness-to-pay (WTP) 
using scenario ICER curves, headroom, decision flips, and a capped WTP adjustment.
"""
)


# -----------------------------
# Core functions
# -----------------------------
def calculate_icer(delta_cost, delta_qaly):
    if delta_qaly <= 0:
        return np.inf
    return delta_cost / delta_qaly


def residual_wtp_adjustment(
    g1_structural: bool,
    g2_decision_impact: bool,
    g3_non_probabilistic: bool,
    headroom_percent: float,
    scenario_flip: bool,
    scenario_spread_percent: float
):
    """
    Returns:
    u: uncertainty adjustment as decimal
    message: interpretation text
    """

    # Gatekeeper: no adjustment unless G1 + G2 + G3 are all satisfied
    if not (g1_structural and g2_decision_impact and g3_non_probabilistic):
        return 0.0, "No WTP adjustment: G1-G3 not fully satisfied"

    # Residual uncertainty classification
    if scenario_flip and headroom_percent < 2:
        return 0.10, "High residual uncertainty: apply up to 10% WTP reduction"

    if scenario_flip and headroom_percent < 5:
        return 0.075, "Moderate-high residual uncertainty: apply 5-7.5% WTP reduction"

    if scenario_spread_percent > 25 and headroom_percent < 10:
        return 0.05, "Moderate residual uncertainty: apply up to 5% WTP reduction"

    return 0.0, "No additional WTP adjustment: sufficient headroom or limited residual uncertainty"


def run_scenario_curves(
    list_intervention_cost,
    comparator_cost,
    scenarios,
    wtp,
    discounts
):
    rows = []

    for d in discounts:
        net_intervention_cost = list_intervention_cost * (1 - d)

        for scenario_name, values in scenarios.items():
            delta_qaly = values["delta_qaly"]
            non_drug_cost = values["non_drug_cost"]

            total_intervention_cost = net_intervention_cost + non_drug_cost
            delta_cost = total_intervention_cost - comparator_cost
            icer = calculate_icer(delta_cost, delta_qaly)

            rows.append({
                "discount": d,
                "discount_percent": d * 100,
                "scenario": scenario_name,
                "net_intervention_cost": net_intervention_cost,
                "total_intervention_cost": total_intervention_cost,
                "delta_cost": delta_cost,
                "delta_qaly": delta_qaly,
                "icer": icer,
                "cost_effective": icer <= wtp
            })

    return pd.DataFrame(rows)


def classify_by_discount(df, wtp):
    summary = []

    for d, group in df.groupby("discount"):
        min_icer = group["icer"].min()
        max_icer = group["icer"].max()

        base_rows = group[group["scenario"] == "Base case"]

        if base_rows.empty:
            base_icer = group["icer"].iloc[0]
        else:
            base_icer = base_rows["icer"].iloc[0]

        any_ce = group["cost_effective"].any()
        all_ce = group["cost_effective"].all()
        decision_flip = any_ce and not all_ce

        headroom_percent = ((wtp - base_icer) / wtp) * 100
        scenario_spread_percent = ((max_icer - min_icer) / wtp) * 100

        if base_icer > wtp:
            status = "Not cost-effective"
        elif decision_flip and headroom_percent < 5:
            status = "Residual uncertainty remains"
        elif decision_flip and headroom_percent >= 5:
            status = "Partly covered by price headroom"
        elif all_ce and headroom_percent >= 10:
            status = "Uncertainty likely internalised by price"
        elif all_ce and headroom_percent < 10:
            status = "Cost-effective but limited headroom"
        else:
            status = "Unclear"

        summary.append({
            "discount": d,
            "discount_percent": d * 100,
            "base_icer": base_icer,
            "min_scenario_icer": min_icer,
            "max_scenario_icer": max_icer,
            "decision_flip": decision_flip,
            "headroom_percent": headroom_percent,
            "scenario_spread_percent": scenario_spread_percent,
            "status": status
        })

    return pd.DataFrame(summary)


def first_discount_where(summary_df, condition):
    selected = summary_df[condition(summary_df)]

    if selected.empty:
        return None

    return selected.sort_values("discount").iloc[0]


# -----------------------------
# Sidebar inputs
# -----------------------------
st.sidebar.header("Model inputs")

wtp_m = st.sidebar.number_input(
    "Magnussen/severity-adjusted WTP (NOK/QALY)",
    min_value=1,
    value=500000,
    step=50000
)

list_intervention_cost = st.sidebar.number_input(
    "List intervention cost",
    min_value=0,
    value=1000000,
    step=50000
)

comparator_cost = st.sidebar.number_input(
    "Comparator cost",
    min_value=0,
    value=100000,
    step=25000
)

selected_discount_percent = st.sidebar.slider(
    "Selected discount for assessment (%)",
    min_value=0,
    max_value=95,
    value=80,
    step=1
)

selected_discount = selected_discount_percent / 100


st.sidebar.header("G1-G3 gatekeeper")

g1_structural = st.sidebar.checkbox(
    "G1: Structural uncertainty exists",
    value=True
)

g2_decision_impact = st.sidebar.checkbox(
    "G2: Decision impact / decision flip possible",
    value=True
)

g3_non_probabilistic = st.sidebar.checkbox(
    "G3: Cannot credibly assign probabilities",
    value=True
)


st.sidebar.header("Scenario QALY inputs")

base_qaly = st.sidebar.number_input(
    "Base case incremental QALYs",
    min_value=0.01,
    value=1.80,
    step=0.10
)

conservative_qaly = st.sidebar.number_input(
    "Conservative scenario incremental QALYs",
    min_value=0.01,
    value=1.20,
    step=0.10
)

waning_qaly = st.sidebar.number_input(
    "Treatment waning scenario incremental QALYs",
    min_value=0.01,
    value=1.00,
    step=0.10
)

optimistic_qaly = st.sidebar.number_input(
    "Optimistic scenario incremental QALYs",
    min_value=0.01,
    value=2.40,
    step=0.10
)


st.sidebar.header("Scenario non-drug costs")

base_non_drug_cost = st.sidebar.number_input(
    "Base case non-drug cost",
    value=0,
    step=10000
)

conservative_non_drug_cost = st.sidebar.number_input(
    "Conservative scenario non-drug cost",
    value=0,
    step=10000
)

waning_non_drug_cost = st.sidebar.number_input(
    "Waning scenario non-drug cost",
    value=0,
    step=10000
)

optimistic_non_drug_cost = st.sidebar.number_input(
    "Optimistic scenario non-drug cost",
    value=0,
    step=10000
)


# -----------------------------
# Scenario structure
# -----------------------------
scenarios = {
    "Base case": {
        "delta_qaly": base_qaly,
        "non_drug_cost": base_non_drug_cost
    },
    "Conservative structural scenario": {
        "delta_qaly": conservative_qaly,
        "non_drug_cost": conservative_non_drug_cost
    },
    "Treatment waning scenario": {
        "delta_qaly": waning_qaly,
        "non_drug_cost": waning_non_drug_cost
    },
    "Optimistic scenario": {
        "delta_qaly": optimistic_qaly,
        "non_drug_cost": optimistic_non_drug_cost
    }
}


discounts = np.arange(0, 0.96, 0.01)

df = run_scenario_curves(
    list_intervention_cost=list_intervention_cost,
    comparator_cost=comparator_cost,
    scenarios=scenarios,
    wtp=wtp_m,
    discounts=discounts
)

summary_df = classify_by_discount(df, wtp_m)


# -----------------------------
# Selected discount assessment
# -----------------------------
selected_row = summary_df.iloc[
    (summary_df["discount"] - selected_discount).abs().argsort()[:1]
].iloc[0]

u, message = residual_wtp_adjustment(
    g1_structural=g1_structural,
    g2_decision_impact=g2_decision_impact,
    g3_non_probabilistic=g3_non_probabilistic,
    headroom_percent=selected_row["headroom_percent"],
    scenario_flip=selected_row["decision_flip"],
    scenario_spread_percent=selected_row["scenario_spread_percent"]
)

effective_wtp = wtp_m * (1 - u)


# -----------------------------
# Main dashboard
# -----------------------------
st.header("1. Selected discount assessment")

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Selected discount",
    f"{selected_discount_percent:.0f}%"
)

col2.metric(
    "Base-case ICER",
    f"{selected_row['base_icer']:,.0f} NOK/QALY"
)

col3.metric(
    "Headroom",
    f"{selected_row['headroom_percent']:.1f}%"
)

col4.metric(
    "Effective WTP",
    f"{effective_wtp:,.0f} NOK/QALY"
)


col5, col6, col7 = st.columns(3)

col5.metric(
    "Scenario spread",
    f"{selected_row['scenario_spread_percent']:.1f}% of WTP"
)

col6.metric(
    "Residual adjustment",
    f"{u:.1%}"
)

col7.metric(
    "Decision flip",
    "Yes" if selected_row["decision_flip"] else "No"
)


if u > 0:
    st.warning(message)
else:
    st.success(message)


st.markdown(
    f"""
**Interpretation at selected discount:**  
At a **{selected_discount_percent:.0f}% discount**, the base-case ICER is 
**{selected_row['base_icer']:,.0f} NOK/QALY** compared with a Magnussen/severity-adjusted WTP of 
**{wtp_m:,.0f} NOK/QALY**.  

The estimated headroom is **{selected_row['headroom_percent']:.1f}%**.  
The scenario spread is **{selected_row['scenario_spread_percent']:.1f}% of WTP**.  
"""
)


# -----------------------------
# Scenario ICER curve
# -----------------------------
st.header("2. Scenario ICER curves across discounts")

plot_df = df.copy()
plot_df = plot_df[np.isfinite(plot_df["icer"])]

fig = px.line(
    plot_df,
    x="discount_percent",
    y="icer",
    color="scenario",
    title="Scenario ICER curves across discount levels",
    labels={
        "discount_percent": "Discount from list price (%)",
        "icer": "ICER (NOK/QALY)",
        "scenario": "Scenario"
    }
)

fig.add_hline(
    y=wtp_m,
    line_dash="dash",
    annotation_text=f"WTP = {wtp_m:,.0f}",
    annotation_position="top left"
)

fig.add_hline(
    y=effective_wtp,
    line_dash="dot",
    annotation_text=f"Effective WTP = {effective_wtp:,.0f}",
    annotation_position="bottom left"
)

fig.update_yaxes(range=[0, wtp_m * 4])

st.plotly_chart(fig, use_container_width=True)


# -----------------------------
# Price anchors
# -----------------------------
st.header("3. Price and discount anchors")

ordinary_threshold = first_discount_where(
    summary_df,
    lambda x: x["base_icer"] <= wtp_m
)

all_scenarios_threshold = first_discount_where(
    summary_df,
    lambda x: x["max_scenario_icer"] <= wtp_m
)

headroom_5 = first_discount_where(
    summary_df,
    lambda x: x["base_icer"] <= wtp_m * 0.95
)

headroom_10 = first_discount_where(
    summary_df,
    lambda x: x["base_icer"] <= wtp_m * 0.90
)

robust_threshold = first_discount_where(
    summary_df,
    lambda x: (x["max_scenario_icer"] <= wtp_m) & (x["headroom_percent"] >= 10)
)


def show_anchor(row):
    if row is None:
        return "Not reached"
    return f"{row['discount_percent']:.1f}%"


a1, a2, a3, a4, a5 = st.columns(5)

a1.metric(
    "Base-case threshold discount",
    show_anchor(ordinary_threshold)
)

a2.metric(
    "All scenarios below WTP",
    show_anchor(all_scenarios_threshold)
)

a3.metric(
    "5% headroom discount",
    show_anchor(headroom_5)
)

a4.metric(
    "10% headroom discount",
    show_anchor(headroom_10)
)

a5.metric(
    "Robust decision discount",
    show_anchor(robust_threshold)
)


st.markdown(
    """
**How to read this:**  

- **Base-case threshold discount**: discount needed for the base case to become cost-effective.  
- **All scenarios below WTP**: discount needed for all included scenarios to fall below WTP.  
- **5% / 10% headroom discount**: discount needed to create a buffer below the WTP threshold.  
- **Robust decision discount**: discount needed for all scenarios to be below WTP and for the base case to have at least 10% headroom.  
"""
)


# -----------------------------
# Summary table by discount
# -----------------------------
st.header("4. Residual uncertainty classification by discount")

display_summary = summary_df.copy()

display_summary["discount_percent"] = display_summary["discount_percent"].round(1)
display_summary["base_icer"] = display_summary["base_icer"].round(0)
display_summary["min_scenario_icer"] = display_summary["min_scenario_icer"].round(0)
display_summary["max_scenario_icer"] = display_summary["max_scenario_icer"].round(0)
display_summary["headroom_percent"] = display_summary["headroom_percent"].round(1)
display_summary["scenario_spread_percent"] = display_summary["scenario_spread_percent"].round(1)

st.dataframe(
    display_summary[
        [
            "discount_percent",
            "base_icer",
            "min_scenario_icer",
            "max_scenario_icer",
            "decision_flip",
            "headroom_percent",
            "scenario_spread_percent",
            "status"
        ]
    ],
    use_container_width=True
)


# -----------------------------
# Scenario-specific table at selected discount
# -----------------------------
st.header("5. Scenario details at selected discount")

selected_scenario_df = df[
    np.isclose(df["discount"], selected_discount, atol=0.005)
].copy()

selected_scenario_df["icer"] = selected_scenario_df["icer"].round(0)
selected_scenario_df["net_intervention_cost"] = selected_scenario_df["net_intervention_cost"].round(0)
selected_scenario_df["delta_cost"] = selected_scenario_df["delta_cost"].round(0)
selected_scenario_df["delta_qaly"] = selected_scenario_df["delta_qaly"].round(3)

st.dataframe(
    selected_scenario_df[
        [
            "scenario",
            "net_intervention_cost",
            "delta_cost",
            "delta_qaly",
            "icer",
            "cost_effective"
        ]
    ],
    use_container_width=True
)


# -----------------------------
# Framework explanation
# -----------------------------
st.header("6. Framework logic")

st.markdown(
    """
### G1-G3 gatekeeper

A downward adjustment of effective WTP is only considered when all three are satisfied:

| Gate | Meaning |
|---|---|
| G1 | Structural uncertainty exists |
| G2 | The uncertainty can change the reimbursement conclusion |
| G3 | The uncertainty cannot be credibly probability-weighted |

If G1-G3 are not all satisfied, the model sets the WTP adjustment to zero.

### Headroom

Headroom is calculated as:

\[
Headroom\\% = \\frac{WTP - ICER_{net}}{WTP}
\]

A low headroom means the decision is close to the threshold and more fragile.

### Scenario spread

Scenario spread is calculated as:

\[
Scenario\\ Spread = \\frac{ICER_{max} - ICER_{min}}{WTP}
\]

A high scenario spread means that different plausible assumptions produce materially different ICERs.

### Residual uncertainty interpretation

Residual uncertainty remains when plausible scenarios cross the WTP threshold, especially when price headroom is limited.
"""
)
