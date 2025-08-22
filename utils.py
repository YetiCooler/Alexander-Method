import re
from wordsegment import load, segment
from config import system_config

load()


def get_tokens(text):
    """
    Splits text first by spaces, then numbers, and further segments each substring
    using wordsegment.
    """
    tokens = []
    for part in text.split():
        substrings = re.findall(r"\D+|\d+", part)
        for substring in substrings:
            if substring.isdigit():
                tokens.append(substring)
            else:
                tokens.extend(segment(substring))
    return tokens


def get_clean_io_name(input_string):
    parts = input_string.split("-")

    result_parts = []
    started = False

    for part in parts:
        # Check if it's all uppercase
        if not started and part.isupper():
            continue  # Skip all-uppercase parts at the beginning
        else:
            started = True
            result_parts.append(part)

    # Join the remaining parts with spaces
    return " ".join(result_parts)


def get_system_config_from_idenfier(identifier):
    system = None
    for config in system_config:
        if config.execution == identifier:
            system = config
            break
        if config.family == identifier:
            system = config
            break

    return system


def get_system_config_by_filename(filename):
    # unwrap all the family names and excution identifiers into this list
    # from system_config
    identifiers = [config.family for config in system_config]
    identifiers += [config.execution for config in system_config]
    for name in identifiers:
        # convert to lowercase
        if name.lower() in filename.lower():
            identifier = name
            system = get_system_config_from_idenfier(identifier)
            return system
    return None


def get_system_config_using_system_description(text):
    # regular expression to match Circuit diagram AVM
    family_name_regex = r"System Description ([A-Z0-9]+)"
    # find the family name using case-insensitive search
    match = re.search(family_name_regex, text, re.IGNORECASE)
    if match:
        identifier = match.group(1)
        system = get_system_config_from_idenfier(identifier)
        return system

    return None


def get_system_config_using_dtc(text):
    # regular expression to match Circuit diagram AVM
    family_name_regex = r"DTC specification ([A-Z0-9]+)"
    # find the family name using case-insensitive search
    match = re.search(family_name_regex, text, re.IGNORECASE)
    if match:
        identifier = match.group(1)
        system = get_system_config_from_idenfier(identifier)
        return system

    return None


def get_system_config_using_circuit_files(text):
    # regular expression to match Circuit diagram AVM
    family_name_regex = r"Circuit diagram ([A-Z0-9]+)"
    # find the family name using case-insensitive search
    match = re.search(family_name_regex, text, re.IGNORECASE)
    if match:
        identifier = match.group(1)
        system = get_system_config_from_idenfier(identifier)
        return system

    return None


def get_system_config_using_server_can(server_can):
    for config in system_config:
        if config.server_can == server_can:
            return config

    return None
