import os
import sys
import argparse
import json
import functools
import subprocess
import shutil
import time

import win32api
import win32file
import win32con
import winreg

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
            sys.exit(1)
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
    INSTALL_LOCATION = os.path.expandvars(r"%LOCALAPPDATA%\RemoveWindowsLockScreenAds")

    def __init__(self, dry_run=False, remove_credits=False):
        self.dry_run = dry_run
        self.remove_credits = remove_credits

    @catch_exception
    def remove_ads_file(self, path):
        if not os.path.exists(path):
            raise ValueError("Path does not exist: {}".format(path))

        logger.debug("Processing ContentDeliveryManager file: {}".format(os.path.basename(path)))

        with open(path, 'r', encoding='utf-8') as f:
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
                    if self.remove_credits:
                        logger.debug("Removing credits: '{}' - '{}'".format(
                            prop['description']['text'],
                            prop['copyright']['text']))
                    else:
                        keep_items.append(item)
                else:
                    logger.debug("Skipping unknown template type: {}".format(prop['template']['text']))
            except KeyError as e:
                logger.exception("")
                logger.debug("Unexpected item format: {}".format(json.dumps(item)))
        jso['items'] = keep_items

        if not self.dry_run:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(jso, f, ensure_ascii=False)

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

    def __autorun_key(self, do_add, path=None):
        key = "RemoveWindowsLockScreenAds"
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r'Software\Microsoft\Windows\CurrentVersion\Run',
            0, winreg.KEY_SET_VALUE
        ) as hKey:
            if do_add:
                # Run key has maximum length of 260 chars, so make a .bat file
                bat_path = os.path.join(self.INSTALL_LOCATION, 'RemoveWindowsLockScreenAds.bat')
                cmdline = ['start', sys.executable, os.path.join(self.INSTALL_LOCATION, os.path.basename(__file__)), '--watch']
                if self.remove_credits:
                    cmdline.append('--remove-credits')
                if path is not None:
                    cmdline.append(path)
                cmdline = ' '.join(cmdline)
                logger.info("On startup will run:\n\t{}".format(cmdline))
                with open(bat_path, 'w') as f:
                    f.write(cmdline)
                winreg.SetValueEx(hKey, key, 0, winreg.REG_SZ, bat_path)
            else:
                try:
                    winreg.DeleteValue(hKey, key)
                except FileNotFoundError:
                    pass

    def install(self, path):
        # Show a warning if using python.exe
        if os.path.basename(sys.executable) == 'python.exe':
            logger.warning("WARNING: Installing using python.exe, a command prompt window will be left open. We recommend installing with pythonw.exe.")

        try:
            # Copy self (script) to install location
            os.makedirs(self.INSTALL_LOCATION, exist_ok=True)
            shutil.copyfile(__file__, os.path.join(self.INSTALL_LOCATION, os.path.basename(__file__)))

            # Create startup key
            self.__autorun_key(True, path=path)
        except Exception as e:
            logger.error("Installation failed: {}".format(e))
            self.uninstall()
            return False

        logger.info("Successfully installed.")
        return True

    def uninstall(self):
        # Remove autorun
        try:
            self.__autorun_key(False)
        except Exception as e:
            logger.error("Failed to remove autorun key: {}".format(e))

        # Kill process
        while True:
            cmdline = ['wmic', 'Path', 'win32_process', 'Where', "CommandLine Like '%{}%'".format(self.INSTALL_LOCATION.replace('\\','\\\\')), 'Call', 'Terminate']
            r = subprocess.run(cmdline, capture_output=True)
            if b'No Instance' in r.stdout:
                break
            time.sleep(.1)

        # Remove files
        try:
            path = self.INSTALL_LOCATION
            if os.path.exists(path):
                shutil.rmtree(path)
        except Exception as e:
            logger.error("Failed to remove installed files: {}".format(e))
        else:
            logger.info("Uninstalled from {}".format(path))

def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--dry-run", action="store_true",
        help="Process and log but do not modify files")
    parser.add_argument("--remove-credits", action="store_true",
        help="Remove the image credits box")
    parser.add_argument("path", nargs="?", default=GetAdSettingsDirectory(),
        help="Path to file or directory to remove lock screen ads from. Default: %(default)s")

    actions = parser.add_argument_group(title="actions")
    excl = actions.add_mutually_exclusive_group(required=True)
    excl.add_argument("--once", action="store_true",
        help="Remove ads from file(s) in path")
    excl.add_argument("--watch", action="store_true",
        help="Continue running, watch directory for new Spotlight files, and remove ads from them")
    excl.add_argument("--install", action="store_true",
        help="Start in --watch mode on login")
    excl.add_argument("--uninstall", action="store_true",
        help="Remove installed files and login task")

    args = parser.parse_args(argv[1:])

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(format='%(message)s', level=logging.INFO)

    adrem = AdRemover(dry_run=args.dry_run, remove_credits=args.remove_credits)

    if args.install:
        if adrem.install(args.path):
            adrem.remove_ads_path(args.path)
    elif args.uninstall:
        adrem.uninstall()
    elif args.watch:
        adrem.watch_dir(args.path)
    elif args.once:
        adrem.remove_ads_path(args.path)

if __name__ == "__main__":
    main(sys.argv)

