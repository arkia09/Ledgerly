from django.db import models

from .matching import normalize_name


class Customer(models.Model):
    name = models.CharField(max_length=200)
    # Casefolded, whitespace-normalised copy of name. The unique constraint lives here,
    # which gives case-insensitive uniqueness that also works for non-ASCII text in SQLite.
    name_key = models.CharField(max_length=200, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        self.name = " ".join(self.name.split())
        self.name_key = normalize_name(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Page(models.Model):
    EXTRACTED = "extracted"
    CONFIRMED = "confirmed"
    STATUS_CHOICES = [(EXTRACTED, "extracted"), (CONFIRMED, "confirmed")]

    image = models.ImageField(upload_to="pages/", blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    # The model's output exactly as returned: {"rows": [...], "page_total": ...}.
    # Never modified after extraction; confirm() diffs the user's rows against it.
    extracted_json = models.JSONField(null=True, blank=True)
    extraction_seconds = models.FloatField(null=True, blank=True)
    model_name = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=EXTRACTED)
    extraction_error = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"Page {self.pk} ({self.status})"


class Entry(models.Model):
    CREDIT = "credit"
    PAYMENT = "payment"
    TYPE_CHOICES = [(CREDIT, "credit"), (PAYMENT, "payment")]

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="entries")
    page = models.ForeignKey(Page, null=True, blank=True, on_delete=models.SET_NULL,
                             related_name="entries")
    date = models.DateField(null=True, blank=True)
    date_text = models.CharField(max_length=50, blank=True)
    item = models.CharField(max_length=200, null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    struck_out = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.customer} {self.type} {self.amount}"


class Correction(models.Model):
    FIELD_CHOICES = [(f, f) for f in
                     ("name", "amount", "date", "type", "struck_out", "item", "row_deleted")]

    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name="corrections")
    row_index = models.PositiveIntegerField(null=True, blank=True)
    field = models.CharField(max_length=20, choices=FIELD_CHOICES)
    model_value = models.TextField(blank=True)
    user_value = models.TextField(blank=True)
    raw_text = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.field}: {self.model_value!r} -> {self.user_value!r}"
