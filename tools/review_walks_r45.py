"""Native full-footprint route and gate use on the R45 review copy."""
from pathlib import Path
import review_walks_r44 as review
ROOT=Path(__file__).resolve().parents[1]
review.ART=ROOT/'artifacts/rebuild_r45'
review.WORLD=ROOT/'run/saves/SEELE_FIELD_R45_REVIEW'
if __name__=='__main__':review.main()
