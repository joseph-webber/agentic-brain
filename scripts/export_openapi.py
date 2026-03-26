#!/usr/bin/env python3
import json
import os
import sys

# Add src to path so we can import agentic_brain
current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(current_dir, "../src")
sys.path.insert(0, src_path)

try:
    from agentic_brain.api.server import app
except ImportError as e:
    print(f"Error importing app: {e}")
    print(f"PYTHONPATH: {sys.path}")
    sys.exit(1)


def export_openapi():
    print("Generating OpenAPI schema...")
    openapi_schema = app.openapi()

    docs_dir = os.path.join(current_dir, "../docs")
    output_path = os.path.join(docs_dir, "openapi.json")

    os.makedirs(docs_dir, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(openapi_schema, f, indent=2)

    print(f"✅ OpenAPI schema exported to {output_path}")


if __name__ == "__main__":
    export_openapi()
