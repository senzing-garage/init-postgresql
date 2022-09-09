#! /usr/bin/env python3

'''
# -----------------------------------------------------------------------------
# init-postgresql initializes a PostgreSQL database for use with Senzing.
#   - Creates the schema (tables, indexes, etc.)
#   - Inserts initial Senzing configuration
#   - init-postgresql.py is idempotent.  It can be run repeatedly.
# -----------------------------------------------------------------------------
'''

# Import from standard library. https://docs.python.org/3/library/

import argparse
import json
import linecache
import logging
import os
import signal
import string
import sys
import time
import urllib.request
from urllib.parse import urlparse, urlunparse

# Import from https://pypi.org/

import psycopg2

# Import from Senzing.

from senzing import G2Config, G2ConfigMgr, G2ModuleException

# Metadata

__all__ = []
__version__ = "1.0.4"  # See https://www.python.org/dev/peps/pep-0396/
__date__ = '2022-08-04'
__updated__ = '2022-09-09'

# See https://github.com/Senzing/knowledge-base/blob/main/lists/senzing-product-ids.md

SENZING_PRODUCT_ID = "5030"
LOG_FORMAT = '%(asctime)s %(message)s'

# Working with bytes.

KILOBYTES = 1024
MEGABYTES = 1024 * KILOBYTES
GIGABYTES = 1024 * MEGABYTES

# Lists from https://www.ietf.org/rfc/rfc1738.txt

SAFE_CHARACTER_LIST = ['$', '-', '_', '.', '+', '!', '*', '(', ')', ',', '"'] + list(string.ascii_letters)
UNSAFE_CHARACTER_LIST = ['"', '<', '>', '#', '%', '{', '}', '|', '\\', '^', '~', '[', ']', '`']
RESERVED_CHARACTER_LIST = [';', ',', '/', '?', ':', '@', '=', '&']

# Singletons

G2_CONFIG_SINGLETON = None
G2_CONFIGURATION_MANAGER_SINGLETON = None

# The "configuration_locator" describes where configuration variables are in:
# 1) Command line options, 2) Environment variables, 3) Configuration files, 4) Default values

CONFIGURATION_LOCATOR = {
    "data_dir": {
        "default": "/opt/senzing/data",
        "env": "SENZING_DATA_DIR",
        "cli": "data-dir"
    },
    "debug": {
        "default": False,
        "env": "SENZING_DEBUG",
        "cli": "debug"
    },
    "engine_configuration_json": {
        "default": None,
        "env": "SENZING_ENGINE_CONFIGURATION_JSON",
        "cli": "engine-configuration-json"
    },
    "etc_dir": {
        "default": "/etc/opt/senzing",
        "env": "SENZING_ETC_DIR",
        "cli": "etc-dir"
    },
    "database_url": {
        "default": None,
        "env": "SENZING_DATABASE_URL",
        "cli": "database-url"
    },
    "g2_dir": {
        "default": "/opt/senzing/g2",
        "env": "SENZING_G2_DIR",
        "cli": "g2-dir"
    },
    "input_sql_url": {
        "default": "/opt/senzing/g2/resources/schema/g2core-schema-postgresql-create.sql",
        "env": "SENZING_INPUT_SQL_URL",
        "cli": "input-sql-url"
    },
    "log_level_parameter": {
        "default": "info",
        "env": "SENZING_LOG_LEVEL",
        "cli": "log-level-parameter"
    },
    "sleep_time_in_seconds": {
        "default": 0,
        "env": "SENZING_SLEEP_TIME_IN_SECONDS",
        "cli": "sleep-time-in-seconds"
    },
    "subcommand": {
        "default": None,
        "env": "SENZING_SUBCOMMAND",
    }
}

# Enumerate keys in 'configuration_locator' that should not be printed to the log.

KEYS_TO_REDACT = [
    "database_url",
    "engine_configuration_json",
]

# -----------------------------------------------------------------------------
# Define argument parser
# -----------------------------------------------------------------------------


