"""Prepare the retained high-detail assets with complete coherent wrist modules."""
from pathlib import Path
import shutil
from reuse_hand_module_r47 import main as reuse_hand_modules

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'artifacts/rebuild_r47/assets'

def main():
    if not ASSETS.exists():
        shutil.copytree(ROOT/'artifacts/rebuild_r46/final_assets_v1',ASSETS)
    reuse_hand_modules()

if __name__=='__main__':main()
