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
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "sku": forms.TextInput(attrs={"class": "form-control"}),
            "condition": forms.Select(attrs={"class": "form-select"}),
            "price": forms.NumberInput(attrs={"step": "0.01", "class": "form-control"}),
            "compare_at_price": forms.NumberInput(
                attrs={"step": "0.01", "class": "form-control"}
            ),
            "stock_quantity": forms.NumberInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"rows": 4, "class": "form-control"}),
            "campus_location": forms.TextInput(
                attrs={
                    "placeholder": "e.g. Hall 5, Library, Main Gate",
                    "class": "form-control",
                }
            ),
            "shipping_weight": forms.NumberInput(
                attrs={"step": "0.01", "class": "form-control"}
            ),
            "shipping_dimensions": forms.TextInput(attrs={"class": "form-control"}),
            "contact_method": forms.Select(attrs={"class": "form-select"}),
            "contact_email": forms.EmailInput(attrs={"class": "form-control"}),
            "contact_phone": forms.TextInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        self.category = kwargs.pop("category", None)
        super().__init__(*args, **kwargs)

        self.fields["price"].label = "Price"
        self.fields["compare_at_price"].label = "Compare at price"
        self.fields["price"].help_text = "Enter the selling price."
        self.fields["compare_at_price"].help_text = "Optional higher reference price (shown struck through)."

        if self.category:
            self.fields["category_obj"].initial = self.category
            self.fields["category_obj"].widget = forms.HiddenInput()
            self.fields["category_obj"].required = False

            for attr in self.category.attributes.all():
                field_name = f"attr_{attr.id}"

                if attr.options:
                    options = [opt.strip() for opt in attr.options.split(",")]
                    choices = [("", f"Select {attr.name}")] + [
                        (opt, opt) for opt in options
                    ]
                    self.fields[field_name] = forms.ChoiceField(
                        label=attr.name,
                        choices=choices,
                        required=False,
                        widget=forms.Select(attrs={"class": "form-select"}),
                    )
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
                    self.fields[field_name] = forms.ChoiceField(
                        label=attr.name,
                        choices=os_choices,
                        required=False,
                        widget=forms.Select(attrs={"class": "form-select"}),
                    )
                else:
                    attr_lower = attr.name.lower()
                    widget = forms.TextInput(attrs={"class": "form-control"})

                    if "date" in attr_lower or "year" in attr_lower:
                        widget = forms.DateInput(
                            attrs={"class": "form-control", "type": "date"}
                        )
                    elif "color" in attr_lower or "colour" in attr_lower:
                        widget = forms.TextInput(
                            attrs={
                                "class": "form-control",
                                "type": "color",
                                "style": "height: 38px; padding: 4px;",
                            }
                        )

                    self.fields[field_name] = forms.CharField(
                        label=attr.name, required=False, widget=widget
                    )

                self.fields[field_name].widget.attrs["data-wizard-step"] = "2"
                if attr.name in ["Brand", "Make", "Provider", "Publisher", "Company"]:
                    self.fields[field_name].widget.attrs["data-wizard-step"] = "1"

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
                        defaults={"value": value},
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
