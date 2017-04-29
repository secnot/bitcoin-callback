"""
generate_keys:

ECDSA key generation helper functions
"""
import os.path
import ecdsa

def safe_save(path, content):
    """Check file file doesn't exist before saving"""
    # Check if file already exists before saving
    if os.path.exists(path):
        raise ValueError("File {} already exists".format(path))

    with open(path, 'wb') as dest_file:
        dest_file.write(content)


if __name__ == '__main__':

    # Private key
    sign_k = ecdsa.SigningKey.generate(curve=ecdsa.SECP256k1)
    safe_save('private.pem', sign_k.to_pem())

    # Public key
    ver_k = sign_k.get_verifying_key()
    safe_save('public.pem', ver_k.to_pem())


