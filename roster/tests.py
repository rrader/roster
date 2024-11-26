import datetime

from django.test import TestCase

from roster.views import current_lesson


def make_datetime(h, m):
    return datetime.datetime(2021, 1, 1, h, m, 0)


class AnimalTestCase(TestCase):
    def test_cur_lesson(self):
        self.assertEqual(
            current_lesson(make_datetime(8, 50)),
            0
        )

        self.assertEqual(
            current_lesson(make_datetime(9, 0)),
            1
        )

        self.assertEqual(
            current_lesson(make_datetime(9, 45)),
            1
        )

        self.assertEqual(
            current_lesson(make_datetime(9, 50)),
            1
        )

        self.assertEqual(
            current_lesson(make_datetime(9, 55)),
            2
        )

        self.assertEqual(
            current_lesson(make_datetime(12, 55)),
            4
        )

        self.assertEqual(
            current_lesson(make_datetime(20, 0)),
            8
        )
