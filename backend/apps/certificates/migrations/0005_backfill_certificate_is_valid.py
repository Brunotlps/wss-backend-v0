from django.db import migrations


def backfill_is_valid(apps, schema_editor):
    """Re-validate certificates wrongly left is_valid=False (#73 follow-up).

    Under the old logic is_valid doubled as the PDF-generation flag: the
    signal created certificates with is_valid=False and the task flipped it
    to True only after the PDF was generated. After the #73 fix, is_valid
    means revocation only, so a legitimate certificate whose PDF was merely
    pending (never failed, never revoked) would now be reported as "revoked".

    Set is_valid=True where is_valid=False AND pdf_generation_failed_at IS
    NULL — i.e. not actually revoked and not a recorded failure. Certificates
    with a failure timestamp are left False for manual review. Idempotent;
    reverse is a no-op (the prior ambiguous state cannot be reconstructed).
    """
    Certificate = apps.get_model("certificates", "Certificate")
    Certificate.objects.filter(
        is_valid=False, pdf_generation_failed_at__isnull=True
    ).update(is_valid=True)


class Migration(migrations.Migration):

    dependencies = [
        ("certificates", "0004_certificate_completion_date_snapshot_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_is_valid, migrations.RunPython.noop),
    ]
