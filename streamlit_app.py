def residual_wtp_adjustment(
    g1_structural: bool,
    g2_decision_impact: bool,
    g3_non_probabilistic: bool,
    headroom_percent: float,
    scenario_flip: bool,
    scenario_spread_percent: float
):
    # Gatekeeper: no adjustment unless G1+G2+G3
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
