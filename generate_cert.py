"""
Gera um certificado SSL auto-assinado para permitir HTTPS local.
Requer: pip install cryptography
"""
import datetime
import ipaddress
import subprocess
import sys

def generate():
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
    except ImportError:
        print("A instalar cryptography...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "cryptography", "--break-system-packages", "-q"])
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

    # Gerar chave privada RSA
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    # Detectar IP local automaticamente
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "127.0.0.1"

    print(f"  IP local detectado: {local_ip}")

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, u"LeituraOCR Local"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"LeituraOCR"),
    ])

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow())
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=3650))
        .add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName(u"localhost"),
                x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
                x509.IPAddress(ipaddress.IPv4Address(local_ip)),
            ]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )

    with open("cert.pem", "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    with open("key.pem", "wb") as f:
        f.write(key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        ))

    print("  cert.pem e key.pem gerados com sucesso.")
    print(f"  Acesse: https://{local_ip}:5000")
    print("  (O browser vai mostrar aviso de segurança — clique em 'Avançado' → 'Continuar')")

if __name__ == "__main__":
    generate()
