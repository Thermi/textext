#!/usr/bin/env python

import argparse 
import logging
import os
import glob
import shutil


def colorize_logging():
    RESET = "\033[0m"
    FG_DEFAULT = "\033[39m"
    FG_BLACK = "\033[30m"
    FG_RED = "\033[31m"
    FG_GREEN = "\033[32m"
    FG_YELLOW = "\033[33m"
    FG_BLUE = "\033[34m"
    FG_MAGENTA = "\033[35m"
    FG_CYAN = "\033[36m"
    FG_LIGHT_GRAY = "\033[37m"
    FG_DARK_GRAY = "\033[90m"
    FG_LIGHT_RED = "\033[91m"
    FG_LIGHT_GREEN = "\033[92m"
    FG_LIGHT_YELLOW = "\033[93m"
    FG_LIGHT_BLUE = "\033[94m"
    FG_LIGHT_MAGENTA = "\033[95m"
    FG_LIGHT_CYAN = "\033[96m"
    FG_WHITE = "\033[97m"

    BG_DEFAULT = "\033[49m"
    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_LIGHT_GRAY = "\033[47m"
    BG_DARK_GRAY = "\033[100m"
    BG_LIGHT_RED = "\033[101m"
    BG_LIGHT_GREEN = "\033[102m"
    BG_LIGHT_YELLOW = "\033[103m"
    BG_LIGHT_BLUE = "\033[104m"
    BG_LIGHT_MAGENTA = "\033[105m"
    BG_LIGHT_CYAN = "\033[106m"
    BG_WHITE = "\033[107m"


    levels = [
              logging.DEBUG,
              logging.INFO,
              logging.WARNING,
              logging.ERROR,
              logging.ERROR+1, # SUCCESS
              logging.CRITICAL
    ]
    names = [
        "DEBUG   ",
        "INFO    ",
        "WARNING ",
        "ERROR   ",
        "SUCCESS ",
        "CRITICAL"
    ]
    colors = [
        RESET,
        BG_DEFAULT + FG_LIGHT_BLUE,
        BG_DEFAULT + FG_YELLOW,
        BG_DEFAULT + FG_RED,
        BG_DEFAULT + FG_GREEN,
        BG_RED + FG_WHITE,
    ]
    for level, name, color in zip(levels, names, colors):
        logging.addLevelName(level, color + name + RESET)


class CopyFileOverDirectoryError(RuntimeError):
    pass


class CopyFileAlreadyExistsError(RuntimeError):
    pass


def copy_extension_files(src, dst, if_already_exists="raise"):
    """
    src: glob expresion to copy from
    dst: destination directory 
    if_already_exists: action on existing files. One of "raise" (default), "skip", "overwrite"
    """
    if os.path.exists(dst):
        if not os.path.isdir(dst):
            logger.critical("Can't copy files to `%s`: it's not a directory")
            raise CopyFileOverDirectoryError("Can't copy files to `%s`: it's not a directory")
    else:
        logger.info("Creating directory `%s`"%dst)
        os.makedirs(dst)

    for file in glob.glob(src):
        basename = os.path.basename(file)
        destination = os.path.join(dst,basename)
        if os.path.exists(destination):
            if if_already_exists=="raise":
                logger.critical("Can't copy `%s`: `%s` already exists"%(file,destination))
                raise CopyFileAlreadyExistsError("Can't copy `%s`: `%s` already exists"%(file,destination))
            elif if_already_exists=="skip":
                logger.info("Skipping `%s`"%file)
                continue
            elif if_already_exists=="overwrite":
                logger.info("Overwriting `%s`"%destination)
                pass

        if os.path.isfile(file):
            logger.info("Copying `%s` to `%s`" % (file,destination) )
            shutil.copy(file, destination)
        else:
            logger.info("Creating directory `%s`"%destination)

            if os.path.exists(destination):
                if not os.path.isdir(destination):
                    os.remove(destination)
                    os.mkdir(destination)
            else:
                os.mkdir(destination)
            copy_extension_files(  os.path.join(file,"*"),
                                   destination,
                                   if_already_exists=if_already_exists)



