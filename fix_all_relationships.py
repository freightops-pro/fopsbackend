#!/usr/bin/env python3
"""
Script to fix all broken SQLAlchemy relationships.
"""
from pathlib import Path

# Define replacements
replacements = {
    'relationship("User"': 'relationship("Users"',
    "relationship('User'": "relationship('Users'",
    'relationship("Company"': 'relationship("Companies"',
    "relationship('Company'": "relationship('Companies'",
    'relationship("Load"': 'relationship("Loads"',
    "relationship('Load'": "relationship('Loads'",
}

models_dir = Path("app/models")
model_files = list(models_dir.glob("*.py"))

fixed_files = []

for file in model_files:
    content = file.read_text(encoding='utf-8')
    original_content = content
    
    for old, new in replacements.items():
        content = content.replace(old, new)
    
    if content != original_content:
        file.write_text(content, encoding='utf-8')
        fixed_files.append(str(file))
        print(f"Fixed: {file}")

print(f"\nTotal files fixed: {len(fixed_files)}")

