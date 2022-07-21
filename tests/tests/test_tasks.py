from unittest.mock import patch

from django.test import TestCase

from django_yubin.models import Message
from django_yubin.tasks import retry_emails, EnqueuedFailed


class TestRetryEmailsTask(TestCase):

    def test_retry_emails_empty(self):
        self.assertEqual(retry_emails(), EnqueuedFailed(0, 0))

    def testRetryEmailsNoRetrayable(self):
        Message.objects.create(
            to_address='',
            from_address='',
            subject='',
            encoded_message='',
        )
        self.assertEqual(retry_emails(), EnqueuedFailed(0, 0))

    def test_retry_emails_max_retries(self):
        retries = 2
        Message.objects.create(
            to_address='',
            from_address='',
            subject='',
            encoded_message='',
            status=Message.STATUS_FAILED,
            enqueued_count=retries + 1,
        )
        self.assertEqual(retry_emails(max_retries=retries), EnqueuedFailed(0, 0))

    def test_retry_emails_success(self):
        emails_count = 2
        for i in range(emails_count):
            Message.objects.create(
                to_address='johndoe@acmecorp.com',
                from_address='no-reply@acmecorp.com',
                subject='Lorem ipsum dolor sit amet %s' % i,
                encoded_message='Lorem ipsum dolor sit amet, consectetur adipiscing elit...',
                status=Message.STATUS_FAILED,
            )
        self.assertEqual(retry_emails(), EnqueuedFailed(emails_count, 0))

    @patch("django_yubin.tasks.send_email.delay", side_effect=Exception)
    def test_retry_emails_failed(self, send_email_mock):
        Message.objects.create(
            to_address='johndoe@acmecorp.com',
            from_address='no-reply@acmecorp.com',
            subject='Lorem ipsum dolor sit amet',
            encoded_message='Lorem ipsum dolor sit amet, consectetur adipiscing elit...',
            status=Message.STATUS_FAILED,
        )
        self.assertEqual(retry_emails(), EnqueuedFailed(0, 1))
