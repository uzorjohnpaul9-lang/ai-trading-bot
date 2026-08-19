"""
Generate RSA Key Pair for Binance API
======================================
Run this once to generate keys for Binance authentication.
"""
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
import os

def generate_keys():
    # Generate RSA private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )

    # Get public key in PEM format (this is what you paste into Binance)
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()

    # Get private key in PEM format (save to file, never share)
    private_key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode()

    # Save private key to file
    key_dir = os.path.dirname(os.path.abspath(__file__))
    private_key_path = os.path.join(key_dir, "binance_private_key.pem")
    with open(private_key_path, "w") as f:
        f.write(private_key_pem)

    print("=" * 60)
    print("  RSA Key Pair Generated!")
    print("=" * 60)
    print()
    print("  STEP 1: Copy this PUBLIC KEY and paste it into Binance API Management:")
    print("-" * 60)
    print(public_key)
    print("-" * 60)
    print()
    print(f"  STEP 2: Private key saved to: {private_key_path}")
    print("           (Do NOT share this file)")
    print()
    print("  STEP 3: In Binance API Management:")
    print("           - Create new API key")
    print("           - When prompted, paste the PUBLIC KEY above")
    print("           - Enable 'Spot & Margin Trading'")
    print()
    print("  STEP 4: Update your .env file with the API Key from Binance")
    print("=" * 60)

    return public_key, private_key_path

if __name__ == "__main__":
    generate_keys()
