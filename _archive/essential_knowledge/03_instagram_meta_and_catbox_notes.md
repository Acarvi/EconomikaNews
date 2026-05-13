# Instagram, Meta, And Catbox Notes

Instagram Reels and Stories can require a public `media_url`.

Instagram Feed/Post can also require a public URL depending on the Graph API endpoint and publishing path.

The practical strategy discussed before the reset was to use temporary hosting such as Catbox, Gofile, Uguu, S3, or Cloudflare R2 to provide a public media URL to Meta.

Catbox seemed like the practical solution worth preserving as an idea.

This should live in CentralPublishingHub, not in EconomikaNoticias.

## Risks

- access tokens;
- Meta permissions and app review;
- Graph API version drift;
- polling media processing status;
- temporary URL expiration;
- public media URL availability and content type;
- retry behavior after Meta processing errors.

No implementation is included in the reset repo.

