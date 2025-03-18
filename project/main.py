import sys
import logging
import click
from api.routes import start_server
from cli.commands import cli, interactive as cli_interactive


def setup_logging():
    """Configure logging"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.getLogger().setLevel(logging.INFO)


@click.group()
@click.option("--debug", is_flag=True, help="Enable debug logging")
def main_cli(debug):
    """University Information System"""
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.debug("Debug logging enabled")


@main_cli.command()
@click.option("--host", default="0.0.0.0", help="API server host")
@click.option("--port", default=8000, type=int, help="API server port")
@click.option(
    "--refresh-interval",
    default=12,
    type=int,
    help="Refresh database every N hours (0 to disable)",
)
def api(host, port, refresh_interval):
    """Start the API server"""
    try:
        start_server(host, port, refresh_interval)
    except Exception as e:
        logging.error(f"API server error: {str(e)}")
        sys.exit(1)


@main_cli.command()
def interactive():
    """Start interactive mode"""
    try:
        logging.info("Starting interactive mode...")
        sys.argv = sys.argv[:1]
        cli_interactive()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        sys.exit(1)


main_cli.add_command(cli)


# * prota import ta courses, meta rebuild prof, meta consolidate names, META einai etoimo

if __name__ == "__main__":
    setup_logging()
    main_cli()
