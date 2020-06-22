import os
import sys
import argparse
import json
import functools

import win32api
import win32file
import win32con

import logging
logger = logging.getLogger("RemoveWindowsLockScreenAds")

def catch_exception(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.exception(e)
            return None
    return wrapper

def exit_on_ctrlsignal(func):
    """
    Python's KeyboardInterrupt handler registers on the next
    bytecode instruction, but since we are waiting in C code
    in ReadDirectoryChangesW it never raises.
    So we set our own handler here.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        def handler(ctrltype):
            exit(1)
            return 1
        win32api.SetConsoleCtrlHandler(handler, True)
        try:
            return func(*args, **kwargs)
        finally:
            win32api.SetConsoleCtrlHandler(handler, False)
    return wrapper

@exit_on_ctrlsignal
def wrap_wait_call(func, *args, **kwargs):
    return func(*args, **kwargs)

def GetAdSettingsDirectory(user=None):
    EXT = r"Packages\Microsoft.Windows.ContentDeliveryManager_cw5n1h2txyewy\LocalState\TargetedContentCache\v3\338387"
    if user is None:
        base = os.path.expandvars("%LOCALAPPDATA%")
    else:
        base = os.path.expanduser('~'+str(user))
        base = os.path.join(base, 'AppData', 'Local')
    return os.path.join(base, EXT)

class AdRemover():
    def __init__(self, dry_run=False):
        self.dry_run = dry_run

    @catch_exception
    def remove_ads_file(self, path):
        if not os.path.exists(path):
            raise ValueError("Path does not exist: {}".format(path))

        logger.debug("Processing ContentDeliveryManager file: {}".format(os.path.basename(path)))

        with open(path, 'r') as f:
            jso = json.load(f)

        # Iterate list of items and pick the ones we want to keep
        keep_items = []
        for item in jso['items']:
            try:
                prop = item['properties']
                if "basicHotspot" == prop['template']['text']:
                    # Annoying ad
                    logger.debug("Removing ad: '{}'".format(prop['title']['text']))
                elif "infoHotspot" == prop['template']['text']:
                    # Image info/credits
                    keep_items.append(item)
                else:
                    logger.debug("Skipping unknown template type: {}".format(prop['template']['text']))
            except KeyError as e:
                logger.exception("")
                logger.debug("Unexpected item format: {}".format(json.dumps(item)))
        jso['items'] = keep_items

        if not self.dry_run:
            with open(path, 'w') as f:
                json.dump(jso, f)

    def remove_ads_dir(self, path):
        for fpath in os.listdir(path):
            self.remove_ads_file(os.path.join(path,fpath))

    def remove_ads_path(self, path):
        if os.path.isdir(path):
            self.remove_ads_dir(path)
        elif os.path.isfile(path):
            self.remove_ads_file(path)

    def watch_dir(self, path):
        if not os.path.exists(path):
            raise ValueError("Path does not exist: {}".format(path))

        if not os.path.isdir(path):
            raise ValueError("Path is not a directory: {}".format(path))

        # Run once to start
        self.remove_ads_dir(path)

        FILE_LIST_DIRECTORY = 1
        FILE_ACTION_REMOVED = 2
        FILE_ACTION_RENAMED_OLD_NAME = 4

        while True:
            # Get handle to directory
            hDir = win32file.CreateFile(
                path,
                FILE_LIST_DIRECTORY,
                win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE | win32con.FILE_SHARE_DELETE,
                None,
                win32con.OPEN_EXISTING,
                win32con.FILE_FLAG_BACKUP_SEMANTICS,
                None)

            # Blocking wait for something in the directory to change or be created
            try:
                changes = wrap_wait_call(win32file.ReadDirectoryChangesW,
                    hDir,
                    100*(4*3+256*2), # Enough for 100 FILE_NOTIFY_INFORMATION WMAX_PATH structs
                    False,
                    win32con.FILE_NOTIFY_CHANGE_FILE_NAME |
                    win32con.FILE_NOTIFY_CHANGE_LAST_WRITE,
                    None,
                    None)
            finally:
                # Close the handle so we can make changes to the files
                # without being notified about it (infinite loop)
                hDir.close()

            processed = set()
            for action, fname in changes:
                # Skip if file is being deleted or doesn't exist
                if action in [FILE_ACTION_REMOVED,FILE_ACTION_RENAMED_OLD_NAME] \
                    or not os.path.exists(path):
                    continue
                # Only process each file once
                if fname in processed:
                    continue
                processed.add(fname)
                filepath = os.path.join(path, fname)
                self.remove_ads_file(filepath)

def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--dry-run", action="store_true",
        help="Process and log but do not modify files")
    parser.add_argument("--watch", action="store_true",
        help="Continue running, watch directory for new Spotlight files, and remove ads from them")
    parser.add_argument("path", nargs="?", default=GetAdSettingsDirectory(),
        help="Path to file or directory to remove lock screen ads from. Default: %(default)s")

    args = parser.parse_args(argv[1:])

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    adrem = AdRemover(dry_run=args.dry_run)

    if args.watch:
        adrem.watch_dir(args.path)
    else:
        adrem.remove_ads_path(args.path)

if __name__ == "__main__":
    main(sys.argv)
