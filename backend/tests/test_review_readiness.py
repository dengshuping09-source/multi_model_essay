from app.api.routes.providers import router


def test_student_readiness_probe_route_is_removed() -> None:
    paths = {route.path for route in router.routes}
    assert "/review-readiness" not in paths
