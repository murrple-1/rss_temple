from api import render


def plain_text(verify_token):
    context = {
        'verify_token': verify_token,
    }

    return render.to_text(
        'verify/templates/plain_text.txt',
        context)


def html_text(verify_token):
    context = {
        'verify_token': verify_token,
    }

    return render.to_html(
        'verify/templates/html_text.html',
        context)


def subject():
    context = {}

    return render.to_text('verify/templates/subject.txt', context)
