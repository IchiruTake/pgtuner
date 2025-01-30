"""
MIT License

Copyright (c) 2024 - 2025 Ichiru

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

---------------------------------------------------------------------------
This script is the PostgreSQL database collector for the PyCollect project, which 
aims to collect the current profile and brings out meaningful suggestions for 
database tuning. This script is written in Python and uses the psycopg2 library
to interact with the PostgreSQL database.

The script includes two parts:
- Collect and backup the database profile
- Analyze the profile and generate suggestions

This work may not be there without these great projects:
- PostgreSQL: https://www.postgresql.org/
- postgresqltuner: https://github.com/jfcoz/postgresqltuner/blob/master/postgresqltuner.pl
- timescaledb-tune: https://github.com/timescale/timescaledb-tune

"""
import os
from pprint import pprint
from zoneinfo import ZoneInfo
import logging
import logging.handlers
from typing import Annotated, Literal
from datetime import datetime

from src.static.vars import DATETIME_PATTERN_FOR_FILENAME, Gi, SUGGESTION_ENTRY_READER_DIR
from src.tuner.data.scope import PGTUNER_SCOPE

from src import pgtuner
from src.tuner.pg_dataclass import PG_TUNE_REQUEST, PG_TUNE_RESPONSE

# ==================================================================================================
# Metadata


def optimize(request: PG_TUNE_REQUEST, output_format: Literal['json', 'text', 'file', 'conf'] = 'conf'):
    # entry.init(request)
    response = pgtuner.optimize(request)

    if request.options.enable_sysctl_general_tuning:
        dt_start = datetime.now(ZoneInfo('UTC'))
        filepath = f'{PGTUNER_SCOPE.KERNEL_SYSCTL.value}_{dt_start.strftime(DATETIME_PATTERN_FOR_FILENAME)}.conf'
        result = pgtuner.write(request, response, PGTUNER_SCOPE.KERNEL_SYSCTL, output_format=output_format,
                               output_file=os.path.join(SUGGESTION_ENTRY_READER_DIR, filepath), exclude_names=[])
        # pprint(result)


    if request.options.enable_database_general_tuning:
        dt_start = datetime.now(ZoneInfo('UTC'))
        filepath = f'{PGTUNER_SCOPE.DATABASE_CONFIG.value}_{dt_start.strftime(DATETIME_PATTERN_FOR_FILENAME)}.conf'
        result = pgtuner.write(request, response, PGTUNER_SCOPE.DATABASE_CONFIG, output_format=output_format,
                               output_file=os.path.join(SUGGESTION_ENTRY_READER_DIR, filepath), exclude_names=[])
        # pprint(result)

    # Test the logger of rotation
    # _logger = logging.getLogger(APP_NAME_UPPER)
    # for _handlers in _logger.handlers:
    #     if isinstance(_handlers, (logging.handlers.RotatingFileHandler, logging.handlers.TimedRotatingFileHandler)):
    #         _handlers.doRollover()
    return None



if __name__ == "__main__":
    logical_cpu: int = 16
    ram_cpu_ratio: float | int = 4.0
    # rq = pgtuner.make_tune_request(logical_cpu=logical_cpu, ram_sample=int(logical_cpu * ram_cpu_ratio * Gi))
    # optimize(rq, output_format='file')

    logical_cpu: int = 4
    rq = pgtuner.make_tune_request(logical_cpu=logical_cpu, ram_sample=int(logical_cpu * ram_cpu_ratio * Gi))
    # backup(rq, pgtuner_env_file=None)
    optimize(rq, output_format='file')
    pass
