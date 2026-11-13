from rearm.types import Damage, Params, Settings


def damaged_params(params: Params, damage: Damage, config: Settings) -> Params:
    """Pure damage construction; the controller alone applies it to a simulator."""
    if damage.kind == "combination":
        for part in damage.components:
            params = damaged_params(params, part, config)
        return params
    mapping = {"j1": "delta1", "j2": "delta2", "extension": "e", "base_x": "x_b",
               "base_y": "y_b", "base_rotation": "psi_b"}
    if damage.kind in ("weight", "loose", "restore"):
        return params
    if damage.kind not in mapping:
        raise ValueError(f"unknown damage {damage.kind}")
    name = mapping[damage.kind]
    amount = damage.amount * config.sim["gear_step_deg"] if damage.kind in ("j1", "j2") else damage.amount
    value = getattr(params, name) + amount
    lo, hi = config.bounds[name]
    if not lo <= value <= hi:
        raise ValueError(f"damage exceeds {name} bounds")
    return params.updated({name: value})
