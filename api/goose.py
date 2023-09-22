from goose3 import Configuration


def default_config() -> Configuration:
    config = Configuration()
    config.browser_user_agent = "RSS Temple"
    config.http_timeout = 30.0

    return config