def get_parser():
    ''' Parse commandline arguments. '''

    subcommands = {
        'mandatory': {
            "help": 'Perform mandatory initialization tasks.',
            "argument_aspects": ["common", "init_sql"],
        },
        'sleep': {
            "help": 'Do nothing but sleep. For Docker testing.',
            "arguments": {
                "--sleep-time-in-seconds": {
                    "dest": "sleep_time_in_seconds",
                    "metavar": "SENZING_SLEEP_TIME_IN_SECONDS",
                    "help": "Sleep time in seconds. DEFAULT: 0 (infinite)"
                },
            },
        },
        'version': {
            "help": 'Print version of program.',
        },
        'docker-acceptance-test': {
            "help": 'For Docker acceptance testing.',
        },
    }

    # Define argument_aspects.

    argument_aspects = {
        "common": {
            "--data-dir": {
                "dest": "data_dir",
                "metavar": "SENZING_DATA_DIR",
                "help": "Path to Senzing data. Default: /opt/senzing/data"
            },
            "--database-url": {
                "dest": "database_url",
                "metavar": "SENZING_DATABASE_URL",
                "help": "URL of PostgreSQL database. Default: none"
            },
            "--debug": {
                "dest": "debug",
                "action": "store_true",
                "help": "Enable debugging. (SENZING_DEBUG) Default: False"
            },
            "--engine-configuration-json": {
                "dest": "engine_configuration_json",
                "metavar": "SENZING_ENGINE_CONFIGURATION_JSON",
                "help": "Advanced Senzing engine configuration. Default: none"
            },
            "--etc-dir": {
                "dest": "etc_dir",
                "metavar": "SENZING_ETC_DIR",
                "help": "Path to Senzing configuration. Default: /etc/opt/senzing"
            },
            "--g2-dir": {
                "dest": "g2_dir",
                "metavar": "SENZING_G2_DIR",
                "help": "Path to Senzing binaries. Default: /opt/senzing/g2"
            },
        },
        "init_sql": {
            "--input-sql-url": {
                "dest": "input_sql_url",
                "metavar": "SENZING_INPUT_SQL_URL",
                "help": "file:// or http:// location of file of SQL statements. Default: none"
            },
        },
    }

    # Augment "subcommands" variable with arguments specified by aspects.

    for subcommand_value in subcommands.values():
        if 'argument_aspects' in subcommand_value:
            for aspect in subcommand_value['argument_aspects']:
                if 'arguments' not in subcommand_value:
                    subcommand_value['arguments'] = {}
                arguments = argument_aspects.get(aspect, {})
                for argument, argument_value in arguments.items():
                    subcommand_value['arguments'][argument] = argument_value

    parser = argparse.ArgumentParser(prog="init-postgres.py", description="Add description. For more information, see https://github.com/Senzing/init-postgres")
    subparsers = parser.add_subparsers(dest='subcommand', help='Subcommands (SENZING_SUBCOMMAND):')

    for subcommand_key, subcommand_values in subcommands.items():
        subcommand_help = subcommand_values.get('help', "")
        subcommand_arguments = subcommand_values.get('arguments', {})
        subparser = subparsers.add_parser(subcommand_key, help=subcommand_help)
        for argument_key, argument_values in subcommand_arguments.items():
            subparser.add_argument(argument_key, **argument_values)

    return parser

# -----------------------------------------------------------------------------
# Message handling
# -----------------------------------------------------------------------------

# 1xx Informational (i.e. logging.info())
# 3xx Warning (i.e. logging.warning())
# 5xx User configuration issues (either logging.warning() or logging.err() for Client errors)
# 7xx Internal error (i.e. logging.error for Server errors)
# 9xx Debugging (i.e. logging.debug())


MESSAGE_INFO = 100
MESSAGE_WARN = 300
MESSAGE_ERROR = 700
MESSAGE_DEBUG = 900

