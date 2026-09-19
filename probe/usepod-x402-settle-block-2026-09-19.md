# UsePod x402: verified payments are blocked at the edge (measured 2026-09-19)

The accountless x402 flow completes steps 1 and 2 and fails at step 3. Quotes work. Payments land
on Solana mainnet. The settle request is answered by Cloudflare with `403 Attention Required`
before UsePod sees it, but **only when the payment is genuine**.

## Reproduction

Endpoint `POST https://api.usepod.ai/proxy/x402/v1/chat/completions`, same byte-identical body in
both steps, `PAYMENT-SIGNATURE` built exactly as `docs.usepod.ai/api/x402-payments` specifies.

| settle request | result |
|---|---|
| fake `quote_id`, fake signature | `400 unknown x402 quote` (reaches the API) |
| real `quote_id`, fake payer, fake signature | `400 Solana transaction lookup failed` (reaches the API) |
| real `quote_id`, real payer, fake signature | `400 Solana transaction not found` (reaches the API) |
| real `quote_id`, real payer, **real paid transaction** | **`403` Cloudflare block page** |

Ruled out by direct test: header name, header casing (`PAYMENT-SIGNATURE`, `payment-signature`,
`X-PAYMENT` all reach the API), header length (376-char forged proof passes), signature entropy
(random 88-char base58 passes), HTTP client (`urllib` and `curl` behave identically), model choice
(`gpt-4o-mini`, `llama-3.1-8b-instruct` and `deepseek-chat` all 403), and retries (4 attempts
inside one quote window, four different `cf-ray` values, all 403).

The only variable that flips the response from 400 to 403 is whether the referenced transaction
actually exists and pays the quote. A request that would succeed is refused at the edge.

## Payments made during this test (Solana mainnet, tape wallet 61QDPf756rts88PADMZX2TUkqbFmdCfCCvkiwtDSuRHo)

45, 45, 90, 9 and 153 lamports to `GXfqVnZENHzvim8rNN8TPwqxWXQe8EBbxhcEMYE8Z7BS`, about $0.004 in
total. Each was accepted on chain and none returned a completion. Under `cap-with-surplus-credit`
the amounts should remain as surplus credit against the payer wallet.

## Cloudflare ray IDs for the blocked settles

`a3d4461dbc01cd72-LHR`, `a3d447b29858d8f8-LHR`, `a3d447d9fd4bd06b-LHR`, `a3d447fdfc81f365-LHR`,
`a3d44827fcaa93f6-LHR` (London edge).

## What this means for Redline

`redline/inference.py` implements the documented flow and is exercised end to end against the live
API. Quote and payment are proven. The completion cannot be retrieved until the edge rule is
changed, so Redline's strategy decisions fall back to the locally configured model and every tape
entry records which one answered.
