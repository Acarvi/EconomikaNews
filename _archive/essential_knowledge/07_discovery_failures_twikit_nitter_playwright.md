# Discovery Failures: Twikit, Nitter, And Playwright

## Twikit Failures

Twikit failed with errors including:

- `Couldn't get KEY_BYTE indices`
- `KeyError('urls')`

These failures suggest schema/API drift and brittle unofficial access.

## Nitter Failures

Nitter failed with:

- `403`
- no results;
- DNS failures.

Public Nitter instances are not a reliable product dependency.

## Playwright Failures

Playwright/browser async execution failed on Windows due to event loop and subprocess behavior.

The previous branch worked around some Windows event loop issues, but that does not make browser scraping a product foundation by itself.

## Conclusion

Do not use Twikit or Nitter as the base of the product.

Browser scraping may be possible, but it requires design from scratch.

An official API or paid data/scraping service may be better.

No decision is made now.

