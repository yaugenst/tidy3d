"""
Commandline interface for tidy3d.
"""

import json
import os.path
import ssl

import click
import requests

from ... import config
from ...config import CONFIG_PATHS
from ..cli.constants import CREDENTIAL_FILE, TIDY3D_DIR
from ..cli.migrate import migrate
from ..core.constants import HEADER_APIKEY
from ..core.environment import Env
from .develop.index import develop

# Prevent race condition on threads
os.makedirs(TIDY3D_DIR, exist_ok=True)


@click.group()
def tidy3d_cli():
    """
    Tidy3d command line tool.
    """


@click.command()
@click.option("--apikey", prompt=False)
def configure(apikey):
    """Click command to configure the api key.

    Parameters
    ----------
    apikey : str
        User input api key.
    """
    configure_fn(apikey)


def configure_fn(apikey: str) -> None:
    """Python function that tries to set configuration based on a provided API key.

    Parameters
    ----------
    apikey : str
        User input api key.
    """

    def auth(req):
        """Enrich auth information to request.
        Parameters
        ----------
        req : requests.Request
            the request needs to add headers for auth.
        Returns
        -------
        requests.Request
            Enriched request.
        """
        req.headers[HEADER_APIKEY] = apikey
        return req

    if os.path.exists(CREDENTIAL_FILE):
        with open(CREDENTIAL_FILE, encoding="utf-8") as fp:
            auth_json = json.load(fp)
        email = auth_json["email"]
        password = auth_json["password"]
        if email and password:
            if migrate():
                click.echo("Migrate successfully. auth.json is renamed to auth.json.bak.")
                return

    if not apikey:
        current_apikey = config.auth.apikey or ""
        message = f"Current API key: [{current_apikey}]\n" if current_apikey else ""
        apikey = click.prompt(f"{message}Please enter your api key", type=str)

    try:
        resp = requests.get(
            f"{Env.current.web_api_endpoint}/apikey", auth=auth, verify=Env.current.ssl_verify
        )
    except (requests.exceptions.SSLError, ssl.SSLError):
        resp = requests.get(f"{Env.current.web_api_endpoint}/apikey", auth=auth, verify=False)

    if resp.status_code == 200:
        click.echo("Configured successfully.")

        # Update the config with the new API key
        config.auth.apikey = apikey

        # If a legacy config already exists, save to that location to maintain compatibility
        legacy_path = CONFIG_PATHS["legacy"]
        old_legacy_path = CONFIG_PATHS["old_legacy"]
        if legacy_path.exists() or old_legacy_path.exists():
            config.save(legacy_path)
            click.echo(f"Configuration saved to {legacy_path}")
        else:
            # Otherwise save to the XDG location (default)
            config.save()
            xdg_path = CONFIG_PATHS["xdg"]
            click.echo(f"Configuration saved to {xdg_path}")
    else:
        click.echo("API key is invalid.")


@click.command()
def migration():
    """Click command to migrate the credential to api key."""
    migrate()


@click.command()
@click.argument("lsf_file")
@click.argument("new_file")
def convert(lsf_file, new_file):
    """Click command to convert .lsf project into Tidy3D .py file"""
    raise ValueError(
        "The converter feature is deprecated. "
        "To use this feature, please use the external tool at "
        "'https://github.com/hirako22/Lumerical-to-Tidy3D-Converter'."
    )


tidy3d_cli.add_command(configure)
tidy3d_cli.add_command(migration)
tidy3d_cli.add_command(convert)
tidy3d_cli.add_command(develop)
