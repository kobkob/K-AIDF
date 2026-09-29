#!/bin/bash

# Default to OLMo model
DEFAULT_MODEL="olmo"

# Parse command (remove legacy prefixes)
COMMAND="$@"

# Route to OLMo by default
if [[ "$COMMAND" == */* ]]; then
    COMMAND="${COMMAND#*/}"
fi

# Execute via Ollama
docker exec ollama ollama run $DEFAULT_MODEL "$COMMAND"