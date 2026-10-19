"""Outbound email for verification and password-reset codes.

Nothing is sent unless a provider is configured in the environment (never in code):
  SAFELEDGER_MAIL_RELAY_URL / _SECRET Google Apps Script web app that sends through your own Gmail (free, HTTPS)
  SAFELEDGER_BREVO_API_KEY            Brevo (free tier, HTTPS API)
  SAFELEDGER_RESEND_API_KEY           Resend (HTTPS API)
  SAFELEDGER_SMTP_HOST / _PORT / _USER / _PASSWORD   any SMTP server (for Gmail use an app password)
  SAFELEDGER_MAIL_FROM                sender address, e.g. "Capzoryx Copilot <you@example.com>"
Failures never raise and never log recipient addresses or message bodies.
"""
import json
import logging
import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import parseaddr
import httpx

log = logging.getLogger('safeledger.mail')


def provider():
    if os.environ.get('SAFELEDGER_MAIL_RELAY_URL') and os.environ.get('SAFELEDGER_MAIL_RELAY_SECRET'):return 'relay'
    if os.environ.get('SAFELEDGER_BREVO_API_KEY'):return 'brevo'
    if os.environ.get('SAFELEDGER_RESEND_API_KEY'):return 'resend'
    if os.environ.get('SAFELEDGER_SMTP_HOST') and os.environ.get('SAFELEDGER_SMTP_USER') and os.environ.get('SAFELEDGER_SMTP_PASSWORD'):return 'smtp'
    return None


def configured():
    return provider() is not None


def sender():
    raw = os.environ.get('SAFELEDGER_MAIL_FROM') or os.environ.get('SAFELEDGER_SMTP_USER') or ''
    name, address = parseaddr(raw)
    return (name or 'Capzoryx Copilot'), address


def send(to, subject, text):
    """Return True if the provider accepted the message."""
    kind = provider()
    name, address = sender()
    if kind is None:return False
    if kind != 'relay' and not address:return False
    try:
        if kind == 'relay':
            url = os.environ['SAFELEDGER_MAIL_RELAY_URL']
            if not url.startswith('https://script.google.com/'):return False
            r = httpx.post(url, timeout=20, follow_redirects=True, json={'secret': os.environ['SAFELEDGER_MAIL_RELAY_SECRET'], 'to': to, 'subject': subject, 'text': text, 'name': name})
            return r.status_code == 200 and r.json().get('ok') is True
        if kind == 'brevo':
            r = httpx.post('https://api.brevo.com/v3/smtp/email', timeout=10, follow_redirects=False,
                           headers={'api-key': os.environ['SAFELEDGER_BREVO_API_KEY'], 'accept': 'application/json'},
                           json={'sender': {'name': name, 'email': address}, 'to': [{'email': to}], 'subject': subject, 'textContent': text})
            return r.status_code in (200, 201, 202)
        if kind == 'resend':
            r = httpx.post('https://api.resend.com/emails', timeout=10, follow_redirects=False,
                           headers={'Authorization': 'Bearer ' + os.environ['SAFELEDGER_RESEND_API_KEY']},
                           json={'from': f'{name} <{address}>', 'to': [to], 'subject': subject, 'text': text})
            return r.status_code in (200, 201, 202)
        message = EmailMessage()
        message['From'] = f'{name} <{address}>'
        message['To'] = to
        message['Subject'] = subject
        message.set_content(text)
        host, port = os.environ['SAFELEDGER_SMTP_HOST'], int(os.environ.get('SAFELEDGER_SMTP_PORT', '587'))
        context = ssl.create_default_context()
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=10, context=context) as server:
                server.login(os.environ['SAFELEDGER_SMTP_USER'], os.environ['SAFELEDGER_SMTP_PASSWORD'])
                server.send_message(message)
        else:
            with smtplib.SMTP(host, port, timeout=10) as server:
                server.starttls(context=context)
                server.login(os.environ['SAFELEDGER_SMTP_USER'], os.environ['SAFELEDGER_SMTP_PASSWORD'])
                server.send_message(message)
        return True
    except Exception as exc:  # delivery problems must not break the request or leak details
        log.warning('Email delivery failed; provider=%s error=%s', kind, type(exc).__name__)
        return False


def code_message(purpose, code):
    what = {'verify': 'verify your email address', 'reset': 'reset your password'}[purpose]
    return (f'Your Capzoryx Copilot code is {code}',
            f'Use this code to {what}: {code}\n\nIt expires in 10 minutes and works once. '
            'If you did not ask for it, you can ignore this email; nobody can use it without your account.\n\n— Capzoryx Copilot')
