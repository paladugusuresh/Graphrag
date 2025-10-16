#!/usr/bin/env python3
"""
Safety script to detect import-time configuration reads.
This script checks for patterns that indicate config is being loaded at module import time.
"""

import os
import re
import sys
from pathlib import Path

# Patterns to detect import-time config loading
UNSAFE_PATTERNS = [
    # Direct config file reads at module level
    (r'^with open\(["\'].*config\.yaml["\'].*\) as \w+:\s*$', 'Direct config.yaml read at module level'),
    (r'^\s*cfg\s*=\s*yaml\.safe_load\(', 'Module-level yaml.safe_load assignment'),
    (r'^\s*CONFIG\s*=\s*yaml\.safe_load\(', 'Module-level CONFIG assignment'),
    (r'^\s*CFG\s*=\s*yaml\.safe_load\(', 'Module-level CFG assignment'),
    
    # Module-level config reads
    (r'^[A-Z_]+\s*=.*open\(["\']config\.yaml', 'Module-level constant from config file'),
]

# Files to exclude from checks
EXCLUDE_PATTERNS = [
    'project_full_dump.py',
    'check_import_time_config.py',
    '__pycache__',
    '.pytest_cache',
    '.git',
    'venv',
    '.venv',
]

def should_check_file(filepath):
    """Determine if file should be checked"""
    # Only check Python files
    if not filepath.endswith('.py'):
        return False
    
    # Skip excluded paths
    for pattern in EXCLUDE_PATTERNS:
        if pattern in filepath:
            return False
    
    return True

def check_file(filepath):
    """Check a single file for unsafe patterns"""
    issues = []
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        in_function = False
        in_class = False
        
        for line_num, line in enumerate(lines, 1):
            # Track if we're inside a function or class
            if re.match(r'^\s*def \w+', line):
                in_function = True
            elif re.match(r'^\s*class \w+', line):
                in_class = True
            elif line.strip() and not line.strip().startswith('#') and not line.strip().startswith('@'):
                # Reset if we're back to module level (no leading whitespace on non-comment)
                if not line.startswith(' ') and not line.startswith('\t'):
                    if not line.startswith('def ') and not line.startswith('class '):
                        in_function = False
                        in_class = False
            
            # Check for unsafe patterns at module level only
            if not in_function:
                for pattern, description in UNSAFE_PATTERNS:
                    if re.search(pattern, line, re.MULTILINE):
                        issues.append({
                            'file': filepath,
                            'line': line_num,
                            'description': description,
                            'code': line.strip()
                        })
    
    except Exception as e:
        print(f"Error checking {filepath}: {e}", file=sys.stderr)
    
    return issues

def main():
    """Main entry point"""
    print("Checking for import-time configuration reads...")
    print("=" * 70)
    
    all_issues = []
    files_checked = 0
    
    # Walk through the graph_rag directory
    for root, dirs, files in os.walk('.'):
        # Remove excluded directories
        dirs[:] = [d for d in dirs if d not in EXCLUDE_PATTERNS]
        
        for file in files:
            filepath = os.path.join(root, file)
            
            if should_check_file(filepath):
                files_checked += 1
                issues = check_file(filepath)
                all_issues.extend(issues)
    
    # Report results
    if all_issues:
        print(f"\n[X] Found {len(all_issues)} potential import-time config reads:\n")
        
        for issue in all_issues:
            print(f"File: {issue['file']}")
            print(f"Line {issue['line']}: {issue['description']}")
            print(f"Code: {issue['code']}")
            print("-" * 70)
        
        print(f"\nTotal: {len(all_issues)} issues in {files_checked} files checked")
        return 1
    else:
        print(f"\n[OK] No import-time config reads detected!")
        print(f"Checked {files_checked} Python files")
        return 0

if __name__ == '__main__':
    sys.exit(main())

