import sys
import os
import json
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def check_daemon():
    try:
        with urllib.request.urlopen("http://localhost:9222/health", timeout=5) as r:
            data = json.loads(r.read())
            if data.get("data", {}).get("status") == "healthy":
                print("✅ Rayobrowse daemon hazır.\n")
                return
    except Exception as e:
        print(f"   Hata: {e}")

    print("❌ Rayobrowse daemon'a ulaşılamadı.")
    print("   Çözüm: docker compose up -d  komutunu çalıştırın.")
    print("   Sonra tekrar deneyin.")
    sys.exit(1)


print("🚀 Rayobrowse kontrol ediliyor...")
check_daemon()

from main import main

if __name__ == "__main__":
    main()
