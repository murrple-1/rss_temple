from api import render


def plain_text(password_reset_token: str):
    context = {
        "password_reset_token": password_reset_token,
    }

    return render.to_text("passwordreset/templates/plain_text.txt", context)


def html_text(password_reset_token: str):
    context = {
        "password_reset_token": password_reset_token,
    }

    return render.to_html("passwordreset/templates/html_text.html", context)


def subject():
    context = {}

    return render.to_text("passwordreset/templates/subject.txt", context)
