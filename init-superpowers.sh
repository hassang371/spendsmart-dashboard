#!/bin/bash
# init-superpowers.sh — Bootstrap Superpowers + Context Engineering for Antigravity
#
# Usage: Run from your new project's root directory
#   bash /path/to/init-superpowers.sh
#
# What it does:
#   1. Copies all workflow files to .agents/workflows/
#   2. Copies all knowledge files to .gemini/knowledge/
#
# Source: Uses the project directory where this script lives as the source.

set -euo pipefail

# Source is the directory where this script lives
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Detect source structure (supports both flat depot and project layout)
if [ -d "$SCRIPT_DIR/workflows" ] && [ -d "$SCRIPT_DIR/knowledge" ]; then
    # Flat depot: workflows/ and knowledge/ at root
    WORKFLOWS_SRC="$SCRIPT_DIR/workflows"
    KNOWLEDGE_SRC="$SCRIPT_DIR/knowledge"
elif [ -d "$SCRIPT_DIR/.agents/workflows" ] && [ -d "$SCRIPT_DIR/.gemini/knowledge" ]; then
    # Project layout: .agents/workflows/ and .gemini/knowledge/
    WORKFLOWS_SRC="$SCRIPT_DIR/.agents/workflows"
    KNOWLEDGE_SRC="$SCRIPT_DIR/.gemini/knowledge"
else
    echo "❌ Error: Cannot find workflow and knowledge source files."
    echo "   Searched in: $SCRIPT_DIR"
    echo "   Expected either:"
    echo "     - workflows/ and knowledge/ (flat depot)"
    echo "     - .agents/workflows/ and .gemini/knowledge/ (project layout)"
    exit 1
fi

# Target is current working directory
TARGET="$(pwd)"

# Don't copy onto yourself
if [ "$TARGET" = "$SCRIPT_DIR" ]; then
    echo "⚠️  You're already in the source project. Nothing to do."
    exit 0
fi

echo "🚀 Initializing Superpowers in: $TARGET"
echo "📦 Source: $SCRIPT_DIR"

# Create target directories
mkdir -p "$TARGET/.agents/workflows"
mkdir -p "$TARGET/.gemini/knowledge"

# Copy workflows
echo ""
echo "📋 Copying workflows..."
WORKFLOW_COUNT=0
for file in "$WORKFLOWS_SRC"/*.md; do
    if [ -f "$file" ]; then
        cp "$file" "$TARGET/.agents/workflows/"
        echo "   ✓ $(basename "$file")"
        WORKFLOW_COUNT=$((WORKFLOW_COUNT + 1))
    fi
done

# Copy knowledge
echo ""
echo "📚 Copying knowledge..."
KNOWLEDGE_COUNT=0
for file in "$KNOWLEDGE_SRC"/*.md; do
    if [ -f "$file" ]; then
        cp "$file" "$TARGET/.gemini/knowledge/"
        echo "   ✓ $(basename "$file")"
        KNOWLEDGE_COUNT=$((KNOWLEDGE_COUNT + 1))
    fi
done

echo ""
echo "✅ Done! Copied $WORKFLOW_COUNT workflows + $KNOWLEDGE_COUNT knowledge files"
echo ""
echo "⚠️  Reminder: If you haven't set up the Global Rule yet, do it once:"
echo "   1. Open Antigravity → Customizations → Rules → + Global"
echo "   2. Paste the content from .agents/workflows/global-rule.md"
echo "   3. This only needs to be done ONCE (it applies to all projects)"
