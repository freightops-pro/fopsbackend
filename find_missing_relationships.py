#!/usr/bin/env python3
"""
Find all models that reference Companies but Companies doesn't have the back_populates
"""
import os
import re
from pathlib import Path

models_dir = Path("app/models")
model_files = list(models_dir.glob("*.py"))

# Find all relationships that reference Companies
companies_references = []

for file in model_files:
    content = file.read_text()
    lines = content.split('\n')
    
    for i, line in enumerate(lines, 1):
        # Look for relationship definitions with back_populates="something"
        if 'relationship(' in line and 'Companies' in line and 'back_populates=' in line:
            # Extract the back_populates value
            match = re.search(r'back_populates=["\'](\w+)["\']', line)
            if match:
                back_pop = match.group(1)
                # Get the model name from the class definition
                for j in range(i-1, max(0, i-50), -1):
                    if 'class ' in lines[j] and '(Base)' in lines[j]:
                        model_match = re.search(r'class (\w+)\(Base\)', lines[j])
                        if model_match:
                            model_name = model_match.group(1)
                            companies_references.append({
                                'model': model_name,
                                'file': str(file),
                                'back_populates': back_pop,
                                'line': i,
                                'content': line.strip()
                            })
                            break

print(f"Found {len(companies_references)} models referencing Companies:\n")
for ref in companies_references:
    print(f"Model: {ref['model']}")
    print(f"  File: {ref['file']}")
    print(f"  Needs relationship: {ref['back_populates']}")
    print(f"  Line {ref['line']}: {ref['content']}")
    print()

