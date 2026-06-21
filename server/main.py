from server.core.http_server import HTTPServer, IEEEHandler
from server.core.tls_context import create_tls_context
from server.control_engine.control_logic import evaluate_and_create_event
from server.utils.runtime_logger import setup_runtime_logger
import threading
import time

HOST = "0.0.0.0"
PORT = 8443
logger = setup_runtime_logger()

def background_control_loop():
    while True:
        evaluate_and_create_event()
        time.sleep(5)

threading.Thread(target=background_control_loop, daemon=True).start()

httpd = HTTPServer((HOST, PORT), IEEEHandler)
httpd.socket = create_tls_context().wrap_socket(httpd.socket, server_side=True)
logger.info("IEEE 2030.5 SERVER RUNNING")
logger.info("PORT: %s", PORT)
logger.info("Mutual TLS ENABLED")
logger.info("Waiting for DER devices...")
httpd.serve_forever()