MESSAGE_DICTIONARY = {
    "100": "senzing-" + SENZING_PRODUCT_ID + "{0:04d}I",
    "170": "Created new default config in SYS_CFG having ID {0}",
    "171": "Default config in SYS_CFG already exists having ID {0}",
    "293": "For information on warnings and errors, see https://github.com/Senzing/stream-loader#errors",
    "294": "Version: {0}  Updated: {1}",
    "295": "Sleeping infinitely.",
    "296": "Sleeping {0} seconds.",
    "297": "Enter {0}",
    "298": "Exit {0}",
    "299": "{0}",
    "300": "senzing-" + SENZING_PRODUCT_ID + "{0:04d}W",
    "499": "{0}",
    "500": "senzing-" + SENZING_PRODUCT_ID + "{0:04d}E",
    "568": "Original and new database URLs do not match. Original URL: {0}; Reconstructed URL: {1}",
    "696": "Bad SENZING_SUBCOMMAND: {0}.",
    "697": "No processing done.",
    "698": "Program terminated with error.",
    "699": "{0}",
    "700": "senzing-" + SENZING_PRODUCT_ID + "{0:04d}E",
    "701": "Missing required parameter: {0}",
    "702": "SQL.execute error: {0}",
    "730": "There are not enough safe characters to do the translation. Unsafe Characters: {0}; Safe Characters: {1}",
    "896": "Could not initialize G2ConfigMgr with '{0}'. Error: {1}",
    "897": "Could not initialize G2Config with '{0}'. Error: {1}",
    "899": "{0}",
    "900": "senzing-" + SENZING_PRODUCT_ID + "{0:04d}D",
    "901": "{0} will not be modified",
    "902": "{0} - Was not created because there is no {1}",
    "950": "Enter function: {0}",
    "951": "Exit  function: {0}",
    "998": "Debugging enabled.",
    "999": "{0}",
}


def message(index, *args):
    ''' Return an instantiated message. '''
    index_string = str(index)
    template = MESSAGE_DICTIONARY.get(index_string, "No message for index {0}.".format(index_string))
    return template.format(*args)


def message_generic(generic_index, index, *args):
    ''' Return a formatted message. '''
    return "{0} {1}".format(message(generic_index, index), message(index, *args))


def message_info(index, *args):
    ''' Return an info message. '''
    return message_generic(MESSAGE_INFO, index, *args)


def message_warning(index, *args):
    ''' Return a warning message. '''
    return message_generic(MESSAGE_WARN, index, *args)


def message_error(index, *args):
    ''' Return an error message. '''
    return message_generic(MESSAGE_ERROR, index, *args)


def message_debug(index, *args):
    ''' Return a debug message. '''
    return message_generic(MESSAGE_DEBUG, index, *args)


def get_exception():
    ''' Get details about an exception. '''
    exception_type, exception_object, traceback = sys.exc_info()
    frame = traceback.tb_frame
    line_number = traceback.tb_lineno
    filename = frame.f_code.co_filename
    linecache.checkcache(filename)
    line = linecache.getline(filename, line_number, frame.f_globals)
    return {
        "filename": filename,
        "line_number": line_number,
        "line": line.strip(),
        "exception": exception_object,
        "type": exception_type,
        "traceback": traceback,
    }

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------


