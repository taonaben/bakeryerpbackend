from django.db import migrations


def migrate_contact_person_to_supplier_contact(apps, schema_editor):
    Supplier = apps.get_model("purchasing", "Supplier")
    SupplierContact = apps.get_model("purchasing", "SupplierContact")

    for supplier in Supplier.objects.exclude(contact_person="").exclude(
        contact_person__isnull=True
    ):
        SupplierContact.objects.create(
            supplier=supplier,
            name=supplier.contact_person,
            is_primary=True,
        )


def reverse_migrate(apps, schema_editor):
    SupplierContact = apps.get_model("purchasing", "SupplierContact")
    Supplier = apps.get_model("purchasing", "Supplier")

    for contact in SupplierContact.objects.filter(is_primary=True).select_related(
        "supplier"
    ):
        Supplier.objects.filter(pk=contact.supplier_id).update(
            contact_person=contact.name
        )


class Migration(migrations.Migration):

    dependencies = [
        ("purchasing", "0009_supplier_contacts_documents"),
    ]

    operations = [
        migrations.RunPython(
            migrate_contact_person_to_supplier_contact,
            reverse_code=reverse_migrate,
        ),
    ]
