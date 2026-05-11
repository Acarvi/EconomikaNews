def test_import_server_without_sentinel():
    import server

    assert server.app is not None


def test_import_publisher():
    import core.publisher

    assert core.publisher.CENTRAL_HUB_BASE
