from django import forms
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile

from .models import Item, ItemMedia, ProductAttributeValue, Comment

MAX_VIDEO_SECONDS = 30
MAX_VIDEO_BYTES = 25 * 1024 * 1024  # 25 MB
MAX_IMAGE_BYTES = 8 * 1024 * 1024  # 8 MB
MAX_IMAGE_SIDE = 1600
MAX_ITEM_MEDIA = 6
ALLOWED_VIDEO_TYPES = {
    "video/mp4",
    "video/webm",
    "video/quicktime",
    "video/x-m4v",
}
ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
}


def resize_uploaded_image(image_field, max_side=MAX_IMAGE_SIDE):
    """Downscale very large / tall uploads so product cards stay consistent."""
    if not image_field or not getattr(image_field, "file", None):
        return
    try:
        from io import BytesIO

        from PIL import Image, ImageOps

        image_field.file.seek(0)
        img = Image.open(image_field.file)
        img = ImageOps.exif_transpose(img)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        elif img.mode == "L":
            img = img.convert("RGB")
        w, h = img.size
        if max(w, h) <= max_side:
            image_field.file.seek(0)
            return
        img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=85, optimize=True)
        buf.seek(0)
        base = (getattr(image_field, "name", None) or "image").rsplit("/", 1)[-1]
        base = base.rsplit(".", 1)[0] + ".jpg"
        image_field.save(base, ContentFile(buf.read()), save=False)
    except Exception:
        try:
            image_field.file.seek(0)
        except Exception:
            pass


def detect_media_type(uploaded):
    name = (getattr(uploaded, "name", "") or "").lower()
    content_type = (getattr(uploaded, "content_type", "") or "").lower()
    if content_type.startswith("video/") or name.endswith(
        (".mp4", ".webm", ".mov", ".m4v")
    ):
        return ItemMedia.MEDIA_VIDEO
    if content_type.startswith("image/") or name.endswith(
        (".jpg", ".jpeg", ".png", ".webp", ".gif")
    ):
        return ItemMedia.MEDIA_IMAGE
    return None


def validate_uploaded_media(uploaded):
    """Return media_type or raise ValidationError."""
    mtype = detect_media_type(uploaded)
    if not mtype:
        raise ValidationError(
            f"Unsupported file: {getattr(uploaded, 'name', 'file')}. Use images or MP4/WebM/MOV."
        )
    size = getattr(uploaded, "size", 0) or 0
    if mtype == ItemMedia.MEDIA_VIDEO:
        if size > MAX_VIDEO_BYTES:
            raise ValidationError("Video must be 25 MB or smaller.")
        content_type = getattr(uploaded, "content_type", "") or ""
        name = (getattr(uploaded, "name", "") or "").lower()
        if content_type and content_type not in ALLOWED_VIDEO_TYPES:
            if not name.endswith((".mp4", ".webm", ".mov", ".m4v")):
                raise ValidationError("Use MP4, WebM, or MOV video only.")
    else:
        if size > MAX_IMAGE_BYTES:
            raise ValidationError("Each image must be 8 MB or smaller.")
        content_type = getattr(uploaded, "content_type", "") or ""
        if content_type and content_type not in ALLOWED_IMAGE_TYPES:
            name = (getattr(uploaded, "name", "") or "").lower()
            if not name.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif")):
                raise ValidationError("Use JPG, PNG, WebP, or GIF images.")
    return mtype


def save_item_media_files(item, files, start_order=0):
    """Create ItemMedia rows from uploaded files; return count added."""
    added = 0
    order = start_order
    for uploaded in files:
        if not uploaded:
            continue
        mtype = validate_uploaded_media(uploaded)
        if mtype == ItemMedia.MEDIA_IMAGE:
            resize_uploaded_image(uploaded)
        ItemMedia.objects.create(
            item=item,
            file=uploaded,
            media_type=mtype,
            sort_order=order,
        )
        order += 1
        added += 1
    if added:
        item.sync_legacy_media_fields()
    return added


