import logging
import click
from .utils import parse
from jinja2 import Environment, PackageLoader, select_autoescape


logger = logging.getLogger(__name__)


@click.group()
def cloud():
    """Cloud resources management"""
    pass


@cloud.command()
@click.argument('config', type=click.File('r'))
def stack(config):
    """Prepare cloud formation YAML configuration.

    This command prepares a YAML file for `vce cloud create`.
    """
    yaml = parse(config, get_data=False)
    config = yaml.data
    params = {'config': yaml.as_yaml(),
              'system': config['system'],
              'server': config['system']['server'],
              'nodes': config['satellites']+config['stations']}

    env = Environment(
        loader=PackageLoader('vce', 'templates'),
        autoescape=select_autoescape([]),
        extensions=['jinja2.ext.do'])

    template = env.get_template('stack.yml.j2')
    print(template.render(params))
