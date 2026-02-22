import pytest

from api.requests import DeploymentEventRequest
from pydantic import ValidationError


def test_deployment_request_requires_tenant():
    req = DeploymentEventRequest(tenant_id="t1", service="s", timestamp=1.0, version="v1")
    assert req.tenant_id == "t1"
    with pytest.raises(ValidationError):
        DeploymentEventRequest(service="s", timestamp=1.0, version="v1")
