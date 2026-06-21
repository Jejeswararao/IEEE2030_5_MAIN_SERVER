import numpy as np

V_NOM = 230.0

# IEEE 1547 Volt-VAR curve
VV_X = [0.92, 0.98, 1.02, 1.08]
VV_Y = [1.0, 0.0, 0.0, -1.0]

# IEEE 1547 Volt-Watt curve
VW_X = [1.06, 1.10, 1.15]
VW_Y = [1.0, 0.8, 0.0]


def pu(v):
    return float(v) / V_NOM


def volt_var(v):
    vpu = pu(v)
    return float(np.interp(vpu, VV_X, VV_Y))


def volt_watt(v):
    vpu = pu(v)
    return float(np.interp(vpu, VW_X, VW_Y))


def select_control_mode(v):
    vpu = pu(v)

    if vpu > 1.10:
        return "VV_VW"
    elif vpu > 1.02 or vpu < 0.98:
        return "VV"
    return "NONE"
