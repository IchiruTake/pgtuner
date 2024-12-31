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

This work may not be there without two great projects:
- PostgreSQL: https://www.postgresql.org/
- postgresqltuner: https://github.com/jfcoz/postgresqltuner/blob/master/postgresqltuner.pl
- timescaledb-tune: https://github.com/timescale/timescaledb-tune

Install with library: pydantic python-dotenv typer "psycopg[binary,pool]" toml psutil

"""
import os
import typer
from zoneinfo import ZoneInfo
from pydantic import Field
from typing import Annotated
# from src.gtune import gtune as pgtuner_gtune
from datetime import datetime

from src.static.c_timezone import PreloadGetUTC
from src.static.c_toml import LoadAppToml
from src.static.vars import APP_NAME_LOWER, PRESET_PROFILE_CHECKSUM, DATETIME_PATTERN_FOR_FILENAME, Gi
from src.utils.checksum import checksum

from src import entry
from src.tuner.pg_dataclass import PG_TUNE_REQUEST, PG_SYS_SHARED_INFO

# ==================================================================================================
# Metadata
TIMESTAMP = datetime.now(tz=PreloadGetUTC()[0]).strftime(DATETIME_PATTERN_FOR_FILENAME)


# ==================================================================================================
app = typer.Typer(name=APP_NAME_LOWER, no_args_is_help=True)
# typer.style(fg=typer.colors.BRIGHT_CYAN, bold=True)  # Tune later

@app.command()
def validate():
    LoadAppToml(skip_checksum_verification=True)


@app.command()
def backup(
        request: PG_TUNE_REQUEST,
        pgtuner_env_file: Annotated[str | None, Field(default=".env", description="The environment file to load")],
    ):
    entry.init(request)
    entry.backup(request, pgtuner_env_file, pgtuner_env_override=False)

    return None


@app.command()
def optimize(
        request: PG_TUNE_REQUEST,
        pgtuner_env_file: Annotated[str | None, Field(default=".env", description="The environment file to load")],
        **kwargs_sys_info,
    ):
    # entry.init(request)
    entry.optimize(request, pgtuner_env_file, env_override=False, **kwargs_sys_info)

    return None



if __name__ == "__main__":
    rq = entry.make_tune_request(is_os_user_managed=False)
    backup(rq, pgtuner_env_file=None)
    optimize(rq, pgtuner_env_file=None, vcpu=32, memory=32 * 6.5 * Gi, hyperthreading=True)
    pass