def get_attribute_metadata(attr_name):
    """Return dict with unit, icon, placeholder, and guidance for product attributes."""
    name_l = (attr_name or "").lower()
    meta = {
        "unit": "",
        "icon": "bi-sliders",
        "placeholder": f"Enter {attr_name}...",
        "help": "",
    }

    if "battery" in name_l:
        meta["unit"] = "mAh"
        meta["icon"] = "bi-battery-charging"
        meta["placeholder"] = "e.g. 5000"
        meta["help"] = "Capacity in milliampere-hours (mAh)"
    elif "ram" in name_l:
        meta["unit"] = "GB"
        meta["icon"] = "bi-memory"
        meta["placeholder"] = "e.g. 8"
        meta["help"] = "Random Access Memory in Gigabytes"
    elif "storage" in name_l or "ssd" in name_l or "hdd" in name_l:
        meta["unit"] = "GB/TB"
        meta["icon"] = "bi-hdd"
        meta["placeholder"] = "e.g. 128 GB or 512 GB SSD"
        meta["help"] = "Internal memory or storage drive"
    elif "screen" in name_l or "display" in name_l:
        meta["unit"] = 'Inches (")'
        meta["icon"] = "bi-aspect-ratio"
        meta["placeholder"] = 'e.g. 6.1" or 15.6"'
        meta["help"] = "Diagonal screen dimension in inches"
    elif "back camera" in name_l or "rear camera" in name_l or "main camera" in name_l:
        meta["unit"] = "MP"
        meta["icon"] = "bi-camera"
        meta["placeholder"] = "e.g. 48"
        meta["help"] = "Megapixels for rear / main lenses"
    elif "front camera" in name_l or "selfie" in name_l:
        meta["unit"] = "MP"
        meta["icon"] = "bi-camera-video"
        meta["placeholder"] = "e.g. 16"
        meta["help"] = "Megapixels for front / selfie camera"
    elif "camera" in name_l:
        meta["unit"] = "MP"
        meta["icon"] = "bi-camera"
        meta["placeholder"] = "e.g. 48 MP Rear, 16 MP Front"
        meta["help"] = "Camera resolution in Megapixels"
    elif "mileage" in name_l:
        meta["unit"] = "km"
        meta["icon"] = "bi-speedometer"
        meta["placeholder"] = "e.g. 45000"
        meta["help"] = "Distance driven in kilometers"
    elif "engine" in name_l or "cc" in name_l:
        meta["unit"] = "cc"
        meta["icon"] = "bi-gear-wide-connected"
        meta["placeholder"] = "e.g. 1500"
        meta["help"] = "Displacement in cubic centimeters (cc)"
    elif "weight" in name_l:
        meta["unit"] = "kg"
        meta["icon"] = "bi-box-seam"
        meta["placeholder"] = "e.g. 1.5"
        meta["help"] = "Weight in kilograms"
    elif "volume" in name_l:
        meta["unit"] = "ml / L"
        meta["icon"] = "bi-droplet"
        meta["placeholder"] = "e.g. 500 ml or 1 Liter"
    elif "alcohol" in name_l:
        meta["unit"] = "% ABV"
        meta["icon"] = "bi-percent"
        meta["placeholder"] = "e.g. 5%"
    elif "voltage" in name_l:
        meta["unit"] = "V"
        meta["icon"] = "bi-lightning-charge"
        meta["placeholder"] = "e.g. 220V"
    elif "company" in name_l or "brand" in name_l or "make" in name_l:
        meta["unit"] = ""
        meta["icon"] = "bi-building"
        meta["placeholder"] = "Select or enter brand..."
    elif "model" in name_l:
        meta["unit"] = ""
        meta["icon"] = "bi-phone"
        meta["placeholder"] = "e.g. Galaxy S22 Ultra, iPhone 13, ThinkPad T14"
    elif "os" in name_l or "operating system" in name_l:
        meta["unit"] = ""
        meta["icon"] = "bi-cpu"
        meta["placeholder"] = "Select OS..."
    elif "year" in name_l:
        meta["unit"] = "Year"
        meta["icon"] = "bi-calendar-event"
        meta["placeholder"] = "e.g. 2023"
    elif "size" in name_l:
        meta["unit"] = ""
        meta["icon"] = "bi-rulers"
        meta["placeholder"] = "Select size..."

    return meta


class ItemForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = [
            "title",
            "sku",
            "category_obj",
            "condition",
            "price",
            "compare_at_price",
            "stock_quantity",
            "description",
            "campus_location",
            "shipping_weight",
            "shipping_dimensions",
            "contact_method",
            "contact_email",
            "contact_phone",
        ]
        widgets = {
            "title": forms.TextInput(attrs={
                "class": "form-control form-control-lg",
                "placeholder": "e.g. iPhone 13 Pro 128GB Sierra Blue (Clean Condition)",
                "id": "id_product_title",
            }),
            "sku": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Auto-generated if left blank (e.g. UC-7A39B1)",
            }),
            "condition": forms.Select(attrs={"class": "form-select", "id": "id_product_condition"}),
            "price": forms.NumberInput(attrs={
                "step": "1",
                "class": "form-control form-control-lg fw-bold",
                "placeholder": "0",
                "id": "id_product_price",
            }),
            "compare_at_price": forms.NumberInput(attrs={
                "step": "1",
                "class": "form-control",
                "placeholder": "Original Price (Optional)",
                "id": "id_product_compare_price",
            }),
            "stock_quantity": forms.NumberInput(attrs={"class": "form-control", "min": "1"}),
            "description": forms.Textarea(attrs={
                "rows": 5,
                "class": "form-control",
                "placeholder": "Describe what is included, cosmetic state, battery health, receipt/warranty, or reason for selling...",
                "id": "id_product_description",
            }),
            "campus_location": forms.TextInput(attrs={
                "placeholder": "e.g. UDSM Main Campus (Hall 5 / Library / CoICT Cafeteria)",
                "class": "form-control",
                "id": "id_product_location",
            }),
            "shipping_weight": forms.NumberInput(attrs={"step": "0.01", "class": "form-control", "placeholder": "Weight in kg"}),
            "shipping_dimensions": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. 15 x 8 x 2 cm"}),
            "contact_method": forms.Select(attrs={"class": "form-select"}),
            "contact_email": forms.EmailInput(attrs={"class": "form-control"}),
            "contact_phone": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. 0712345678"}),
        }

    def __init__(self, *args, **kwargs):
        self.category = kwargs.pop("category", None)
        super().__init__(*args, **kwargs)

        # Detect category in edit mode if not explicitly passed
        if not self.category and self.instance and self.instance.pk and self.instance.category_obj:
            self.category = self.instance.category_obj

        self.fields["sku"].required = False
        self.fields["price"].label = "Selling Price (TZS)"
        self.fields["compare_at_price"].label = "Compare-at Price (TZS)"
        self.fields["price"].help_text = "Actual amount the buyer will pay in Tanzanian Shillings."
        self.fields["compare_at_price"].help_text = "Higher reference price to show a discount badge to buyers."

        if self.category:
            self.fields["category_obj"].initial = self.category
            self.fields["category_obj"].widget = forms.HiddenInput()
            self.fields["category_obj"].required = False

            # Existing attribute values lookup for edit mode
            existing_attr_values = {}
            if self.instance and self.instance.pk:
                existing_attr_values = {
                    pav.attribute_id: pav.value
                    for pav in self.instance.attribute_values.all()
                }

            for attr in self.category.attributes.all():
                field_name = f"attr_{attr.id}"
                meta = get_attribute_metadata(attr.name)

                if attr.options:
                    options = [opt.strip() for opt in attr.options.split(",") if opt.strip()]
                    choices = [("", f"Select {attr.name}")] + [(opt, opt) for opt in options]
                    field = forms.ChoiceField(
                        label=attr.name,
                        choices=choices,
                        required=False,
                        widget=forms.Select(attrs={"class": "form-select"}),
                    )
                    field.options_list = options
                elif attr.name.lower() in ["os", "operating system", "platform"]:
                    os_choices = [
                        ("", f"Select {attr.name}"),
                        ("Android", "Android"),
                        ("iOS", "iOS"),
                        ("Windows", "Windows"),
                        ("macOS", "macOS"),
                        ("Linux", "Linux"),
                        ("Other", "Other"),
                    ]
                    field = forms.ChoiceField(
                        label=attr.name,
                        choices=os_choices,
                        required=False,
                        widget=forms.Select(attrs={"class": "form-select"}),
                    )
                    field.options_list = ["Android", "iOS", "Windows", "macOS", "Linux", "Other"]
                else:
                    attr_lower = attr.name.lower()
                    widget_attrs = {
                        "class": "form-control",
                        "placeholder": meta["placeholder"],
                    }

                    if "date" in attr_lower or "year" in attr_lower:
                        widget = forms.DateInput(attrs={**widget_attrs, "type": "date"})
                    elif "color" in attr_lower or "colour" in attr_lower:
                        widget = forms.TextInput(attrs={
                            **widget_attrs,
                            "type": "color",
                            "style": "height: 42px; padding: 4px;",
                        })
                    else:
                        widget = forms.TextInput(attrs=widget_attrs)

                    field = forms.CharField(label=attr.name, required=False, widget=widget)
                    field.options_list = []

                # Attach rich metadata for template rendering
                field.unit = meta["unit"]
                field.icon = meta["icon"]
                field.placeholder = meta["placeholder"]
                if meta["help"]:
                    field.help_text = meta["help"]

                # Populate initial value in edit mode
                if attr.id in existing_attr_values:
                    field.initial = existing_attr_values[attr.id]

                self.fields[field_name] = field

    def clean_sku(self):
        sku = self.cleaned_data.get("sku")
        if not (sku or "").strip():
            import uuid
            return f"UC-{uuid.uuid4().hex[:8].upper()}"
        return sku.strip()

    def get_attribute_fields(self):
        """Return all category dynamic attribute bound fields with metadata."""
        return [self[f] for f in self.fields if f.startswith("attr_")]

    def save(self, commit=True):
        if self.category:
            self.instance.category_obj = self.category
        item = super().save(commit=False)
        if commit:
            item.save()
            for name, value in self.cleaned_data.items():
                if name.startswith("attr_") and value:
                    attr_id = int(name.replace("attr_", ""))
                    ProductAttributeValue.objects.update_or_create(
                        product=item,
                        attribute_id=attr_id,
                        defaults={"value": str(value)},
                    )
        return item


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ["content"]
        widgets = {
            "content": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Ask a question or leave a comment...",
                }
            )
        }
