"""Use the established camera/compiled-terrain proof in the R44 construction world."""
from pathlib import Path
import review_spaces_r43 as review

ROOT=Path(__file__).resolve().parents[1]
review.ART=ROOT/'artifacts/rebuild_r44'
review.WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'
review.MODE='r44-facility-photos'

if __name__=='__main__':review.main()
