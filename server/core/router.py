from urllib.parse import urlparse
from server.function_sets.mup import handle_mup
from server.function_sets.der_control import handle_derc_list

# NEW LEVEL-2 IMPORTS
from server.function_sets.dcap import handle_dcap
from server.function_sets.end_device import handle_end_device
from server.function_sets.der import handle_der
from server.function_sets.der_program import handle_der_program

# ✅ NEW IMPORT (ADD THIS)
from server.function_sets.mup_read import handle_get_mup


def route_request(handler, method):

    parsed = urlparse(handler.path)
    path = parsed.path
    parts = path.strip("/").split("/")

    # -------------------------------------------------
    # EXISTING ROUTES (DO NOT REMOVE)
    # -------------------------------------------------

    if path == "/mup" and method == "POST":
        return handle_mup(handler)

    if len(parts) == 3 and parts[0] == "derp" and parts[2] == "derc":
        # /derp/<program_id>/derc
        return handle_derc_list(handler, parts[1])

    # -------------------------------------------------
    # ✅ NEW ROUTE (ADD HERE)
    # -------------------------------------------------

    if path == "/mup_read" and method == "GET":
        return handle_get_mup(handler)

    # -------------------------------------------------
    # LEVEL-2 IEEE 2030.5 ROUTES (ADDED)
    # -------------------------------------------------

    # -------- Device Capability --------
    if path == "/dcap" and method == "GET":
        return handle_dcap(handler)

    # -------- End Device --------
    if len(parts) == 2 and parts[0] == "edev":
        # /edev/<id>
        return handle_end_device(handler, parts[1])

    # -------- DER under EndDevice --------
    if len(parts) == 3 and parts[0] == "edev" and parts[2] == "der":
        # /edev/<id>/der
        return handle_der(handler, parts[1])

    # -------- DER Program List --------
    if path == "/derp" and method == "GET":
        return handle_der_program(handler)

    # -------------------------------------------------
    # DEFAULT RESPONSE
    # -------------------------------------------------

    handler.send_response(404)
    handler.end_headers()
