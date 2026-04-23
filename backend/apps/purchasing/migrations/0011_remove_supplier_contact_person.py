from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("purchasing", "0010_migrate_contact_person"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="supplier",
            name="contact_person",
        ),
    ]
