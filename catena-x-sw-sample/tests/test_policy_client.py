from app.policy_client import PolicyClient, PolicyRegistrationRequest


def test_register_policy_builds_management_payload() -> None:
    client = PolicyClient("https://edc-management.local")
    request = PolicyRegistrationRequest(
        policy_id="policy-asset-001",
        odrl_policy={
            "@context": "http://www.w3.org/ns/odrl.jsonld",
            "@type": "Offer",
            "permission": [{"action": "use"}],
        },
    )

    result = client.register_policy(request)

    assert result["endpoint"].endswith("/v3/policydefinitions")
    assert result["payload"]["@id"] == "policy-asset-001"
    assert result["payload"]["policy"]["@type"] == "Offer"
