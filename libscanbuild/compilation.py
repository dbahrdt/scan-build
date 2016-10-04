# -*- coding: utf-8 -*-
#                     The LLVM Compiler Infrastructure
#
# This file is distributed under the University of Illinois Open Source
# License. See LICENSE.TXT for details.
""" This module is responsible for to parse a compiler invocation. """

import re
import os
import collections

__all__ = ['split_command', 'split_compiler', 'classify_source']

# Ignored compiler options map for compilation database creation.
# The map is used in `split_command` method. (Which does ignore and classify
# parameters.) Please note, that these are not the only parameters which
# might be ignored.
#
# Keys are the option name, value number of options to skip
IGNORED_FLAGS = {
    # compiling only flag, ignored because the creator of compilation
    # database will explicitly set it.
    '-c': 0,
    # preprocessor macros, ignored because would cause duplicate entries in
    # the output (the only difference would be these flags). this is actual
    # finding from users, who suffered longer execution time caused by the
    # duplicates.
    '-MD': 0,
    '-MMD': 0,
    '-MG': 0,
    '-MP': 0,
    '-MF': 1,
    '-MT': 1,
    '-MQ': 1,
    # linker options, ignored because for compilation database will contain
    # compilation commands only. so, the compiler would ignore these flags
    # anyway. the benefit to get rid of them is to make the output more
    # readable.
    '-static': 0,
    '-shared': 0,
    '-s': 0,
    '-rdynamic': 0,
    '-l': 1,
    '-L': 1,
    '-u': 1,
    '-z': 1,
    '-T': 1,
    '-Xlinker': 1
}

# Known C/C++ compiler wrapper name patterns
COMPILER_WRAPPER_PATTERN = re.compile(r'^(distcc|ccache)$')

# Known C/C++ compiler executable name patterns
COMPILER_PATTERNS = frozenset([
    re.compile(r'^(cc|c\+\+|cxx|CC)$'),
    re.compile(r'^([^-]*-)*[mg](cc|\+\+)(-\d+(\.\d+){0,2})?$'),
    re.compile(r'^([^-]*-)*clang(\+\+)?(-\d+(\.\d+){0,2})?$'),
    re.compile(r'^llvm-g(cc|\+\+)$'),
    re.compile(r'^i(cc|cpc)$'),
    re.compile(r'^(g|)xl(c|C|c\+\+)$'),
])

# Known C++ compiler executable name patterns
COMPILER_CPP_PATTERNS = frozenset([
    re.compile(r'^(.+)(\+\+)(-.+|)$'),  # C++ compilers usually ends with '++'
    re.compile(r'^(icpc|xlC|cxx|CC)$'),
])


def split_command(command):
    """ Returns a value when the command is a compilation, None otherwise.

    The value on success is a named tuple with the following attributes:

        files:    list of source files
        flags:    list of compile options
        compiler: string value of 'c' or 'c++' """

    # quit right now, if the program was not a C/C++ compiler
    compiler_and_arguments = split_compiler(command)
    if compiler_and_arguments is None:
        return None

    # the result of this method
    result = collections.namedtuple('Compilation',
                                    ['compiler', 'flags', 'files'])
    result.compiler = compiler_and_arguments[0]
    result.flags = []
    result.files = []
    # iterate on the compile options
    args = iter(compiler_and_arguments[1])
    for arg in args:
        # quit when compilation pass is not involved
        if arg in {'-E', '-S', '-cc1', '-M', '-MM', '-###'}:
            return None
        # ignore some flags
        elif arg in IGNORED_FLAGS:
            count = IGNORED_FLAGS[arg]
            for _ in range(count):
                next(args)
        elif re.match(r'^-(l|L|Wl,).+', arg):
            pass
        # some parameters could look like filename, take as compile option
        elif arg in {'-D', '-I'}:
            result.flags.extend([arg, next(args)])
        # parameter which looks source file is taken...
        elif re.match(r'^[^-].+', arg) and classify_source(arg):
            result.files.append(arg)
        # and consider everything else as compile option.
        else:
            result.flags.append(arg)
    # do extra check on number of source files
    return result if result.files else None


def classify_source(filename, c_compiler=True):
    """ Classify source file names and returns the presumed language,
    based on the file name extension.

    :param filename:    the source file name
    :param c_compiler:  indicate that the compiler is a C compiler,
    :return:            the language from file name extension. """

    mapping = {
        '.c': 'c' if c_compiler else 'c++',
        '.i': 'c-cpp-output' if c_compiler else 'c++-cpp-output',
        '.ii': 'c++-cpp-output',
        '.m': 'objective-c',
        '.mi': 'objective-c-cpp-output',
        '.mm': 'objective-c++',
        '.mii': 'objective-c++-cpp-output',
        '.C': 'c++',
        '.cc': 'c++',
        '.CC': 'c++',
        '.cp': 'c++',
        '.cpp': 'c++',
        '.cxx': 'c++',
        '.c++': 'c++',
        '.C++': 'c++',
        '.txx': 'c++'
    }

    __, extension = os.path.splitext(os.path.basename(filename))
    return mapping.get(extension)


def split_compiler(command):
    """ A predicate to decide the command is a compiler call or not.

    :param command: the command to classify
    :return:        None if the command is not a compilation
                    (compiler_language, rest of the command) tuple if the
                    command is a compilation. """

    def is_wrapper(candidate):
        return True if COMPILER_WRAPPER_PATTERN.match(candidate) else False

    def is_compiler(candidate):
        return any(pattern.match(candidate) for pattern in COMPILER_PATTERNS)

    def is_cplusplus(candidate):
        return any(pattern.match(candidate)
                   for pattern in COMPILER_CPP_PATTERNS)

    if command:  # not empty list will allow to index '0' and '1:'
        executable = os.path.basename(command[0])
        parameters = command[1:]
        # 'wrapper' 'parameters' and
        # 'wrapper' 'compiler' 'parameters' are valid.
        # plus, a wrapper can wrap wrapper too.
        if is_wrapper(executable):
            result = split_compiler(parameters)
            return ('c', parameters) if result is None else result
        # and 'compiler' 'parameters' is valid.
        elif is_compiler(executable):
            language = 'c++' if is_cplusplus(executable) else 'c'
            return language, parameters
    return None