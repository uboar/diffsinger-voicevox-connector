#!/usr/bin/env bash
# DiffSinger Connector を macOS でダブルクリック起動するためのスクリプト。
# 配布時には実行権限が必要です:
#   chmod +x scripts/start.command
# Finder でダブルクリックすると Terminal が開いてサーバーが起動します。
set -e
cd "$(dirname "$0")/.."
python3 -m diffsinger_engine
