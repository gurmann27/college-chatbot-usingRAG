import os
import sys
from pathlib import Path

# 1. Add bundled site-packages to sys.path
root_dir = Path(__file__).resolve().parent
site_packages = root_dir / ".python_packages" / "lib" / "site-packages"
if site_packages.exists() and str(site_packages) not in sys.path:
    sys.path.insert(0, str(site_packages))

# 2. Add college-rag-backend to sys.path
backend_dir = root_dir / "college-rag-backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# 3. Import app
from app.main import app  # noqa: E402

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", os.environ.get("WEBSITES_PORT", 8000)))
    print(f"Starting server on 0.0.0.0:{port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)
