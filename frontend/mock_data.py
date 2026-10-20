"""
Central Market (San Francisco) corridor metadata for Challenge 3:
Community Economic Resilience & Micro-Grants — Track 1: Main Street Relief.

Applicant profiles are NOT hardcoded here; they are loaded dynamically from the
live BigQuery database (`a4i_econ.businesses` / `a4i_econ.CascadeEconomy`) via
`frontend/server.py` (`GET /api/applicants`) only if present in the database.
"""

from typing import Dict, Any, List

CORRIDOR_INFO: Dict[str, Any] = {
    "corridor": "Central Market",
    "city": "San Francisco",
    "dataset": "a4i_econ",
    "graph_name": "a4i_econ.CascadeEconomy",
    "snapshot_date": "2026-08-09",
    "total_businesses": 230,
    "distinct_naics4": 65,
    "suppliers_with_2hop_depth": 86,
    "census_tracts": 7,
    "corridor_poverty_rate": 0.221,
    "corridor_no_vehicle_rate": 0.542,
    "corridor_assistance_rate": 0.148,
    "default_budget": 50000,
    "validation_passed": 18,
    "validation_total": 18,
    "sba_historical_loans": 9,
    "sba_historical_charge_offs": 3,
}

TRACT_DEMOGRAPHICS: Dict[str, Dict[str, Any]] = {
    "06075012501": {
        "geo_id": "06075012501",
        "name": "Census Tract 125.01 (6th & Taylor / Tenderloin Border)",
        "poverty_rate": 0.312,
        "no_vehicle_rate": 0.684,
        "public_assistance_rate": 0.215,
        "median_income": 34200,
    },
    "06075012502": {
        "geo_id": "06075012502",
        "name": "Census Tract 125.02 (Mid-Market / 6th to 8th St)",
        "poverty_rate": 0.284,
        "no_vehicle_rate": 0.635,
        "public_assistance_rate": 0.189,
        "median_income": 41800,
    },
    "06075017601": {
        "geo_id": "06075017601",
        "name": "Census Tract 176.01 (Market & Mission / 7th to 10th St)",
        "poverty_rate": 0.246,
        "no_vehicle_rate": 0.580,
        "public_assistance_rate": 0.162,
        "median_income": 52400,
    },
    "06075017802": {
        "geo_id": "06075017802",
        "name": "Census Tract 178.02 (Mint Plaza / 5th & Mission)",
        "poverty_rate": 0.195,
        "no_vehicle_rate": 0.490,
        "public_assistance_rate": 0.124,
        "median_income": 68900,
    },
    "06075016801": {
        "geo_id": "06075016801",
        "name": "Census Tract 168.01 (Civic Center / Van Ness)",
        "poverty_rate": 0.178,
        "no_vehicle_rate": 0.465,
        "public_assistance_rate": 0.110,
        "median_income": 74500,
    },
}

# Applicant profiles are loaded dynamically from BigQuery only if present there.
APPLICANTS: List[Dict[str, Any]] = []

SBA_CHARGE_OFF_BACKTEST: List[Dict[str, Any]] = [
    {
        "business_id": "ttx-0719201-99",
        "name": "Market Street Poultry & Provisions Inc (Historical Closure)",
        "naics4": "4244",
        "bank_name": "East West Bank",
        "gross_approval": 110000,
        "charged_off": True,
        "charge_off_date": "2024-11-18",
        "model_fragility_retrospective": 0.86,
        "cascade_impact_observed": "2 downstream cafes switched to out-of-city Oakland distributors (+22% delivery cost).",
    },
    {
        "business_id": "ttx-0688120-99",
        "name": "Golden Gate Linen & Uniform Supply LLC (Historical Closure)",
        "naics4": "8123",
        "bank_name": "Wells Fargo Bank, National Association",
        "gross_approval": 75000,
        "charged_off": True,
        "charge_off_date": "2025-02-09",
        "model_fragility_retrospective": 0.78,
        "cascade_impact_observed": "Triggered supply disruption for 3 Mid-Market restaurants & 1 boutique hotel.",
    },
    {
        "business_id": "ttx-0811402-99",
        "name": "7th & Mission Bakery Cooperative (Historical Closure)",
        "naics4": "3118",
        "bank_name": "Self-Help Federal Credit Union",
        "gross_approval": 58000,
        "charged_off": True,
        "charge_off_date": "2025-06-27",
        "model_fragility_retrospective": 0.81,
        "cascade_impact_observed": "3 coffee shops lost local pastry supplier within 300m walking radius.",
    },
]

