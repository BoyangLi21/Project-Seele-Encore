"""Reuse the bounded production check on this precise interim batch."""
from pathlib import Path
import test_packaged_server_r42 as check

ROOT=Path(__file__).resolve().parents[1]
check.OUT=ROOT/'artifacts/server-ready-r43-stage'
check.STAGE=check.OUT/'stage'
check.TEST=check.OUT/'production-run'
check.WORLD='SEELE_R43_STAGE_WORLD'
check.REVISION='R43-stage'

if __name__=='__main__':check.main()
