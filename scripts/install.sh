#!/bin/bash

# One-liner installation script
INSTALL_DIR="/opt/kobkob"

# Check dependencies
if ! command -v curl &> /dev/null; then
    echo "Error: curl is not installed.";
    exit 1
fi

if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed.";
    exit 1
fi

# Clone and install
echo "Installing Kobkob...";
mkdir -p $INSTALL_DIR && \
cd $INSTALL_DIR && \
git clone https://github.com/kobkob/K-AIDF . && \
make install

# Post-install instructions
echo "\nInstallation complete. Run:"
echo "  cd $INSTALL_DIR && ./scripts/cli-entrypoint.sh"
echo "\nTo sign documents, run:"
echo "  ./mcp-server/sign --manifest=manifest.json"