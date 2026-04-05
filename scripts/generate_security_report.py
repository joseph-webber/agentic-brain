#!/usr/bin/env python3
"""
Security Report Generator for agentic-brain
Runs penetration tests and generates a formatted report.
"""

import json
import os
import sys
import time
from datetime import datetime

import pytest


def generate_report():
    print("🔒 Starting Security Penetration Test Suite...")
    print(f"Time: {datetime.now().isoformat()}")
    print("-" * 50)

    # Run pytest and capture output
    # We use a custom plugin or hook to get structured data,
    # but for simplicity we'll just run it and check exit code

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = f"security_report_{timestamp}.md"

    class ReportPlugin:
        def __init__(self):
            self.passed = 0
            self.failed = 0
            self.results = []

        def pytest_runtest_logreport(self, report):
            if report.when == "call":
                status = "PASSED" if report.passed else "FAILED"
                if report.passed:
                    self.passed += 1
                else:
                    self.failed += 1
                self.results.append(
                    {
                        "nodeid": report.nodeid,
                        "status": status,
                        "duration": report.duration,
                    }
                )

    plugin = ReportPlugin()

    # Run tests programmatically
    ret_code = pytest.main(
        ["tests/test_security/test_pentest.py", "-v"], plugins=[plugin]
    )

    # Generate Markdown Report
    with open(report_file, "w") as f:
        f.write("# 🛡️ Security Penetration Test Report\n\n")
        f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("**Target:** agentic-brain\n\n")

        f.write("## 📊 Summary\n")
        total = plugin.passed + plugin.failed
        success_rate = (plugin.passed / total * 100) if total > 0 else 0

        f.write(f"- **Total Tests:** {total}\n")
        f.write(f"- **Passed:** {plugin.passed} ✅\n")
        f.write(f"- **Failed:** {plugin.failed} ❌\n")
        f.write(f"- **Success Rate:** {success_rate:.1f}%\n\n")

        f.write("## 🔍 Detailed Findings\n\n")

        categories = {
            "Injection": [],
            "Auth": [],
            "Data": [],
            "DoS": [],
            "Privilege": [],
        }

        for res in plugin.results:
            name = res["nodeid"].split("::")[-1]
            status_icon = "✅" if res["status"] == "PASSED" else "❌"

            # Categorize
            cat = "Other"
            if "Injection" in res["nodeid"]:
                cat = "Injection"
            elif "Auth" in res["nodeid"]:
                cat = "Auth"
            elif "Data" in res["nodeid"]:
                cat = "Data"
            elif "DoS" in res["nodeid"]:
                cat = "DoS"
            elif "Privilege" in res["nodeid"]:
                cat = "Privilege"

            if cat != "Other":
                categories[cat].append(f"- {status_icon} **{name}**: {res['status']}")
            else:
                categories.setdefault("Other", []).append(
                    f"- {status_icon} **{name}**: {res['status']}"
                )

        for cat, items in categories.items():
            if items:
                f.write(f"### {cat} Tests\n")
                for item in items:
                    f.write(f"{item}\n")
                f.write("\n")

        f.write("## 📝 Recommendations\n")
        if plugin.failed == 0:
            f.write(
                "No critical vulnerabilities detected in this suite. Continue regular automated testing.\n"
            )
        else:
            f.write(
                "⚠️ Vulnerabilities detected! Immediate remediation required for failed tests.\n"
            )

    print(f"\n✅ Report generated: {report_file}")

    # Also print to stdout
    with open(report_file) as f:
        print(f.read())

    return ret_code


if __name__ == "__main__":
    sys.exit(generate_report())
