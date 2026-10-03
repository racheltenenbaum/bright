#!/bin/bash
# SessionStart hook: if the latest finished CI run on master failed, tell
# Claude (and Rachel) so it gets investigated and fixed instead of silently
# piling up failure emails. The repo is public, so the unauthenticated API
# works even when the local `gh` login has expired.
REPO="racheltenenbaum/bright"
API="https://api.github.com/repos/$REPO/actions/runs?branch=master&status=completed&per_page=1"

run=$(curl -s -m 8 "$API" | jq -c '.workflow_runs[0] // empty' 2>/dev/null)
[ -z "$run" ] && exit 0

conclusion=$(jq -r '.conclusion' <<<"$run")
[ "$conclusion" != "failure" ] && exit 0

sha=$(jq -r '.head_sha[0:7]' <<<"$run")
title=$(jq -r '.display_title' <<<"$run")
url=$(jq -r '.html_url' <<<"$run")
when=$(jq -r '.created_at' <<<"$run")

ctx="CI IS RED: the latest GitHub Actions run on master failed (commit $sha \"$title\", $when, $url). Rachel wants these fixed proactively: early in this session, tell her CI is failing, reproduce it locally with the exact CI command (pytest tests/ --cov=src --cov-report=term-missing --cov-fail-under=99, starting from the committed test_bright.db), fix the root cause, push, and confirm the next run passes."

jq -n --arg ctx "$ctx" --arg msg "CI is failing on master ($sha) — Claude will look into it." \
  '{systemMessage: $msg, hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: $ctx}}'
