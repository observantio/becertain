# datasources/exceptions.py

class DataSourceError(Exception):
    pass


class DataSourceUnavailable(DataSourceError):
    pass


class QueryTimeout(DataSourceError):
    pass


class InvalidQuery(DataSourceError):
    pass


class BackendStartupTimeout(DataSourceError):
    pass