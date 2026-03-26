import typer
from typer.testing import CliRunner
from typing import Optional

app = typer.Typer()

@app.command()
def entity(
    action: str,
    name: Optional[str] = typer.Argument(None),
    fields: str = typer.Option("", "--fields"),
):
    print(f"action={action}, name={name}")

runner = CliRunner()

print("--- Test 1: entity create ---")
result = runner.invoke(app, ["entity", "create"])
print(f"Exit: {result.exit_code}")
print(result.stdout)

print("--- Test 3: create ---")
result = runner.invoke(app, ["create"])
print(f"Exit: {result.exit_code}")
print(result.stdout)

print("--- Test 4: create Note ---")
result = runner.invoke(app, ["create", "Note"])
print(f"Exit: {result.exit_code}")
print(result.stdout)
