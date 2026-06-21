import hashlib

def generate_lfdi(cert_pem: str) -> str:
    return hashlib.sha256(cert_pem.encode()).hexdigest()[:32].upper()

def generate_sfdi(lfdi: str) -> str:
    return lfdi[-8:]
