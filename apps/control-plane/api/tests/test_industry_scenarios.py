from uuid import uuid4

from yino_platform_api.domain.customer_service import (
    CustomerServiceCreate,
    CustomerServiceInstance,
)
from yino_platform_api.industry_scenarios import CONSULT_OFFERING, INDUSTRY_SCENARIOS


def test_industry_scenarios_are_complete_synthetic_call_scripts() -> None:
    keys = [item.stable_key for item in INDUSTRY_SCENARIOS]
    assert len(keys) == 7
    assert len(set(keys)) == 7
    tenant_id = uuid4()
    for scenario in INDUSTRY_SCENARIOS:
        instance = scenario.to_instance(tenant_id=tenant_id)
        CustomerServiceCreate(
            display_name=instance.display_name,
            organization_name=instance.organization_name,
            greeting=instance.greeting,
            platform_prompt=instance.platform_prompt,
            tenant_prompt=instance.tenant_prompt,
            voice=instance.voice,
            response=instance.response,
        )
        CustomerServiceInstance.model_validate(instance.model_dump())
        assert "合成演示" in instance.organization_name
        assert "[[tool:create_appointment" in instance.platform_prompt
        assert "[[tool:create_callback" in instance.platform_prompt
        assert "[[tool:check_availability" in instance.platform_prompt
        assert CONSULT_OFFERING in {item.name for item in scenario.offerings}
        for offering in scenario.offerings:
            assert offering.name in instance.platform_prompt
        assert scenario.hours
        assert scenario.knowledge
        assert len(instance.platform_prompt) <= 8000
        assert len(instance.tenant_prompt) <= 8000
        assert len(instance.greeting) <= 300
