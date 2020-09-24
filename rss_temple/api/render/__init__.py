from django.template.loader import render_to_string


def to_text(text_template_filepath, context):
    return render_to_string(text_template_filepath, context)


def to_html(html_template_filepath, context):
    return render_to_string(html_template_filepath, context)
