"""
start.py — Inicia o LeituraOCR com HTTPS via ngrok (recomendado para telemóvel)
ou com certificado local como fallback.

Uso:
    python start.py          # tenta ngrok, cai para HTTPS local
    python start.py --local  # força HTTPS local (certificado auto-assinado)
    python start.py --ngrok  # força ngrok
"""

import sys
import os
import subprocess
import threading
import time

PORT = 5000

def start_with_ngrok():
    """Inicia Flask em HTTP e cria túnel ngrok HTTPS."""
    try:
        from pyngrok import ngrok, conf
    except ImportError:
        print("📦 A instalar pyngrok...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyngrok", "--break-system-packages", "-q"])
        from pyngrok import ngrok, conf

    # Iniciar túnel ngrok na porta 5000
    print("🔗 A criar túnel ngrok...")
    tunnel = ngrok.connect(PORT, "http")
    public_url = tunnel.public_url

    # ngrok dá HTTP por defeito, pedir HTTPS
    if public_url.startswith("http://"):
        public_url = public_url.replace("http://", "https://", 1)

    print("")
    print("=" * 55)
    print("✅  HTTPS PRONTO — abra este link no telemóvel:")
    print("")
    print(f"    {public_url}")
    print("")
    print("  • Link válido enquanto o servidor estiver a correr")
    print("  • Funciona em qualquer dispositivo, sem aviso de segurança")
    print("  • Câmara funcionará normalmente")
    print("=" * 55)
    print("")

    return public_url

def start_with_local_ssl():
    """Inicia Flask com certificado auto-assinado."""
    ssl_cert, ssl_key = "cert.pem", "key.pem"
    if not (os.path.exists(ssl_cert) and os.path.exists(ssl_key)):
        print("🔐 A gerar certificado SSL...")
        import generate_cert
        generate_cert.generate()

    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        ip = "127.0.0.1"

    print("")
    print("=" * 55)
    print("✅  HTTPS LOCAL — abra no browser do PC:")
    print(f"    https://{ip}:{PORT}")
    print("")
    print("  ⚠️  No telemóvel: aceite o aviso de segurança")
    print("     Chrome: escreva  thisisunsafe  na página de aviso")
    print("=" * 55)
    print("")

    return (ssl_cert, ssl_key)

def run_flask(ssl_context=None):
    import app as flask_app
    flask_app.app.run(
        debug=False,
        host="0.0.0.0",
        port=PORT,
        ssl_context=ssl_context,
        use_reloader=False,
    )

if __name__ == "__main__":
    mode = "auto"
    if "--local" in sys.argv:
        mode = "local"
    elif "--ngrok" in sys.argv:
        mode = "ngrok"

    ssl_context = None

    if mode in ("auto", "ngrok"):
        try:
            start_with_ngrok()
            # Flask em HTTP puro (ngrok trata do HTTPS)
            ssl_context = None
        except Exception as e:
            print(f"⚠️  ngrok falhou ({e}). A usar HTTPS local...")
            ssl_context = start_with_local_ssl()
    else:
        ssl_context = start_with_local_ssl()

    print("🚀 A iniciar servidor Flask...")
    run_flask(ssl_context)
