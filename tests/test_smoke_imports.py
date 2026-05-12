def test_smoke_imports_without_secrets():
    import config.settings
    import core.publisher
    import core.viral_scout
    import server
    import services.publishing_hub_client
    import services.discovery
    import services.discovery.models
    import services.discovery.rss_sources
    import services.discovery.x_sources

    assert server.app is not None
    assert core.publisher.CENTRAL_HUB_BASE
    assert hasattr(core.viral_scout, "ViralScout")
    assert hasattr(services.publishing_hub_client, "PublishingHubClient")
    assert config.settings.get_settings() is not None
    assert hasattr(services.discovery, "TwikitXSource")
    assert hasattr(services.discovery.models, "DiscoveryCandidate")
    assert hasattr(services.discovery.rss_sources, "NewsRSSSource")
    assert hasattr(services.discovery.x_sources, "BrowserXSource")
    assert hasattr(services.discovery.x_sources, "TwikitXSource")

    # main.py is GUI/render-heavy and covered by local smoke, not lightweight server CI.
