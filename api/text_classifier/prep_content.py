from bs4 import BeautifulSoup


def prep_for_lang_detection(content: str) -> str:
    return "".join(BeautifulSoup(content, "lxml").stripped_strings)


def prep_for_classification(content: str) -> str:
    # TODO more here needs to be done (remove special characters, normalize whitespace, etc)
    return prep_for_lang_detection(content)
