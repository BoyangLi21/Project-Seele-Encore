"""Run the established native camera proof on the R45 construction copy."""
from pathlib import Path
import review_spaces_r43 as review

ROOT=Path(__file__).resolve().parents[1]
review.ART=ROOT/'artifacts/rebuild_r45'
review.WORLD=ROOT/'run/saves/SEELE_FIELD_R45_REVIEW'
review.TEMPLATE=ROOT/'.Codex/client-launch-r17.json'
review.DEFAULT_PROPERTIES={
    'bodyPoseReview':(ROOT/'artifacts/server-ready-r44-stage/stage/client/projectseele-local-maps/eva_body_r43.json').as_posix(),
    'gameplayReviewDirectory':(ROOT/'artifacts/server-ready-r44-stage/stage/client/projectseele-local-maps').as_posix()
}
# This camera driver is a test mode identifier, independent of the save name.
review.MODE='r44-facility-photos'
if __name__=='__main__':review.main()
