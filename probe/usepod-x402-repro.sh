set -e
E=https://api.usepod.ai/proxy/x402/v1/chat/completions
UA='redline/0.1 (+https://github.com/Yonkoo11/redline)'
KP=~/.config/solana/redline-tape.json
B='{"model":"gpt-4o-mini","messages":[{"role":"user","content":"Reply with exactly: redline online"}],"max_tokens":16}'
printf '%s' "$B" > body.json
curl -s -D q.h -o q.b --max-time 30 -X POST "$E" -H "user-agent: $UA" -H 'content-type: application/json' --data-binary @body.json
echo "quote status: $(head -1 q.h)"
eval "$(python3 - <<'PY'
import base64,json,re
h=open('q.h').read(); raw=re.search(r'(?im)^payment-required:\s*(.+)$',h).group(1).strip()
env=json.loads(base64.b64decode(raw+'=='))
sol=[a for a in env['accepts'] if a.get('asset')=='SOL'][0]
print(f"QUOTE_ID={sol['quote_id']}\nNET={sol['network']}\nPAYTO={sol['pay_to']}\nLAMPORTS={sol['amount_microunits']}\nEXP={sol['expires_at']}")
PY
)"
echo "rail: $LAMPORTS lamports -> $PAYTO (expires $EXP)"
AMT=$(python3 -c "print(f'{$LAMPORTS/1e9:.9f}')")
SIG=$(solana transfer "$PAYTO" "$AMT" --allow-unfunded-recipient --keypair "$KP" --url https://api.mainnet-beta.solana.com --output json | python3 -c "import json,sys;print(json.load(sys.stdin)['signature'])")
echo "paid: $SIG"
PAYER=$(solana-keygen pubkey "$KP")
PROOF=$(python3 -c "
import base64,json
print(base64.b64encode(json.dumps({'quote_id':'$QUOTE_ID','network':'$NET','asset':'SOL','payer_wallet':'$PAYER','signature':'$SIG'},separators=(',',':')).encode()).decode())")
echo "proof length: ${#PROOF}"
curl -s -D s.h -o s.b --max-time 60 -X POST "$E" -H "user-agent: $UA" -H 'content-type: application/json' -H "PAYMENT-SIGNATURE: $PROOF" --data-binary @body.json
echo "settle status: $(head -1 s.h)"
grep -iE '^(cf-ray|server|payment-response|content-type)' s.h | head -4
head -c 400 s.b; echo
