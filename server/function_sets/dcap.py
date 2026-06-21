def handle_dcap(handler):

    xml = """<?xml version="1.0"?>
<DeviceCapability xmlns="urn:ieee:std:2030.5:ns">
  <selfDeviceLink>/edev/1</selfDeviceLink>
  <endDeviceListLink>/edev</endDeviceListLink>
  <timeLink>/time</timeLink>
  <functionSetAssignmentsListLink>/fsa</functionSetAssignmentsListLink>
</DeviceCapability>
"""

    handler.send_response(200)
    handler.send_header("Content-Type", "application/sep+xml")
    handler.end_headers()
    handler.wfile.write(xml.encode())
