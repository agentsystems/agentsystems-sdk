#!/usr/bin/env python3
import os
import typer

app = typer.Typer()


@app.command()
def test(
    token: str = typer.Option(
        None, "--token", envvar="DOCKER_OAT", help="Test token from env"
    )
):
    print(f"Token from env: {token}")
    print(f"Direct env check: {os.getenv('DOCKER_OAT')}")


if __name__ == "__main__":
    app()