def get_configuration(subcommand, args):
    ''' Order of precedence: CLI, OS environment variables, INI file, default. '''
    result = {}

    # Copy default values into configuration dictionary.

    for key, value in list(CONFIGURATION_LOCATOR.items()):
        result[key] = value.get('default', None)

    # "Prime the pump" with command line args. This will be done again as the last step.

    for key, value in list(args.__dict__.items()):
        new_key = key.format(subcommand.replace('-', '_'))
        if value:
            result[new_key] = value

    # Copy OS environment variables into configuration dictionary.

    for key, value in list(CONFIGURATION_LOCATOR.items()):
        os_env_var = value.get('env', None)
        if os_env_var:
            os_env_value = os.getenv(os_env_var, None)
            if os_env_value:
                result[key] = os_env_value

    # Copy 'args' into configuration dictionary.

    for key, value in list(args.__dict__.items()):
        new_key = key.format(subcommand.replace('-', '_'))
        if value:
            result[new_key] = value

    # Add program information.

    result['program_version'] = __version__
    result['program_updated'] = __updated__

    # Special case: subcommand from command-line

    if args.subcommand:
        result['subcommand'] = args.subcommand

    # Special case: Change boolean strings to booleans.

    booleans = [
        'debug'
    ]
    for boolean in booleans:
        boolean_value = result.get(boolean)
        if isinstance(boolean_value, str):
            boolean_value_lower_case = boolean_value.lower()
            if boolean_value_lower_case in ['true', '1', 't', 'y', 'yes']:
                result[boolean] = True
            else:
                result[boolean] = False

    # Special case: Change integer strings to integers.

    integers = [
        'sleep_time_in_seconds'
    ]
    for integer in integers:
        integer_string = result.get(integer)
        result[integer] = int(integer_string)

    # Normalize SENZING_INPUT_URL

    if result.get('input_sql_url', "").startswith("/"):
        result['input_sql_url'] = "file://{0}".format(result.get('input_sql_url'))

    return result


def validate_configuration(config):
    ''' Check aggregate configuration from commandline options, environment variables, config files, and defaults. '''

    user_warning_messages = []
    user_error_messages = []

    # Perform subcommand specific checking.

    subcommand = config.get('subcommand')

    if subcommand in ['mandatory']:

        if not config.get('input_sql_url'):
            user_error_messages.append(message_error(701, 'SENZING_INPUT_SQL_URL'))

        if not config.get('database_url') and not config.get('engine_configuration_json'):
            user_error_messages.append(message_error(701, 'either SENZING_DATABASE_URL or SENZING_ENGINE_CONFIGURATION_JSON'))

    # Log warning messages.

    for user_warning_message in user_warning_messages:
        logging.warning(user_warning_message)

    # Log error messages.

    for user_error_message in user_error_messages:
        logging.error(user_error_message)

    # Log where to go for help.

    if len(user_warning_messages) > 0 or len(user_error_messages) > 0:
        logging.info(message_info(293))

    # If there are error messages, exit.

    if len(user_error_messages) > 0:
        exit_error(697)


def redact_configuration(config):
    ''' Return a shallow copy of config with certain keys removed. '''
    result = config.copy()
    for key in KEYS_TO_REDACT:
        try:
            result.pop(key)
        except Exception:
            pass
    return result

# -----------------------------------------------------------------------------
# Utility functions
# -----------------------------------------------------------------------------


def bootstrap_signal_handler(signal_number, frame):
    ''' Exit on signal error. '''
    logging.debug(message_debug(901, signal_number, frame))
    sys.exit(0)


def create_signal_handler_function(args):
    ''' Tricky code.  Uses currying technique. Create a function for signal handling.
        that knows about "args".
    '''

    def result_function(signal_number, frame):
        logging.info(message_info(298, args))
        logging.debug(message_debug(901, signal_number, frame))
        sys.exit(0)

    return result_function


def entry_template(config):
    ''' Format of entry message. '''
    debug = config.get("debug", False)
    config['start_time'] = time.time()
    if debug:
        final_config = config
    else:
        final_config = redact_configuration(config)
    config_json = json.dumps(final_config, sort_keys=True)
    return message_info(297, config_json)


def exit_template(config):
    ''' Format of exit message. '''
    debug = config.get("debug", False)
    stop_time = time.time()
    config['stop_time'] = stop_time
    config['elapsed_time'] = stop_time - config.get('start_time', stop_time)
    if debug:
        final_config = config
    else:
        final_config = redact_configuration(config)
    config_json = json.dumps(final_config, sort_keys=True)
    return message_info(298, config_json)


