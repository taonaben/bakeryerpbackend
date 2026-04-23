from django.contrib import admin

from apps.purchasing.models import (
    GoodsReceipt,
    GoodsReceiptLineItem,
    PurchaseOrder,
    PurchaseOrderLineItem,
    PurchaseRequisition,
    PurchaseRequisitionLineItem,
    PurchasingConfig,
    Supplier,
    SupplierContact,
    SupplierDocument,
    SupplierInvoice,
    SupplierInvoiceLineItem,
    SupplierProduct,
)

admin.site.register(Supplier)
admin.site.register(SupplierContact)
admin.site.register(SupplierDocument)
admin.site.register(SupplierProduct)
admin.site.register(PurchaseRequisition)
admin.site.register(PurchaseRequisitionLineItem)
admin.site.register(PurchaseOrder)
admin.site.register(PurchaseOrderLineItem)
admin.site.register(GoodsReceipt)
admin.site.register(GoodsReceiptLineItem)
admin.site.register(SupplierInvoice)
admin.site.register(SupplierInvoiceLineItem)
admin.site.register(PurchasingConfig)
