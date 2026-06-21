from server.database.database import query

def handle_get_mup(handler):

    row = query(
        "SELECT * FROM mup_log ORDER BY id DESC LIMIT 1",
        one=True
    )

    if not row:
        handler.send_response(204)
        handler.end_headers()
        return

    xml = f"""
    <Metering>
        <voltage_a>{row['voltage_a']}</voltage_a>
        <voltage_b>{row['voltage_b']}</voltage_b>
        <voltage_c>{row['voltage_c']}</voltage_c>

        <power_a>{row['power_a']}</power_a>
        <power_b>{row['power_b']}</power_b>
        <power_c>{row['power_c']}</power_c>

        <reactive_a>{row['reactive_a']}</reactive_a>
        <reactive_b>{row['reactive_b']}</reactive_b>
        <reactive_c>{row['reactive_c']}</reactive_c>

        <frequency>{row['frequency']}</frequency>
    </Metering>
    """
    handler.send_response(200)
    handler.send_header("Content-Type", "application/xml")
    handler.end_headers()
    handler.wfile.write(xml.encode())
