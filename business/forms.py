from django import forms
from .models import Item, ProductAttributeValue

class ItemForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = [
            'title',
            'sku',
            'category_obj',
            'price',
            'compare_at_price',
            'stock_quantity',
            'description',
            'campus_location',
            'shipping_weight',
            'shipping_dimensions',
            'contact_method',
            'contact_email',
            'contact_phone',
            'image',
            'image2',
            'image3',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'price': forms.NumberInput(attrs={'step': '0.01'}),
            'campus_location': forms.TextInput(attrs={'placeholder': 'e.g. Hall 5, Library, Main Gate'}),
        }

    def __init__(self, *args, **kwargs):
        self.category = kwargs.pop('category', None)
        super().__init__(*args, **kwargs)

        if self.category:
            # Hide the category field as it's already selected
            self.fields['category_obj'].initial = self.category
            self.fields['category_obj'].widget = forms.HiddenInput()
            self.fields['category_obj'].required = False
            
            # Dynamically add fields for attributes linked to this category
            for attr in self.category.attributes.all():
                field_name = f"attr_{attr.id}"
                if attr.options:
                    # Use CharField with datalist to allow custom input
                    options = [opt.strip() for opt in attr.options.split(',')]
                    self.fields[field_name] = forms.CharField(
                        label=attr.name, 
                        required=False, 
                        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': f'Select or type {attr.name}', 'autocomplete': 'off'})
                    )
                    # Attach options to the field so we can render them in the template
                    self.fields[field_name].datalist_options = options
                else:
                    self.fields[field_name] = forms.CharField(label=attr.name, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
                
                # Add a special class to identify dynamic attributes for JS wizard
                self.fields[field_name].widget.attrs['data-wizard-step'] = '2' # Default to step 2
                # If it's Brand/Make, move to step 1
                if attr.name in ['Brand', 'Make', 'Provider', 'Publisher']:
                    self.fields[field_name].widget.attrs['data-wizard-step'] = '1'

    def save(self, commit=True):
        if self.category:
            self.instance.category_obj = self.category
        item = super().save(commit=False)
        if commit:
            item.save()
            # Save dynamic attributes
            for name, value in self.cleaned_data.items():
                if name.startswith('attr_') and value:
                    attr_id = int(name.replace('attr_', ''))
                    ProductAttributeValue.objects.create(product=item, attribute_id=attr_id, value=value)
        return item