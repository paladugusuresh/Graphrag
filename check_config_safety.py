#!/usr/bin/env python3
"""
Safety check script to verify no import-time config reads remain in the codebase.
This script checks for common patterns that violate lazy config loading principles.
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple

# Patterns to check for
VIOLATION_PATTERNS = [
    (r'with open\(["\']config\.yaml["\']\s*,\s*["\']r["\']\)', 
     "Import-time config.yaml read detected"),
    (r'^\s*[A-Z_]+\s*=\s*CFG\[', 
     "Module-level CFG assignment detected"),
    (r'^\s*[A-Z_]+\s*=\s*yaml\.safe_load', 
     "Module-level yaml.safe_load detected"),
    (r'GraphDatabase\.driver\([^)]*NEO4J', 
     "Import-time Neo4j driver creation detected"),
]

# Directories to check
DIRS_TO_CHECK = ['graph_rag', '.']

# Files to check specifically
FILES_TO_CHECK = ['main.py']

# Exceptions: some patterns are OK in certain contexts
EXCEPTIONS = {
    'graph_rag/config_manager.py': 'Contains the ConfigManager implementation',
    'graph_rag/schema_catalog.py': 'Function-level config reads are allowed',
    'graph_rag/schema_embeddings.py': 'Function-level config reads are allowed',
    'check_config_safety.py': 'This is the safety checker itself',
    'project_full_dump.py': 'Archive/snapshot file - not active code',
}


def check_file(file_path: Path) -> List[Tuple[int, str, str]]:
    """
    Check a single file for config violations.
    Returns list of (line_number, pattern_description, line_content)
    """
    violations = []
    
    # Check if file is in exceptions
    str_path = str(file_path).replace('\\', '/')
    for exception_path, reason in EXCEPTIONS.items():
        if exception_path in str_path:
            print(f"[OK] Skipping {file_path} ({reason})")
            return violations
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"[WARN] Could not read {file_path}: {e}")
        return violations
    
    for line_num, line in enumerate(lines, 1):
        for pattern, description in VIOLATION_PATTERNS:
            if re.search(pattern, line):
                violations.append((line_num, description, line.strip()))
    
    return violations


def main():
    """Run safety checks on all Python files"""
    print("=" * 70)
    print("CONFIG SAFETY CHECKER - Detecting import-time config reads")
    print("=" * 70)
    print()
    
    all_violations = {}
    
    # Check specific files
    for file_name in FILES_TO_CHECK:
        file_path = Path(file_name)
        if file_path.exists():
            violations = check_file(file_path)
            if violations:
                all_violations[str(file_path)] = violations
        else:
            print(f"[WARN] File not found: {file_path}")
    
    # Check directories
    for dir_name in DIRS_TO_CHECK:
        dir_path = Path(dir_name)
        if not dir_path.exists():
            print(f"[WARN] Directory not found: {dir_path}")
            continue
        
        for py_file in dir_path.glob('**/*.py'):
            # Skip __pycache__ and other generated files
            if '__pycache__' in str(py_file) or 'test_' in py_file.name:
                continue
            
            violations = check_file(py_file)
            if violations:
                all_violations[str(py_file)] = violations
    
    # Report results
    print()
    print("=" * 70)
    print("RESULTS")
    print("=" * 70)
    print()
    
    if not all_violations:
        print("[SUCCESS] No config safety violations found!")
        print()
        print("All files are using lazy config loading via ConfigManager.")
        return 0
    else:
        print(f"[FAILURE] Found {len(all_violations)} file(s) with violations:")
        print()
        
        for file_path, violations in sorted(all_violations.items()):
            print(f"FILE: {file_path}")
            for line_num, description, line_content in violations:
                print(f"   Line {line_num}: {description}")
                print(f"   > {line_content}")
            print()
        
        print("=" * 70)
        print(f"Total violations: {sum(len(v) for v in all_violations.values())}")
        print()
        print("Action required:")
        print("1. Refactor files to use graph_rag.config_manager.get_config_value()")
        print("2. Replace import-time config reads with lazy loading")
        print("3. Re-run this script to verify fixes")
        return 1


if __name__ == "__main__":
    sys.exit(main())
