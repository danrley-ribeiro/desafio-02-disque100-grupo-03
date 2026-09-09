#!/usr/bin/env python3
"""
=============================================================================
Dashboard de Inteligência Territorial do Disque 100 - Governo de Santa Catarina
=============================================================================
Ponto de entrada de compatibilidade que delega a execução para o pacote modular
otimizado em `streamlit_app/app.py`.
=============================================================================
"""

import sys
from pathlib import Path

CURRENT_FILE_DIR = Path(__file__).resolve().parent
ROOT_DIR = CURRENT_FILE_DIR.parent if CURRENT_FILE_DIR.name == "dashboards" else CURRENT_FILE_DIR

for p in [str(ROOT_DIR), str(ROOT_DIR / "streamlit_app")]:
    if p not in sys.path:
        sys.path.insert(0, p)

from streamlit_app.config import FONTES_OFICIAIS
from streamlit_app.app import main

__all__ = ["main", "FONTES_OFICIAIS"]

if __name__ == "__main__":
    main()
