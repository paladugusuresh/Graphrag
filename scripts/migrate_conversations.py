#!/usr/bin/env python3
"""
Migration script for legacy conversation files.

This script normalizes legacy conversation .jsonl files to the new format,
ensuring consistent structure across all stored conversations.

Usage:
    python scripts/migrate_conversations.py [--dry-run] [--backup]

Options:
    --dry-run: Show what would be changed without making changes
    --backup: Create .bak backup files before modifying
"""

import json
import os
import sys
import argparse
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from graph_rag.conversation_store import normalize_message

def migrate_conversation_file(filepath: str, dry_run: bool = False, backup: bool = False):
    """
    Migrate a single conversation file to normalized format.
    
    Args:
        filepath: Path to the conversation .jsonl file
        dry_run: If True, only show what would be changed
        backup: If True, create a backup before modifying
        
    Returns:
        Tuple of (messages_processed, messages_changed)
    """
    print(f"Processing: {filepath}")
    
    # Read existing messages
    messages = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            try:
                messages.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"  Warning: Failed to parse line {line_num}: {e}")
                continue
    
    # Normalize messages
    normalized_messages = []
    changes = 0
    for i, msg in enumerate(messages):
        normalized = normalize_message(msg)
        normalized_messages.append(normalized)
        
        # Check if message changed
        if normalized != msg:
            changes += 1
            if dry_run:
                print(f"  Message {i+1} would be normalized:")
                print(f"    Before: {msg}")
                print(f"    After:  {normalized}")
    
    if changes == 0:
        print(f"  No changes needed ({len(messages)} messages already normalized)")
        return len(messages), 0
    
    if dry_run:
        print(f"  Would normalize {changes}/{len(messages)} messages")
        return len(messages), changes
    
    # Create backup if requested
    if backup:
        backup_path = f"{filepath}.bak"
        os.rename(filepath, backup_path)
        print(f"  Created backup: {backup_path}")
    
    # Write normalized messages
    with open(filepath, 'w', encoding='utf-8') as f:
        for msg in normalized_messages:
            f.write(json.dumps(msg) + '\n')
    
    print(f"  Normalized {changes}/{len(messages)} messages")
    return len(messages), changes

def main():
    parser = argparse.ArgumentParser(
        description="Migrate legacy conversation files to normalized format"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without making changes"
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Create .bak backup files before modifying"
    )
    parser.add_argument(
        "--conversations-dir",
        default="conversations",
        help="Directory containing conversation files (default: conversations)"
    )
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("Conversation Migration Tool")
    print("=" * 70)
    print()
    
    if args.dry_run:
        print("DRY RUN MODE: No files will be modified")
        print()
    
    if args.backup and not args.dry_run:
        print("BACKUP MODE: Creating .bak files before modification")
        print()
    
    # Find all conversation files
    if not os.path.exists(args.conversations_dir):
        print(f"Error: Directory '{args.conversations_dir}' does not exist")
        return 1
    
    conv_files = [
        os.path.join(args.conversations_dir, f)
        for f in os.listdir(args.conversations_dir)
        if f.startswith("conv_") and f.endswith(".jsonl")
    ]
    
    if not conv_files:
        print(f"No conversation files found in '{args.conversations_dir}'")
        return 0
    
    print(f"Found {len(conv_files)} conversation file(s)")
    print()
    
    # Migrate each file
    total_messages = 0
    total_changes = 0
    
    for filepath in conv_files:
        try:
            messages, changes = migrate_conversation_file(
                filepath,
                dry_run=args.dry_run,
                backup=args.backup
            )
            total_messages += messages
            total_changes += changes
        except Exception as e:
            print(f"  Error processing {filepath}: {e}")
            continue
        print()
    
    # Summary
    print("=" * 70)
    print("Migration Summary")
    print("=" * 70)
    print(f"Files processed: {len(conv_files)}")
    print(f"Total messages: {total_messages}")
    print(f"Messages {'that would be ' if args.dry_run else ''}normalized: {total_changes}")
    print()
    
    if args.dry_run and total_changes > 0:
        print("Run without --dry-run to apply changes")
    elif total_changes > 0:
        print("Migration complete!")
    else:
        print("All conversations already in normalized format!")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