def exit_error(index, *args):
    ''' Log error message and exit program. '''
    logging.error(message_error(index, *args))
    logging.error(message_error(698))
    sys.exit(1)


def exit_silently():
    ''' Exit program. '''
    sys.exit(0)

# -----------------------------------------------------------------------------
# Class: G2Initializer
# -----------------------------------------------------------------------------


class G2Initializer:
    '''Perform steps to initialize Senzing.'''

    def __init__(self, g2_configuration_manager, g2_config):
        self.g2_config = g2_config
        self.g2_configuration_manager = g2_configuration_manager

    def create_default_config_id(self):
        ''' Initialize the G2 database. '''

        # Determine of a default/initial G2 configuration already exists.

        default_config_id_bytearray = bytearray()
        try:
            self.g2_configuration_manager.getDefaultConfigID(default_config_id_bytearray)
        except Exception as err:
            raise Exception("G2ConfigMgr.getDefaultConfigID({0}) failed".format(default_config_id_bytearray)) from err

        # If a default configuration exists, there is nothing more to do.

        if default_config_id_bytearray:
            logging.info(message_info(171, default_config_id_bytearray.decode()))
            return None

        # If there is no default configuration, create one in the 'configuration_bytearray' variable.

        config_handle = self.g2_config.create()
        configuration_bytearray = bytearray()
        try:
            self.g2_config.save(config_handle, configuration_bytearray)
        except Exception as err:
            raise Exception("G2Confg.save({0}, {1}) failed".format(config_handle, configuration_bytearray)) from err

        self.g2_config.close(config_handle)

        # Save configuration JSON into G2 database.

        config_comment = "Initial configuration."
        new_config_id = bytearray()
        try:
            self.g2_configuration_manager.addConfig(configuration_bytearray.decode(), config_comment, new_config_id)
        except Exception as err:
            raise Exception("G2ConfigMgr.addConfig({0}, {1}, {2}) failed".format(configuration_bytearray.decode(), config_comment, new_config_id)) from err

        # Set the default configuration ID.

        try:
            self.g2_configuration_manager.setDefaultConfigID(new_config_id)
        except Exception as err:
            raise Exception("G2ConfigMgr.setDefaultConfigID({0}) failed".format(new_config_id)) from err

        return new_config_id

# -----------------------------------------------------------------------------
# Database URL parsing
# -----------------------------------------------------------------------------


def translate(mapping, astring):
    ''' Translate characters. '''

    new_string = str(astring)
    for key, value in mapping.items():
        new_string = new_string.replace(key, value)
    return new_string


def get_unsafe_characters(astring):
    ''' Return the list of unsafe characters found in astring. '''

    result = []
    for unsafe_character in UNSAFE_CHARACTER_LIST:
        if unsafe_character in astring:
            result.append(unsafe_character)
    return result


def get_safe_characters(astring):
    ''' Return the list of safe characters found in astring. '''

    result = []
    for safe_character in SAFE_CHARACTER_LIST:
        if safe_character not in astring:
            result.append(safe_character)
    return result


