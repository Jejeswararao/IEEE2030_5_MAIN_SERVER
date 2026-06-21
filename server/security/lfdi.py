import hashlib

def generate_lfdi(cert_bin):

    digest = hashlib.sha256(cert_bin).hexdigest()
    return digest[:40].upper()


def generate_sfdi(lfdi):

    numeric = int(lfdi, 16)
    return str(numeric)[-9:]
	
