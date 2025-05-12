import multiprocessing as mp
import os
import platform

from src.utils.static import LOG_FILE_PATH, GC_FILE_PATH
from src.utils.base import TranslateNone, OptimGC
from src.utils.log import BuildLogger

# ==================================================================================================
IS_CHILD_PROCESS: bool = not (mp.current_process().name == 'MainProcess')
# Ignore the logger initialization if it is not the parent process (ignore child process during multiprocessing)
print(f'Checking if it is a child process ... \nOS: {platform.system()} - PID: {os.getpid()} - PPID: {os.getppid()}')
if not IS_CHILD_PROCESS:
    # Ignore the logger initialization if it is not the parent process (ignore child process during multiprocessing)
    print('Optimizing garbage collector and build logger...')
    OptimGC(GC_FILE_PATH)
    BuildLogger(LOG_FILE_PATH)
    print('Logger is built.')
else:
    OptimGC(GC_FILE_PATH)