def parse_database_url(original_senzing_database_url):
    ''' Given a canonical database URL, decompose into URL components. '''

    result = {}

    # Get the value of SENZING_DATABASE_URL environment variable.

    senzing_database_url = original_senzing_database_url

    # Create lists of safe and unsafe characters.

    unsafe_characters = get_unsafe_characters(senzing_database_url)
    safe_characters = get_safe_characters(senzing_database_url)

    # Detect an error condition where there are not enough safe characters.

    if len(unsafe_characters) > len(safe_characters):
        logging.error(message_error(730, unsafe_characters, safe_characters))
        return result

    # Perform translation.
    # This makes a map of safe character mapping to unsafe characters.
    # "senzing_database_url" is modified to have only safe characters.

    translation_map = {}
    safe_characters_index = 0
    for unsafe_character in unsafe_characters:
        safe_character = safe_characters[safe_characters_index]
        safe_characters_index += 1
        translation_map[safe_character] = unsafe_character
        senzing_database_url = senzing_database_url.replace(unsafe_character, safe_character)

    # Parse "translated" URL.

    parsed = urlparse(senzing_database_url)
    schema = parsed.path.strip('/')

    # Construct result.

    result = {
        'scheme': translate(translation_map, parsed.scheme),
        'netloc': translate(translation_map, parsed.netloc),
        'path': translate(translation_map, parsed.path),
        'params': translate(translation_map, parsed.params),
        'query': translate(translation_map, parsed.query),
        'fragment': translate(translation_map, parsed.fragment),
        'username': translate(translation_map, parsed.username),
        'password': translate(translation_map, parsed.password),
        'hostname': translate(translation_map, parsed.hostname),
        'port': translate(translation_map, parsed.port),
        'schema': translate(translation_map, schema),
    }

    # For safety, compare original URL with reconstructed URL.

    url_parts = [
        result.get('scheme'),
        result.get('netloc'),
        result.get('path'),
        result.get('params'),
        result.get('query'),
        result.get('fragment'),
    ]
    test_senzing_database_url = urlunparse(url_parts)
    if test_senzing_database_url != original_senzing_database_url:
        logging.warning(message_warning(568, original_senzing_database_url, test_senzing_database_url))

    # Return result.

    return result

# -----------------------------------------------------------------------------
# Utility functions
# -----------------------------------------------------------------------------


def create_senzing_database_connection_string(database_url):
    '''Transform PostgreSQL URL to a format Senzing understands.'''
    parsed_database_url = parse_database_url(database_url)
    return "{scheme}://{username}:{password}@{hostname}:{port}:{schema}/".format(**parsed_database_url)


def get_db_parameters(database_url):
    ''' Tokenize a database URL. '''

    parsed_database_url = parse_database_url(database_url)
    result = {
        'dbname': parsed_database_url.get('schema', ""),
        'user': parsed_database_url.get('username', ""),
        'password':parsed_database_url.get('password', ""),
        'host':parsed_database_url.get('hostname', ""),
        "port":parsed_database_url.get('port', ""),
    }
    return result


def process_sql_file(input_url, db_parameters):
    ''' Read an SQL file line-by-line and do a database execute on each line. '''

    db_connection = psycopg2.connect(**db_parameters)
    db_connection.autocommit = True

    if input_url:
        with urllib.request.urlopen(input_url) as input_file:
            for line in input_file:
                line_string = line.decode('utf-8').strip()
                if line_string:
                    try:
                        db_cursor = db_connection.cursor()
                        db_cursor.execute(line_string)
                        db_cursor.close()
                    except (Exception, psycopg2.DatabaseError) as error:
                        err_message = ' '.join(str(error).split())
                        logging.error(message_error(702, err_message))

    if db_connection is not None:
        db_connection.close()


def create_database_url(a_string, old_value, new_value, occurrence):
    ''' Replace the last instance of a character to form a proper URL. '''

    split_list = a_string.rsplit(old_value, occurrence)
    return new_value.join(split_list)

# -----------------------------------------------------------------------------
# Senzing services.
# -----------------------------------------------------------------------------


def get_g2_configuration_dictionary(config):
    ''' Construct a dictionary in the form of the old ini files. '''

    result = {
        "PIPELINE": {
            "CONFIGPATH": config.get("etc_dir"),
            "RESOURCEPATH": "{0}/resources".format(config.get("g2_dir")),
            "SUPPORTPATH": config.get("data_dir"),
        },
        "SQL": {
            "BACKEND": "SQL",
            "CONNECTION": create_senzing_database_connection_string(config.get('database_url')),
        }
    }
    return result


def get_g2_configuration_json(config):
    ''' Return a JSON string with Senzing configuration. '''
    result = ""
    if config.get('engine_configuration_json'):
        result = config.get('engine_configuration_json')
    else:
        result = json.dumps(get_g2_configuration_dictionary(config))
    return result

