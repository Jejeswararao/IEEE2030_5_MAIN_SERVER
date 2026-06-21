import logging
import time
import xml.etree.ElementTree as ET
from server.database.database import execute
from server.control_engine.control_logic import evaluate_and_create_event

def handle_mup(handler):

    try:
        length = int(handler.headers['Content-Length'])
        body = handler.rfile.read(length)

        logging.info("RAW MUP payload: %s", body)

        root = ET.fromstring(body)

        # ✅ SAFE FLOAT
        def safe(x):
            try:
                return float(x)
            except:
                return 0.0

        # =========================
        # VOLTAGES
        # =========================
        Va = safe(root.findtext(".//voltage_a") or root.findtext(".//{*}voltage_a"))
        Vb = safe(root.findtext(".//voltage_b") or root.findtext(".//{*}voltage_b"))
        Vc = safe(root.findtext(".//voltage_c") or root.findtext(".//{*}voltage_c"))

        # =========================
        # ACTIVE POWER
        # =========================
        Pa = safe(root.findtext(".//power_a") or root.findtext(".//{*}power_a"))
        Pb = safe(root.findtext(".//power_b") or root.findtext(".//{*}power_b"))
        Pc = safe(root.findtext(".//power_c") or root.findtext(".//{*}power_c"))

        # =========================
        # REACTIVE POWER
        # =========================
        Qa = safe(root.findtext(".//reactive_a") or root.findtext(".//{*}reactive_a"))
        Qb = safe(root.findtext(".//reactive_b") or root.findtext(".//{*}reactive_b"))
        Qc = safe(root.findtext(".//reactive_c") or root.findtext(".//{*}reactive_c"))

        # =========================
        # FREQUENCY
        # =========================
        freq = safe(root.findtext(".//frequency") or root.findtext(".//{*}frequency"))

        logging.info(
            "Parsed MUP values: Va=%s Vb=%s Vc=%s Pa=%s Pb=%s Pc=%s Qa=%s Qb=%s Qc=%s frequency=%s",
            Va, Vb, Vc, Pa, Pb, Pc, Qa, Qb, Qc, freq,
        )

        # =========================
        # INSERT INTO DB
        # =========================
        execute("""
        INSERT INTO mup_log (
            voltage_a, voltage_b, voltage_c,
            total_pv_power,
            power_a, power_b, power_c,
            reactive_a, reactive_b, reactive_c,
            frequency
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            Va, Vb, Vc,
            Pa + Pb + Pc,
            Pa, Pb, Pc,
            Qa, Qb, Qc,
            freq
        ))

        # 🔥 CONTROL ENGINE
        evaluate_and_create_event()

        handler.send_response(200)
        handler.end_headers()

    except Exception as e:
        logging.exception("MUP ERROR: %s", e)
        handler.send_response(500)
        handler.end_headers()