EQUITY_AUDIT_SUMMARY: Dict[str, Any] = {
    "industry_mix_comparison": [
        {
            "sector": "Food Wholesale, Manufacturing & Cold Chain (NAICS 311 / 424 / 493)",
            "corridor_share_pct": 14.8,
            "naive_cascade_share_pct": 66.7,
            "our_portfolio_share_pct": 68.0,
            "bias_direction": "OVER-REPRESENTED (+53.2%)",
            "explanation": "BEA Input-Output tables record dense B2B transactions for food & manufacturing inputs.",
        },
        {
            "sector": "Restaurants, Cafes & Catering (NAICS 722)",
            "corridor_share_pct": 28.3,
            "naive_cascade_share_pct": 22.2,
            "our_portfolio_share_pct": 16.0,
            "bias_direction": "PROTECTED DOWNSTREAM",
            "explanation": "Stabilized primarily as 1-hop and 2-hop beneficiaries of upstream wholesale grants.",
        },
        {
            "sector": "Personal Services, Barber Shops & Retail Pharmacies (NAICS 812 / 446)",
            "corridor_share_pct": 31.4,
            "naive_cascade_share_pct": 0.0,
            "our_portfolio_share_pct": 16.0,
            "bias_direction": "STRUCTURALLY UNDER-COUNTED BY BEA",
            "explanation": "Sell to the public rather than other businesses (0 outgoing `Supplies` edges). Our UI flags these for a 15% Equity Leaf Carve-Out.",
        },
        {
            "sector": "Commercial Printing, Equipment & Trade Services (NAICS 323 / 444 / 532)",
            "corridor_share_pct": 25.5,
            "naive_cascade_share_pct": 11.1,
            "our_portfolio_share_pct": 0.0,
            "bias_direction": "FILTERED FOR ROBUSTNESS",
            "explanation": "Top printing hub (SoMa Print) was skipped because its SBA 7(a) loan is Paid in Full (low distress).",
        },
    ],
    "tract_need_comparison": {
        "corridor_avg_poverty_pct": 22.1,
        "funded_portfolio_poverty_pct": 27.6,
        "corridor_avg_no_vehicle_pct": 54.2,
        "funded_portfolio_no_vehicle_pct": 61.7,
        "corridor_avg_assistance_pct": 14.8,
        "funded_portfolio_assistance_pct": 18.3,
        "verdict": (
            "PASS ON DEMOGRAPHIC NEED (+5.5% higher poverty reach than corridor baseline), "
            "WARNING ON INDUSTRY MECHANICS (BEA supply edges favor input-heavy wholesalers/roasters over personal services)."
        ),
    },
}

VALIDATION_CHECKS: List[Dict[str, Any]] = [
    {"check": "businesses: at least 60", "status": "PASS", "detail": "230 businesses"},
    {"check": "businesses: keys unique (ttxid)", "status": "PASS", "detail": "230 distinct of 230 (no silent path duplication)"},
    {"check": "businesses: no null keys", "status": "PASS", "detail": "0 null ids"},
    {"check": "businesses: all located", "status": "PASS", "detail": "0 without coordinates"},
    {"check": "businesses: industry spread", "status": "PASS", "detail": "65 distinct NAICS4"},
    {"check": "businesses: geographically tight", "status": "PASS", "detail": "extent 0.021 lat x 0.024 lon degrees"},
    {"check": "supplies: element keys unique", "status": "PASS", "detail": "1,412 distinct edge_ids"},
    {"check": "supplies: no self-loops", "status": "PASS", "detail": "0 self-referencing"},
    {"check": "supplies: endpoints resolve", "status": "PASS", "detail": "0 bad sources, 0 bad destinations"},
    {"check": "supplies: two-hop paths exist", "status": "PASS", "detail": "86 businesses reach someone 2 hops out"},
    {"check": "footfall: worker_share > 0", "status": "PASS", "detail": "0 non-positive allocations"},
    {"check": "tracts: geo_id 11 chars (LPAD)", "status": "PASS", "detail": "7 tracts, leading zero preserved (06075...)"},
    {"check": "tracts: no race columns in model input", "status": "PASS", "detail": "none present (Responsible AI audit compliance)"},
    {"check": "loans: SBA 7(a) real edges present", "status": "PASS", "detail": "9 real loan edges, 3 historical charge-offs"},
]
