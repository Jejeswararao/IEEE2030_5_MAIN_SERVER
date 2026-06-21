def handle_end_device(handler, device_id):

    xml = f"""<?xml version="1.0"?>
<EndDevice xmlns="urn:ieee:std:2030.5:ns">
  <sFDI>111111111111</sFDI>
  <lFDI>AAAAAAAAAAAAAAAAAAAA</lFDI>
  <DERListLink>/edev/{device_id}/der</DERListLink>
</EndDevice>
"""

    handler.send_response(200)
    handler.send_header("Content-Type", "application/sep+xml")
    handler.end_headers()
    handler.wfile.write(xml.encode())
