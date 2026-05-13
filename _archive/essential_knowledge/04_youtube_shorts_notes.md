# YouTube Shorts Notes

YouTube Shorts publishing should go through CentralPublishingHub.

The Hub can use a local file path when it runs on the same machine as the rendered video.

YouTube publishing requires OAuth credentials in the Hub.

EconomikaNoticias should only send a payload describing the publish intent. It should not own OAuth tokens, refresh logic, upload sessions, or platform-specific retries.

