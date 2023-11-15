from common.db.tables.adam import TapStatus
from common.db.database import get_db
from common.define import AudioConstant

db = next(get_db())


def update_one_tap(name, status):
    db.query(TapStatus).filter(TapStatus.material_name == name).update(dict(status=status))
    db.commit()


def init_tap():
    db.query(TapStatus).update(dict(status=0))
    db.commit()


def get_all_status():
    taps = db.query(TapStatus).all()
    result = {}
    for tap in taps:
        result[tap.material_name] = tap.status
    return result
