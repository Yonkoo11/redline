#!/bin/bash
# Phase 1 venue gate. Without --execute it stops before spending anything.
#   bash ~/Projects/redline/run-venue-gate.sh            # dry run
#   bash ~/Projects/redline/run-venue-gate.sh --execute  # spends ~$0.85
export REDLINE_OPERATOR_PUBKEY="AqRT7dJrWw4t5vcgDDh9NosgFZKSMYhywxCvHFnJTwjm"
exec ~/.hermes/hermes-agent/venv/bin/python ~/Projects/redline/tests/venue_gate.py "$@"
