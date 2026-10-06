"""A self-signed certificate for one host name, written to the directory given.

    python make_cert.py <dir> [host]      (host defaults to spike-front)

The backend image has `cryptography` and no openssl binary.
"""

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

out = Path(sys.argv[1])
host = sys.argv[2] if len(sys.argv) > 2 else "spike-front"
key = ec.generate_private_key(ec.SECP256R1())
name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, host)])
now = datetime.now(tz=UTC)
cert = (
    x509.CertificateBuilder()
    .subject_name(name)
    .issuer_name(name)
    .public_key(key.public_key())
    .serial_number(x509.random_serial_number())
    .not_valid_before(now - timedelta(minutes=5))
    .not_valid_after(now + timedelta(days=1))
    .add_extension(x509.SubjectAlternativeName([x509.DNSName(host)]), critical=False)
    .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
    .sign(key, hashes.SHA256())
)
(out / "cert.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
(out / "key.pem").write_bytes(
    key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
)
