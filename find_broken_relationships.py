#!/usr/bin/env python3
"""
Script to find all broken SQLAlchemy relationships in the models directory.
"""
import os
import re
from pathlib import Path

# Get all model files
models_dir = Path("app/models")
model_files = list(models_dir.glob("*.py"))

# Extract all class names from models
all_model_classes = set()
for file in model_files:
    content = file.read_text()
    # Find all class definitions that inherit from Base
    classes = re.findall(r'^class (\w+)\(Base\):', content, re.MULTILINE)
    all_model_classes.update(classes)

print(f"Found {len(all_model_classes)} model classes:")
print(sorted(all_model_classes))
print("\n" + "="*80 + "\n")

# Now find all relationship() calls
broken_relationships = []

for file in model_files:
    content = file.read_text()
    # Find all relationship definitions
    relationships = re.findall(
        r'relationship\(["\'](\w+)["\']',
        content
    )
    
    for rel_model in relationships:
        if rel_model not in all_model_classes:
            # Find the line number
            lines = content.split('\n')
            for i, line in enumerate(lines, 1):
                if f'relationship("{rel_model}"' in line or f"relationship('{rel_model}'" in line:
                    broken_relationships.append({
                        'file': str(file),
                        'line': i,
                        'missing_model': rel_model,
                        'line_content': line.strip()
                    })

print(f"Found {len(broken_relationships)} broken relationships:\n")
for br in broken_relationships:
    print(f"ERROR {br['file']}:{br['line']}")
    print(f"   Missing model: {br['missing_model']}")
    print(f"   Line: {br['line_content']}")
    print()

