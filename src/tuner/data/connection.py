from pydantic import BaseModel, PostgresDsn, Field, PositiveInt
from pydantic.types import constr

from src.static.vars import (APP_NAME_UPPER, ENV_PGPORT, ENV_PGHOST, ENV_PGDATABASE, ENV_PGUSER, ENV_PGPASSWORD,
                             ENV_PGC_CONN_EXTARGS, )
from src.utils.env import GetEnvVar

__all__ = ["PG_CONNECTION"]

# =============================================================================
_CONSTR = constr(strip_whitespace=True)
_HOSTVARS = [f"{APP_NAME_UPPER}_{ENV_PGHOST}", ENV_PGHOST]
_PORTVARS = [f"{APP_NAME_UPPER}_{ENV_PGPORT}", ENV_PGPORT]
_USERVARS = [f"{APP_NAME_UPPER}_{ENV_PGUSER}", ENV_PGUSER]
_PWDVARS = [f"{APP_NAME_UPPER}_{ENV_PGPASSWORD}", ENV_PGPASSWORD]
_DBVARS = [f"{APP_NAME_UPPER}_{ENV_PGDATABASE}", ENV_PGDATABASE]
_CONNEXTRAVARS = [f"{APP_NAME_UPPER}_{ENV_PGC_CONN_EXTARGS}", ENV_PGC_CONN_EXTARGS]


class PG_CONNECTION(BaseModel):
    f"""
    This class is used to store the PostgreSQL connection information and generate the subsequent DSN string 
    for the connection. If the environment variable is not set, then the user would be asked to input the value.

    Parameters:
    ----------

    host: str
        The PostgreSQL host (extracted from these environment variables by priority: {APP_NAME_UPPER}_{ENV_PGHOST}, 
        or {ENV_PGHOST} (default to 'localhost').

    port: PositiveInt
        The PostgreSQL port (extracted from these environment variables by priority: {APP_NAME_UPPER}_{ENV_PGPORT} 
        or {ENV_PGPORT} (default to 5432).

    user: str
        The PostgreSQL user (extracted from these environment variables by priority: {APP_NAME_UPPER}_{ENV_PGUSER}
        or {ENV_PGUSER} (default to 'postgres').

    pwd: str
        The PostgreSQL password (extracted from these environment variables by priority: {APP_NAME_UPPER}_{ENV_PGPASSWORD}
        or {ENV_PGPASSWORD} (default to 'postgres').

    database: str
        The PostgreSQL database (extracted from these environment variables by priority: {APP_NAME_UPPER}_{ENV_PGDATABASE}
        or {ENV_PGDATABASE} (default to 'postgres').

    conn_ext_args: str
        The PostgreSQL connection extra arguments (extracted from these environment variables by priority:
        {APP_NAME_UPPER}_{ENV_PGC_CONN_EXTARGS} or {ENV_PGC_CONN_EXTARGS} (default to None).

    """
    host: _CONSTR = (
        Field(default_factory=lambda: GetEnvVar(_HOSTVARS, "localhost",
                                                input_message_string="Enter the PostgreSQL host: "),
              frozen=True, description="The PostgreSQL host")
    )
    port: PositiveInt = (
        Field(default_factory=lambda: GetEnvVar(_PORTVARS, 5432, env_type_cast_fn=int, input_type_cast_fn=int,
                                                input_message_string="Enter the PostgreSQL port: "),
              frozen=True, description="The PostgreSQL port")
    )
    user: _CONSTR = (
        Field(default_factory=lambda: GetEnvVar(_USERVARS, "postgres",
                                                input_message_string="Enter the PostgreSQL user: "),
              frozen=True, description="The PostgreSQL user")
    )
    pwd: _CONSTR = (
        Field(default_factory=lambda: GetEnvVar(_PWDVARS, "postgres",
                                                input_message_string="Enter the PostgreSQL password: "),
              frozen=True, description="The PostgreSQL password")
    )
    database: _CONSTR = (
        Field(default_factory=lambda: GetEnvVar(_DBVARS, "postgres",
                                                input_message_string="Enter the PostgreSQL database: "),
              frozen=True, description="The PostgreSQL database")
    )
    conn_ext_args: _CONSTR | None = (
        Field(default_factory=lambda: GetEnvVar(_CONNEXTRAVARS, None,
                                                input_message_string="Enter the PostgreSQL connection extra arguments: "),
              frozen=True, description="The PostgreSQL connection extra arguments")
    )

    @property
    def dsn(self) -> PostgresDsn:
        return PostgresDsn.build(scheme="postgresql", username=self.user, password=self.pwd, host=self.host,
                                 port=self.port, path=self.database, query=self.conn_ext_args)
