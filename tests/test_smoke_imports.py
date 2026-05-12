def test_smoke_imports_without_secrets():
    import config.settings
    import core.publisher
    import core.viral_scout
    import main
    import server
    import services.publishing_hub_client

    assert server.app is not None
    assert core.publisher.CENTRAL_HUB_BASE
    assert hasattr(core.viral_scout, "ViralScout")
    assert hasattr(services.publishing_hub_client, "PublishingHubClient")
    assert config.settings.get_settings() is not None
