# DNS.py
import os

def configurar_motor_chromium():
    flags = [
        # Aceleración por hardware
        "--enable-gpu",
        "--enable-gpu-rasterization",
        "--ignore-gpu-blocklist",
        "--enable-oop-rasterization",
        
        # Red y DNS 1.1.1.1
        '--dns-over-https-templates="https://cloudflare-dns.com/dns-query"',
        "--enable-features=dns-over-https",
        
        # Audio 3D y Multimedia
        "--enable-webaudio", # Activa la API de Web Audio (Audio Espacial/3D)
        "--enable-accelerated-video-decode",
        "--autoplay-policy=no-user-gesture-required" # Permite autoplay de audio
    ]
    
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = " ".join(flags)