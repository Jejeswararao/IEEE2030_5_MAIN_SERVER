def handle_der(handler, device_id):

    xml = f"""<?xml version="1.0"?>
<DER xmlns="urn:ieee:std:2030.5:ns">
  <DERProgramListLink>/derp</DERProgramListLink>
</DER>
"""

    handler.send_response(200)
    handler.send_header("Content-Type", "application/sep+xml")
    handler.end_headers()
    handler.wfile.write(xml.encode())
