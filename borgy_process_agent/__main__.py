import os
import argparse
import importlib

from borgy_process_agent.utils import Env, load_module_from_path
from borgy_process_agent.logger import configure
from borgy_process_agent.runners.base import BaseRunner

env = Env()

parser = argparse.ArgumentParser(description='Ork Process Agent',
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('-d',
                    '--driver',
                    type=str,
                    default='auto',
                    choices=['auto', 'ork', 'docker'],
                    help='Specify the driver type, ork, docker or auto')
parser.add_argument('-c',
                    '--code',
                    type=str,
                    default='borgy_process_agent/usercode/user.py',
                    help='Absolute path to a module or file exposing '
                    '2 callbacks to be used by the process agent. The '
                    'functions must be named user_create and user_update.')
parser.add_argument('-v',
                    '--verbose',
                    action='store_true',
                    default=False,
                    help='Turn on _very_ verbose debug mode.')
parser.add_argument('--api_host',
                    type=str,
                    default='0.0.0.0',
                    help='Host address to use for the PA api server. '
                    'This flag should normally only be used in Docker mode.')
parser.add_argument('--api_port',
                    type=int,
                    default=8666,
                    help='Port to use for the PA api server. '
                    'This flag should normally only be used in Docker mode.')
parser.add_argument('-k',
                    '--keep-alive',
                    action='store_true',
                    default=False,
                    help='Keep the API server alive after all jobs complete. '
                    'Allows to keep using the UI for exploring jobs.')
parser.add_argument('--disable-auto-rerun',
                    action='store_true',
                    default=False,
                    help='Do not automatically rerun INTERRUPTED jobs.')
parser.add_argument('--integration-tests',
                    action='store_true',
                    default=False,
                    help='Special flag to be used only by borgy integration tests. '
                    'Forces the usercode to usercode/integration_tests.py')
parser.add_argument('-s',
                    '--max-running',
                    type=int,
                    default=500,
                    help='Maximum number of jobs to allow running in parallel '
                    'in the cluster.')

def import_runner(module):
    return importlib.import_module(f'borgy_process_agent.runners.{module}').Runner


def main():
    args = parser.parse_args()

    debug: bool = env.get_bool('PA_DEBUG', default=args.verbose)
    api_host: str = env.get('PA_API_HOST', default=args.api_host)
    api_port: int = env.get_int('PA_API_PORT', default=args.api_port)

    logger = configure(debug=debug)
    runner_name = args.driver
    if runner_name == 'auto':
        if 'EAI_JOB_ID' in os.environ and 'EAI_USER' in os.environ:
            runner_name = 'ork'
        else:
            runner_name = 'docker'

    Runner: BaseRunner = import_runner(runner_name)
    usercode_path: str = ('borgy_process_agent/usercode/integration_tests.py'
                          if args.integration_tests else args.code)
    usercode = load_module_from_path(usercode_path)
    logger.info('Loading user code module: %s', usercode_path)
    auto_rerun: bool = not args.disable_auto_rerun
    runner = Runner(api_host=api_host,
                    api_port=api_port,
                    debug=debug,
                    keep_alive=args.keep_alive,
                    max_running=args.max_running,
                    auto_rerun=auto_rerun)
    runner.register_callback('create', usercode.user_create)
    runner.register_callback('update', usercode.user_update)
    runner.start()


if __name__ == '__main__':
    main()
