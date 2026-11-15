import sys
from pathlib import Path

# 1. Add bundled packages to sys.path if present
site_packages = Path(__file__).resolve().parent / ".python_packages" / "lib" / "site-packages"
if site_packages.exists() and str(site_packages) not in sys.path:
    sys.path.insert(0, str(site_packages))

# 2. Add college-rag-backend to sys.path so 'app' package is found
backend_dir = Path(__file__).resolve().parent / "college-rag-backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# 3. Import the FastAPI app from backend
from app.main import app  # noqa: E402

if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.environ.get("PORT", os.environ.get("WEBSITES_PORT", 8000)))
    uvicorn.run("main:app", host="0.0.0.0", port=port)

