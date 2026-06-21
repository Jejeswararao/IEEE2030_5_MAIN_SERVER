import logging
import time
from server.database.database import query, execute
from server.control_engine.ieee1547_controller import (
    volt_var,
    volt_watt,
    select_control_mode,
)

Q_MAX = 6000
V_MIN = 220.0
V_MAX = 235.0


def _pick_phase_and_voltage(Va, Vb, Vc):
    voltages = [Va, Vb, Vc]
    v_max = max(voltages)
    v_min = min(voltages)
    logging.info("CONTROL ENGINE TRIGGERED")
    logging.info("Va=%s Vb=%s Vc=%s", Va, Vb, Vc)
    if v_max > V_MAX:
        return voltages.index(v_max) + 1, v_max, "OVER_VOLTAGE"

    if v_min < V_MIN:
        return voltages.index(v_min) + 1, v_min, "UNDER_VOLTAGE"

    return None, None, "NONE"


def evaluate_and_create_event():

    rows = query("""
        SELECT voltage_a, voltage_b, voltage_c, total_pv_power
        FROM mup_log
        ORDER BY id DESC LIMIT 1
    """)

    logging.info("Data received: %s", rows)

    if not rows:
        return

    r = rows[0]

    Va = float(r["voltage_a"])
    Vb = float(r["voltage_b"])
    Vc = float(r["voltage_c"])
    P = float(r["total_pv_power"])

    voltages = [Va, Vb, Vc]

    V_max = max(voltages)
    V_min = min(voltages)

    if V_max > 240:
        target_phase = voltages.index(V_max) + 1
        V = V_max
        condition = "OVER_VOLTAGE"

    elif V_min < 220:
        target_phase = voltages.index(V_min) + 1
        V = V_min
        condition = "UNDER_VOLTAGE"

    else:
        logging.info("No control needed")
        return

    logging.info("Target phase: %s", target_phase)
    mode = select_control_mode(V)
    logging.info("Mode: %s", mode)

    if mode == "NONE":
        return

    qset = None
    pset = None

    if mode == "VV":
        qpu = volt_var(V)
        qset = int(qpu * Q_MAX)
        pset = 0

    elif mode == "VV_VW":
        qpu = volt_var(V)
        ppu = volt_watt(V)
        qset = int(qpu * Q_MAX)
        pset = int(P * ppu)

    mrid = f"CTRL{int(time.time())}"

    execute("""
        INSERT INTO der_controls
        (mrid, program_id, created_at, q_set, p_set, target_phase, condition, active)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1)
    """,
        (mrid, 1, int(time.time()), qset, pset, target_phase, condition)
    )

    logging.info("[CONTROL] %s | Phase=%s | Q=%s | P=%s", condition, target_phase, qset, pset)

def generate_der_control(program_id):

    rows = query("""
        SELECT mrid, q_set, p_set, target_phase
        FROM der_controls
        WHERE active=1 AND program_id=?
        ORDER BY id DESC LIMIT 1
    """, (program_id,))

    if not rows:
        return None

    r = rows[0]

    return {
        "mrid": r["mrid"],
        "qset": r["q_set"],
        "pset": r["p_set"],
        "target_phase": r["target_phase"]
    }
