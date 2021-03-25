import html
import re

import html_sanitizer


def _only_https_img(element):
	if element.tag == 'img' and not element.attrib.get('src', '').startswith('https://'):
		element.tag = 'img_'

	return element


_my_html_sanitizer_ = None


def _my_html_sanitizer():
    global _my_html_sanitizer_
    if _my_html_sanitizer_ is None:
        my_settings = dict(html_sanitizer.sanitizer.DEFAULT_SETTINGS)

        my_settings['tags'].add('img')
        my_settings['tags'].add('pre')
        my_settings['tags'].add('code')
        my_settings['empty'].add('img')
        my_settings['attributes'].update({'img': ('src', )})
        my_settings['element_preprocessors'].append(_only_https_img)

        _my_html_sanitizer_ = html_sanitizer.Sanitizer(settings=my_settings)

    return _my_html_sanitizer_


_is_html_regex = re.compile(r'<\/?[a-z][\s\S]*>', re.IGNORECASE)


def is_html(text):
	return _is_html_regex.search(text) is not None


def sanitize(text):
	if is_html(text):
		return sanitize_html(text)
	else:
		return sanitize_plain(text)


def sanitize_html(text):
	return _my_html_sanitizer().sanitize(text)


def sanitize_plain(text):
	return '<br>'.join(html.escape(text).splitlines())
