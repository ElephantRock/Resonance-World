# ruff: noqa
import math
import evaluate_d2_vnext_q2_acquisition as e
def test_frozen_statistics():
    assert e.A_MIN_COMPLETE_PER_SCHEMA==12 and e.FUTURE_MIN_ANALYZABLE==88 and e.JOINT_CLEARANCE_TARGET==0.95 and e.PER_SCHEMA_CLEARANCE_TARGET==0.9875 and e.PER_SCHEMA_ALPHA==0.0125 and e.MAX_FUTURE_TOTAL_ATTEMPTS==640
def test_exact_lower_and_required_n_monotone():
    assert e.clopper_pearson_lower(0,96)==0.0
    assert math.isclose(e.clopper_pearson_lower(96,96),e.PER_SCHEMA_ALPHA**(1/96),rel_tol=1e-12)
    a=e.required_future_attempts(e.clopper_pearson_lower(70,96));b=e.required_future_attempts(e.clopper_pearson_lower(80,96));c=e.required_future_attempts(e.clopper_pearson_lower(90,96));assert c<b<a
