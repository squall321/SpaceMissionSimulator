"""
SpaceD-AADE Platform - Entry Point
"""
import sys
import os
from pathlib import Path

# 프로젝트 루트를 Python path에 추가
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

# WebEngine은 메인 스크립트보다 먼저 초기화 필요
import os
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu-sandbox")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")

from gui.main_window import main

if __name__ == "__main__":
    main()