# -----------------------------------------------------------------------------
# Senzing services.
# -----------------------------------------------------------------------------


def get_g2_config(config, g2_config_name="init-container-G2-config"):
    ''' Get the G2Config resource. '''
    global G2_CONFIG_SINGLETON

    if G2_CONFIG_SINGLETON:
        return G2_CONFIG_SINGLETON

    try:
        g2_configuration_json = get_g2_configuration_json(config)
        result = G2Config()
        result.init(g2_config_name, g2_configuration_json, config.get('debug'))
    except G2ModuleException as err:
        exit_error(897, g2_configuration_json, err)

    G2_CONFIG_SINGLETON = result
    return result


def get_g2_configuration_manager(config, g2_configuration_manager_name="init-container-G2-configuration-manager"):
    ''' Get the G2ConfigMgr resource. '''
    global G2_CONFIGURATION_MANAGER_SINGLETON

    if G2_CONFIGURATION_MANAGER_SINGLETON:
        return G2_CONFIGURATION_MANAGER_SINGLETON

    try:
        g2_configuration_json = get_g2_configuration_json(config)
        result = G2ConfigMgr()
        result.init(g2_configuration_manager_name, g2_configuration_json, config.get('debug'))
    except G2ModuleException as err:
        exit_error(896, g2_configuration_json, err)

    G2_CONFIGURATION_MANAGER_SINGLETON = result
    return result

# -----------------------------------------------------------------------------
# tasks
#   Common function signature: task_XXX(config)
# -----------------------------------------------------------------------------


def task_process_sql_file(config):
    ''' Process a file of SQL statements. '''

    input_url = config.get('input_sql_url')
    db_parameters_list = []

    # If set, include CLI/Environment single database URL.

    database_url = config.get('database_url')
    if database_url:
        db_parameters_list.append(database_url)

    # If set, include database URLs listed in SENZING_ENGINE_CONFIGURATION_JSON.

    engine_configuration_json = config.get('engine_configuration_json')
    if engine_configuration_json:
        engine_configuration = json.loads(engine_configuration_json)

        db_url_raw = engine_configuration.get('SQL', {}).get('CONNECTION')
        if db_url_raw:
            db_parameters_list.append(create_database_url(db_url_raw, ":", "/", 1))

        cluster_key = engine_configuration.get('SQL', {}).get('BACKEND')
        if cluster_key:
            if cluster_key == "SQL":
                pass  # Special case. Do nothing.
            else:
                cluster_values = []
                cluster = engine_configuration.get(cluster_key)
                for value in cluster.values():
                    cluster_values.append(value)
                cluster_values_set = set(cluster_values)

                for cluster_value in cluster_values_set:
                    cluster_db_raw = engine_configuration.get(cluster_value, {}).get("DB_1")
                    db_parameters_list.append(create_database_url(cluster_db_raw, ":", "/", 1))

    # Run the input SQL file against all databases.

    db_parameters_set = set(db_parameters_list)
    for db_parameters in db_parameters_set:
        process_sql_file(input_url, get_db_parameters(db_parameters))


def task_update_senzing_configuration(config):
    ''' Insert Senzing configuration into the database. '''

    # Get Senzing resources.

    g2_config = get_g2_config(config)
    g2_configuration_manager = get_g2_configuration_manager(config)

    # Initialize G2 database.

    g2_initializer = G2Initializer(g2_configuration_manager, g2_config)
    try:
        default_config_id = g2_initializer.create_default_config_id()
        if default_config_id:
            logging.info(message_info(170, default_config_id.decode()))
    except Exception as err:
        logging.error(message_error(701, err, type(err.__cause__), err.__cause__))

# -----------------------------------------------------------------------------
# do_* functions
#   Common function signature: do_XXX(args)
# -----------------------------------------------------------------------------


