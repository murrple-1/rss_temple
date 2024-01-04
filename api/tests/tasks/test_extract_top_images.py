import datetime
import logging
import os
from typing import ClassVar, Generator

from bs4 import BeautifulSoup, Tag
from django.template.loader import get_template
from django.test import tag
from django.utils import timezone

from api.models import Feed, FeedEntry
from api.tasks.extract_top_images import extract_top_images
from api.tests import TestFileServerTestCase


class TaskTestCase(TestFileServerTestCase):
    old_app_logger_level: ClassVar[int]
    old_django_logger_level: ClassVar[int]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.old_app_logger_level = logging.getLogger("rss_temple").getEffectiveLevel()
        cls.old_django_logger_level = logging.getLogger("django").getEffectiveLevel()

        logging.getLogger("rss_temple").setLevel(logging.CRITICAL)
        logging.getLogger("django").setLevel(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        logging.getLogger("rss_temple").setLevel(cls.old_app_logger_level)
        logging.getLogger("django").setLevel(cls.old_django_logger_level)

    def _generate_feed_entry_descriptors(
        self,
    ) -> Generator[tuple[int, str, str, str], None, None]:
        template = get_template("tests/entry.html")

        # via https://github.com/python-pillow/Pillow/blob/26fc975a6506983076627f4ff1ac2dfea39c3d19/Tests/test_file_jpeg.py#L864C16-L864C16
        with open(
            "api/tests/test_files/site/images/generated/malformed.jpg", "wb"
        ) as f:
            f.write(b"\xFF" * 4097)

        i = 1
        for og_tag_filename in (
            None,
            "64x64.jpg",
            "128x128.jpg",
            "256x256.jpg",
            "512x512.jpg",
            "notexist.jpg",
            "generated/malformed.jpg",
        ):
            for img_tag_filename in (
                None,
                "64x64.jpg",
                "128x128.jpg",
                "256x256.jpg",
                "512x512.jpg",
            ):
                rendered_content = template.render(
                    {
                        "i": i,
                        "hostname": TaskTestCase.live_server_url,
                        "og_tag_filename": og_tag_filename,
                        "img_tag_filename": img_tag_filename,
                    }
                )

                html_filename = f"entry_{og_tag_filename.replace('.', '').replace('/', '_') if og_tag_filename is not None else None}_{img_tag_filename.replace('.', '').replace('/', '_') if img_tag_filename is not None else None}.html"

                html_filepath = os.path.join(
                    "api/tests/test_files/site/generated/", html_filename
                )
                with open(html_filepath, "w") as f:
                    f.write(rendered_content)

                soup = BeautifulSoup(rendered_content, "lxml")

                h1_tag = soup.find("h1")
                assert isinstance(h1_tag, Tag)
                title = h1_tag.text

                p_tag = soup.find("p")
                assert isinstance(p_tag, Tag)
                content = str(p_tag)

                yield (
                    i,
                    f"{TaskTestCase.live_server_url}/site/generated/{html_filename}",
                    title,
                    content,
                )

                i += 1

        for html_filename in ["entry_no_og_image_content.html"]:
            html_filepath = os.path.join("api/tests/test_files/site/", html_filename)
            with open(html_filepath, "r") as f:
                soup = BeautifulSoup(f, "lxml")

            h1_tag = soup.find("h1")
            assert isinstance(h1_tag, Tag)
            title = h1_tag.text

            p_tag = soup.find("p")
            assert isinstance(p_tag, Tag)
            content = str(p_tag)

            yield (
                i,
                f"{TaskTestCase.live_server_url}/site/{html_filename}",
                title,
                content,
            )

            i += 1

        yield (
            i,
            f"{TaskTestCase.live_server_url}/site/entry_notexist.html",
            "Title",
            "<p>Content</p>",
        )
        i += 1

    @tag("slow")
    def test_extract_top_images(self):
        now = timezone.now()

        feed = Feed.objects.create(
            feed_url=f"{TaskTestCase.live_server_url}/rss.xml",
            title="Sample Feed",
            home_url=TaskTestCase.live_server_url,
            published_at=now + datetime.timedelta(days=-1),
            updated_at=None,
            db_updated_at=None,
        )

        for i, url, title, content in self._generate_feed_entry_descriptors():
            FeedEntry.objects.create(
                feed=feed,
                published_at=now + datetime.timedelta(days=-i),
                title=title,
                url=url,
                content=content,
                author_name="John Doe",
                db_updated_at=None,
                is_archived=False,
            )

        count = extract_top_images(
            FeedEntry.objects.all(), 3, 2000, 256, 256, 1000 * 1000
        )

        self.assertEqual(
            FeedEntry.objects.filter(has_top_image_been_processed=False).count(), 0
        )
        self.assertEqual(
            FeedEntry.objects.filter(has_top_image_been_processed=True).count(), count
        )
        self.assertGreater(FeedEntry.objects.filter(top_image_src="").count(), 0)
        self.assertLess(
            FeedEntry.objects.filter(top_image_src="").count(),
            FeedEntry.objects.count(),
        )
        self.assertEqual(
            FeedEntry.objects.exclude(top_image_processing_attempt_count=0).count(),
            0,
        )
