__author__ = "Thorin Schiffer"


def remove_decorator(source_code, name):
    """
    Removes decorator with the name from the source code

    @param source_code: code of the function as returned by inspect module
    @param name: name of the decorator to remove
    @return: source code of the function without the decorator statement
    """
    start = source_code.find(f"@{name}")
    end = source_code.find("def")
    if start < 0:
        return source_code
    return source_code[:start] + source_code[end:]


def sem_to_minor(version):
    """
    Returns a minor release part of the semantic version
    @param version: semantic version in format x.x.x
    @return: minor release in format x.x
    """
    return ".".join(version.split(".")[:2])
