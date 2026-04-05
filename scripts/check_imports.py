import importlib
import os
import pkgutil
import sys


def check_imports(start_dir):
    print(f"Checking imports in {start_dir}...")
    success_count = 0
    error_count = 0

    # Add src to python path
    src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
    sys.path.insert(0, src_path)

    for root, dirs, files in os.walk(start_dir):
        for file in files:
            if file.endswith(".py") and not file.startswith("test_"):
                # Construct module name
                rel_path = os.path.relpath(os.path.join(root, file), start_dir)
                module_name = "agentic_brain." + rel_path.replace(os.sep, ".")[:-3]
                if module_name.endswith(".__init__"):
                    module_name = module_name[:-9]

                try:
                    importlib.import_module(module_name)
                    print(f"✅ Imported {module_name}")
                    success_count += 1
                except ImportError as e:
                    print(f"❌ Failed to import {module_name}: {e}")
                    error_count += 1
                except Exception as e:
                    print(f"❌ Error importing {module_name}: {e}")
                    error_count += 1

    print("\nImport check complete.")
    print(f"Success: {success_count}")
    print(f"Errors: {error_count}")

    if error_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    src_dir = os.path.join(os.path.dirname(__file__), "..", "src", "agentic_brain")
    check_imports(src_dir)
