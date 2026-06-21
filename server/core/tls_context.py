import ssl
from server.config.server_config import SERVER_CERT, SERVER_KEY, CA_CERT

def create_tls_context():

    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)

    context.verify_mode = ssl.CERT_REQUIRED

    context.load_cert_chain(
        certfile=SERVER_CERT,
        keyfile=SERVER_KEY
    )

    context.load_verify_locations(CA_CERT)

    return context
