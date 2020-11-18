
"""
The "engine room" of django-yubin mailer.

Functions here actually handle the sending of messages.
"""

import logging
import smtplib
from socket import error as SocketError

from django.core.mail import get_connection
from django.utils.encoding import force_bytes, smart_str

from . import models, settings


logger = logging.getLogger(__name__)


def send_db_message(message, smtp_connection=None, blacklist=None, log=True):
    """
    Sends a django_yubin.models.Message, returning a response code as to the
    action taken.

    The response codes can be found in ``django_yubin.constants``. The
    response will be either ``RESULT_FAILED`` for a deferred message,
    ``RESULT_SENT`` for a successful sent message or ``RESULT_SKIPPED`` for
    blacklisted email or if ``settings.PAUSE_SEND`` is True.

    To allow optimizations if multiple messages are to be sent, an SMTP
    connection can be provided and a list of blacklisted email addresses.
    Otherwise an SMTP connection will be opened to send this message and the
    email recipient address checked against the ``Blacklist`` table.

    If the message recipient is blacklisted, the message will be removed from
    the queue without being sent. Otherwise, the message is attempted to be
    sent with an SMTP failure resulting in the message being flagged as
    deferred so it can be tried again later.

    By default, a log is created as to the action. Either way, the original
    message is not deleted.
    """
    log_message = ''
    message.status = models.Message.STATUS_IN_PROCESS

    if smtp_connection is None:
        smtp_connection = get_connection()
    opened_connection = False

    if blacklist is None:
        blacklisted = models.Blacklist.objects.filter(email=message.to_address)
    else:
        blacklisted = message.to_address in blacklist

    if blacklisted:
        logger.info("Not sending to blacklisted email: %s" %
                    message.to_address.encode("utf-8"))
        message.status = models.Message.STATUS_BLACKLISTED

    elif settings.PAUSE_SEND:
        logger.info("Sending is paused, discarding the email.")
        message.status = models.Message.STATUS_DISCARDED

    else:
        try:
            logger.info("Sending message to %s: %s" %
                        (message.to_address.encode("utf-8"),
                         message.subject.encode("utf-8")))
            opened_connection = smtp_connection.open()
            try:
                smtp_connection.connection.sendmail(
                    message.from_address,
                    [message.to_address],
                    smart_str(message.encoded_message).encode('utf-8'))
            except UnicodeDecodeError:
                smtp_connection.connection.sendmail(
                    message.from_address,
                    [message.to_address],
                    force_bytes(message.encoded_message))
            message.mark_as_sent()
        except (SocketError,
                smtplib.SMTPSenderRefused, smtplib.SMTPRecipientsRefused, smtplib.SMTPAuthenticationError,
                UnicodeDecodeError, UnicodeEncodeError) as e:
            logger.warning("Message to %s has failed: %s" % (message.to_address.encode("utf-8"), e))
            try:
                log_message = unicode(e)
            except NameError:
                log_message = e
            message.status = models.Message.STATUS_FAILED

    message.save()

    if log:
        models.Log.objects.create(message=message, action=message.status, log_message=log_message)

    if opened_connection:
        smtp_connection.close()
