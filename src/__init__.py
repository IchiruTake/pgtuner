import gc
import toml
from pprint import pprint
from src.static.vars import LOG_FILE_PATH, GC_FILE_PATH
from src.log import BuildLogger

def optimize_garbage_scheduler() -> None:
    with open(GC_FILE_PATH, 'r') as gc_file_stream:
        profile: dict = toml.load(gc_file_stream)['GC']
        if profile['DISABLED'] is True:
            gc.disable()
            return None

        if profile['CLEANUP_AND_FREEZE'] is True:
            gc.collect(2)
            gc.freeze()

        if profile['DEBUG'] is True:
            gc.set_debug(gc.DEBUG_STATS)

        gc.set_threshold(profile['ALLO'], profile['GEN_0'], profile['GEN_1'])

    return None

# ==================================================================================================
print("Optimizing garbage collector...")
optimize_garbage_scheduler()
print("Garbage collector is optimized.")

with open(LOG_FILE_PATH, 'r') as f:
    print("Building logger...")
    _content = toml.load(f)['LOGGER']
    pprint(_content)

    LOGGER = BuildLogger(_content)
    print("Logger is built.")
