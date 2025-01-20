import os

__all__ = ['SecureFileCheck', ]

def SecureFileCheck(filename: str, directory: str = '~') -> str:
    """
    This function is a helper function to ensure file directory is not being hard link or symlink to another directory.

    Parameters:
    ----------

    filename: str
        The file name to be checked. The extension must be included.

    directory: str
        The directory path to be checked.

    Returns:
    -------

    str
        The file path of the file name.

    """
    directory = os.path.expanduser(directory or '~')
    path = os.path.join(directory, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"The file {path} does not exist.")
    if os.path.islink(path):
        raise FileExistsError(f"The file {path} is a symbolic link. You must use the real file path.")
    realpath = os.path.realpath(path, strict=True)
    realdir = os.path.realpath(directory, strict=True)
    if os.path.commonpath([realpath, realdir]) != realdir:
        raise FileExistsError(f"The file {path} is not in the directory {realdir}.")
    return realpath
