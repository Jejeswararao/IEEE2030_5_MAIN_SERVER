from http.server import HTTPServer, BaseHTTPRequestHandler
import logging
from server.core.router import route_request

class IEEEHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        logging.info("GET request from %s -> %s", self.client_address[0], self.path)
        route_request(self, "GET")

    def do_POST(self):
        logging.info("POST request from %s -> %s", self.client_address[0], self.path)
        route_request(self, "POST")

    def do_PUT(self):
        logging.info("PUT request from %s -> %s", self.client_address[0], self.path)
        route_request(self, "PUT")

    def log_message(self, format, *args):
        logging.info("%s - %s", self.client_address[0], format % args)
