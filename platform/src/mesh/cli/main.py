"""``mesh`` command-line entry point."""

import typer
from rich.console import Console
from rich.table import Table

from mesh import __version__
from mesh.cli.doctor import default_checks, overall_ok, run_checks
from mesh.core.settings import load_settings

app = typer.Typer(help="AI Mesh prototype CLI.", no_args_is_help=True)


@app.command()
def version() -> None:
    """Print the platform version."""
    typer.echo(f"mesh {__version__}")


@app.command()
def doctor() -> None:
    """Check the local environment and infrastructure. Exits non-zero if any check fails."""
    results = run_checks(default_checks(load_settings()))
    table = Table(title="mesh doctor")
    table.add_column("check")
    table.add_column("status")
    table.add_column("detail")
    for r in results:
        status = "[green]ok[/green]" if r.ok else "[red]FAIL[/red]"
        table.add_row(r.name, status, r.detail)
    Console().print(table)
    if not overall_ok(results):
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
