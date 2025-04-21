from typing import Any
from django import forms


class RemoveFeedsForm(forms.Form):
    feed_id = forms.CharField(widget=forms.HiddenInput)
    reason = forms.CharField(widget=forms.Textarea, required=True)

    template_name_div = "admin/remove_feeds_form/div.html"
    template_name_p = "admin/remove_feeds_form/p.html"
    template_name_table = "admin/remove_feeds_form/table.html"
    template_name_ul = "admin/remove_feeds_form/ul.html"

    feed_title: str
    feed_url: str
    known_reasons: list[str]

    class Media:
        css = {
            "all": ["remove_feeds.css"],
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        initial = kwargs["initial"]

        assert isinstance(initial, dict)
        self.feed_title = initial.pop("feed_title")
        self.feed_url = initial.pop("feed_url")
        self.known_reasons = initial.pop("known_reasons", [])

        super().__init__(*args, **kwargs)

    def get_context(self) -> dict[str, Any]:
        return {
            "feed_title": self.feed_title,
            "feed_url": self.feed_url,
            "known_reasons": self.known_reasons,
        } | super().get_context()


RemoveFeedsFormset = forms.formset_factory(RemoveFeedsForm, extra=0)
