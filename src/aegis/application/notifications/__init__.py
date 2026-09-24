"""Notification use cases. Application does not import boto3 or SMTP."""

from aegis.application.notifications.notify import NotifyInvestigation, notify_best_effort

__all__ = ["NotifyInvestigation", "notify_best_effort"]
