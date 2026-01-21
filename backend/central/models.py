from django.db import models
import uuid


# Create your models here.
class Company(models.Model):
    """Model to represent a company"""

    # UUID field that serves as the primary key, automatically generated and not editable
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Company name field, must be unique and max 255 characters
    name = models.CharField(max_length=255)
    # Boolean field to track if company is active (True) or inactive (False)
    status = models.BooleanField(default=True)  # Active or Inactive
    # Automatically set timestamp when company is created
    created_at = models.DateTimeField(auto_now_add=True)

    # Meta class for model configuration
    class Meta:
        # Display name in Django admin
        verbose_name = "Company"
        # Plural display name in Django admin
        verbose_name_plural = "Companies"
        indexes = [
            models.Index(fields=['status'], name='company_status_idx'),
        ]

    # String representation of the company object
    def __str__(self):
        # Returns the company name when object is printed
        return self.name


class Warehouse(models.Model):
    
    WAREHOUSE_TYPE_CHOICES = [
        ("storage", "Storage"),
        ("distribution", "Distribution"),
        ("production", "Production"),
        ("returns", "Returns"),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="warehouses"
    )
    name = models.CharField(max_length=255, unique=True)
    status = models.BooleanField(default=True)  # Active or Inactive
    wh_type = models.CharField(choices=WAREHOUSE_TYPE_CHOICES, max_length=50, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Warehouse"
        verbose_name_plural = "Warehouses"
        indexes = [
            models.Index(fields=['company', 'status'], name='warehouse_company_status_idx'),
            models.Index(fields=['wh_type'], name='warehouse_type_idx'),
        ]

    def __str__(self):
        return f"{self.name} ({self.company.name})"


class Product(models.Model):
    """Master product catalog - one instance per product type"""

    UNIT_CHOICES = [
        ("kg", "Kilogram"),
        ("g", "Gram"),
        ("l", "Liter"),
        ("ml", "Milliliter"),
        ("pieces", "Pieces"),
        ("dozen", "Dozen"),
        ("box", "Box"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sku = models.CharField(max_length=100, unique=True, blank=True)
    name = models.CharField(max_length=255, unique=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="products")
    category = models.CharField(max_length=255, null=True, blank=True)
    unit_of_measure = models.CharField(
        max_length=50, choices=UNIT_CHOICES, null=True, blank=True
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Product"
        verbose_name_plural = "Products"
        indexes = [
            models.Index(fields=['company', 'is_active'], name='product_company_active_idx'),
            models.Index(fields=['category'], name='product_category_idx'),
            models.Index(fields=['sku'], name='product_sku_idx'),
        ]

    def save(self, *args, **kwargs):
        if not self.sku:
            from central.services.sku_generator import SKUGenerator
            self.sku = SKUGenerator.generate_sku(
                name=self.name,
                category=self.category,
                unit_of_measure=self.unit_of_measure
            )
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.sku})"
