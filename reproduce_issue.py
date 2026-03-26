import click
import typer

print(f"Click: {click.__version__}")
print(f"Typer: {typer.__version__}")
try:

    class TyperChoice(click.Choice[str]):
        pass

    print("Subscripting Choice works")
except Exception as e:
    print(f"Error: {e}")
