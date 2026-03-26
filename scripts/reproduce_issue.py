import sys
import os
import traceback

# Add src to python path
src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, src_path)

try:
    print("Importing agentic_brain.infra.health_monitor...")
    import agentic_brain.infra.health_monitor

    print("Success!")
except Exception:
    traceback.print_exc()

try:
    print("\nImporting agentic_brain.infra.event_bridge...")
    import agentic_brain.infra.event_bridge

    print("Success!")
except Exception:
    traceback.print_exc()
