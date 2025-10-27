# graph_rag/sanitizer.py
import re
import unicodedata
from typing import Set

# Maximum allowed text length
MAX_TEXT_LENGTH = 4096

# Suspicious sequences to remove/replace
SUSPICIOUS_SEQUENCES = [
    ';',
    '\\n\\n',
    'MATCH ',
    'CREATE ',
    'DELETE ',
    'CALL apoc',
    'DROP TABLE',
    'DELETE FROM',
    'UPDATE ',
    'INSERT INTO',
    'EXEC ',
    'EXECUTE ',
    'xp_cmdshell',
    'sp_executesql',
    'UNION SELECT',
    'OR 1=1',
    'AND 1=1',
    '--',
    '/*',
    '*/',
    '<script',
    '</script>',
    'javascript:',
    'eval(',
    'setTimeout(',
    'setInterval(',
]

# Cypher keywords for malicious detection
CYPHER_KEYWORDS = {
    'MATCH', 'CREATE', 'MERGE', 'DELETE', 'REMOVE', 'SET', 'RETURN',
    'WHERE', 'WITH', 'UNWIND', 'CALL', 'YIELD', 'LOAD CSV', 'FOREACH',
    'CASE', 'WHEN', 'THEN', 'ELSE', 'END', 'UNION', 'OPTIONAL',
    'DETACH DELETE', 'DROP', 'CREATE INDEX', 'CREATE CONSTRAINT'
}

# Shell/system command patterns
SHELL_PATTERNS = [
    r'\b(rm|del|format|fdisk|mkfs)\b',
    r'\b(cat|type|more|less)\b',
    r'\b(ls|dir|find|locate)\b',
    r'\b(chmod|chown|sudo)\b',
    r'\b(wget|curl|nc|netcat)\b',
    r'\b(python|perl|ruby|bash|sh|cmd|powershell)\b',
    r'\b(ping|nslookup|dig|telnet)\b',
]

# SQL injection patterns
SQL_PATTERNS = [
    r"'\s*(OR|AND)\s*'?\d+'?\s*=\s*'?\d+'?",
    r"'\s*(OR|AND)\s*'[^']*'\s*=\s*'[^']*'",
    r"UNION\s+SELECT",
    r"DROP\s+TABLE",
    r"INSERT\s+INTO",
    r"UPDATE\s+\w+\s+SET",
    r"DELETE\s+FROM",
]

def sanitize_text(text: str) -> str:
    """
    Sanitizes input text by removing suspicious sequences, control characters,
    normalizing whitespace, and limiting length.
    
    Args:
        text: Input text to sanitize
        
    Returns:
        Sanitized text safe for processing
    """
    if not isinstance(text, str):
        return ""
    
    # Limit length first to avoid processing extremely long strings
    if len(text) > MAX_TEXT_LENGTH:
        text = text[:MAX_TEXT_LENGTH]
    
    # Remove control characters (Unicode category Cc)
    text = ''.join(char for char in text if unicodedata.category(char) != 'Cc')
    
    # Replace suspicious sequences with spaces
    for sequence in SUSPICIOUS_SEQUENCES:
        text = text.replace(sequence, ' ')
    
    # Normalize whitespace - collapse multiple whitespace chars to single space
    text = re.sub(r'\s+', ' ', text)
    
    # Strip leading/trailing whitespace
    text = text.strip()
    
    return text

def is_probably_malicious(text: str) -> bool:
    """
    Uses heuristics to detect potentially malicious input.
    
    Args:
        text: Input text to analyze
        
    Returns:
        True if text appears potentially malicious, False otherwise
    """
    if not isinstance(text, str):
        return False
    
    text_upper = text.upper()
    
    # Check for dangerous write operations (should be blocked even if alone)
    dangerous_write_keywords = {'CREATE', 'DELETE', 'MERGE', 'DROP', 'REMOVE', 'DETACH DELETE'}
    if any(keyword in text_upper for keyword in dangerous_write_keywords):
        return True
    
    # Count Cypher keywords
    cypher_keyword_count = sum(1 for keyword in CYPHER_KEYWORDS if keyword in text_upper)
    
    # Check for multiple Cypher keywords (likely injection attempt)
    if cypher_keyword_count >= 2:
        return True
    
    # Check for shell command patterns
    for pattern in SHELL_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    
    # Check for SQL injection patterns
    for pattern in SQL_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    
    # Check for excessive special characters (potential obfuscation)
    special_char_count = sum(1 for char in text if char in ';(){}[]<>|&$`"\'\\')
    if len(text) > 0 and (special_char_count / len(text)) > 0.3:
        return True
    
    # Check for suspicious character sequences
    suspicious_patterns = [
        r'[;\'"]\s*[;\'"]\s*[;\'"]',  # Multiple quotes/semicolons
        r"'\s*\d+\s*'\s*=\s*'\s*\d+\s*'",  # Quoted numeric equality (SQL injection like '1'='1')
        r'<\s*script',                # Script tags
        r'javascript\s*:',            # JavaScript protocol
        r'\beval\s*\(',               # eval function
        r'\bsetTimeout\s*\(',         # setTimeout function
        r'\bsetInterval\s*\(',        # setInterval function
    ]
    
    for pattern in suspicious_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    
    return False
