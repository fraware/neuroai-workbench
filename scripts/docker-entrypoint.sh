#!/bin/sh
set -eu
if [ "$#" -gt 0 ] && [ "$1" = "serve" ]; then
  workspace="${2:-/workspace}"
  if [ ! -f "$workspace/workspace.json" ]; then
    neuroai-workbench init "$workspace" --name "Container NeuroAI workspace"
  fi
fi
exec neuroai-workbench "$@"
