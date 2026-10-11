"""
Vulnerable Python test fixture for CodeGuard AI evaluation.
Demonstrates SQL injection, arbitrary code execution, insecure subprocess, and hardcoded secret.
"""

import subprocess
import os
import sqlite3

OPENAI_API_KEY = "sk-abcdef1234567890abcdef1234567890"

def get_user_by_name(cursor, username: str):
    # Vulnerability 1: SQL Injection
    query = "SELECT * FROM users WHERE username = %s" % username
    return cursor.execute(query)

def calculate_expression(user_input: str):
    # Vulnerability 2: Arbitrary code execution via eval
    return eval(user_input)

def run_system_diagnostic(host: str):
    # Vulnerability 3: Insecure subprocess with shell=True
    return subprocess.run(f"ping -c 1 {host}", shell=True, capture_output=True)
