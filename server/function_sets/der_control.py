import logging
import time
from server.database.database import query, execute
from server.control_engine.control_logic import generate_der_control


def handle_derc_list(handler, program_id):
    result = generate_der_control(program_id)

    if not result:
        handler.send_response(204)
        handler.end_headers()
        return

    mrid = result["mrid"]
    qset = result["qset"]
    pset = result["pset"]
    target_phase = result["target_phase"]

    control_xml = ""

    if qset is not None:
        control_xml += f"""
        <opModFixedVar>
            <value>{qset}</value>
        </opModFixedVar>
        """

    if pset is not None:
        control_xml += f"""
        <opModFixedW>
            <value>{pset}</value>
        </opModFixedW>
        """

    control_xml += f"""
        <DERControlExt>
            <targetPhase>{target_phase}</targetPhase>
        </DERControlExt>
    """

    now = int(time.time())

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<DERControlList xmlns="urn:ieee:std:2030.5:ns">
  <DERControl>
    <mRID>{mrid}</mRID>
    <creationTime>{now}</creationTime>
    <interval>
      <start>{now}</start>
      <duration>300</duration>
    </interval>
    <DERControlBase>
      {control_xml}
    </DERControlBase>
  </DERControl>
</DERControlList>
"""

    logging.info("DER control setpoints: P=%s Q=%s", pset, qset)

    handler.send_response(200)
    handler.send_header("Content-Type", "application/sep+xml")
    handler.end_headers()
    handler.wfile.write(xml.encode())