def do_docker_acceptance_test(subcommand, args):
    ''' For use with Docker acceptance testing. '''

    # Get context from CLI, environment variables, and ini files.

    config = get_configuration(subcommand, args)

    # Prolog.

    logging.info(entry_template(config))

    # Epilog.

    logging.info(exit_template(config))


def do_mandatory(subcommand, args):
    ''' Do a task. '''

    # Get context from CLI, environment variables, and ini files.

    config = get_configuration(subcommand, args)
    validate_configuration(config)

    # Prolog.

    logging.info(entry_template(config))

    # Do work.

    task_process_sql_file(config)
    task_update_senzing_configuration(config)

    # Epilog.

    logging.info(exit_template(config))


def do_sleep(subcommand, args):
    ''' Sleep.  Used for debugging. '''

    # Get context from CLI, environment variables, and ini files.

    config = get_configuration(subcommand, args)

    # Prolog.

    logging.info(entry_template(config))

    # Pull values from configuration.

    sleep_time_in_seconds = config.get('sleep_time_in_seconds')

    # Sleep.

    if sleep_time_in_seconds > 0:
        logging.info(message_info(296, sleep_time_in_seconds))
        time.sleep(sleep_time_in_seconds)

    else:
        sleep_time_in_seconds = 3600
        while True:
            logging.info(message_info(295))
            time.sleep(sleep_time_in_seconds)

    # Epilog.

    logging.info(exit_template(config))


def do_version(subcommand, args):
    ''' Log version information. '''

    logging.info(message_info(294, __version__, __updated__))
    logging.debug(message_debug(902, subcommand, args))

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------


if __name__ == "__main__":

    # Configure logging. See https://docs.python.org/2/library/logging.html#levels

    LOG_LEVEL_MAP = {
        "notset": logging.NOTSET,
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "fatal": logging.FATAL,
        "warning": logging.WARNING,
        "error": logging.ERROR,
        "critical": logging.CRITICAL
    }

    LOG_LEVEL_PARAMETER = os.getenv("SENZING_LOG_LEVEL", "info").lower()
    LOG_LEVEL = LOG_LEVEL_MAP.get(LOG_LEVEL_PARAMETER, logging.INFO)
    logging.basicConfig(format=LOG_FORMAT, level=LOG_LEVEL)
    logging.debug(message_debug(998))

    # Trap signals temporarily until args are parsed.

    signal.signal(signal.SIGTERM, bootstrap_signal_handler)
    signal.signal(signal.SIGINT, bootstrap_signal_handler)

    # Parse the command line arguments.

    SUBCOMMAND = os.getenv("SENZING_SUBCOMMAND", None)
    PARSER = get_parser()
    if len(sys.argv) > 1:
        ARGS = PARSER.parse_args()
        SUBCOMMAND = ARGS.subcommand
    elif SUBCOMMAND:
        ARGS = argparse.Namespace(subcommand=SUBCOMMAND)
    else:
        PARSER.print_help()
        if len(os.getenv("SENZING_DOCKER_LAUNCHED", "")) > 0:
            SUBCOMMAND = "sleep"
            ARGS = argparse.Namespace(subcommand=SUBCOMMAND)
            do_sleep(SUBCOMMAND, ARGS)
        exit_silently()

    # Catch interrupts. Tricky code: Uses currying.

    SIGNAL_HANDLER = create_signal_handler_function(ARGS)
    signal.signal(signal.SIGINT, SIGNAL_HANDLER)
    signal.signal(signal.SIGTERM, SIGNAL_HANDLER)

    # Transform subcommand from CLI parameter to function name string.

    SUBCOMMAND_FUNCTION_NAME = "do_{0}".format(SUBCOMMAND.replace('-', '_'))

    # Test to see if function exists in the code.

    if SUBCOMMAND_FUNCTION_NAME not in globals():
        logging.warning(message_warning(696, SUBCOMMAND))
        PARSER.print_help()
        exit_silently()

    # Tricky code for calling function based on string.

    globals()[SUBCOMMAND_FUNCTION_NAME](SUBCOMMAND, ARGS)
