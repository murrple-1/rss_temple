from django.db.models import F
from django.test import SimpleTestCase

from query_utils import sort as sortutils

sort_configs: dict[str, dict[str, sortutils.SortConfig]] = {
    "object": {
        "uuid": sortutils.SortConfig(
            [sortutils.standard_sort("uuid")], sortutils.DefaultDescriptor(0, "ASC")
        ),
        "text": sortutils.SortConfig([sortutils.standard_sort("text")], None),
        "imageSrc": sortutils.SortConfig([sortutils.standard_sort("image_src")], None),
    },
}


class SortsTestCase(SimpleTestCase):
    @staticmethod
    def _to_order_by_args(object_name, sort, default_sort_enabled):
        sort_list = sortutils.to_sort_list(
            object_name, sort, default_sort_enabled, sort_configs
        )
        order_by_args = sortutils.sort_list_to_order_by_args(
            object_name, sort_list, sort_configs
        )

        return order_by_args

    def test_default(self):
        order_by_args = SortsTestCase._to_order_by_args("object", "text:ASC", True)

        self.assertEqual(order_by_args, [F("text").asc(), F("uuid").asc()])

    def test_nondefault(self):
        order_by_args = SortsTestCase._to_order_by_args("object", "text:ASC", False)

        self.assertEqual(order_by_args, [F("text").asc()])

    def test_multiple_default(self):
        order_by_args = SortsTestCase._to_order_by_args(
            "object", "text:ASC,imageSrc:ASC", True
        )

        self.assertEqual(
            order_by_args, [F("text").asc(), F("image_src").asc(), F("uuid").asc()]
        )

    def test_multiple_nondefault(self):
        order_by_args = SortsTestCase._to_order_by_args(
            "object", "text:ASC,imageSrc:ASC", False
        )

        self.assertEqual(order_by_args, [F("text").asc(), F("image_src").asc()])

    def test_descending_default(self):
        order_by_args = SortsTestCase._to_order_by_args("object", "text:DESC", True)

        self.assertEqual(order_by_args, [F("text").desc(), F("uuid").asc()])

    def test_descending_nondefault(self):
        order_by_args = SortsTestCase._to_order_by_args("object", "text:DESC", False)

        self.assertEqual(order_by_args, [F("text").desc()])

    def test_multiple_descending_default(self):
        order_by_args = SortsTestCase._to_order_by_args(
            "object", "text:DESC,imageSrc:DESC", True
        )

        self.assertEqual(
            order_by_args, [F("text").desc(), F("image_src").desc(), F("uuid").asc()]
        )

    def test_multiple_descending_nondefault(self):
        order_by_args = SortsTestCase._to_order_by_args(
            "object", "text:DESC,imageSrc:DESC", False
        )

        self.assertEqual(order_by_args, [F("text").desc(), F("image_src").desc()])

    def test_multiple_mixed_default(self):
        order_by_args = SortsTestCase._to_order_by_args(
            "object", "text:DESC,imageSrc:ASC", True
        )

        self.assertEqual(
            order_by_args, [F("text").desc(), F("image_src").asc(), F("uuid").asc()]
        )

    def test_multiple_mixed_nondefault(self):
        order_by_args = SortsTestCase._to_order_by_args(
            "object", "text:DESC,imageSrc:ASC", False
        )

        self.assertEqual(order_by_args, [F("text").desc(), F("image_src").asc()])

    def test_multiple_overwritedefault(self):
        order_by_args = SortsTestCase._to_order_by_args(
            "object", "uuid:ASC,text:DESC", True
        )

        self.assertEqual(order_by_args, [F("uuid").asc(), F("text").desc()])

    def test_sort_malformed(self):
        with self.assertRaises(ValueError):
            sortutils.to_sort_list("object", "bad sort string", True, sort_configs)

    def test_bad_sort_list(self):
        with self.assertRaises(AttributeError):
            sortutils.sort_list_to_order_by_args(
                "object",
                [
                    {
                        "field_name": "bad_field",
                        "direction": "ASC",
                    }
                ],
                sort_configs,
            )
