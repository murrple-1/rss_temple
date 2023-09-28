from bs4 import BeautifulSoup


def prep_for_lang_detection(title: str, content: str) -> str:
    return " ".join(
        BeautifulSoup(f"<h1>{title}</h1>{content}", "lxml").stripped_strings
    )


def prep_for_classification(title: str, content: str) -> str:
    # TODO more here needs to be done (remove special characters, normalize whitespace, etc)
    return prep_for_lang_detection(title, content)
