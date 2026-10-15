"""Annual cost of a step, from explicit and inspectable inputs.

annual = runs_per_year x ( sum(material qty x ERP price)
                          + labour min / 60 x labour rate
                          + energy kWh x energy price
                          + disperser min / 60 x occupancy rate
                          + holding h x holding-tank rate
                          + nitrogen m3 x N2 price
                          + waste solvent L x disposal price )
"""

from __future__ import annotations

from . import archive


def runs_per_year(step: dict) -> tuple[float, str]:
    pp = archive.plant_parameters()
    vol = pp["volumes"]
    basis = step.get("runs_basis")
    if basis == "winter":
        base = vol[step["process"]]["per_year"]
        return base * vol["winter_fraction"], f"{base:,} batches x winter share {vol['winter_fraction']:.0%}"
    if basis == "pigment_lots":
        return vol["pigment_lots_per_year"], "incoming pigment lots/yr"
    if basis == "pigment_additions":
        return vol["pigment_additions_per_year"], "pigment additions/yr"
    if basis in ("ALK", "EPX", "TNK", "SOL"):
        return vol[basis]["per_year"], vol[basis]["label"]
    v = vol[step["process"]]
    return v["per_year"], v["label"]


def step_cost(step: dict) -> dict:
    pp = archive.plant_parameters()
    mats = archive.materials()
    lines = []
    for m in step.get("materials", []):
        info = mats.get(m["code"])
        if not info:
            continue
        lines.append({"label": info["name"], "qty": m["qty"], "unit": info["unit"], "unit_cost": info["price_eur"],
                      "amount": m["qty"] * info["price_eur"], "source": f"ERP price list {m['code']}"})

    def add(label, qty, unit, rate, src):
        if qty:
            lines.append({"label": label, "qty": qty, "unit": unit, "unit_cost": rate, "amount": qty * rate, "source": src})

    add("Labour", step.get("labor_min", 0) / 60, "h", pp["labor_rate_eur_per_h"], "plant parameters: labour rate")
    add("Energy", step.get("energy_kwh", 0), "kWh", pp["energy_price_eur_per_kwh"], "plant parameters: energy price")
    add("Disperser occupancy", step.get("disperser_min", 0) / 60, "h", pp["disperser_occupancy_eur_per_h"],
        "plant parameters: occupancy rate")
    add("Holding tank", step.get("holding_h", 0), "h", pp["holding_tank_eur_per_h"], "plant parameters: holding tank rate")
    add("Nitrogen", step.get("nitrogen_m3", 0), "m3", pp["nitrogen_eur_per_m3"], "plant parameters: N2 price")
    add("Waste solvent disposal", step.get("waste_solvent_l", 0), "l", pp["solvent_disposal_eur_per_l"],
        "plant parameters: disposal price")
    per_run = sum(x["amount"] for x in lines)
    runs, basis = runs_per_year(step)
    for x in lines:
        x["amount"] = round(x["amount"], 2)
    return {
        "per_run_eur": round(per_run, 2), "runs_per_year": round(runs), "basis": basis,
        "annual_eur": round(per_run * runs), "lines": lines,
        "formula": "annual = runs/yr x (materials + labour + energy + occupancy + holding + N2 + disposal)",
        "source": pp.get("source", "plant parameters"),
    }
