def handle_der_program(handler):

    xml = """<?xml version="1.0"?>
<DERProgramList xmlns="urn:ieee:std:2030.5:ns">
  <DERProgram>
    <mRID>DERP1</mRID>
    <DERControlListLink>/derp/1/derc</DERControlListLink>
  </DERProgram>
</DERProgramList>
"""

    handler.send_response(200)
    handler.send_header("Content-Type", "application/sep+xml")
    handler.end_headers()
    handler.wfile.write(xml.encode())
