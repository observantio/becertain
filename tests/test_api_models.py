"""
Test Suite for API Models

Copyright (c) 2026 Stefan Kumarasinghe

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
"""

import pytest

from api.requests import DeploymentEventRequest
from pydantic import ValidationError


def test_deployment_request_requires_tenant():
    req = DeploymentEventRequest(tenant_id="t1", service="s", timestamp=1.0, version="v1")
    assert req.tenant_id == "t1"
    with pytest.raises(ValidationError):
        DeploymentEventRequest(service="s", timestamp=1.0, version="v1")