class RequirementCheckResult(object):
    def __init__(self, value, messages, nested=None):
        self.value = value
        self.messages = messages
        self.nested = nested if nested is not None else []

    def print_to_logger(self, offset=0):
        if self.value:
            lvl = logging.ERROR + 1  # success
        else:
            lvl = logging.ERROR

        if self.nested:
            nest_symbol = "+"
        else:
            nest_symbol = ""

        for msg in self.messages:
            line = ""
            if offset > 0:
                if offset > 1:
                    line += " " * (offset - 1)
                line += (offset - 1) * 2 * " " + "|" + "--"

            line += nest_symbol
            line += " " + msg + "[%d]" % offset

            logger.log(lvl, line)

            if self.nested:
                nest_symbol = "|"
            else:
                nest_symbol = ""

        for nst in self.nested:
            nst.print_to_logger(offset + 1)

    def flatten(self):
        if len(self.nested) == 0:
            return self

        if self.nested[0].messages == ["OR"] and self.messages == ["OR"]:
            return RequirementCheckResult(
                    self.value,
                    ["OR"],
                    self.nested[0].nested + self.nested[1:]
                ).flatten()

        if self.nested[0].messages == ["AND"] and self.messages == ["AND"]:
            return RequirementCheckResult(
                    self.value,
                    ["AND"],
                    self.nested[0].nested + self.nested[1:]
                ).flatten()

        return self


class Requirement(object):
    def __init__(self, criteria):
        # type: (Callable[None,RequirementCheckResult]) -> None
        self.criteria = criteria  # type: Callable[None, RequirementCheckResult]

    def check(self):
        # type: () -> RequirementCheckResult
        return self.criteria()

    def __and__(self, rhs):
        # type: (Requirement) -> Requirement
        def and_impl():
            L = self.check()
            R = rhs.check()
            return RequirementCheckResult(L.value and R.value,
                                          ["AND"],
                                          [L, R]
                                          )

        return Requirement(and_impl)

    def __or__(self, rhs):
        # type: (Requirement) -> Requirement
        def or_impl():
            L = self.check()
            R = rhs.check()
            return RequirementCheckResult(L.value or R.value,
                                          ["OR"],
                                          [L, R]
                                          )
        return Requirement(or_impl)

    def __neg__(self, other):
        # type: (Requirement) -> Requirement
        def neg_impl():
            lhs_value, lhs_messages = self.check()
            return RequirementCheckResult(not lhs_value,
                                          ["NOT"],
                                          lhs_messages
                                          )
        return Requirement(neg_impl)


def check_requirements():
    def find_in_PATH(executable):
        messages = []
        for path in os.environ["PATH"].split(":"):
            full_path_guess = os.path.join(path, executable)
            logger.debug("Looking for `%s` in `%s`" % (executable, path))
            if os.path.isfile(full_path_guess):
                logger.debug("Found `%s` at `%s`"%(executable,path))
                messages.append("Found `%s` at `%s`"%(executable,path))
        if len(messages)>0:
            return RequirementCheckResult(True, messages)
        messages.append("`%s` is not found PATH" % (executable))
        return RequirementCheckResult(False, messages)

    r = (
        Requirement(lambda : find_in_PATH("pdflatex"))|
        Requirement(lambda : find_in_PATH("laulatex"))|
        Requirement(lambda : find_in_PATH("xelatex"))
    )

    check_result = r.check()

    check_result = check_result.flatten()

    check_result.print_to_logger()

colorize_logging()
logger = logging.getLogger('TexText')
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('[%(name)s][%(levelname)6s]: %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

    
if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Install TexText')
    
    if_already_exists = parser.add_mutually_exclusive_group()
    if_already_exists.add_argument(
                "--overwrite-if-exist", 
                dest='if_already_exists', 
                action='store_const',
                const="overwrite",
                default="raise",
                help="Overwrite already existing extension files"
                )
    if_already_exists.add_argument(
                "--skip-if-exist", 
                dest='if_already_exists', 
                action='store_const',
                const="skip",
                help="Retain already existing extension files"
                )


    parser.add_argument(
                "--inkscape-extensions-path",
                default=os.path.expanduser("~/.config/inkscape/extensions"),
                help="Path to inkscape extensions directory"
        )

    args = parser.parse_args()

    check_requirements()

    try:
        copy_extension_files(
            src="extension/*",
            dst=args.inkscape_extensions_path,
            if_already_exists=args.if_already_exists
        )
    except CopyFileAlreadyExistsError:
        logger.info("Hint: add `--overwrite-if-exist` option to overwrite existing files and directories")
        logger.info("Hint: add `--skip-if-exist` option to retain existing files and directories")
